import os
import time
import uuid
import httpx
import secrets
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import RedirectResponse

from database import SessionLocal, SessionModel

router = APIRouter()

CLIENT_ID     = os.environ["BLIZZARD_CLIENT_ID"]
CLIENT_SECRET = os.environ["BLIZZARD_CLIENT_SECRET"]
REDIRECT_URI  = os.environ.get("REDIRECT_URI", "http://localhost:8000/auth/callback")

_token_cache: dict = {"token": None, "expires_at": 0}

_oauth_states: dict = {}

_OAUTH_STATE_TTL    = 600   # sekundy ważności state
_OAUTH_STATE_MAX    = 500   # max liczba aktywnych state'ów


def _cleanup_oauth_states():
    """Usuwa wygasłe state'y OAuth. Wywołuj przed każdym dodaniem nowego."""
    cutoff = time.time() - _OAUTH_STATE_TTL
    expired = [k for k, v in _oauth_states.items() if v < cutoff]
    for k in expired:
        del _oauth_states[k]


def _get_session(session_id: str) -> dict | None:
    with SessionLocal() as db:
        row = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
    if not row:
        return None
    if time.time() > row.expires_at:
        with SessionLocal() as db:
            db.query(SessionModel).filter(SessionModel.session_id == session_id).delete()
            db.commit()
        return None
    return {"access_token": row.access_token, "expires_at": row.expires_at}


async def get_blizzard_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "https://oauth.battle.net/token",
                data={"grant_type": "client_credentials"},
                auth=(CLIENT_ID, CLIENT_SECRET),
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            _token_cache["token"] = data["access_token"]
            _token_cache["expires_at"] = now + data["expires_in"]
        except Exception as e:
            raise
    return _token_cache["token"]


async def get_session_token(session_id: str) -> str:
    """Zwraca access_token dla sesji lub rzuca 401."""
    s = _get_session(session_id)
    if not s:
        raise HTTPException(401, "Sesja wygasla lub nie istnieje. Zaloguj sie ponownie.")
    return s["access_token"]


@router.get("/auth/login")
async def auth_login():
    _cleanup_oauth_states()
    if len(_oauth_states) >= _OAUTH_STATE_MAX:
        raise HTTPException(429, "Zbyt wiele aktywnych sesji logowania. Spróbuj za chwilę.")
    state = secrets.token_urlsafe(16)
    _oauth_states[state] = time.time()
    url = (
        f"https://oauth.battle.net/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=wow.profile"
        f"&state={state}"
    )
    return RedirectResponse(url)


@router.get("/auth/callback")
async def auth_callback(code: str, state: str = None):
    if not state or state not in _oauth_states:
        raise HTTPException(400, "Invalid state parameter")

    state_time = _oauth_states.pop(state)
    if time.time() - state_time > _OAUTH_STATE_TTL:
        raise HTTPException(400, "State parameter expired")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth.battle.net/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
            auth=(CLIENT_ID, CLIENT_SECRET),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

    session_id = str(uuid.uuid4())
    expires_at = time.time() + data.get("expires_in", 86400)

    with SessionLocal() as db:
        # Wyczysc wygasle sesje przy okazji
        db.query(SessionModel).filter(SessionModel.expires_at < time.time()).delete()
        db.add(SessionModel(
            session_id   = session_id,
            access_token = data["access_token"],
            expires_at   = expires_at,
        ))
        db.commit()

    return RedirectResponse(f"/?session={session_id}")


@router.get("/auth/logout")
async def auth_logout(session: str = None):
    if session:
        with SessionLocal() as db:
            db.query(SessionModel).filter(SessionModel.session_id == session).delete()
            db.commit()
    return RedirectResponse("/")
