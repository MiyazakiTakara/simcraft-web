import os
import html as html_lib

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded


def get_client_ip(request):
    forwarded = request.headers.get("CF-Connecting-IP")
    if forwarded:
        return forwarded
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

from starlette.middleware.base import BaseHTTPMiddleware

from logging_config import setup_logging
from database import init_db, SessionLocal, JobModel
from auth import router as auth_router
from characters import router as characters_router
from simulation import router as sim_router, RESULTS_DIR, jobs, create_job
from results import router as results_router
from history import router as history_router
from admin import router as admin_router, load_appearance_config
from reactions import router as reactions_router

log = setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

REQUIRED_ENV_VARS = [
    "BLIZZARD_CLIENT_ID",
    "BLIZZARD_CLIENT_SECRET",
]

def _validate_env():
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        log.error("missing-env-vars", vars=missing)
        raise RuntimeError(f"Missing required env vars: {missing}")
    log.info("env-validated")

_validate_env()

init_db()
log.info("database-initialized")

limiter = Limiter(key_func=get_client_ip)

app = FastAPI(title="SimCraft Web")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path.split("?")[0]
        if path.endswith((".js", ".css", ".html")) or path in ("/",) or path.startswith("/result/") or path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.add_middleware(NoCacheStaticMiddleware)

app.include_router(auth_router)
app.include_router(characters_router)
app.include_router(sim_router)
app.include_router(results_router)
app.include_router(history_router)
app.include_router(admin_router)
app.include_router(reactions_router)


# ---------- Publiczny endpoint appearance (bez autoryzacji) ----------

@app.get("/api/appearance")
async def get_appearance_public():
    config = load_appearance_config()
    return JSONResponse(
        content=config,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "CDN-Cache-Control": "no-store",
            "Cloudflare-CDN-Cache-Control": "no-store",
        }
    )


BASE_URL = os.environ.get("BASE_URL", "https://sim.miyazakitakara.ovh")


@app.get("/result/{job_id}", response_class=HTMLResponse)
async def result_page(job_id: str):
    from database import SessionLocal, HistoryEntryModel

    with SessionLocal() as db:
        entry = db.query(HistoryEntryModel).filter(HistoryEntryModel.job_id == job_id).first()

    char_name   = (entry and entry.character_name)  or "Addon Export"
    char_class  = (entry and entry.character_class) or ""
    char_spec   = (entry and entry.character_spec)  or ""
    dps         = (entry and entry.dps)             or 0
    fight_style = (entry and entry.fight_style)     or "Patchwerk"

    if dps >= 1_000_000:
        dps_str = f"{dps / 1_000_000:.2f}M"
    elif dps >= 1_000:
        dps_str = f"{dps / 1_000:.1f}k"
    else:
        dps_str = str(int(dps))

    spec_class = f"{char_spec} {char_class}".strip()
    raw_title  = f"{char_name} ({spec_class}) — {dps_str} DPS" if spec_class else f"{char_name} — {dps_str} DPS"
    raw_desc   = f"Symulacja SimCraft · {fight_style} · {dps_str} DPS. Sprawdź pełny breakdown spelli i wykres DPS."

    og_title = html_lib.escape(raw_title)
    og_desc  = html_lib.escape(raw_desc)
    og_image = html_lib.escape(f"{BASE_URL}/api/result/{job_id}/dps-chart.png")
    og_url   = html_lib.escape(f"{BASE_URL}/result/{job_id}")

    with open("/app/frontend/result.html") as f:
        html_content = f.read()

    og_tags = f"""
    <meta property="og:title"       content="{og_title}"/>
    <meta property="og:description" content="{og_desc}"/>
    <meta property="og:image"       content="{og_image}"/>
    <meta property="og:url"         content="{og_url}"/>
    <meta property="og:type"        content="website"/>
    <meta name="twitter:card"       content="summary_large_image"/>
    <meta name="twitter:title"      content="{og_title}"/>
    <meta name="twitter:description" content="{og_desc}"/>
    <meta name="twitter:image"      content="{og_image}"/>
    <title>{og_title} — SimCraft Web</title>
"""
    html_content = html_content.replace("<!-- OG_META_PLACEHOLDER -->", og_tags)
    return HTMLResponse(content=html_content)


def _mark_stale_running_jobs():
    with SessionLocal() as db:
        stale = db.query(JobModel).filter(JobModel.status == "running").all()
        for job in stale:
            job.status = "error"
            job.error  = "Serwer został zrestartowany w trakcie symulacji"
        if stale:
            db.commit()
            log.warning("stale-jobs-marked", count=len(stale))


def _restore_jobs():
    for entry in os.scandir(RESULTS_DIR):
        if not entry.is_dir():
            continue
        out = os.path.join(entry.path, "output.json")
        if os.path.exists(out):
            jobs[entry.name] = {"status": "done", "json_path": out, "error": None, "counted": False}
            create_job(entry.name, out)

    _SKIP = {"history.json", "sessions.json"}
    for fname in os.listdir(RESULTS_DIR):
        if not fname.endswith(".json") or fname in _SKIP:
            continue
        job_id = fname[:-5]
        if job_id in jobs:
            continue
        fpath = os.path.join(RESULTS_DIR, fname)
        jobs[job_id] = {"status": "done", "json_path": fpath, "error": None, "counted": False}
        create_job(job_id, fpath)

    log.info("jobs-restored", count=len(jobs))


_mark_stale_running_jobs()
_restore_jobs()

app.mount("/", StaticFiles(directory="/app/frontend", html=True), name="static")
