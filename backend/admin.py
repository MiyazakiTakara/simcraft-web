import os
import re
import time
import uuid
import secrets
import httpx
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func

from database import SessionLocal, AdminSessionModel, NewsModel, LogEntryModel, get_logs, HistoryEntryModel, JobModel, PageVisitModel

router = APIRouter(prefix="/admin")

ADMIN_COOKIE = "admin_session"
SESSION_TTL  = 60 * 60 * 8  # 8 godzin

_SIMC_GH_BRANCH = "midnight"


def _cfg():
    url   = os.environ["KEYCLOAK_URL"].rstrip("/")
    realm = os.environ["KEYCLOAK_REALM"]
    base  = f"{url}/realms/{realm}/protocol/openid-connect"
    return {
        "client_id":     os.environ["KEYCLOAK_CLIENT_ID"],
        "client_secret": os.environ["KEYCLOAK_CLIENT_SECRET"],
        "redirect_uri":  os.environ["ADMIN_REDIRECT_URI"],
        "oidc_base":     base,
    }


# ---------- helpers ----------

def _get_admin_session(session_id: str) -> dict | None:
    with SessionLocal() as db:
        row = db.query(AdminSessionModel).filter(AdminSessionModel.session_id == session_id).first()
    if not row:
        return None
    if time.time() > row.expires_at:
        with SessionLocal() as db:
            db.query(AdminSessionModel).filter(AdminSessionModel.session_id == session_id).delete()
            db.commit()
        return None
    return {"username": row.username}


def _require_admin(request: Request) -> dict:
    session_id = request.cookies.get(ADMIN_COOKIE)
    if session_id:
        session = _get_admin_session(session_id)
        if session:
            return session
    raise HTTPException(status_code=302, headers={"Location": "/admin/login"})


# ---------- SimC version check (cache 1h) ----------

_simc_version_cache: dict = {"ts": 0, "data": None}
_SIMC_VERSION_CACHE_TTL = 3600


def _get_local_simc_version(simc_path: str) -> str | None:
    import subprocess
    try:
        r = subprocess.run([simc_path, "--version"], capture_output=True, text=True, timeout=5)
        out = r.stdout + r.stderr
        m = re.search(r"SimulationCraft\s+([\d]+-\d+)", out)
        return m.group(1) if m else out.strip()[:40] or None
    except Exception:
        return None


async def _get_latest_simc_version() -> dict:
    now = time.time()
    if _simc_version_cache["data"] and now - _simc_version_cache["ts"] < _SIMC_VERSION_CACHE_TTL:
        return _simc_version_cache["data"]

    headers  = {"Accept": "application/vnd.github+json"}
    base_url = "https://api.github.com/repos/simulationcraft/simc"

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            import asyncio
            config_resp, commit_resp = await asyncio.gather(
                client.get(f"{base_url}/contents/engine/config.hpp?ref={_SIMC_GH_BRANCH}", headers=headers),
                client.get(f"{base_url}/commits/{_SIMC_GH_BRANCH}", headers=headers),
            )
            config_resp.raise_for_status()
            commit_resp.raise_for_status()

        import base64
        content = base64.b64decode(config_resp.json()["content"]).decode("utf-8")
        major   = re.search(r'#define SC_MAJOR_VERSION\s+"([\d]+)"', content)
        minor   = re.search(r'#define SC_MINOR_VERSION\s+"([\d]+)"', content)
        version = f"{major.group(1)}-{minor.group(1)}" if major and minor else None

        commit_data = commit_resp.json()
        result = {
            "version":          version,
            "last_commit_sha":  commit_data["sha"][:7],
            "last_commit_date": commit_data["commit"]["committer"]["date"],
            "last_commit_url":  commit_data["html_url"],
        }
    except Exception as e:
        result = {"version": None, "error": str(e)}

    _simc_version_cache["ts"]   = now
    _simc_version_cache["data"] = result
    return result


# ---------- auth routes ----------

@router.get("/login")
async def admin_login():
    cfg   = _cfg()
    state = secrets.token_urlsafe(16)
    url = (
        f"{cfg['oidc_base']}/auth"
        f"?client_id={cfg['client_id']}"
        f"&redirect_uri={cfg['redirect_uri']}"
        f"&response_type=code"
        f"&scope=openid profile email"
        f"&state={state}"
    )
    return RedirectResponse(url)


@router.get("/callback")
async def admin_callback(code: str, state: str = None):
    cfg = _cfg()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{cfg['oidc_base']}/token",
            data={
                "grant_type":    "authorization_code",
                "code":          code,
                "redirect_uri":  cfg["redirect_uri"],
                "client_id":     cfg["client_id"],
                "client_secret": cfg["client_secret"],
            },
            timeout=10,
        )
        resp.raise_for_status()
        token_data = resp.json()

        userinfo_resp = await client.get(
            f"{cfg['oidc_base']}/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
            timeout=10,
        )
        userinfo_resp.raise_for_status()
        userinfo = userinfo_resp.json()

    username   = userinfo.get("preferred_username") or userinfo.get("sub", "unknown")
    session_id = str(uuid.uuid4())
    expires_at = time.time() + SESSION_TTL

    with SessionLocal() as db:
        db.query(AdminSessionModel).filter(AdminSessionModel.expires_at < time.time()).delete()
        db.add(AdminSessionModel(session_id=session_id, username=username, expires_at=expires_at))
        db.commit()

    response = RedirectResponse("/admin", status_code=302)
    response.set_cookie(
        key=ADMIN_COOKIE, value=session_id,
        httponly=True, secure=True, samesite="lax", max_age=SESSION_TTL,
    )
    return response


@router.get("/logout")
async def admin_logout(request: Request):
    session_id = request.cookies.get(ADMIN_COOKIE)
    if session_id:
        with SessionLocal() as db:
            db.query(AdminSessionModel).filter(AdminSessionModel.session_id == session_id).delete()
            db.commit()
    response = RedirectResponse("/admin/login", status_code=302)
    response.delete_cookie(ADMIN_COOKIE)
    return response


# ---------- panel route ----------

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_panel(request: Request):
    _require_admin(request)
    with open("/app/frontend/admin.html") as f:
        return HTMLResponse(f.read())


# ---------- dashboard API ----------

@router.get("/api/dashboard")
async def get_dashboard(request: Request):
    _require_admin(request)
    import psutil

    now      = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d  = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    with SessionLocal() as db:
        total_sims  = db.query(func.count(HistoryEntryModel.id)).scalar() or 0
        total_users = db.query(HistoryEntryModel.user_id).distinct().count() or 0

        today_sims = db.query(func.count(HistoryEntryModel.id)).filter(
            HistoryEntryModel.created_at >= last_24h
        ).scalar() or 0

        week_sims = db.query(func.count(HistoryEntryModel.id)).filter(
            HistoryEntryModel.created_at >= last_7d
        ).scalar() or 0

        month_sims = db.query(func.count(HistoryEntryModel.id)).filter(
            HistoryEntryModel.created_at >= last_30d
        ).scalar() or 0

        monthly_trend_rows = db.query(
            func.date_trunc('day', HistoryEntryModel.created_at).label('day'),
            func.count(HistoryEntryModel.id).label('count'),
        ).filter(
            HistoryEntryModel.created_at >= last_30d
        ).group_by('day').order_by('day').all()

        class_rows = db.query(
            HistoryEntryModel.character_class,
            func.count(HistoryEntryModel.id).label('count'),
        ).group_by(HistoryEntryModel.character_class).order_by(
            func.count(HistoryEntryModel.id).desc()
        ).all()

        fs_rows = db.query(
            HistoryEntryModel.fight_style,
            func.count(HistoryEntryModel.id).label('count'),
        ).group_by(HistoryEntryModel.fight_style).order_by(
            func.count(HistoryEntryModel.id).desc()
        ).all()

        top10_rows = db.query(HistoryEntryModel).order_by(
            HistoryEntryModel.dps.desc()
        ).limit(10).all()

        total_jobs  = db.query(func.count(JobModel.job_id)).scalar() or 0
        active_jobs = db.query(func.count(JobModel.job_id)).filter(
            JobModel.status == 'running'
        ).scalar() or 0

    boot_time  = datetime.fromtimestamp(psutil.boot_time())
    uptime     = datetime.now() - boot_time
    uptime_str = f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds%3600)//60}m"

    return {
        "stats": {
            "total_simulations":  total_sims,
            "total_users":        total_users,
            "today_simulations":  today_sims,
            "week_simulations":   week_sims,
            "month_simulations":  month_sims,
            "total_jobs":         total_jobs,
            "active_jobs":        active_jobs,
            "cpu_percent":        psutil.cpu_percent(),
            "memory_percent":     psutil.virtual_memory().percent,
            "uptime":             uptime_str,
        },
        "monthly_trend": [
            {"day": str(row.day)[:10], "count": row.count}
            for row in monthly_trend_rows
        ],
        "class_distribution": [
            {"character_class": row.character_class or "Unknown", "count": row.count}
            for row in class_rows
        ],
        "fight_style_distribution": [
            {"fight_style": row.fight_style or "Unknown", "count": row.count}
            for row in fs_rows
        ],
        "top_dps": [{
            "job_id":          r.job_id,
            "character_name":  r.character_name,
            "character_class": r.character_class,
            "character_spec":  r.character_spec,
            "dps":             r.dps,
            "fight_style":     r.fight_style,
            "created_at":      r.created_at.isoformat() if r.created_at else None,
        } for r in top10_rows],
    }


# ---------- news API ----------

class NewsCreate(BaseModel):
    title: str
    body: str
    published: bool = True


class NewsUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    published: bool | None = None


@router.get("/api/news")
async def list_news(request: Request):
    _require_admin(request)
    with SessionLocal() as db:
        rows = db.query(NewsModel).order_by(NewsModel.created_at.desc()).all()
    return [{
        "id": r.id, "title": r.title, "body": r.body,
        "published": r.published,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]


@router.post("/api/news", status_code=201)
async def create_news(request: Request, data: NewsCreate):
    _require_admin(request)
    with SessionLocal() as db:
        entry = NewsModel(title=data.title, body=data.body, published=data.published)
        db.add(entry)
        db.commit()
        db.refresh(entry)
    return {"id": entry.id, "title": entry.title}


@router.patch("/api/news/{news_id}")
async def update_news(news_id: int, request: Request, data: NewsUpdate):
    _require_admin(request)
    with SessionLocal() as db:
        row = db.query(NewsModel).filter(NewsModel.id == news_id).first()
        if not row:
            raise HTTPException(404, "News not found")
        if data.title     is not None: row.title     = data.title
        if data.body      is not None: row.body      = data.body
        if data.published is not None: row.published = data.published
        db.commit()
    return {"ok": True}


@router.delete("/api/news/{news_id}")
async def delete_news(news_id: int, request: Request):
    _require_admin(request)
    with SessionLocal() as db:
        deleted = db.query(NewsModel).filter(NewsModel.id == news_id).delete()
        db.commit()
    if not deleted:
        raise HTTPException(404, "News not found")
    return {"ok": True}


# ---------- publiczne API ----------

@router.get("/api/news/public")
async def public_news():
    with SessionLocal() as db:
        rows = (db.query(NewsModel)
                .filter(NewsModel.published == True)
                .order_by(NewsModel.created_at.desc())
                .limit(20).all())
    return [{
        "id": r.id, "title": r.title, "body": r.body,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]


@router.get("/api/logs")
async def list_logs(request: Request, limit: int = 100, level: str = None):
    _require_admin(request)
    logs = get_logs(limit=limit, level=level)
    return [{
        "id": l.id, "level": l.level, "message": l.message, "context": l.context,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    } for l in logs]


@router.get("/api/users")
async def list_users(request: Request, limit: int = 50):
    _require_admin(request)
    with SessionLocal() as db:
        rows = (
            db.query(
                HistoryEntryModel.user_id,
                HistoryEntryModel.character_name,
                HistoryEntryModel.character_class,
                HistoryEntryModel.character_spec,
            )
            .filter(HistoryEntryModel.user_id.isnot(None))
            .distinct().all()
        )

        users_map = {}
        for user_id, char_name, char_class, char_spec in rows:
            if user_id not in users_map:
                users_map[user_id] = {
                    "user_id":         user_id,
                    "character_name":  char_name,
                    "character_class": char_class,
                    "character_spec":  char_spec,
                    "sim_count":       0,
                    "avg_dps":         0,
                    "last_sim":        None,
                }

        stats = (
            db.query(
                HistoryEntryModel.user_id,
                func.count(HistoryEntryModel.id).label("sim_count"),
                func.avg(HistoryEntryModel.dps).label("avg_dps"),
                func.max(HistoryEntryModel.created_at).label("last_sim"),
            )
            .filter(HistoryEntryModel.user_id.isnot(None))
            .group_by(HistoryEntryModel.user_id).all()
        )

        for user_id, sim_count, avg_dps, last_sim in stats:
            if user_id in users_map:
                users_map[user_id]["sim_count"] = sim_count
                users_map[user_id]["avg_dps"]   = round(avg_dps, 0) if avg_dps else 0
                users_map[user_id]["last_sim"]   = last_sim.isoformat() if last_sim else None

    users = sorted(users_map.values(), key=lambda x: x["last_sim"] or "", reverse=True)[:limit]
    return users


@router.get("/api/users/{user_id}/simulations")
async def get_user_simulations(request: Request, user_id: str, limit: int = 20):
    _require_admin(request)
    with SessionLocal() as db:
        rows = (
            db.query(HistoryEntryModel)
            .filter(HistoryEntryModel.user_id == user_id)
            .order_by(HistoryEntryModel.created_at.desc())
            .limit(limit).all()
        )
    return [{
        "job_id":          r.job_id,
        "character_name":  r.character_name,
        "character_class": r.character_class,
        "character_spec":  r.character_spec,
        "dps":             r.dps,
        "fight_style":     r.fight_style,
        "created_at":      r.created_at.isoformat() if r.created_at else None,
    } for r in rows]


@router.delete("/api/simulations")
async def delete_simulations(request: Request, older_than_days: int = None, user_id: str = None):
    _require_admin(request)
    with SessionLocal() as db:
        query = db.query(HistoryEntryModel)
        if user_id:
            query = query.filter(HistoryEntryModel.user_id == user_id)
        elif older_than_days:
            cutoff = datetime.utcnow() - timedelta(days=older_than_days)
            query  = query.filter(HistoryEntryModel.created_at < cutoff)
        deleted = query.delete()
        db.commit()
    return {"deleted": deleted}


# ---------- Limits Management ----------

class LimitsUpdate(BaseModel):
    max_concurrent_sims: int | None = None
    rate_limit_per_minute: int | None = None
    job_timeout: int | None = None


@router.get("/api/limits")
async def get_limits(request: Request):
    _require_admin(request)
    return {
        "max_concurrent_sims":   int(os.environ.get("MAX_CONCURRENT_SIMS", "3")),
        "rate_limit_per_minute": 5,
        "job_timeout":           int(os.environ.get("JOB_TIMEOUT", "360")),
    }


@router.patch("/api/limits")
async def update_limits(request: Request, data: LimitsUpdate):
    _require_admin(request)
    return {"ok": True, "message": "Limits updated (not persisted in this demo)"}


# ---------- Health Check ----------

@router.get("/api/health")
async def health_check(request: Request):
    _require_admin(request)

    health_status = {
        "database":     "ok",
        "blizzard_api": "unknown",
        "keycloak":     "unknown",
        "simc_binary":  "unknown",
        "results_dir":  "unknown",
        "simc_version": {},
    }

    try:
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"

    try:
        from auth import get_blizzard_token
        token = await get_blizzard_token()
        health_status["blizzard_api"] = "ok" if token else "error: no token"
    except Exception as e:
        health_status["blizzard_api"] = f"error: {str(e)}"

    try:
        cfg  = _cfg()
        async with httpx.AsyncClient() as client:
            url  = f"{cfg['oidc_base'].split('/protocol')[0]}/.well-known/openid-configuration"
            resp = await client.get(url, timeout=5)
            if resp.status_code == 200:
                health_status["keycloak"] = "ok"
            elif resp.status_code in (401, 403):
                health_status["keycloak"] = "ok (requires auth)"
            else:
                health_status["keycloak"] = f"error: {resp.status_code}"
    except Exception as e:
        health_status["keycloak"] = f"error: {str(e)}"

    simc_path = os.environ.get("SIMC_PATH", "/app/SimulationCraft/simc")
    if os.path.exists(simc_path) and os.access(simc_path, os.X_OK):
        health_status["simc_binary"] = "ok"
    else:
        health_status["simc_binary"] = f"error: not found or not executable at {simc_path}"

    results_dir = os.environ.get("RESULTS_DIR", "/app/results")
    health_status["results_dir"] = "ok" if (os.path.exists(results_dir) and os.access(results_dir, os.W_OK)) \
        else f"error: not writable at {results_dir}"

    local_version  = _get_local_simc_version(simc_path) if health_status["simc_binary"] == "ok" else None
    latest         = await _get_latest_simc_version()
    latest_version = latest.get("version")

    if local_version and latest_version:
        up_to_date = local_version.strip() == latest_version.strip()
    else:
        up_to_date = None

    health_status["simc_version"] = {
        "local":            local_version,
        "latest":           latest_version,
        "up_to_date":       up_to_date,
        "last_commit_sha":  latest.get("last_commit_sha"),
        "last_commit_date": latest.get("last_commit_date"),
        "last_commit_url":  latest.get("last_commit_url"),
        "cache_age_s":      int(time.time() - _simc_version_cache["ts"]),
        **(  {"error": latest["error"]} if "error" in latest else {}  ),
    }

    return health_status


# ---------- Task Management ----------

@router.get("/api/tasks")
async def list_tasks(request: Request):
    _require_admin(request)
    from simulation import jobs
    active_tasks = [
        {"job_id": job_id, "status": "running", "started_at": job_info.get("started_at")}
        for job_id, job_info in jobs.items()
        if job_info.get("status") == "running"
    ]
    return {"active_tasks": active_tasks, "total_active": len(active_tasks)}


@router.delete("/api/tasks/{job_id}")
async def cancel_task(request: Request, job_id: str):
    _require_admin(request)
    from simulation import jobs, _release_slot
    from database import update_job_status

    if job_id not in jobs:
        raise HTTPException(404, "Task not found")

    jobs[job_id]["status"] = "cancelled"
    jobs[job_id]["error"]  = "Cancelled by admin"
    _release_slot(job_id)
    update_job_status(job_id, "error", error="Cancelled by admin")
    return {"ok": True, "message": f"Task {job_id} cancelled"}


# ---------- Appearance Settings ----------

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APPEARANCE_CONFIG_FILE = BASE_DIR / "config" / "appearance.json"


class AppearanceUpdate(BaseModel):
    header_title: str | None = None
    hero_title: str | None = None
    emoji: str | None = None
    hero_custom_text: str | None = None


def load_appearance_config():
    default_config = {
        "header_title":     "SimCraft Web",
        "hero_title":       "World of Warcraft",
        "emoji":            "⚔️",
        "hero_custom_text": "",
    }
    try:
        APPEARANCE_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if APPEARANCE_CONFIG_FILE.exists():
            with open(APPEARANCE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
        else:
            with open(APPEARANCE_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            return default_config
    except Exception as e:
        print(f"Error loading appearance config: {e}")
        return default_config


def save_appearance_config(config):
    try:
        APPEARANCE_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(APPEARANCE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving appearance config: {e}")
        return False


@router.get("/api/appearance")
async def get_appearance(request: Request):
    _require_admin(request)
    return load_appearance_config()


@router.post("/api/appearance")
async def update_appearance(request: Request, data: AppearanceUpdate):
    _require_admin(request)
    config = load_appearance_config()
    if data.header_title     is not None: config["header_title"]     = data.header_title
    if data.hero_title       is not None: config["hero_title"]       = data.hero_title
    if data.emoji            is not None: config["emoji"]            = data.emoji
    if data.hero_custom_text is not None: config["hero_custom_text"] = data.hero_custom_text
    if save_appearance_config(config):
        return {"ok": True, "message": "Appearance settings saved successfully"}
    raise HTTPException(500, "Failed to save appearance settings")


# ---------- Traffic ----------

@router.get("/api/traffic/stats")
async def get_traffic_stats(request: Request):
    _require_admin(request)
    now      = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d  = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    with SessionLocal() as db:
        total_visits   = db.query(func.count(PageVisitModel.id)).scalar() or 0
        today_visits   = db.query(func.count(PageVisitModel.id)).filter(PageVisitModel.created_at >= last_24h).scalar() or 0
        week_visits    = db.query(func.count(PageVisitModel.id)).filter(PageVisitModel.created_at >= last_7d).scalar() or 0
        month_visits   = db.query(func.count(PageVisitModel.id)).filter(PageVisitModel.created_at >= last_30d).scalar() or 0

        # unikalne IP (na podstawie ip_hash) w ostatnich 30 dniach
        unique_30d = db.query(func.count(func.distinct(PageVisitModel.ip_hash))).filter(
            PageVisitModel.created_at >= last_30d,
            PageVisitModel.ip_hash.isnot(None)
        ).scalar() or 0

        unique_today = db.query(func.count(func.distinct(PageVisitModel.ip_hash))).filter(
            PageVisitModel.created_at >= last_24h,
            PageVisitModel.ip_hash.isnot(None)
        ).scalar() or 0

        # trend dzienny — ostatnie 30 dni
        daily_rows = db.query(
            func.date_trunc('day', PageVisitModel.created_at).label('day'),
            func.count(PageVisitModel.id).label('total'),
            func.count(func.distinct(PageVisitModel.ip_hash)).label('unique'),
        ).filter(
            PageVisitModel.created_at >= last_30d
        ).group_by('day').order_by('day').all()

        # top 10 stron
        top_pages_rows = db.query(
            PageVisitModel.path,
            func.count(PageVisitModel.id).label('count'),
        ).filter(
            PageVisitModel.created_at >= last_30d
        ).group_by(PageVisitModel.path).order_by(
            func.count(PageVisitModel.id).desc()
        ).limit(10).all()

        # rozkład godzinowy (ostatnie 7 dni)
        hourly_rows = db.query(
            func.extract('hour', PageVisitModel.created_at).label('hour'),
            func.count(PageVisitModel.id).label('count'),
        ).filter(
            PageVisitModel.created_at >= last_7d
        ).group_by('hour').order_by('hour').all()

    return {
        "summary": {
            "total_visits":   total_visits,
            "today_visits":   today_visits,
            "week_visits":    week_visits,
            "month_visits":   month_visits,
            "unique_today":   unique_today,
            "unique_30d":     unique_30d,
        },
        "daily_trend": [
            {"day": str(row.day)[:10], "total": row.total, "unique": row.unique}
            for row in daily_rows
        ],
        "top_pages": [
            {"path": row.path, "count": row.count}
            for row in top_pages_rows
        ],
        "hourly": [
            {"hour": int(row.hour), "count": row.count}
            for row in hourly_rows
        ],
    }
