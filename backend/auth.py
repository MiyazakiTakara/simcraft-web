import os
import time
import uuid
import httpx
import secrets
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional

from database import (
    SessionLocal, SessionModel,
    get_session_info, set_main_character, clear_first_login,
    get_or_create_user, get_user_settings, save_user_settings,
    get_bnet_id_by_session,
)

router = APIRouter()

CLIENT_ID     = os.environ["BLIZZARD_CLIENT_ID"]
CLIENT_SECRET = os.environ["BLIZZARD_CLIENT_SECRET"]
REDIRECT_URI  = os.environ.get("REDIRECT_URI", "http://localhost:8000/auth/callback")

_token_cache: dict = {"token": None, "expires_at": 0}
_oauth_states: dict = {}
_OAUTH_STATE_TTL = 600
_OAUTH_STATE_MAX = 500


def _cleanup_oauth_states():
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
    return _token_cache["token"]


async def get_session_token(session_id: str) -> str:
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
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI},
            auth=(CLIENT_ID, CLIENT_SECRET),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        access_token = data["access_token"]

        userinfo_resp = await client.get(
            "https://oauth.battle.net/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        userinfo_resp.raise_for_status()
        userinfo = userinfo_resp.json()
        bnet_id = str(userinfo.get("id", ""))

    user = get_or_create_user(bnet_id) if bnet_id else None
    is_first_login = not (user and user["main_character_name"])

    session_id = str(uuid.uuid4())
    expires_at = time.time() + data.get("expires_in", 86400)

    with SessionLocal() as db:
        db.query(SessionModel).filter(SessionModel.expires_at < time.time()).delete()
        db.add(SessionModel(
            session_id           = session_id,
            access_token         = access_token,
            expires_at           = expires_at,
            bnet_id              = bnet_id or None,
            main_character_name  = user["main_character_name"]  if user else None,
            main_character_realm = user["main_character_realm"] if user else None,
            is_first_login       = is_first_login,
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


@router.get("/auth/session/info")
async def session_info(session: str):
    info = get_session_info(session)
    if not info:
        raise HTTPException(401, "Sesja wygasla lub nie istnieje.")
    return info


@router.post("/auth/session/refresh")
async def refresh_session(session: str):
    """
    Sprawdza ważność tokena BNet i przedłuża sesję jeśli token wciąż żywy.
    Zwraca { ok, expires_at, expires_in_seconds }.
    """
    with SessionLocal() as db:
        row = db.query(SessionModel).filter(SessionModel.session_id == session).first()
        if not row:
            raise HTTPException(401, "Sesja nie istnieje.")

        now = time.time()
        if now > row.expires_at:
            db.delete(row)
            db.commit()
            raise HTTPException(401, "Sesja wygasła — zaloguj się ponownie.")

        # Waliduj token u Blizzarda
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://oauth.battle.net/userinfo",
                    headers={"Authorization": f"Bearer {row.access_token}"},
                    timeout=8,
                )
                if resp.status_code == 401:
                    db.delete(row)
                    db.commit()
                    raise HTTPException(401, "Token BNet wygasł — zaloguj się ponownie.")
        except httpx.RequestError:
            pass  # BNet niedostępny — nie karaj użytkownika

        # Przedłuż sesję o 1h od teraz jeśli wygasa za mniej niż 2h
        if row.expires_at - now < 7200:
            row.expires_at = now + 3600
            db.commit()

    return {
        "ok": True,
        "expires_at": row.expires_at,
        "expires_in_seconds": int(row.expires_at - now)
    }


@router.get("/auth/session/settings")
async def get_settings(session: str):
    """Zwraca ustawienia zalogowanego użytkownika."""
    info = get_session_info(session)
    if not info or not info.get("bnet_id"):
        raise HTTPException(401, "Sesja wygasla lub nie istnieje.")
    settings = get_user_settings(info["bnet_id"])
    if not settings:
        raise HTTPException(404, "Użytkownik nie znaleziony.")
    return settings


class SettingsRequest(BaseModel):
    main_character_name:  Optional[str] = None
    main_character_realm: Optional[str] = None
    profile_private:      bool = False


@router.patch("/auth/session/settings")
async def update_settings(session: str, body: SettingsRequest):
    """Zapisuje ustawienia użytkownika."""
    info = get_session_info(session)
    if not info or not info.get("bnet_id"):
        raise HTTPException(401, "Sesja wygasla lub nie istnieje.")
    if body.main_character_name is not None and not body.main_character_name.strip():
        raise HTTPException(400, "Nazwa postaci nie może być pusta.")
    result = save_user_settings(
        bnet_id              = info["bnet_id"],
        main_character_name  = body.main_character_name,
        main_character_realm = body.main_character_realm,
        profile_private      = body.profile_private,
    )
    return {"ok": True, **result}


class MainCharRequest(BaseModel):
    name:  str
    realm: str


@router.patch("/auth/session/main-character")
async def update_main_character(session: str, body: MainCharRequest):
    info = get_session_info(session)
    if not info:
        raise HTTPException(401, "Sesja wygasla lub nie istnieje.")
    if not body.name or not body.realm:
        raise HTTPException(400, "Podaj name i realm.")
    set_main_character(session, body.name.strip(), body.realm.strip())
    return {"ok": True}


@router.post("/auth/session/skip-first-login")
async def skip_first_login(session: str):
    info = get_session_info(session)
    if not info:
        raise HTTPException(401, "Sesja wygasla lub nie istnieje.")
    clear_first_login(session)
    return {"ok": True}


@router.get("/auth/session/character-privacy")
async def get_character_privacy(session: str):
    """
    Zwraca mapę name|realm_slug -> bool dla wszystkich postaci użytkownika.
    Źródłem prawdy jest tabela history — bez odpytywania Blizzard API.
    Postacie które mają chociaż jedną prywatną symulację są oznaczone True,
    postacie które mają symulacje ale żadna nie jest prywatna — False.
    Postacie bez żadnych symulacji nie pojawiają się w historii, więc
    frontend domyślnie traktuje je jako publiczne (klucz nieobecny = False).
    """
    from database import SessionLocal, HistoryEntryModel

    bnet_id = get_bnet_id_by_session(session)
    if not bnet_id:
        raise HTTPException(401, "Sesja wygasla lub nie istnieje.")

    privacies: dict[str, bool] = {}

    with SessionLocal() as db:
        # Pobierz wszystkie unikalne kombinacje postac+realm dla tego usera
        rows = db.query(
            HistoryEntryModel.character_name,
            HistoryEntryModel.character_realm_slug,
            HistoryEntryModel.is_private,
        ).filter(
            HistoryEntryModel.user_id == bnet_id,
        ).all()

    for char_name, realm_slug, is_private in rows:
        if not char_name or not realm_slug:
            continue
        key = char_name + "|" + realm_slug
        # Raz ustawione True (prywatna) nie jest nadpisywane przez False
        if key not in privacies:
            privacies[key] = bool(is_private)
        elif is_private:
            privacies[key] = True

    return {"privacies": privacies}


class CharPrivacyRequest(BaseModel):
    character_name: str
    character_realm: str
    is_private: bool


@router.patch("/auth/session/character-privacy")
async def update_character_privacy(session: str, body: CharPrivacyRequest):
    """Ustawia prywatność dla konkretnej postaci - ukrywa/odkrywa wszystkie jej symulacje."""
    from database import SessionLocal, HistoryEntryModel

    bnet_id = get_bnet_id_by_session(session)
    if not bnet_id:
        raise HTTPException(401, "Sesja wygasla lub nie istnieje.")

    with SessionLocal() as db:
        db.query(HistoryEntryModel).filter(
            HistoryEntryModel.user_id == bnet_id,
            HistoryEntryModel.character_name == body.character_name,
            HistoryEntryModel.character_realm_slug == body.character_realm,
        ).update({"is_private": body.is_private})
        db.commit()

    return {"ok": True}
