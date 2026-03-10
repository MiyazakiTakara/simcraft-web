import os
import asyncio
import uuid
import json
import time
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, validator
from typing import Optional

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Configuration constants
RESULTS_DIR = "/app/results"
SIMC_PATH = "/app/SimulationCraft/simc"
MAX_CONCURRENT_JOBS = 5
JOB_TIMEOUT_SECONDS = 3600  # 1 hour
JOB_RETENTION_HOURS = 168  # Keep jobs for 7 days (so shared links don't die)
SIMC_TIMEOUT_SECONDS = 1800  # 30 minutes for SimC process

os.makedirs(RESULTS_DIR, exist_ok=True)

# Global state
jobs: dict = {}
running_count = 0


class SimRequest(BaseModel):
    """Request model for simulation submission"""
    session: Optional[str] = None
    name: Optional[str] = None
    realm_slug: Optional[str] = None
    region: Optional[str] = "eu"
    addon_text: Optional[str] = None
    fight_style: str = "Patchwerk"
    iterations: int = 1000
    target_error: float = 0.5

    @validator("iterations")
    def validate_iterations(cls, v):
        """Ensure iterations are within reasonable bounds"""
        if v < 10 or v > 100000:
            raise ValueError("Iterations must be between 10 and 100000")
        return v

    @validator("target_error")
    def validate_target_error(cls, v):
        """Ensure target error is between 0 and 5%"""
        if v <= 0 or v > 5:
            raise ValueError("Target error must be between 0 and 5")
        return v


def _is_valid_job_id(job_id: str) -> bool:
    """Validate job ID format (must be valid UUID)"""
    try:
        uuid.UUID(job_id)
        return True
    except ValueError:
        return False


def _cleanup_old_jobs():
    """Remove jobs older than JOB_RETENTION_HOURS"""
    current_time = time.time()
    cutoff_time = current_time - (JOB_RETENTION_HOURS * 3600)
    
    removed = []
    for job_id, job_data in list(jobs.items()):
        created_at = job_data.get("created_at", current_time)
        if created_at < cutoff_time and job_data.get("status") in ["done", "error"]:
            # Clean up associated files
            try:
                json_path = job_data.get("json_path")
                if json_path and os.path.exists(json_path):
                    os.remove(json_path)
                    logger.info(f"[{job_id}] Removed result file: {json_path}")
            except Exception as e:
                logger.warning(f"[{job_id}] Failed to remove file: {e}")
            
            del jobs[job_id]
            removed.append(job_id)
    
    if removed:
        logger.info(f"Cleaned up {len(removed)} old jobs")


def _build_profile(req: SimRequest) -> str:
    """Build SimulationCraft profile string from request"""
    lines = []
    if req.addon_text:
        lines.append(req.addon_text.strip())
    elif req.name and req.realm_slug and req.region:
        lines.append(f"armory={req.region},{req.realm_slug},{req.name.lower()}")
    else:
        raise ValueError("Missing character data: provide either addon_text or name+realm_slug+region")

    lines += [
        f"fight_style={req.fight_style}",
        f"iterations={req.iterations}",
        f"target_error={req.target_error}",
        "json2=1",
    ]
    return "\n".join(lines)


async def _run_sim(job_id: str, profile: str):
    """Execute SimulationCraft simulation in background"""
    global running_count
    
    simc_file = os.path.join(RESULTS_DIR, f"{job_id}.simc")
    json_file = os.path.join(RESULTS_DIR, f"{job_id}.json")
    
    try:
        # Write profile to file
        with open(simc_file, "w") as f:
            f.write(profile)
        logger.info(f"[{job_id}] Starting simulation (iterations={profile.count('iterations')})")

        # Execute SimulationCraft
        cmd = f'LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 {SIMC_PATH} "{simc_file}" json2="{json_file}"'
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        
        try:
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=SIMC_TIMEOUT_SECONDS
            )
            log = stdout.decode(errors="replace")
        except asyncio.TimeoutError:
            logger.error(f"[{job_id}] SimulationCraft timed out after {SIMC_TIMEOUT_SECONDS}s")
            proc.kill()
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = f"Simulation timed out after {SIMC_TIMEOUT_SECONDS} seconds"
            return
        
        logger.info(f"[{job_id}] SimC exit code: {proc.returncode}")

        # Clean up profile file
        try:
            os.remove(simc_file)
        except Exception as e:
            logger.warning(f"[{job_id}] Failed to remove profile file: {e}")

        # Check if simulation succeeded
        if proc.returncode != 0 or not os.path.exists(json_file):
            error_msg = log[-2000:] if log else "Unknown error"
            logger.error(f"[{job_id}] Simulation failed: {error_msg[:500]}")
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = error_msg
            return

        jobs[job_id]["status"] = "done"
        jobs[job_id]["json_path"] = json_file
        jobs[job_id]["completed_at"] = time.time()
        logger.info(f"[{job_id}] Simulation completed successfully")

    except Exception as e:
        logger.exception(f"[{job_id}] Unexpected error during simulation")
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
    finally:
        running_count -= 1


@router.post("/api/simulate")
async def start_sim(req: SimRequest, bg: BackgroundTasks):
    """Start a new simulation job"""
    global running_count
    
    # Clean up old jobs periodically
    _cleanup_old_jobs()
    
    # Check concurrent job limit
    if running_count >= MAX_CONCURRENT_JOBS:
        logger.warning(f"Job rejected: {running_count}/{MAX_CONCURRENT_JOBS} concurrent jobs already running")
        raise HTTPException(
            503,
            f"Server busy: {running_count} simulations running (max: {MAX_CONCURRENT_JOBS})"
        )

    try:
        profile = _build_profile(req)
    except ValueError as e:
        logger.warning(f"Invalid simulation request: {e}")
        raise HTTPException(400, str(e))

    job_id = str(uuid.uuid4())
    running_count += 1
    
    jobs[job_id] = {
        "status": "running",
        "json_path": None,
        "error": None,
        "created_at": time.time(),
        "completed_at": None,
    }
    
    bg.add_task(_run_sim, job_id, profile)
    logger.info(f"Started job {job_id} ({running_count}/{MAX_CONCURRENT_JOBS} running)")
    
    return {"job_id": job_id, "status": "running"}


@router.get("/api/job/{job_id}")
async def job_status(job_id: str):
    """Get current status of a simulation job"""
    if not _is_valid_job_id(job_id):
        logger.warning(f"Invalid job ID format: {job_id}")
        raise HTTPException(400, "Invalid job ID format")
    
    job = jobs.get(job_id)
    if not job:
        logger.info(f"Job not found: {job_id}")
        raise HTTPException(404, "Job not found")
    
    response = {
        "job_id": job_id,
        "status": job["status"],
        "created_at": job.get("created_at"),
        "completed_at": job.get("completed_at"),
    }
    
    if job.get("error"):
        response["error"] = job["error"]
    
    return response


# History tracking
history_file = os.path.join(RESULTS_DIR, "history.json")
history: list = []


class HistoryEntry(BaseModel):
    """History entry model"""
    job_id: str
    character_name: Optional[str] = None
    dps: float
    fight_style: str
    created_at: float = None


def _load_history():
    """Load history from disk"""
    global history
    if os.path.exists(history_file):
        try:
            with open(history_file, "r") as f:
                history = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            history = []
    else:
        history = []


def _save_history():
    """Save history to disk"""
    try:
        with open(history_file, "w") as f:
            json.dump(history, f)
    except Exception as e:
        logger.error(f"Failed to save history: {e}")


# Load history on startup
_load_history()


@router.post("/api/history")
async def save_history(entry: HistoryEntry):
    """Save simulation result to public history"""
    if entry.created_at is None:
        entry.created_at = time.time()
    
    history_entry = {
        "job_id": entry.job_id,
        "character_name": entry.character_name,
        "dps": entry.dps,
        "fight_style": entry.fight_style,
        "created_at": entry.created_at,
    }
    
    # Add to beginning of history (keep it latest first)
    history.insert(0, history_entry)
    
    # Keep only last 1000 entries
    if len(history) > 1000:
        history.pop()
    
    _save_history()
    logger.info(f"Added to history: {entry.character_name} - {entry.dps} DPS")
    
    return {"status": "saved"}


@router.get("/api/history")
async def get_history():
    """Get personal/authenticated history (for now same as public)"""
    return history[:100]  # Return last 100 entries


@router.get("/api/history/public")
async def get_public_history():
    """Get public history (visible to all)"""
    return history[:100]  # Return last 100 entries
