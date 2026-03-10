import os
import asyncio
import uuid
import json

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

RESULTS_DIR = "/app/results"
os.makedirs(RESULTS_DIR, exist_ok=True)

jobs: dict = {}

SIMC_PATH = "/app/SimulationCraft/simc"


class SimRequest(BaseModel):
    session:    Optional[str] = None
    name:       Optional[str] = None
    realm_slug: Optional[str] = None
    region:     Optional[str] = "eu"
    addon_text: Optional[str] = None
    fight_style: str = "Patchwerk"
    iterations:  int = 1000
    target_error: float = 0.5


def _build_profile(req: SimRequest) -> str:
    lines = []
    if req.addon_text:
        lines.append(req.addon_text.strip())
    elif req.name and req.realm_slug and req.region:
        lines.append(f"armory={req.region},{req.realm_slug},{req.name.lower()}")
    else:
        raise ValueError("Brak danych postaci")

    lines += [
        f"fight_style={req.fight_style}",
        f"iterations={req.iterations}",
        f"target_error={req.target_error}",
        "json2=1",
    ]
    return "\n".join(lines)


async def _run_sim(job_id: str, profile: str):
    simc_file = os.path.join(RESULTS_DIR, f"{job_id}.simc")
    json_file  = os.path.join(RESULTS_DIR, f"{job_id}.json")

    with open(simc_file, "w") as f:
        f.write(profile)

    cmd = f'LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 {SIMC_PATH} "{simc_file}" json2="{json_file}"'
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    log = stdout.decode(errors="replace")
    print(f"[{job_id}] simc exit={proc.returncode}", flush=True)

    try:
        os.remove(simc_file)
    except Exception:
        pass

    if proc.returncode != 0 or not os.path.exists(json_file):
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"]  = log[-2000:]
        return

    jobs[job_id]["status"]    = "done"
    jobs[job_id]["json_path"] = json_file


@router.post("/api/simulate")
async def start_sim(req: SimRequest, bg: BackgroundTasks):
    try:
        profile = _build_profile(req)
    except ValueError as e:
        raise HTTPException(400, str(e))

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "json_path": None, "error": None}
    bg.add_task(_run_sim, job_id, profile)
    return {"job_id": job_id}


@router.get("/api/job/{job_id}")
async def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job nie istnieje")
    return {"job_id": job_id, "status": job["status"], "error": job.get("error")}
