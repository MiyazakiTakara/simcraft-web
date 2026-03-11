import os
import uuid
import subprocess
import threading
import time
import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

from logging_config import setup_logging
from database import create_job, update_job_status, get_job

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

log = setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

RESULTS_DIR = os.environ.get("RESULTS_DIR", "/app/results")
os.makedirs(RESULTS_DIR, exist_ok=True)

SIMC_PATH    = os.environ.get("SIMC_PATH", "/app/SimulationCraft/simc")
JOB_TIMEOUT  = int(os.environ.get("JOB_TIMEOUT", "360"))
SIMC_APIKEY_PATH = os.environ.get("SIMC_APIKEY_PATH", "/root/.simc_apikey")

# Stale wpisy starsze niż JOBS_TTL sekund są usuwane przez watchdog
JOBS_TTL = int(os.environ.get("JOBS_TTL", str(60 * 60 * 4)))  # domyślnie 4h

MAX_ADDON_TEXT_LENGTH = 50000

ADDON_TEXT_BLOCKED_PATTERNS = [
    re.compile(r"^#\s*(quit|exit|delete|rm|del)", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*!\s*.*", re.MULTILINE),
    re.compile(r"exec\s+['\"\"]]", re.IGNORECASE),
    re.compile(r"source\s+.*\.sh", re.IGNORECASE),
    re.compile(r"\|.*sh", re.IGNORECASE),
    re.compile(r"^\s*include\s*=", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*file\s*=", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*output\s*=", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*json2?\s*=", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*html\s*=", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*xml\s*=", re.MULTILINE | re.IGNORECASE),
]


def _validate_addon_text(text: str) -> str:
    if not text:
        return text
    if len(text) > MAX_ADDON_TEXT_LENGTH:
        raise HTTPException(400, f"Addon text too long (max {MAX_ADDON_TEXT_LENGTH} chars)")
    for pattern in ADDON_TEXT_BLOCKED_PATTERNS:
        if pattern.search(text):
            raise HTTPException(400, "Invalid characters or commands in addon text")
    return text


jobs: dict = {}

MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT_SIMS", "3"))

_running_lock = threading.Lock()


def _count_running() -> int:
    return sum(1 for j in jobs.values() if j.get("counted"))


def _release_slot(job_id: str):
    """Zwalnia slot tylko raz — ustawia counted=False."""
    with _running_lock:
        job = jobs.get(job_id)
        if job and job.get("counted"):
            job["counted"] = False


class SimRequest(BaseModel):
    session: Optional[str] = None
    name: Optional[str] = None
    realm_slug: Optional[str] = None
    region: Optional[str] = "eu"
    addon_text: Optional[str] = None
    fight_style: Optional[str] = "Patchwerk"
    iterations: Optional[int] = 1000
    target_error: Optional[float] = 0.5


def _build_simc_input(req: SimRequest, out_path: str) -> str:
    lines = []
    lines.append(f"fight_style={req.fight_style}")
    lines.append(f"iterations={min(req.iterations or 1000, 10000)}")
    lines.append(f"target_error={max(0.1, min(req.target_error or 0.5, 5.0))}")
    lines.append(f"json2={out_path}")
    lines.append("output=/dev/null")

    if req.addon_text:
        validated = _validate_addon_text(req.addon_text)
        lines.append(validated.strip())
    else:
        region = (req.region or "eu").lower()
        realm  = (req.realm_slug or "").lower()
        name   = (req.name or "").lower()
        lines.append(f"armory={region},{realm},{name}")

    return "\n".join(lines)


def _run_sim(job_id: str, simc_input: str, out_path: str):
    """out_path przekazywany jako argument — unikamy czytania jobs[] poza _running_lock."""
    job_dir  = os.path.join(RESULTS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    inp_path = os.path.join(job_dir, "input.simc")

    with open(inp_path, "w") as f:
        f.write(simc_input)

    try:
        blizzard_id     = os.environ.get("BLIZZARD_CLIENT_ID")
        blizzard_secret = os.environ.get("BLIZZARD_CLIENT_SECRET")
        if blizzard_id and blizzard_secret:
            with open(SIMC_APIKEY_PATH, "w") as f:
                f.write(f"{blizzard_id}:{blizzard_secret}")
            os.chmod(SIMC_APIKEY_PATH, 0o600)

        result = subprocess.run(
            [SIMC_PATH, inp_path],
            capture_output=True, text=True, timeout=JOB_TIMEOUT
        )
        if result.returncode != 0 or not os.path.exists(out_path):
            error_msg = result.stderr[-2000:] if result.stderr else "simc failed"
            update_job_status(job_id, "error", error_msg)
            log.error("sim-failed", job_id=job_id, returncode=result.returncode, error=error_msg)
        else:
            update_job_status(job_id, "done")
            log.info("sim-completed", job_id=job_id)
    except subprocess.TimeoutExpired:
        error_msg = f"Symulacja przekroczyla limit czasu ({JOB_TIMEOUT}s)"
        update_job_status(job_id, "error", error_msg)
        log.error("sim-timeout", job_id=job_id, timeout=JOB_TIMEOUT)
    except Exception as e:
        update_job_status(job_id, "error", str(e))
        log.exception("sim-exception", job_id=job_id)
    finally:
        _release_slot(job_id)


def _watchdog():
    """Co 60s: timeout aktywnych jobów + czyszczenie starych wpisów z jobs{}."""
    while True:
        time.sleep(60)
        now = time.time()
        to_delete = []

        for job_id, job in list(jobs.items()):
            started = job.get("started_at", now)

            # Timeout aktywnego joba
            if job.get("counted") and now - started > JOB_TIMEOUT + 60:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"]  = "Job timeout (watchdog)"
                update_job_status(job_id, "error", "Job timeout (watchdog)")
                _release_slot(job_id)
                log.warning("job-timeout", job_id=job_id)

            # Usunięcie zakończonych/błędnych wpisów starszych niż JOBS_TTL
            if not job.get("counted") and now - started > JOBS_TTL:
                to_delete.append(job_id)

        for job_id in to_delete:
            jobs.pop(job_id, None)

        if to_delete:
            log.info("jobs-dict-cleanup", removed=len(to_delete))


threading.Thread(target=_watchdog, daemon=True).start()


@router.post("/api/simulate")
@limiter.limit("5/minute")
async def start_sim(request: Request, req: SimRequest):
    if not req.addon_text and not (req.name and req.realm_slug):
        raise HTTPException(400, "Podaj addon_text lub name+realm_slug")

    with _running_lock:
        if _count_running() >= MAX_CONCURRENT:
            raise HTTPException(429, f"Serwer zajety ({MAX_CONCURRENT} symulacji rownoczesnie). Sprobuj za chwile.")

        job_id   = str(uuid.uuid4())
        job_dir  = os.path.join(RESULTS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        out_path = os.path.join(job_dir, "output.json")

        jobs[job_id] = {
            "status":     "running",
            "json_path":  out_path,
            "error":      None,
            "started_at": time.time(),
            "counted":    True,
        }

    log.info("sim-started", job_id=job_id, addon_text=bool(req.addon_text), character=req.name, realm=req.realm_slug)
    create_job(job_id, out_path)

    simc_input = _build_simc_input(req, out_path)
    t = threading.Thread(target=_run_sim, args=(job_id, simc_input, out_path), daemon=True)
    t.start()

    return {"job_id": job_id}


@router.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    db_job = get_job(job_id)
    if db_job:
        return {"status": db_job["status"], "error": db_job["error"]}
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {"status": job["status"], "error": job.get("error")}
