import os
import time
import json
import uuid
import httpx
import secrets
import threading
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

router = APIRouter()

CLIENT_ID     = os.environ["BLIZZARD_CLIENT_ID"]
CLIENT_SECRET = os.environ["BLIZZARD_CLIENT_SECRET"]
REDIRECT_URI  = os.environ.get("REDIRECT_URI", "http://localhost:8000/auth/callback")

RESULTS_DIR   = os.environ.get("RESULTS_DIR", "/app/results")
SESSIONS_FILE = os.path.join(RESULTS_DIR, "sessions.json")
_lock = threading.Lock()

print(f"REDIRECT_URI = {REDIRECT_URI}", flush=True)

_token_cache: dict = {"token": None, "expires_at": 0}


def _load_sessions() -> dict:
    if not os.path.exists(SESSIONS_FILE):
        return {}
    try:
        with open(SESSIONS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_sessions(sessions: dict):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(SESSIONS_FILE, "w") as f:
        json.dump(sessions, f)


def _get_session(session_id: str) -> dict | None:
    with _lock:
        sessions = _load_sessions()
    s = sessions.get(session_id)
    if not s:
        return None
    # Wygasla sesja
    if time.time() > s.get("expires_at", 0):
        with _lock:
            sessions = _load_sessions()
            sessions.pop(session_id, None)
            _save_sessions(sessions)
        return None
    return s


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
            print(f"TOKEN RESPONSE: {resp.status_code} {resp.text[:200]}", flush=True)
            resp.raise_for_status()
            data = resp.json()
            _token_cache["token"] = data["access_token"]
            _token_cache["expires_at"] = now + data["expires_in"]
        except Exception as e:
            print(f"TOKEN ERROR: {e}", flush=True)
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
    state = secrets.token_urlsafe(16)
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
    session_data = {
        "access_token": data["access_token"],
        "expires_at":   time.time() + data.get("expires_in", 86400),
    }
    with _lock:
        sessions = _load_sessions()
        sessions[session_id] = session_data
        # Wyczysc wygasle sesje
        now = time.time()
        sessions = {k: v for k, v in sessions.items() if v.get("expires_at", 0) > now}
        sessions[session_id] = session_data
        _save_sessions(sessions)

    return RedirectResponse(f"/?session={session_id}")


@router.get("/auth/logout")
async def auth_logout(session: str = None):
    if session:
        with _lock:
            sessions = _load_sessions()
            sessions.pop(session, None)
            _save_sessions(sessions)
    return RedirectResponse("/")
