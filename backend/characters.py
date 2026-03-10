import asyncio
import httpx
from fastapi import APIRouter

from auth import get_session_token, get_blizzard_token

router = APIRouter()


async def _fetch_spec(client: httpx.AsyncClient, token: str, realm_slug: str, name: str) -> str:
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

    top_chars = chars[:20]
    async with httpx.AsyncClient() as client:
        specs = await asyncio.gather(*[
            _fetch_spec(client, blizzard_token, c["realm_slug"], c["name"])
            for c in top_chars
        ])
    for ch, spec in zip(top_chars, specs):
        ch["spec"] = spec

    return chars


@router.get("/api/character-media")
async def get_character_media(session: str, realm_slug: str, name: str):
    token = await get_blizzard_token()
    name_lower = name.lower()

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

    if avatar is None:
        from fastapi import HTTPException
        raise HTTPException(404, "Avatar not found")

    return {"avatar": avatar}


@router.get("/api/character/equipment")
async def get_character_equipment(session: str, realm_slug: str, name: str):
    token = await get_blizzard_token()
    name_lower = name.lower()

    url = f"https://eu.api.blizzard.com/profile/wow/character/{realm_slug}/{name_lower}/equipment?namespace=profile-eu&locale=en_GB"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code == 404:
            from fastapi import HTTPException
            raise HTTPException(404, "Character not found")
        if resp.status_code == 401:
            from fastapi import HTTPException
            raise HTTPException(401, "Character data is private")
        resp.raise_for_status()
        data = resp.json()

    equipment = []
    for slot in data.get("equipped_items", []):
        item = {
            "slot": slot.get("slot", {}).get("name", ""),
            "name": slot.get("item", {}).get("name", ""),
            "icon": slot.get("item", {}).get("media", {}).get("id", ""),
            "quality": slot.get("item", {}).get("quality", {}).get("type", ""),
            "level": slot.get("level", {}).get("value", 0),
            "stats": [],
        }
        for stat in slot.get("stats", []):
            item["stats"].append({
                "type": stat.get("type", ""),
                "value": stat.get("value", 0),
            })
        enchant = slot.get("enchant", {})
        if enchant:
            item["enchant"] = enchant.get("display_string", "")
        gem = slot.get("gem", {})
        if gem:
            item["gem"] = gem.get("item", {}).get("name", "")
        equipment.append(item)

    return {"equipment": equipment}


@router.get("/api/character/statistics")
async def get_character_statistics(session: str, realm_slug: str, name: str):
    token = await get_blizzard_token()
    name_lower = name.lower()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://eu.api.blizzard.com/profile/wow/character/{realm_slug}/{name_lower}/statistics?namespace=profile-eu&locale=en_GB",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code == 404:
            from fastapi import HTTPException
            raise HTTPException(404, "Character not found")
        if resp.status_code == 401:
            from fastapi import HTTPException
            raise HTTPException(401, "Character data is private")
        resp.raise_for_status()
        data = resp.json()

    stats = {}
    stat_map = {
        "health": "Health",
        "power": "Power",
        "power_regen": "Power Regen",
        "speed": "Speed",
        "strength": "Strength",
        "agility": "Agility",
        "stamina": "Stamina",
        "intellect": "Intellect",
        "crit_rating": "Crit",
        "crit_percent": "Crit %",
        "haste_rating": "Haste",
        "haste_percent": "Haste %",
        "mastery_rating": "Mastery",
        "mastery_percent": "Mastery %",
        "versatility_rating": "Versatility",
        "versatility_damage_done_bonus": "Vers %",
        "avoidance_rating": "Avoidance",
        "armor": "Armor",
        "dodge_rating": "Dodge",
        "dodge_percent": "Dodge %",
        "parry_rating": "Parry",
        "parry_percent": "Parry %",
        "block_rating": "Block",
        "block_percent": "Block %",
    }

    for key, label in stat_map.items():
        val = data.get(key)
        if val is not None:
            stats[label] = val

    return {"statistics": stats}


@router.get("/api/character/talents")
async def get_character_talents(session: str, realm_slug: str, name: str):
    token = await get_blizzard_token()
    name_lower = name.lower()
    url = f"https://eu.api.blizzard.com/profile/wow/character/{realm_slug}/{name_lower}/talents?namespace=profile-eu&locale=en_GB"
    print(f"TALENTS API: {url}", flush=True)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        print(f"TALENTS RESP: {resp.status_code} {resp.text[:200]}", flush=True)
        if resp.status_code == 404:
            from fastapi import HTTPException
            raise HTTPException(404, "Character not found")
        if resp.status_code == 401:
            from fastapi import HTTPException
            raise HTTPException(401, "Character data is private")
        resp.raise_for_status()
        data = resp.json()

    talents = []
    for t in data.get("talents", []):
        if t.get("selected"):
            for tier in t.get("tiers", []):
                tier_data = {
                    "tier": tier.get("tier_index", 0),
                    "spell": None,
                }
                spell = tier.get("spell", {})
                if spell:
                    tier_data["spell"] = {
                        "name": spell.get("name", ""),
                        "icon": spell.get("icon", ""),
                        "id": spell.get("id", ""),
                    }
                talents.append(tier_data)

    return {"talents": talents}
