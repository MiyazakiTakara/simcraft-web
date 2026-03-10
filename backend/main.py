import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from auth import router as auth_router
from characters import router as characters_router
from simulation import router as sim_router, RESULTS_DIR, jobs
from results import router as results_router
from history import router as history_router

_id  = os.environ["BLIZZARD_CLIENT_ID"]
_sec = os.environ["BLIZZARD_CLIENT_SECRET"]
with open("/root/.simc_apikey", "w") as _f:
    _f.write(f"{_id}:{_sec}")
print(f".simc_apikey written ({os.path.getsize('/root/.simc_apikey')} bytes)", flush=True)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="SimCraft Web")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(characters_router)
app.include_router(sim_router)
app.include_router(results_router)
app.include_router(history_router)


def _restore_jobs():
    for fname in os.listdir(RESULTS_DIR):
        if not fname.endswith(".json") or fname == "history.json":
            continue
        # Nowa struktura: wyniki sa w podfolderach job_id/output.json
        job_id = fname[:-5]
        fpath  = os.path.join(RESULTS_DIR, fname)
        jobs[job_id] = {"status": "done", "json_path": fpath, "error": None}

    # Nowa struktura: job_id/output.json
    for entry in os.scandir(RESULTS_DIR):
        if entry.is_dir():
            out = os.path.join(entry.path, "output.json")
            if os.path.exists(out):
                jobs[entry.name] = {"status": "done", "json_path": out, "error": None}

    print(f"Odtworzono {len(jobs)} jobow z dysku", flush=True)


_restore_jobs()

app.mount("/", StaticFiles(directory="/app/frontend", html=True), name="static")
