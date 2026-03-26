import os
import re
import time
import uuid
import shutil
import base64
import json
import secrets
import httpx
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, or_

from database import (
    SessionLocal, AdminSessionModel, NewsModel, LogEntryModel, get_logs, delete_logs,
    HistoryEntryModel, JobModel, PageVisitModel, add_log, SimcRebuildLogModel,
    get_config, set_config, UserModel, AdminAuditLogModel, log_audit,
    AdminAlertModel, trigger_alert, resolve_alert, resolve_alert_by_type,
    get_active_alert_count,
)

router = APIRouter(prefix="/admin")

ADMIN_COOKIE       = "admin_session"
SESSION_TTL        = 60 * 60 * 8  # 8 godzin
REQUIRED_ROLE      = "simcraft-admin"

_SIMC_GH_BRANCH = "midnight"

# ---------- progi alertów (#58) ----------
_ALERT_THRESHOLDS = {
    "queue_overload":   5,
    "low_disk_pct":     90,
    "error_rate_1h":    10,
}


def _cfg():
    url   = os.environ["KEYCLOAK_URL"].rstrip("/")
    realm = os.environ["KEYCLOAK_REALM"]
    base  = f"{url}/realms/{realm}/protocol/openid-connect"
    return {
        "client_id":     os.environ["KEYCLOAK_CLIENT_ID"],
        "client_secret": os.environ["KEYCLOAK_CLIENT_SECRET"],
        "redirect_uri":  os.environ["ADMIN_REDIRECT_URI"],
        "oidc_base":     base,
        "realm_base":    f"{url}/realms/{realm}",
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


def _decode_jwt_payload(token: str) -> dict:
    """Dekoduje payload JWT bez weryfikacji podpisu (weryfikacja odbywa się przez Keycloak)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        padding = 4 - len(parts[1]) % 4
        payload_b64 = parts[1] + ("=" * (padding % 4))
        return json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
    except Exception:
        return {}


def _has_required_role(token: str, client_id: str) -> bool:
    """Sprawdza czy access token zawiera rolę REQUIRED_ROLE w resource_access.<client_id>.roles."""
    payload = _decode_jwt_payload(token)
    roles = (
        payload
        .get("resource_access", {})
        .get(client_id, {})
        .get("roles", [])
    )
    return REQUIRED_ROLE in roles


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

        import base64 as _b64
        content = _b64.b64decode(config_resp.json()["content"]).decode("utf-8")
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


# ---------- WoW Retail build cache (6h) ----------

_wow_build_cache: dict = {"ts": 0, "data": None}
_WOW_BUILD_CACHE_TTL = 6 * 3600


async def get_wow_retail_build() -> dict:
    now = time.time()
    if _wow_build_cache["data"] and now - _wow_build_cache["ts"] < _WOW_BUILD_CACHE_TTL:
        data = dict(_wow_build_cache["data"])
        data["cache_age_s"] = int(now - _wow_build_cache["ts"])
        return data

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get("http://us.patch.battle.net:1119/wow/versions")
            resp.raise_for_status()
            text = resp.text

        build_str   = None
        version_str = None
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) >= 6:
                versions_name = parts[5].strip()
                if re.match(r'^\d+\.\d+\.\d+\.\d+$', versions_name):
                    build_str   = versions_name
                    version_str = ".".join(versions_name.split(".")[:3])
                    break

        if not build_str:
            raise ValueError(f"Cannot parse TACT response. Raw:\n{text[:500]}")

        result = {"build": build_str, "version": version_str}

    except Exception as e:
        result = {"error": str(e)}

    _wow_build_cache["ts"]   = now
    _wow_build_cache["data"] = result
    result = dict(result)
    result["cache_age_s"] = 0
    return result


def get_wow_build_cached() -> str | None:
    data = _wow_build_cache.get("data")
    if data and "build" in data:
        return data["build"]
    return None


# ---------- SimC Rebuild state ----------

_rebuild_state: dict = {
    "status":       "idle",
    "triggered_by": None,
    "started_at":   None,
    "finished_at":  None,
    "simc_before":  None,
    "simc_after":   None,
    "error":        None,
    "log_id":       None,
}


def _get_last_rebuild() -> dict | None:
    try:
        with SessionLocal() as db:
            row = db.query(SimcRebuildLogModel).order_by(
                SimcRebuildLogModel.started_at.desc()
            ).first()
            if not row:
                return None
            return {
                "id":           row.id,
                "triggered_by": row.triggered_by,
                "status":       row.status,
                "wow_build":    row.wow_build,
                "simc_before":  row.simc_before,
                "simc_after":   row.simc_after,
                "started_at":   row.started_at.isoformat() if row.started_at else None,
                "finished_at":  row.finished_at.isoformat() if row.finished_at else None,
            }
    except Exception:
        return None


# ---------- alert evaluation (#58) ----------

def _evaluate_alerts(health_status: dict, active_jobs: int,
                     free_bytes: int | None, total_disk: int | None) -> None:
    threshold_queue = _ALERT_THRESHOLDS["queue_overload"]
    if active_jobs >= threshold_queue:
        trigger_alert(
            "queue_overload",
            f"Aktywne joby: {active_jobs} (\u2265{threshold_queue} \u2014 pr\u00f3g przeci\u0105\u017cenia kolejki)",
        )
    else:
        resolve_alert_by_type("queue_overload")

    if free_bytes is not None and total_disk:
        used_pct = round((total_disk - free_bytes) / total_disk * 100, 1)
        threshold_disk = _ALERT_THRESHOLDS["low_disk_pct"]
        if used_pct >= threshold_disk:
            trigger_alert(
                "low_disk",
                f"Dysk: {used_pct}% zaj\u0119ty (\u2265{threshold_disk}% \u2014 pr\u00f3g niskiego miejsca)",
            )
        else:
            resolve_alert_by_type("low_disk")

    critical_checks = {
        "database":     health_status.get("database", ""),
        "simc_binary":  health_status.get("simc_binary", ""),
    }
    for check_name, status_val in critical_checks.items():
        atype = f"service_down:{check_name}"
        if not str(status_val).startswith("ok"):
            trigger_alert(atype, f"Serwis '{check_name}' zg\u0142asza b\u0142\u0105d: {str(status_val)[:200]}")
        else:
            resolve_alert_by_type(atype)

    try:
        cutoff = datetime.utcnow() - timedelta(hours=1)
        with SessionLocal() as db:
            error_count = db.query(func.count(JobModel.job_id)).filter(
                JobModel.status == "error",
                JobModel.completed_at >= cutoff,
            ).scalar() or 0
        threshold_err = _ALERT_THRESHOLDS["error_rate_1h"]
        if error_count >= threshold_err:
            trigger_alert(
                "error_rate",
                f"B\u0142\u0119dne joby (ostatnia 1h): {error_count} (\u2265{threshold_err} \u2014 wysoka stopa b\u0142\u0119d\u00f3w)",
            )
        else:
            resolve_alert_by_type("error_rate")
    except Exception:
        pass


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

    if not _has_required_role(token_data["access_token"], cfg["client_id"]):
        username = userinfo.get("preferred_username") or userinfo.get("sub", "unknown")
        log_audit(username, "auth.login_denied", {"reason": f"missing role: {REQUIRED_ROLE}"})
        raise HTTPException(status_code=403, detail="Brak uprawnie\u0144 do tego panelu.")

    username   = userinfo.get("preferred_username") or userinfo.get("sub", "unknown")
    session_id = str(uuid.uuid4())
    expires_at = time.time() + SESSION_TTL

    with SessionLocal() as db:
        db.query(AdminSessionModel).filter(AdminSessionModel.expires_at < time.time()).delete()
        db.add(AdminSessionModel(session_id=session_id, username=username, expires_at=expires_at))
        db.commit()

    log_audit(username, "auth.login")

    response = RedirectResponse("/admin", status_code=302)
    response.set_cookie(
        key=ADMIN_COOKIE, value=session_id,
        httponly=True, secure=True, samesite="lax", max_age=SESSION_TTL,
    )
    return response


@router.get("/logout")
async def admin_logout(request: Request):
    session_id = request.cookies.get(ADMIN_COOKIE)
    username   = "unknown"
    if session_id:
        session = _get_admin_session(session_id)
        if session:
            username = session.get("username", "unknown")
        with SessionLocal() as db:
            db.query(AdminSessionModel).filter(AdminSessionModel.session_id == session_id).delete()
            db.commit()

    log_audit(username, "auth.logout")

    cfg = _cfg()
    app_base = os.environ.get("APP_BASE_URL", "").rstrip("/")
    post_logout_uri = f"{app_base}/admin/login" if app_base else "/admin/login"
    keycloak_logout_url = (
        f"{cfg['oidc_base']}/logout"
        f"?client_id={cfg['client_id']}"
        f"&post_logout_redirect_uri={post_logout_uri}"
    )

    response = RedirectResponse(keycloak_logout_url, status_code=302)
    response.delete_cookie(ADMIN_COOKIE)
    return response


# ---------- panel routes ----------

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_panel(request: Request):
    """Główny panel admina — admin-v2 (nowy)."""
    _require_admin(request)
    with open("/app/frontend/admin-v2.html") as f:
        return HTMLResponse(f.read())


@router.get("/legacy", response_class=HTMLResponse)
async def admin_panel_legacy(request: Request):
    """Stary panel admina — zachowany pod /admin/legacy."""
    _require_admin(request)
    with open("/app/frontend/admin.html") as f:
        return HTMLResponse(f.read())


# ---------- dashboard API ----------

def _calc_duration_stats(db) -> dict:
    from sqlalchemy import text as sa_text
    try:
        result = db.execute(sa_text("""
            SELECT
                ROUND(AVG(EXTRACT(EPOCH FROM (completed_at - started_at)))::numeric, 1) AS avg_s,
                PERCENTILE_CONT(0.5) WITHIN GROUP
                    (ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at)))           AS median_s,
                COUNT(*) FILTER (WHERE EXTRACT(EPOCH FROM (completed_at - started_at)) < 30)   AS lt30,
                COUNT(*) FILTER (WHERE EXTRACT(EPOCH FROM (completed_at - started_at)) BETWEEN 30  AND 59)  AS lt60,
                COUNT(*) FILTER (WHERE EXTRACT(EPOCH FROM (completed_at - started_at)) BETWEEN 60  AND 119) AS lt120,
                COUNT(*) FILTER (WHERE EXTRACT(EPOCH FROM (completed_at - started_at)) >= 120) AS gt120
            FROM jobs
            WHERE status = 'done'
              AND completed_at IS NOT NULL
              AND started_at   IS NOT NULL
        """)).fetchone()
        if result:
            return {
                "avg_s":    float(result.avg_s)    if result.avg_s    is not None else None,
                "median_s": float(result.median_s) if result.median_s is not None else None,
                "histogram": {
                    "lt30":  int(result.lt30  or 0),
                    "lt60":  int(result.lt60  or 0),
                    "lt120": int(result.lt120 or 0),
                    "gt120": int(result.gt120 or 0),
                },
            }
    except Exception:
        pass
    return {"avg_s": None, "median_s": None, "histogram": {"lt30": 0, "lt60": 0, "lt120": 0, "gt120": 0}}


def _calc_error_rate(db, hours: int) -> float | None:
    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        total = db.query(func.count(JobModel.job_id)).filter(
            JobModel.completed_at >= cutoff,
            JobModel.status.in_(["done", "error"]),
        ).scalar() or 0
        if total == 0:
            return 0.0
        errors = db.query(func.count(JobModel.job_id)).filter(
            JobModel.completed_at >= cutoff,
            JobModel.status == "error",
        ).scalar() or 0
        return round(errors / total * 100, 1)
    except Exception:
        return None


def _calc_dps_trend_by_class(db) -> list[dict]:
    from sqlalchemy import text as sa_text
    try:
        rows = db.execute(sa_text("""
            SELECT
                character_class,
                DATE_TRUNC('day', created_at)::date AS day,
                ROUND(AVG(dps)::numeric, 0)         AS avg_dps,
                COUNT(*)                            AS cnt
            FROM history
            WHERE created_at >= NOW() - INTERVAL '30 days'
              AND dps > 0
              AND character_class IS NOT NULL
              AND character_class != ''
            GROUP BY character_class, day
            HAVING COUNT(*) >= 3
            ORDER BY day, character_class
        """)).fetchall()
        return [
            {
                "class":   r.character_class,
                "date":    str(r.day),
                "avg_dps": int(r.avg_dps),
            }
            for r in rows
        ]
    except Exception:
        return []


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
        total_users = db.query(func.count(UserModel.bnet_id)).scalar() or 0

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

        duration_stats  = _calc_duration_stats(db)
        error_rate_24h  = _calc_error_rate(db, hours=24)
        error_rate_7d   = _calc_error_rate(db, hours=24 * 7)
        dps_trend       = _calc_dps_trend_by_class(db)

    boot_time  = datetime.fromtimestamp(__import__('psutil').boot_time())
    uptime     = datetime.now() - boot_time
    uptime_str = f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds%3600)//60}m"

    return {
        "stats": {
            "total_simulations":       total_sims,
            "total_users":             total_users,
            "today_simulations":       today_sims,
            "week_simulations":        week_sims,
            "month_simulations":       month_sims,
            "total_jobs":              total_jobs,
            "active_jobs":             active_jobs,
            "cpu_percent":             psutil.cpu_percent(),
            "memory_percent":          psutil.virtual_memory().percent,
            "uptime":                  uptime_str,
            "avg_sim_duration_s":      duration_stats["avg_s"],
            "median_sim_duration_s":   duration_stats["median_s"],
            "error_rate_24h":          error_rate_24h,
            "error_rate_7d":           error_rate_7d,
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
        "duration_histogram": duration_stats["histogram"],
        "dps_trend_by_class":  dps_trend,
    }


# ---------- traffic stats API ----------

@router.get("/api/traffic/stats")
async def get_traffic_stats(request: Request):
    _require_admin(request)
    from sqlalchemy import text as sa_text

    now      = datetime.utcnow()
    today    = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_7d  = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    with SessionLocal() as db:
        today_visits = db.query(func.count(PageVisitModel.id)).filter(
            PageVisitModel.created_at >= today
        ).scalar() or 0

        unique_today = db.query(func.count(func.distinct(PageVisitModel.ip_hash))).filter(
            PageVisitModel.created_at >= today,
            PageVisitModel.ip_hash.isnot(None),
        ).scalar() or 0

        week_visits = db.query(func.count(PageVisitModel.id)).filter(
            PageVisitModel.created_at >= last_7d
        ).scalar() or 0

        month_visits = db.query(func.count(PageVisitModel.id)).filter(
            PageVisitModel.created_at >= last_30d
        ).scalar() or 0

        unique_30d = db.query(func.count(func.distinct(PageVisitModel.ip_hash))).filter(
            PageVisitModel.created_at >= last_30d,
            PageVisitModel.ip_hash.isnot(None),
        ).scalar() or 0

        total_visits = db.query(func.count(PageVisitModel.id)).scalar() or 0

        daily_rows = db.execute(sa_text("""
            SELECT
                DATE_TRUNC('day', created_at)::date AS day,
                COUNT(*)                            AS total,
                COUNT(DISTINCT ip_hash)             AS unique
            FROM page_visits
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY day
            ORDER BY day
        """)).fetchall()

        hourly_rows = db.execute(sa_text("""
            SELECT
                EXTRACT(HOUR FROM created_at)::int AS hour,
                COUNT(*)                           AS count
            FROM page_visits
            WHERE created_at >= NOW() - INTERVAL '7 days'
            GROUP BY hour
            ORDER BY hour
        """)).fetchall()

        top_pages_rows = db.execute(sa_text("""
            SELECT path, COUNT(*) AS count
            FROM page_visits
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY path
            ORDER BY count DESC
            LIMIT 10
        """)).fetchall()

    return {
        "summary": {
            "today_visits":  today_visits,
            "unique_today":  unique_today,
            "week_visits":   week_visits,
            "month_visits":  month_visits,
            "unique_30d":    unique_30d,
            "total_visits":  total_visits,
        },
        "daily_trend": [
            {"day": str(r.day), "total": r.total, "unique": r.unique}
            for r in daily_rows
        ],
        "hourly": [
            {"hour": r.hour, "count": r.count}
            for r in hourly_rows
        ],
        "top_pages": [
            {"path": r.path, "count": r.count}
            for r in top_pages_rows
        ],
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
    session = _require_admin(request)
    with SessionLocal() as db:
        entry = NewsModel(title=data.title, body=data.body, published=data.published)
        db.add(entry)
        db.commit()
        db.refresh(entry)
    log_audit(session["username"], "news.create", {"id": entry.id, "title": data.title})
    return {"id": entry.id, "title": entry.title}


@router.patch("/api/news/{news_id}")
async def update_news(news_id: int, request: Request, data: NewsUpdate):
    session = _require_admin(request)
    with SessionLocal() as db:
        row = db.query(NewsModel).filter(NewsModel.id == news_id).first()
        if not row:
            raise HTTPException(404, "News not found")
        if data.title     is not None: row.title     = data.title
        if data.body      is not None: row.body      = data.body
        if data.published is not None: row.published = data.published
        db.commit()
    log_audit(session["username"], "news.update", {"id": news_id})
    return {"ok": True}


@router.delete("/api/news/{news_id}")
async def delete_news(news_id: int, request: Request):
    session = _require_admin(request)
    with SessionLocal() as db:
        deleted = db.query(NewsModel).filter(NewsModel.id == news_id).delete()
        db.commit()
    if not deleted:
        raise HTTPException(404, "News not found")
    log_audit(session["username"], "news.delete", {"id": news_id})
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


# ---------- Logs API ----------

@router.get("/api/logs")
async def list_logs(request: Request, limit: int = 50, offset: int = 0, level: str = None):
    _require_admin(request)
    limit = min(limit, 200)
    data  = get_logs(limit=limit, offset=offset, level=level)
    return data


@router.delete("/api/logs")
async def clear_logs(request: Request, older_than_days: int = None):
    session = _require_admin(request)
    deleted = delete_logs(older_than_days=older_than_days)
    log_audit(
        session["username"],
        "logs.clear",
        {"older_than_days": older_than_days, "deleted": deleted},
    )
    return {"deleted": deleted}


# ---------- Audit Log ----------

@router.get("/api/audit-log")
async def get_audit_log(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    username: str = None,
    action: str = None,
):
    _require_admin(request)
    limit = min(limit, 200)
    with SessionLocal() as db:
        q = db.query(AdminAuditLogModel).order_by(AdminAuditLogModel.created_at.desc())
        if username:
            q = q.filter(AdminAuditLogModel.username == username)
        if action:
            q = q.filter(AdminAuditLogModel.action.like(f"{action}%"))
        total = q.count()
        rows  = q.offset(offset).limit(limit).all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [{
            "id":         r.id,
            "username":   r.username,
            "action":     r.action,
            "details":    r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows],
    }


# ---------- Global Search ----------

@router.get("/api/search")
async def admin_search(request: Request, q: str = ""):
    _require_admin(request)
    q = q.strip()
    if len(q) < 2:
        return {"simulations": [], "users": [], "news": []}

    like = f"%{q}%"
    LIMIT = 5

    with SessionLocal() as db:
        sim_rows = db.query(HistoryEntryModel).filter(
            or_(
                HistoryEntryModel.job_id.ilike(like),
                HistoryEntryModel.character_name.ilike(like),
                HistoryEntryModel.character_realm_slug.ilike(like),
                HistoryEntryModel.character_class.ilike(like),
                HistoryEntryModel.character_spec.ilike(like),
            )
        ).order_by(HistoryEntryModel.created_at.desc()).limit(LIMIT).all()

        user_rows = db.query(UserModel).filter(
            or_(
                UserModel.bnet_id.ilike(like),
                UserModel.main_character_name.ilike(like),
            )
        ).limit(LIMIT).all()

        news_rows = db.query(NewsModel).filter(
            or_(
                NewsModel.title.ilike(like),
                NewsModel.body.ilike(like),
            )
        ).order_by(NewsModel.created_at.desc()).limit(LIMIT).all()

    return {
        "simulations": [{
            "job_id":          r.job_id,
            "character_name":  r.character_name,
            "character_class": r.character_class,
            "character_spec":  r.character_spec,
            "realm":           r.character_realm_slug,
            "dps":             r.dps,
            "created_at":      r.created_at.isoformat() if r.created_at else None,
        } for r in sim_rows],
        "users": [{
            "bnet_id":         r.bnet_id,
            "character_name":  r.main_character_name,
        } for r in user_rows],
        "news": [{
            "id":        r.id,
            "title":     r.title,
            "published": r.published,
        } for r in news_rows],
    }


# ---------- Client Error Reporting ----------

_client_error_hits: dict[str, list[float]] = defaultdict(list)
_CLIENT_ERROR_RATE_LIMIT  = 10
_CLIENT_ERROR_RATE_WINDOW = 60


def _check_client_error_rate_limit(request: Request) -> None:
    ip  = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    now = time.time()
    hits = _client_error_hits[ip]
    _client_error_hits[ip] = [t for t in hits if now - t < _CLIENT_ERROR_RATE_WINDOW]
    if len(_client_error_hits[ip]) >= _CLIENT_ERROR_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many error reports")
    _client_error_hits[ip].append(now)


class ClientErrorReport(BaseModel):
    type:    str
    message: str
    source:  str | None = None
    line:    int | None = None
    col:     int | None = None
    stack:   str | None = None
    url:     str | None = None
    ts:      str | None = None


@router.post("/api/client-error", status_code=204)
async def report_client_error(request: Request, data: ClientErrorReport):
    _check_client_error_rate_limit(request)
    context_parts = []
    if data.url:    context_parts.append(f"url: {data.url}")
    if data.source: context_parts.append(f"source: {data.source}:{data.line}:{data.col}")
    if data.stack:  context_parts.append(f"stack:\n{data.stack[:2000]}")
    prefix = "[uncaught_error]" if data.type == "error" else "[unhandled_rejection]"
    add_log(
        level   = "ERROR",
        message = f"{prefix} {data.message[:500]}",
        context = "\n".join(context_parts) or None,
    )


# ---------- Health Check API ----------

@router.get("/api/health")
async def get_health(request: Request):
    _require_admin(request)
    import psutil
    import subprocess

    result: dict = {}

    # --- database ---
    try:
        with SessionLocal() as db:
            db.execute(__import__('sqlalchemy').text("SELECT 1"))
        result["database"] = "ok"
    except Exception as e:
        result["database"] = f"error: {e}"

    # --- simc binary ---
    simc_path = os.environ.get("SIMC_PATH", "/app/SimulationCraft/simc")
    local_version = _get_local_simc_version(simc_path)
    if local_version:
        result["simc_binary"] = f"ok ({local_version})"
    else:
        result["simc_binary"] = "error: binary not found or not executable"

    # --- simc version vs upstream ---
    try:
        latest = await _get_latest_simc_version()
        local_plain = local_version or ""
        latest_ver  = latest.get("version") or ""
        up_to_date  = (local_plain == latest_ver) if (local_plain and latest_ver) else None
        result["simc_version"] = {
            "local":            local_plain or None,
            "latest":           latest_ver or None,
            "up_to_date":       up_to_date,
            "last_commit_sha":  latest.get("last_commit_sha"),
            "last_commit_date": latest.get("last_commit_date"),
            "last_commit_url":  latest.get("last_commit_url"),
            "cache_age_s":      int(time.time() - _simc_version_cache["ts"]) if _simc_version_cache["ts"] else None,
        }
    except Exception as e:
        result["simc_version"] = {"error": str(e)}

    # --- wow_build ---
    wow_cache = _wow_build_cache.get("data")
    if wow_cache:
        result["wow_build"] = {
            "build":       wow_cache.get("build"),
            "version":     wow_cache.get("version"),
            "cache_age_s": int(time.time() - _wow_build_cache["ts"]),
            "error":       wow_cache.get("error"),
        }
    else:
        try:
            wow_data = await get_wow_retail_build()
            result["wow_build"] = {
                "build":       wow_data.get("build"),
                "version":     wow_data.get("version"),
                "cache_age_s": 0,
                "error":       wow_data.get("error"),
            }
        except Exception as e:
            result["wow_build"] = {"build": None, "version": None, "cache_age_s": None, "error": str(e)}

    # --- last simc rebuild ---
    result["last_rebuild"] = _get_last_rebuild()

    # --- current rebuild state ---
    result["rebuild_state"] = {
        "status":       _rebuild_state["status"],
        "triggered_by": _rebuild_state["triggered_by"],
        "started_at":   _rebuild_state["started_at"],
        "finished_at":  _rebuild_state["finished_at"],
        "error":        _rebuild_state["error"],
    }

    # --- system metrics ---
    try:
        disk = psutil.disk_usage("/")
        free_bytes  = disk.free
        total_bytes = disk.total
        used_pct    = round(disk.used / disk.total * 100, 1)
        result["disk"] = {
            "free_bytes":  free_bytes,
            "total_bytes": total_bytes,
            "used_pct":    used_pct,
        }
    except Exception:
        free_bytes  = None
        total_bytes = None
        result["disk"] = {"error": "unavailable"}

    result["cpu_percent"]    = psutil.cpu_percent()
    result["memory_percent"] = psutil.virtual_memory().percent

    # --- queue ---
    try:
        with SessionLocal() as db:
            active_jobs = db.query(func.count(JobModel.job_id)).filter(
                JobModel.status == "running"
            ).scalar() or 0
        result["active_jobs"] = active_jobs
    except Exception:
        active_jobs = 0
        result["active_jobs"] = 0

    # --- keycloak ping ---
    try:
        cfg = _cfg()
        async with httpx.AsyncClient(timeout=4) as client:
            kc_resp = await client.get(
                f"{cfg['realm_base']}/.well-known/openid-configuration"
            )
        result["keycloak"] = "ok" if kc_resp.status_code == 200 else f"http {kc_resp.status_code}"
    except Exception as e:
        result["keycloak"] = f"error: {str(e)[:80]}"

    # --- alert evaluation ---
    _evaluate_alerts(result, active_jobs, free_bytes, total_bytes)

    return result


# ---------- Alerts API ----------

@router.get("/api/alerts")
async def list_alerts(
    request: Request,
    resolved: bool = False,
    limit: int = 50,
):
    _require_admin(request)
    limit = min(limit, 200)
    with SessionLocal() as db:
        q = db.query(AdminAlertModel).order_by(AdminAlertModel.triggered_at.desc())
        if not resolved:
            q = q.filter(AdminAlertModel.resolved == False)
        items = q.limit(limit).all()
        active_count = db.query(func.count(AdminAlertModel.id)).filter(
            AdminAlertModel.resolved == False
        ).scalar() or 0
    return {
        "active_count": active_count,
        "items": [{
            "id":           a.id,
            "alert_type":   a.alert_type,
            "message":      a.message,
            "resolved":     a.resolved,
            "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
            "resolved_at":  a.resolved_at.isoformat()  if a.resolved_at  else None,
        } for a in items],
    }


@router.get("/api/alerts/badge")
async def get_alert_badge(request: Request):
    _require_admin(request)
    return {"active_count": get_active_alert_count()}


@router.get("/api/alerts/count")
async def get_alert_count(request: Request):
    """Alias dla /api/alerts/badge — zwraca liczbę aktywnych alertów."""
    _require_admin(request)
    return {"active_count": get_active_alert_count()}


@router.post("/api/alerts/{alert_id}/resolve")
async def resolve_alert_endpoint(alert_id: int, request: Request):
    session = _require_admin(request)
    ok = resolve_alert(alert_id)
    if not ok:
        raise HTTPException(404, "Alert not found")
    log_audit(session["username"], "alert.resolve", {"id": alert_id})
    return {"ok": True}


@router.post("/api/alerts/resolve-all")
async def resolve_all_alerts(request: Request):
    session = _require_admin(request)
    with SessionLocal() as db:
        updated = db.query(AdminAlertModel).filter(
            AdminAlertModel.resolved == False
        ).update({
            "resolved":    True,
            "resolved_at": datetime.utcnow(),
        })
        db.commit()
    log_audit(session["username"], "alert.resolve_all", {"resolved_count": updated})
    return {"resolved_count": updated}


# ---------- SimC Rebuild API ----------

@router.get("/api/simc/rebuild-log")
async def get_rebuild_log(
    request: Request,
    limit: int = 20,
    offset: int = 0,
):
    _require_admin(request)
    limit = min(limit, 100)
    with SessionLocal() as db:
        total = db.query(func.count(SimcRebuildLogModel.id)).scalar() or 0
        rows  = db.query(SimcRebuildLogModel).order_by(
            SimcRebuildLogModel.started_at.desc()
        ).offset(offset).limit(limit).all()
    return {
        "total":  total,
        "offset": offset,
        "limit":  limit,
        "items": [{
            "id":           r.id,
            "triggered_by": r.triggered_by,
            "status":       r.status,
            "wow_build":    r.wow_build,
            "simc_before":  r.simc_before,
            "simc_after":   r.simc_after,
            "started_at":   r.started_at.isoformat()  if r.started_at  else None,
            "finished_at":  r.finished_at.isoformat() if r.finished_at else None,
        } for r in rows],
    }


@router.post("/api/simc/rebuild")
async def trigger_simc_rebuild(request: Request):
    session  = _require_admin(request)
    username = session["username"]

    if _rebuild_state["status"] == "running":
        return {"status": "already_running", "started_at": _rebuild_state["started_at"]}

    simc_path   = os.environ.get("SIMC_PATH", "/app/SimulationCraft/simc")
    simc_before = _get_local_simc_version(simc_path)
    wow_build   = get_wow_build_cached()

    with SessionLocal() as db:
        log_row = SimcRebuildLogModel(
            triggered_by = username,
            status       = "running",
            wow_build    = wow_build,
            simc_before  = simc_before,
            started_at   = datetime.utcnow(),
        )
        db.add(log_row)
        db.commit()
        db.refresh(log_row)
        log_id = log_row.id

    _rebuild_state.update({
        "status":       "running",
        "triggered_by": username,
        "started_at":   datetime.utcnow().isoformat(),
        "finished_at":  None,
        "simc_before":  simc_before,
        "simc_after":   None,
        "error":        None,
        "log_id":       log_id,
    })

    log_audit(username, "simc.rebuild.start", {"log_id": log_id, "simc_before": simc_before})

    import asyncio
    import subprocess as _sp

    async def _do_rebuild_ssh():
        ssh_host   = os.environ.get("REBUILD_SSH_HOST",   "localhost")
        ssh_user   = os.environ.get("REBUILD_SSH_USER",   "deploy")
        ssh_key    = os.environ.get("REBUILD_SSH_KEY_PATH", "/run/secrets/rebuild_ssh_key")
        ssh_script = os.environ.get("REBUILD_SSH_SCRIPT",  "/opt/scripts/rebuild-simc.sh")

        final_status = "error"
        simc_after   = None
        error_msg    = None
        full_log     = ""

        try:
            proc = await asyncio.create_subprocess_exec(
                "ssh",
                "-i",         ssh_key,
                "-o",         "StrictHostKeyChecking=no",
                "-o",         "BatchMode=yes",
                "-o",         "ConnectTimeout=10",
                f"{ssh_user}@{ssh_host}",
                ssh_script,
                stdout=_sp.PIPE,
                stderr=_sp.STDOUT,
            )
            out_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=900)
            full_log = out_bytes.decode(errors="replace")[:50000]

            if proc.returncode == 0:
                version_match = re.search(r"^SIMC_VERSION=(.+)$", full_log, re.MULTILINE)
                if version_match:
                    simc_after = version_match.group(1).strip()[:64]
                else:
                    simc_after = _get_local_simc_version(simc_path)
                final_status = "success"
            else:
                error_msg = f"SSH script exited with code {proc.returncode}"

        except asyncio.TimeoutError:
            error_msg = "rebuild timed out (900s)"
        except FileNotFoundError:
            error_msg = "ssh binary not found in container (install openssh-client)"
        except Exception as exc:
            error_msg = str(exc)

        finished = datetime.utcnow()

        with SessionLocal() as db:
            row = db.query(SimcRebuildLogModel).filter(SimcRebuildLogModel.id == log_id).first()
            if row:
                row.status      = final_status
                row.simc_after  = simc_after
                row.finished_at = finished
                row.log_output  = (full_log + (f"\n\nERROR: {error_msg}" if error_msg else ""))[:50000]
                db.commit()

        _rebuild_state.update({
            "status":      final_status,
            "finished_at": finished.isoformat(),
            "simc_after":  simc_after,
            "error":       error_msg,
        })

        log_audit(username, f"simc.rebuild.{final_status}", {
            "log_id":      log_id,
            "simc_before": simc_before,
            "simc_after":  simc_after,
            "error":       error_msg,
        })

    asyncio.create_task(_do_rebuild_ssh())

    return {
        "status":     "started",
        "log_id":     log_id,
        "started_at": _rebuild_state["started_at"],
    }


@router.get("/api/simc/rebuild-state")
async def get_rebuild_state(request: Request):
    """Szybki polling statusu aktualnego rebuildu."""
    _require_admin(request)
    return _rebuild_state


# ---------- Scheduler API ----------

class SchedulerUpdate(BaseModel):
    enabled:    bool | None = None
    interval_h: int  | None = None


@router.get("/api/scheduler")
async def get_scheduler_status(request: Request):
    """Zwraca aktualny stan schedulera auto-rebuildu."""
    _require_admin(request)
    import scheduler as _sched
    from database import SessionModel

    status = _sched.get_status()

    now = time.time()
    with SessionLocal() as db:
        active_sessions  = db.query(func.count(SessionModel.session_id)).filter(
            SessionModel.expires_at > now
        ).scalar() or 0
        expired_sessions = db.query(func.count(SessionModel.session_id)).filter(
            SessionModel.expires_at <= now
        ).scalar() or 0

    status["sessions"] = {
        "active":  active_sessions,
        "expired": expired_sessions,
    }
    return status



@router.patch("/api/scheduler")
async def update_scheduler(request: Request, data: SchedulerUpdate):
    session = _require_admin(request)
    import scheduler as _sched

    changes = {}

    if data.enabled is not None:
        set_config("scheduler.enabled", "true" if data.enabled else "false")
        changes["enabled"] = data.enabled

    if data.interval_h is not None:
        interval_h = max(1, min(168, data.interval_h))
        _sched.reschedule(interval_h)
        changes["interval_h"] = interval_h

    log_audit(session["username"], "scheduler.update", changes)
    return _sched.get_status()


@router.post("/api/scheduler/trigger-now")
async def scheduler_trigger_now(request: Request):
    session = _require_admin(request)
    import asyncio
    import scheduler as _sched

    log_audit(session["username"], "scheduler.trigger_now")
    asyncio.create_task(_sched.trigger_now())
    return {"ok": True, "message": "Sprawdzanie WoW build uruchomione w tle."}

@router.post("/api/scheduler/cleanup-sessions")
async def manual_cleanup_sessions(request: Request):
    session = _require_admin(request)
    import asyncio
    import scheduler as _sched

    log_audit(session["username"], "scheduler.cleanup_sessions")
    asyncio.create_task(_sched._cleanup_sessions())
    return {"ok": True, "message": "Czyszczenie wygasłych sesji uruchomione w tle."}


# ---------- App Config API ----------

_CONFIG_KEYS: dict[str, dict] = {
    "max_concurrent_sims":    {"type": "int",  "default": 3},
    "job_timeout":            {"type": "int",  "default": 300},
    "guest_sims_enabled":     {"type": "bool", "default": True},
    "history_limit_per_user": {"type": "int",  "default": 50},
    "rate_limit_per_minute":  {"type": "int",  "default": 10},
    "one_button_mode_enabled": {"type": "bool", "default": False},
    "public_history_limit":   {"type": "int",  "default": 20},
    "user_history_limit":     {"type": "int",  "default": 20},
    "char_cache_ttl_minutes": {"type": "int",  "default": 60},
}


def _read_config() -> dict:
    result = {}
    for key, meta in _CONFIG_KEYS.items():
        raw = get_config(f"app.{key}")
        if raw is None:
            result[key] = meta["default"]
        elif meta["type"] == "int":
            try:
                result[key] = int(raw)
            except (ValueError, TypeError):
                result[key] = meta["default"]
        elif meta["type"] == "bool":
            result[key] = str(raw).lower() in ("true", "1", "yes")
        else:
            result[key] = raw
    return result


class AppConfigUpdate(BaseModel):
    max_concurrent_sims:     int  | None = None
    job_timeout:             int  | None = None
    guest_sims_enabled:      bool | None = None
    history_limit_per_user:  int  | None = None
    rate_limit_per_minute:   int  | None = None
    one_button_mode_enabled: bool | None = None
    public_history_limit:    int  | None = None
    user_history_limit:      int  | None = None
    char_cache_ttl_minutes:  int  | None = None


@router.get("/api/config")
async def get_app_config(request: Request):
    _require_admin(request)
    return _read_config()


@router.patch("/api/config")
async def update_app_config(request: Request, data: AppConfigUpdate):
    session = _require_admin(request)
    changes = {}

    for key, meta in _CONFIG_KEYS.items():
        value = getattr(data, key, None)
        if value is None:
            continue
        if meta["type"] == "int":
            set_config(f"app.{key}", str(int(value)))
        elif meta["type"] == "bool":
            set_config(f"app.{key}", "true" if value else "false")
        else:
            set_config(f"app.{key}", str(value))
        changes[key] = value

    if changes:
        log_audit(session["username"], "config.update", changes)

    return _read_config()


# ---------- Appearance API ----------

_APPEARANCE_DEFAULTS = {
    "header_title":     "SimCraft Web",
    "hero_title":       "World of Warcraft",
    "emoji":            "\u2694\ufe0f",
    "hero_custom_text": "",
}


def load_appearance_config() -> dict:
    """Publiczny helper — używany przez GET /api/appearance w main.py."""
    return {
        key: (get_config(f"appearance.{key}") or default)
        for key, default in _APPEARANCE_DEFAULTS.items()
    }


class AppearanceUpdate(BaseModel):
    header_title:     str | None = None
    hero_title:       str | None = None
    emoji:            str | None = None
    hero_custom_text: str | None = None


@router.get("/api/appearance")
async def get_appearance(request: Request):
    _require_admin(request)
    return load_appearance_config()


@router.post("/api/appearance")
async def save_appearance(request: Request, data: AppearanceUpdate):
    session = _require_admin(request)
    changes = {}
    for key in _APPEARANCE_DEFAULTS:
        value = getattr(data, key)
        if value is not None:
            set_config(f"appearance.{key}", value)
            changes[key] = value
    if changes:
        log_audit(session["username"], "appearance.update", changes)
    return load_appearance_config()


# ---------- Users API ----------

@router.get("/api/users")
async def list_users(
    request: Request,
    limit: int = 25,
    offset: int = 0,
    total: bool = False,
    search: str = "",
):
    _require_admin(request)
    limit = min(limit, 200)

    with SessionLocal() as db:
        q = db.query(UserModel).filter(UserModel.bnet_id.isnot(None))

        if search:
            like = f"%{search}%"
            q = q.filter(
                or_(
                    UserModel.bnet_id.ilike(like),
                    UserModel.main_character_name.ilike(like),
                )
            )

        total_count = q.count() if total else None
        users = q.order_by(UserModel.created_at.desc()).offset(offset).limit(limit).all()

        result = []
        for u in users:
            agg = db.query(
                func.count(HistoryEntryModel.id).label("sim_count"),
                func.avg(HistoryEntryModel.dps).label("avg_dps"),
                func.max(HistoryEntryModel.created_at).label("last_sim"),
            ).filter(
                HistoryEntryModel.user_id == u.bnet_id,
            ).first()

            last_char = db.query(HistoryEntryModel).filter(
                HistoryEntryModel.user_id == u.bnet_id,
                HistoryEntryModel.character_name.isnot(None),
            ).order_by(HistoryEntryModel.created_at.desc()).first()

            result.append({
                "user_id":         u.bnet_id,
                "character_name":  (
                    u.main_character_name
                    or (last_char.character_name if last_char else None)
                ),
                "character_class": last_char.character_class if last_char else None,
                "character_spec":  last_char.character_spec  if last_char else None,
                "sim_count":       int(agg.sim_count) if agg and agg.sim_count else 0,
                "avg_dps":         float(agg.avg_dps) if agg and agg.avg_dps else None,
                "last_sim":        agg.last_sim.isoformat() if agg and agg.last_sim else None,
                "registered_at":   u.created_at.isoformat() if u.created_at else None,
                "profile_private": bool(u.profile_private),
            })

    if total:
        return {"total": total_count, "items": result}
    return result


@router.get("/api/users/{user_id}/simulations")
async def get_user_simulations(user_id: str, request: Request):
    _require_admin(request)

    with SessionLocal() as db:
        user = db.query(UserModel).filter(UserModel.bnet_id == user_id).first()
        if not user:
            raise HTTPException(404, "User not found")

        sims = db.query(HistoryEntryModel).filter(
            HistoryEntryModel.user_id == user_id,
        ).order_by(HistoryEntryModel.created_at.desc()).limit(200).all()

    return [{
        "job_id":         s.job_id,
        "character_name": s.character_name,
        "character_class": s.character_class,
        "character_spec":  s.character_spec,
        "dps":             s.dps,
        "fight_style":     s.fight_style,
        "one_button_mode": s.one_button_mode,
        "wow_build":       s.wow_build,
        "created_at":      s.created_at.isoformat() if s.created_at else None,
    } for s in sims]


@router.delete("/api/users/{user_id}/simulations")
async def delete_all_user_simulations(user_id: str, request: Request):
    session = _require_admin(request)

    with SessionLocal() as db:
        user = db.query(UserModel).filter(UserModel.bnet_id == user_id).first()
        if not user:
            raise HTTPException(404, "User not found")

        deleted = db.query(HistoryEntryModel).filter(
            HistoryEntryModel.user_id == user_id,
        ).delete(synchronize_session=False)
        db.commit()

    log_audit(session["username"], "user.sims.delete_all", {"user_id": user_id, "deleted": deleted})
    return {"deleted_count": deleted}


@router.delete("/api/simulations/{job_id}")
async def delete_simulation(job_id: str, request: Request):
    session = _require_admin(request)

    with SessionLocal() as db:
        deleted = db.query(HistoryEntryModel).filter(
            HistoryEntryModel.job_id == job_id,
        ).delete(synchronize_session=False)
        db.commit()

    if not deleted:
        raise HTTPException(404, "Simulation not found")

    log_audit(session["username"], "simulation.delete", {"job_id": job_id})
    return {"ok": True}


# ---------- Maintenance Mode API ----------

@router.get("/api/maintenance")
async def get_maintenance(request: Request):
    _require_admin(request)
    enabled = get_config("maintenance.enabled") in ("true", "1")
    message = get_config("maintenance.message") or "Serwis jest tymczasowo niedost\u0119pny. Wracamy wkr\u00f3tce!"
    return {"enabled": enabled, "message": message}


class MaintenanceUpdate(BaseModel):
    enabled: bool
    message: str = ""


@router.post("/api/maintenance")
async def save_maintenance(request: Request, data: MaintenanceUpdate):
    session = _require_admin(request)
    set_config("maintenance.enabled", "true" if data.enabled else "false")
    set_config("maintenance.message", data.message.strip())
    log_audit(session["username"], "maintenance.update", {
        "enabled": data.enabled,
        "message": data.message[:100],
    })
    return {"enabled": data.enabled, "message": data.message.strip()}


# ---------- Tasks API ----------

@router.get("/api/tasks")
async def list_tasks(request: Request):
    _require_admin(request)
    with SessionLocal() as db:
        active = db.query(JobModel).filter(
            JobModel.status.in_(["running", "pending"])
        ).order_by(JobModel.started_at.desc()).limit(50).all()

        recent_done = db.query(JobModel).filter(
            JobModel.status.in_(["done", "error"])
        ).order_by(JobModel.completed_at.desc()).limit(20).all()

    def _fmt(job: JobModel) -> dict:
        return {
            "job_id":       job.job_id,
            "status":       job.status,
            "started_at":   job.started_at.isoformat()   if job.started_at   else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error":        job.error,
        }

    return {
        "active_tasks": [_fmt(j) for j in active],
        "recent_tasks": [_fmt(j) for j in recent_done],
    }


@router.delete("/api/tasks/{job_id}")
async def cancel_task(job_id: str, request: Request):
    session = _require_admin(request)
    with SessionLocal() as db:
        job = db.query(JobModel).filter(JobModel.job_id == job_id).first()
        if not job:
            raise HTTPException(404, "Task not found")
        if job.status not in ("running", "pending"):
            raise HTTPException(400, f"Cannot cancel task with status '{job.status}'")
        job.status       = "error"
        job.completed_at = datetime.utcnow()
        db.commit()
    log_audit(session["username"], "task.cancel", {"job_id": job_id})
    return {"ok": True, "job_id": job_id}
