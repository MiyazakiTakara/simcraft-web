import asyncio
import httpx
from fastapi import APIRouter

from auth import get_session_token, get_blizzard_token

router = APIRouter()


async def _fetch_spec(client: httpx.AsyncClient, token: str, realm_slug: str, name: str) -> str:
    """Pobiera active_spec dla postaci z dedykowanego endpointu."""
    try:
        resp = await client.get(
            f"https://eu.api.blizzard.com/profile/wow/character/{realm_slug}/{name.lower()}"
            "?namespace=profile-eu&locale=en_GB",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("active_spec", {}).get("name", "")
    except Exception:
        pass
    return ""


@router.get("/api/characters")
async def list_characters(session: str):
    access_token = await get_session_token(session)
    blizzard_token = await get_blizzard_token()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://eu.api.blizzard.com/profile/user/wow"
            "?namespace=profile-eu&locale=en_GB",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        print(f"CHARACTERS RESPONSE: {resp.status_code}", flush=True)
        resp.raise_for_status()
        data = resp.json()

    chars = []
    for account in data.get("wow_accounts", []):
        for ch in account.get("characters", []):
            if ch.get("level", 0) < 10:
                continue
            chars.append({
                "id":         ch["id"],
                "name":       ch["name"],
                "realm_slug": ch["realm"]["slug"],
                "realm":      ch["realm"]["name"],
                "region":     "eu",
                "class":      ch.get("playable_class", {}).get("name", ""),
                "spec":       "",
                "level":      ch["level"],
                "avatar":     None,
            })

    chars.sort(key=lambda c: c["level"], reverse=True)

    # Pobierz spec rownolegla dla max 20 najwyzszych postaci (rate limit)
    top_chars = chars[:20]
    async with httpx.AsyncClient() as client:
        specs = await asyncio.gather(*[
            _fetch_spec(client, blizzard_token, c["realm_slug"], c["name"])
            for c in top_chars
        ])
    for ch, spec in zip(top_chars, specs):
        ch["spec"] = spec

    return chars


@router.get("/api/character/{session}/{realm_slug}/{name}")
async def get_character(session: str, realm_slug: str, name: str):
    token = await get_blizzard_token()
    name_lower = name.lower()
    print(f"Fetching: realm_slug={realm_slug} name={name_lower}", flush=True)

    async with httpx.AsyncClient() as client:
        media_resp = await client.get(
            f"https://eu.api.blizzard.com/profile/wow/character"
            f"/{realm_slug}/{name_lower}/character-media"
            f"?namespace=profile-eu&locale=en_GB",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        avatar = None
        if media_resp.status_code == 200:
            assets = media_resp.json().get("assets", [])
            for a in assets:
                if a.get("key") == "avatar":
                    avatar = a.get("value")
                    break

    return {"avatar": avatar}
