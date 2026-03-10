import os
import uuid
import subprocess
import threading
import json
import re
import time
import collections

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

RESULTS_DIR = os.environ.get("RESULTS_DIR", "/app/results")
os.makedirs(RESULTS_DIR, exist_ok=True)

jobs: dict = {}

# Max rownoczesnych symulacji
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


def _build_simc_input(req: SimRequest) -> str:
    lines = []
    lines.append(f"fight_style={req.fight_style}")
    lines.append(f"iterations={min(req.iterations, 10000)}")
    lines.append(f"target_error={max(0.1, min(req.target_error, 5.0))}")
    lines.append("json2=output.json")
    lines.append("output=/dev/null")

    if req.addon_text:
        lines.append(req.addon_text.strip())
    else:
        region = (req.region or "eu").lower()
        realm  = req.realm_slug or ""
        name   = req.name or ""
        lines.append(f"{name}=armory,{region},{realm},{name.lower()}")

    return "\n".join(lines)


def _run_sim(job_id: str, simc_input: str):
    global _running_sims
    job_dir  = os.path.join(RESULTS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    inp_path = os.path.join(job_dir, "input.simc")
    out_path = os.path.join(job_dir, "output.json")

    with open(inp_path, "w") as f:
        f.write(simc_input.replace("json2=output.json", f"json2={out_path}"))

    try:
        result = subprocess.run(
            ["/usr/local/bin/simc", inp_path],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0 or not os.path.exists(out_path):
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"]  = result.stderr[-2000:] if result.stderr else "simc failed"
        else:
            jobs[job_id]["status"]    = "done"
            jobs[job_id]["json_path"] = out_path
    except subprocess.TimeoutExpired:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"]  = "Simulation timed out (>5 min)"
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"]  = str(e)
    finally:
        with _running_lock:
            _running_sims -= 1


@router.post("/api/sim")
@limiter.limit("5/minute")
async def start_sim(request: Request, req: SimRequest):
    global _running_sims

    # Walidacja
    if not req.addon_text and not (req.name and req.realm_slug):
        raise HTTPException(400, "Podaj addon_text lub name+realm_slug")

    with _running_lock:
        if _running_sims >= MAX_CONCURRENT:
            raise HTTPException(429, f"Serwer zajety ({MAX_CONCURRENT} symulacji rownoczesnie). Sprobuj za chwile.")
        _running_sims += 1

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "json_path": None, "error": None}

    simc_input = _build_simc_input(req)
    t = threading.Thread(target=_run_sim, args=(job_id, simc_input), daemon=True)
    t.start()

    return {"job_id": job_id}


@router.get("/api/sim/{job_id}/status")
async def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {"status": job["status"], "error": job.get("error")}
