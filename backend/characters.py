import httpx
from fastapi import APIRouter, HTTPException

from auth import _sessions, get_blizzard_token

router = APIRouter()


@router.get("/api/characters")
async def list_characters(session: str):
    sess = _sessions.get(session)
    if not sess:
        raise HTTPException(401, "Nieprawidlowa sesja – zaloguj sie ponownie")

    access_token = sess["access_token"]
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
                "level":      ch["level"],
                "avatar":     None,
            })
    chars.sort(key=lambda c: c["level"], reverse=True)
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
