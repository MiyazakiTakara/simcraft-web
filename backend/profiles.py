import httpx
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from database import SessionLocal, UserModel, HistoryEntryModel, get_bnet_id_by_session
from auth import get_blizzard_token

router = APIRouter()

_REGION_HOSTS = {
    "eu": "eu.api.blizzard.com",
    "us": "us.api.blizzard.com",
    "kr": "kr.api.blizzard.com",
    "tw": "tw.api.blizzard.com",
}
_DEFAULT_REGION = "eu"


def _blizzard_base(region: str) -> str:
    host = _REGION_HOSTS.get(region.lower(), _REGION_HOSTS[_DEFAULT_REGION])
    return f"https://{host}"


def _namespace(region: str) -> str:
    r = region.lower() if region.lower() in _REGION_HOSTS else _DEFAULT_REGION
    return f"profile-{r}"


async def _fetch_avatar(token: str, realm_slug: str, name: str, region: str = _DEFAULT_REGION) -> str | None:
    base = _blizzard_base(region)
    ns   = _namespace(region)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{base}/profile/wow/character/{realm_slug}/{name.lower()}/character-media"
                f"?namespace={ns}&locale=en_GB",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                for a in resp.json().get("assets", []):
                    if a.get("key") == "avatar":
                        return a.get("value")
    except Exception:
        pass
    return None


async def _fetch_char_info(token: str, realm_slug: str, name: str, region: str = _DEFAULT_REGION) -> dict:
    base = _blizzard_base(region)
    ns   = _namespace(region)
    result = {"class": "", "spec": "", "level": 0, "realm": ""}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{base}/profile/wow/character/{realm_slug}/{name.lower()}"
                f"?namespace={ns}&locale=en_GB",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                result["class"]  = data.get("character_class", {}).get("name", "")
                result["spec"]   = data.get("active_spec", {}).get("name", "")
                result["level"]  = data.get("level", 0)
                result["realm"]  = data.get("realm", {}).get("name", "")
    except Exception:
        pass
    return result


@router.get("/api/profile/{realm}/{name}")
async def get_user_profile(
    realm: str,
    name: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    region: str = Query(default=_DEFAULT_REGION),
):
    realm_slug = realm.lower()
    name_norm  = name.lower()

    # Znajdź usera po main_character
    with SessionLocal() as db:
        user = db.query(UserModel).filter(
            text("LOWER(main_character_name) = :name AND LOWER(main_character_realm) = :realm"),
        ).params(name=name_norm, realm=realm_slug).first()

        if not user:
            raise HTTPException(404, "Profile not found")

        if user.profile_private:
            raise HTTPException(403, "Profile is private")

        offset = (page - 1) * limit
        total = db.query(HistoryEntryModel).filter(
            HistoryEntryModel.user_id == user.bnet_id,
            HistoryEntryModel.is_private == False,
        ).count()

        rows = db.query(HistoryEntryModel).filter(
            HistoryEntryModel.user_id == user.bnet_id,
            HistoryEntryModel.is_private == False,
        ).order_by(HistoryEntryModel.created_at.desc()).offset(offset).limit(limit).all()

        history = [
            {
                "job_id":          r.job_id,
                "character_name":  r.character_name,
                "character_class": r.character_class or "",
                "character_spec":  r.character_spec  or "",
                "character_realm": r.character_realm_slug or "",
                "dps":             float(r.dps) if r.dps else 0.0,
                "fight_style":     r.fight_style or "",
                "created_at":      r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    # Pobierz awatar i info o postaci z Blizzard
    try:
        token = await get_blizzard_token()
        avatar    = await _fetch_avatar(token, realm_slug, user.main_character_name, region)
        char_info = await _fetch_char_info(token, realm_slug, user.main_character_name, region)
    except Exception:
        avatar    = None
        char_info = {"class": "", "spec": "", "level": 0, "realm": ""}

    return {
        "character": {
            "name":       user.main_character_name,
            "realm":      char_info["realm"] or realm,
            "realm_slug": realm_slug,
            "class":      char_info["class"],
            "spec":       char_info["spec"],
            "level":      char_info["level"],
            "avatar":     avatar,
        },
        "history": history,
        "total":   total,
        "page":    page,
        "pages":   max(1, -(-total // limit)),
    }
