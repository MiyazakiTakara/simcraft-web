import os
import shutil
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
from database import create_job, update_job_status, get_job, save_result_data, get_config

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

log = setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

RESULTS_DIR = os.environ.get("RESULTS_DIR", "/app/results")
os.makedirs(RESULTS_DIR, exist_ok=True)

SIMC_PATH        = os.environ.get("SIMC_PATH", "/app/SimulationCraft/simc")
SIMC_APIKEY_PATH = os.environ.get("SIMC_APIKEY_PATH", "/root/.simc_apikey")

JOBS_TTL = int(os.environ.get("JOBS_TTL", str(60 * 60 * 4)))

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


def _get_max_concurrent() -> int:
    """Czyta max_concurrent_sims z app_config (dynamicznie). Fallback: env -> 3."""
    val = get_config("max_concurrent_sims")
    if val is not None:
        try:
            return max(1, int(val))
        except (ValueError, TypeError):
            pass
    return int(os.environ.get("MAX_CONCURRENT_SIMS", "3"))


def _get_job_timeout() -> int:
    """Czyta job_timeout z app_config (dynamicznie). Fallback: env -> 360."""
    val = get_config("job_timeout")
    if val is not None:
        try:
            return max(30, int(val))
        except (ValueError, TypeError):
            pass
    return int(os.environ.get("JOB_TIMEOUT", "360"))


def _get_guest_sims_enabled() -> bool:
    """Czyta guest_sims_enabled z app_config. Fallback: True."""
    val = get_config("guest_sims_enabled", "true")
    return str(val).lower() == "true"


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

_running_lock = threading.Lock()


def _count_running() -> int:
    return sum(1 for j in jobs.values() if j.get("counted"))


def _release_slot(job_id: str):
    with _running_lock:
        job = jobs.get(job_id)
        if job and job.get("counted"):
            job["counted"] = False


def _set_job_status(job_id: str, status: str, error: str = None):
    """Aktualizuje status joba w jobs dict (RAM) oraz w DB."""
    if job_id in jobs:
        jobs[job_id]["status"] = status
        if error is not None:
            jobs[job_id]["error"] = error
    update_job_status(job_id, status, error)


def _read_talents(inp_path: str) -> str | None:
    try:
        with open(inp_path) as f:
            content = f.read()
        m = re.search(r"^talents=([A-Za-z0-9+/=_-]+)", content, re.MULTILINE)
        return m.group(1).strip() if m else None
    except Exception:
        return None


def _read_talents_from_json(out_path: str) -> str | None:
    try:
        import json
        from results import _extract_talents_from_raw
        with open(out_path) as f:
            raw = json.load(f)
        players = raw.get("sim", {}).get("players", [])
        if not players:
            return None
        return _extract_talents_from_raw(raw, players[0])
    except Exception:
        return None


def _cleanup_job_dir(job_dir: str):
    try:
        if os.path.exists(job_dir):
            shutil.rmtree(job_dir)
    except Exception as e:
        log.warning("cleanup-failed", job_dir=job_dir, error=str(e))


class SimRequest(BaseModel):
    session: Optional[str] = None
    name: Optional[str] = None
    realm_slug: Optional[str] = None
    region: Optional[str] = "eu"
    addon_text: Optional[str] = None
    fight_style: Optional[str] = "Patchwerk"
    iterations: Optional[int] = 1000
    target_error: Optional[float] = 0.5
    one_button_mode: Optional[bool] = False


def _build_simc_input(req: SimRequest, out_path: str) -> str:
    lines = []
    lines.append(f"fight_style={req.fight_style}")
    lines.append(f"iterations={min(req.iterations or 1000, 10000)}")
    lines.append(f"target_error={max(0.1, min(req.target_error or 0.5, 5.0))}")
    if req.one_button_mode:
        lines.append("optimal_raid_action_list=1")
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
    from results import parse_results

    # Czyta timeout dynamicznie z app_config w momencie startu wątku
    job_timeout = _get_job_timeout()

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
            capture_output=True, text=True, timeout=job_timeout
        )

        if result.returncode != 0 or not os.path.exists(out_path):
            error_msg = result.stderr[-2000:] if result.stderr else "simc failed"
            _set_job_status(job_id, "error", error_msg)
            log.error("sim-failed", job_id=job_id, returncode=result.returncode, error=error_msg)
            _cleanup_job_dir(job_dir)
        else:
            talents = _read_talents(inp_path)
            parsed  = parse_results(out_path)
            if "error" not in parsed:
                if not talents:
                    talents = parsed.get("talents_str") or None
                if not talents and os.path.exists(out_path):
                    talents = _read_talents_from_json(out_path)

                if talents:
                    log.info("talents-found", job_id=job_id, length=len(talents))
                else:
                    log.warning("talents-not-found", job_id=job_id)

                ok = save_result_data(job_id, parsed, talents)
                if not ok:
                    log.warning("save-result-failed", job_id=job_id)
            else:
                log.warning("parse-error", job_id=job_id, error=parsed.get("error"))

            _set_job_status(job_id, "done")
            log.info("sim-completed", job_id=job_id)
            _cleanup_job_dir(job_dir)

    except subprocess.TimeoutExpired:
        error_msg = f"Symulacja przekroczyla limit czasu ({job_timeout}s)"
        _set_job_status(job_id, "error", error_msg)
        log.error("sim-timeout", job_id=job_id, timeout=job_timeout)
        _cleanup_job_dir(job_dir)
    except Exception as e:
        _set_job_status(job_id, "error", str(e))
        log.exception("sim-exception", job_id=job_id)
        _cleanup_job_dir(job_dir)
    finally:
        _release_slot(job_id)


def _watchdog():
    while True:
        time.sleep(60)
        now = time.time()
        to_delete = []

        for job_id, job in list(jobs.items()):
            started     = job.get("started_at", now)
            job_timeout = _get_job_timeout()

            if job.get("counted") and now - started > job_timeout + 60:
                _set_job_status(job_id, "error", "Job timeout (watchdog)")
                _release_slot(job_id)
                log.warning("job-timeout", job_id=job_id)

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

    # source=addon zawsze gdy użyto addon_text, niezależnie czy user jest zalogowany
    source = "addon" if req.addon_text else "web"

    # Sprawdź czy symulacje dla gości są włączone
    if not req.session and not _get_guest_sims_enabled():
        raise HTTPException(403, "Symulacje dla niezalogowanych użytkowników są wyłączone")

    # Pobierz aktualny WoW build z cache
    from admin import get_wow_build_cached
    wow_build = get_wow_build_cached()

    # Czyta limit dynamicznie z app_config przy każdym requescie
    max_concurrent = _get_max_concurrent()

    with _running_lock:
        if _count_running() >= max_concurrent:
            raise HTTPException(429, f"Serwer zajety ({max_concurrent} symulacji rownoczesnie). Sprobuj za chwile.")

        job_id   = str(uuid.uuid4())
        job_dir  = os.path.join(RESULTS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        out_path = os.path.join(job_dir, "output.json")

        jobs[job_id] = {
            "status":          "running",
            "json_path":       out_path,
            "error":           None,
            "started_at":      time.time(),
            "counted":         True,
            "source":          source,
            "wow_build":       wow_build,
            "one_button_mode": bool(req.one_button_mode),
        }

    log.info("sim-started", job_id=job_id, source=source, wow_build=wow_build,
             addon_text=bool(req.addon_text), character=req.name, realm=req.realm_slug,
             one_button_mode=bool(req.one_button_mode))
    create_job(job_id, out_path)

    simc_input = _build_simc_input(req, out_path)
    t = threading.Thread(target=_run_sim, args=(job_id, simc_input, out_path), daemon=True)
    t.start()

    return {"job_id": job_id, "source": source, "one_button_mode": bool(req.one_button_mode)}


@router.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    rebuild_banner = None
    try:
        from admin import _rebuild_state
        if _rebuild_state.get("status") == "running":
            rebuild_banner = {
                "type":         "simc_rebuild",
                "message":      "Trwa automatyczna aktualizacja SimulationCraft do najnowszej wersji. Wyniki mogą być chwilowo niedostępne.",
                "triggered_by": _rebuild_state.get("triggered_by"),
                "started_at":   _rebuild_state.get("started_at"),
            }
    except Exception:
        pass

    # In-memory najpierw — zawiera wow_build z chwili startu joba
    job = jobs.get(job_id)
    if job:
        resp = {
            "status":    job["status"],
            "error":     job.get("error"),
            "wow_build": job.get("wow_build"),
        }
        if rebuild_banner:
            resp["rebuild_banner"] = rebuild_banner
        return resp

    # Fallback: DB (job wyczyszczony z RAM po JOBS_TTL)
    db_job = get_job(job_id)
    if db_job:
        resp = {"status": db_job["status"], "error": db_job["error"], "wow_build": None}
        if rebuild_banner:
            resp["rebuild_banner"] = rebuild_banner
        return resp

    raise HTTPException(404, "Job not found")
