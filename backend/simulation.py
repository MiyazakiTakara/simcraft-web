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

SIMC_PATH = os.environ.get("SIMC_PATH", "/app/SimulationCraft/simc")
JOB_TIMEOUT = int(os.environ.get("JOB_TIMEOUT", "360"))

SIMC_APIKEY_PATH = os.environ.get("SIMC_APIKEY_PATH", "/root/.simc_apikey")

MAX_ADDON_TEXT_LENGTH = 50000

ADDON_TEXT_BLOCKED_PATTERNS = [
    re.compile(r"^#\s*(quit|exit|delete|rm|del)", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*!\s*.*", re.MULTILINE),
    re.compile(r"exec\s+['\"]", re.IGNORECASE),
    re.compile(r"source\s+.*\.sh", re.IGNORECASE),
    re.compile(r"\|.*sh", re.IGNORECASE),
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
_running_sims = 0
_running_lock = threading.Lock()


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


def _run_sim(job_id: str, simc_input: str):
    global _running_sims
    job_dir  = os.path.join(RESULTS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    inp_path = os.path.join(job_dir, "input.simc")

    with open(inp_path, "w") as f:
        f.write(simc_input)

    try:
        blizzard_id = os.environ.get("BLIZZARD_CLIENT_ID")
        blizzard_secret = os.environ.get("BLIZZARD_CLIENT_SECRET")
        if blizzard_id and blizzard_secret:
            api_key_path = os.path.expanduser("~/.simc_apikey")
            with open(api_key_path, "w") as f:
                f.write(f"{blizzard_id}:{blizzard_secret}")
            os.chmod(api_key_path, 0o600)

        result = subprocess.run(
            [SIMC_PATH, inp_path],
            capture_output=True, text=True, timeout=JOB_TIMEOUT
        )
        out_path = jobs[job_id].get("json_path")
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
        with _running_lock:
            _running_sims -= 1


def _watchdog():
    while True:
        time.sleep(60)
        now = time.time()
        for job_id, job in list(jobs.items()):
            if job.get("status") == "running":
                started = job.get("started_at", now)
                if now - started > JOB_TIMEOUT + 60:
                    jobs[job_id]["status"] = "error"
                    jobs[job_id]["error"]  = "Job timeout (watchdog)"
                    update_job_status(job_id, "error", "Job timeout (watchdog)")
                    with _running_lock:
                        global _running_sims
                        if _running_sims > 0:
                            _running_sims -= 1
                    log.warning("job-timeout", job_id=job_id)


threading.Thread(target=_watchdog, daemon=True).start()


@router.post("/api/simulate")
@limiter.limit("5/minute")
async def start_sim(request: Request, req: SimRequest):
    global _running_sims

    if not req.addon_text and not (req.name and req.realm_slug):
        raise HTTPException(400, "Podaj addon_text lub name+realm_slug")

    with _running_lock:
        if _running_sims >= MAX_CONCURRENT:
            raise HTTPException(429, f"Serwer zajety ({MAX_CONCURRENT} symulacji rownoczesnie). Sprobuj za chwile.")
        _running_sims += 1

    job_id   = str(uuid.uuid4())
    log.info("sim-started", job_id=job_id, addon_text=bool(req.addon_text), character=req.name, realm=req.realm_slug)
    job_dir  = os.path.join(RESULTS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    out_path = os.path.join(job_dir, "output.json")

    jobs[job_id] = {
        "status":     "running",
        "json_path":  out_path,
        "error":      None,
        "started_at": time.time(),
    }

    create_job(job_id, out_path)

    simc_input = _build_simc_input(req, out_path)
    t = threading.Thread(target=_run_sim, args=(job_id, simc_input), daemon=True)
    t.start()

    return {"job_id": job_id}


@router.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    db_job = get_job(job_id)
    if db_job:
        return {"status": db_job.status, "error": db_job.error}
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {"status": job["status"], "error": job.get("error")}
