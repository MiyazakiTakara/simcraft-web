import os
import asyncio
import time
import uuid
import json
import threading

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from auth import router as auth_router
from characters import router as characters_router
from simulation import router as sim_router, RESULTS_DIR, jobs
from results import router as results_router

_id  = os.environ["BLIZZARD_CLIENT_ID"]
_sec = os.environ["BLIZZARD_CLIENT_SECRET"]
with open("/root/.simc_apikey", "w") as _f:
    _f.write(f"{_id}:{_sec}")
print(f".simc_apikey written ({os.path.getsize('/root/.simc_apikey')} bytes)", flush=True)

app = FastAPI(title="SimCraft Web")

app.include_router(auth_router)
app.include_router(characters_router)
app.include_router(sim_router)
app.include_router(results_router)


def _restore_jobs():
    for fname in os.listdir(RESULTS_DIR):
        if not fname.endswith(".json") or fname == "history.json":
            continue
        job_id = fname[:-5]
        fpath = os.path.join(RESULTS_DIR, fname)
        jobs[job_id] = {"status": "done", "json_path": fpath, "error": None}
    print(f"Odtworzono {len(jobs)} jobow z dysku", flush=True)


_restore_jobs()

app.mount("/", StaticFiles(directory="/app/frontend", html=True), name="static")
