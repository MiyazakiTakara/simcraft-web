import os
import time
import httpx
import secrets
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()

CLIENT_ID     = os.environ["BLIZZARD_CLIENT_ID"]
CLIENT_SECRET = os.environ["BLIZZARD_CLIENT_SECRET"]
REDIRECT_URI  = os.environ.get("REDIRECT_URI", "http://localhost:8000/auth/callback")

print(f"REDIRECT_URI = {REDIRECT_URI}", flush=True)

_token_cache: dict = {"token": None, "expires_at": 0}
_sessions: dict = {}   # session_id -> {"access_token": ..., "expires_at": ...}


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

    import uuid, time
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "access_token": data["access_token"],
        "expires_at": time.time() + data.get("expires_in", 3600),
    }
    return RedirectResponse(f"/?session={session_id}")


@router.get("/auth/logout")
async def auth_logout():
    return RedirectResponse("/")
