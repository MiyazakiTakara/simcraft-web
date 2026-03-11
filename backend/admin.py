import os
import time
import uuid
import secrets
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func

from database import SessionLocal, AdminSessionModel, NewsModel, LogEntryModel, get_logs, HistoryEntryModel

router = APIRouter(prefix="/admin")

ADMIN_COOKIE = "admin_session"
SESSION_TTL  = 60 * 60 * 8  # 8 godzin


def _cfg():
    """Lazy-load Keycloak config — czytane przy pierwszym request, nie przy imporcie."""
    url    = os.environ["KEYCLOAK_URL"].rstrip("/")
    realm  = os.environ["KEYCLOAK_REALM"]
    base   = f"{url}/realms/{realm}/protocol/openid-connect"
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
    if not session_id:
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    session = _get_admin_session(session_id)
    if not session:
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return session


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
        db.add(AdminSessionModel(
            session_id = session_id,
            username   = username,
            expires_at = expires_at,
        ))
        db.commit()

    response = RedirectResponse("/admin", status_code=302)
    response.set_cookie(
        key=ADMIN_COOKIE,
        value=session_id,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=SESSION_TTL,
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
    return [{"id": r.id, "title": r.title, "body": r.body,
             "published": r.published, "created_at": r.created_at} for r in rows]


@router.post("/api/news", status_code=201)
async def create_news(request: Request, data: NewsCreate):
    _require_admin(request)
    with SessionLocal() as db:
        entry = NewsModel(
            title=data.title,
            body=data.body,
            published=data.published,
            created_at=int(time.time()),
        )
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
        if data.title is not None:
            row.title = data.title
        if data.body is not None:
            row.body = data.body
        if data.published is not None:
            row.published = data.published
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
    return [{"id": r.id, "title": r.title, "body": r.body, "created_at": r.created_at} for r in rows]


@router.get("/api/logs")
async def list_logs(request: Request, limit: int = 100, level: str = None):
    _require_admin(request)
    logs = get_logs(limit=limit, level=level)
    return [{
        "id": l.id,
        "level": l.level,
        "message": l.message,
        "context": l.context,
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
            .distinct()
            .all()
        )
        
        users_map = {}
        for user_id, char_name, char_class, char_spec in rows:
            if user_id not in users_map:
                users_map[user_id] = {
                    "user_id": user_id,
                    "character_name": char_name,
                    "character_class": char_class,
                    "character_spec": char_spec,
                    "sim_count": 0,
                    "total_dps": 0,
                    "last_sim": 0,
                }
        
        stats = (
            db.query(
                HistoryEntryModel.user_id,
                func.count(HistoryEntryModel.id).label("sim_count"),
                func.avg(HistoryEntryModel.dps).label("avg_dps"),
                func.max(HistoryEntryModel.created_at).label("last_sim"),
            )
            .filter(HistoryEntryModel.user_id.isnot(None))
            .group_by(HistoryEntryModel.user_id)
            .all()
        )
        
        for user_id, sim_count, avg_dps, last_sim in stats:
            if user_id in users_map:
                users_map[user_id]["sim_count"] = sim_count
                users_map[user_id]["avg_dps"] = round(avg_dps, 0) if avg_dps else 0
                users_map[user_id]["last_sim"] = last_sim
    
    users = sorted(users_map.values(), key=lambda x: x["last_sim"] or 0, reverse=True)[:limit]
    return users


@router.get("/api/users/{user_id}/simulations")
async def get_user_simulations(request: Request, user_id: str, limit: int = 20):
    _require_admin(request)
    with SessionLocal() as db:
        rows = (
            db.query(HistoryEntryModel)
            .filter(HistoryEntryModel.user_id == user_id)
            .order_by(HistoryEntryModel.created_at.desc())
            .limit(limit)
            .all()
        )
    return [{
        "job_id": r.job_id,
        "character_name": r.character_name,
        "character_class": r.character_class,
        "character_spec": r.character_spec,
        "dps": r.dps,
        "fight_style": r.fight_style,
        "created_at": r.created_at,
    } for r in rows]
