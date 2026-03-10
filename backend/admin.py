import os
import time
import uuid
import secrets
import httpx
from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from database import SessionLocal, AdminSessionModel, NewsModel

router = APIRouter(prefix="/admin")

KEYCLOAK_URL      = os.environ["KEYCLOAK_URL"].rstrip("/")
KEYCLOAK_REALM    = os.environ["KEYCLOAK_REALM"]
KEYCLOAK_CLIENT_ID     = os.environ["KEYCLOAK_CLIENT_ID"]
KEYCLOAK_CLIENT_SECRET = os.environ["KEYCLOAK_CLIENT_SECRET"]
ADMIN_REDIRECT_URI     = os.environ["ADMIN_REDIRECT_URI"]

ADMIN_COOKIE   = "admin_session"
SESSION_TTL    = 60 * 60 * 8  # 8 godzin

_oidc_base = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect"


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
    state = secrets.token_urlsafe(16)
    url = (
        f"{_oidc_base}/auth"
        f"?client_id={KEYCLOAK_CLIENT_ID}"
        f"&redirect_uri={ADMIN_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid profile email"
        f"&state={state}"
    )
    return RedirectResponse(url)


@router.get("/callback")
async def admin_callback(code: str, state: str = None):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_oidc_base}/token",
            data={
                "grant_type":   "authorization_code",
                "code":         code,
                "redirect_uri": ADMIN_REDIRECT_URI,
                "client_id":    KEYCLOAK_CLIENT_ID,
                "client_secret": KEYCLOAK_CLIENT_SECRET,
            },
            timeout=10,
        )
        resp.raise_for_status()
        token_data = resp.json()

        # Pobierz info o userze
        userinfo_resp = await client.get(
            f"{_oidc_base}/userinfo",
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
    html_path = "/app/frontend/admin.html"
    with open(html_path) as f:
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


# ---------- publiczne API (bez autoryzacji) ----------

@router.get("/api/news/public")
async def public_news():
    with SessionLocal() as db:
        rows = db.query(NewsModel).filter(NewsModel.published == True).order_by(NewsModel.created_at.desc()).limit(20).all()
    return [{"id": r.id, "title": r.title, "body": r.body, "created_at": r.created_at} for r in rows]
