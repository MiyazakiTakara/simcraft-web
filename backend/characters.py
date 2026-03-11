import asyncio
import httpx
from fastapi import APIRouter, HTTPException

from auth import get_session_token, get_blizzard_token

router = APIRouter()

# Mapowanie region -> host Blizzard API
_REGION_HOSTS: dict[str, str] = {
    "eu": "eu.api.blizzard.com",
    "us": "us.api.blizzard.com",
    "kr": "kr.api.blizzard.com",
    "tw": "tw.api.blizzard.com",
}
_DEFAULT_REGION = "eu"


def _blizzard_base(region: str) -> str:
    """Zwraca bazowy URL API Blizzard dla danego regionu."""
    host = _REGION_HOSTS.get(region.lower(), _REGION_HOSTS[_DEFAULT_REGION])
    return f"https://{host}"


def _namespace(region: str, kind: str = "profile") -> str:
    """Zwraca namespace Blizzard (np. profile-eu) dla danego regionu."""
    r = region.lower() if region.lower() in _REGION_HOSTS else _DEFAULT_REGION
    return f"{kind}-{r}"


async def _fetch_spec(client: httpx.AsyncClient, token: str, region: str, realm_slug: str, name: str) -> str:
    base = _blizzard_base(region)
    ns   = _namespace(region)
    try:
        resp = await client.get(
            f"{base}/profile/wow/character/{realm_slug}/{name.lower()}"
            f"?namespace={ns}&locale=en_GB",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("active_spec", {}).get("name", "")
    except Exception:
        pass
    return ""


@router.get("/api/characters")
async def list_characters(session: str, region: str = _DEFAULT_REGION):
    region = region.lower()
    access_token   = await get_session_token(session)
    blizzard_token = await get_blizzard_token()
    base = _blizzard_base(region)
    ns   = _namespace(region)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{base}/profile/user/wow?namespace={ns}&locale=en_GB",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
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
                "region":     region,
                "class":      ch.get("playable_class", {}).get("name", ""),
                "spec":       "",
                "level":      ch["level"],
                "avatar":     None,
            })

    chars.sort(key=lambda c: c["level"], reverse=True)

    top_chars = chars[:20]
    async with httpx.AsyncClient() as client:
        specs = await asyncio.gather(*[
            _fetch_spec(client, blizzard_token, region, c["realm_slug"], c["name"])
            for c in top_chars
        ])
    for ch, spec in zip(top_chars, specs):
        ch["spec"] = spec

    return chars


@router.get("/api/character-media")
async def get_character_media(session: str, realm_slug: str, name: str, region: str = _DEFAULT_REGION):
    region = region.lower()
    token  = await get_blizzard_token()
    base   = _blizzard_base(region)
    ns     = _namespace(region)
    name_lower = name.lower()

    async with httpx.AsyncClient() as client:
        media_resp = await client.get(
            f"{base}/profile/wow/character/{realm_slug}/{name_lower}/character-media"
            f"?namespace={ns}&locale=en_GB",
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
        raise HTTPException(404, "Avatar not found")

    return {"avatar": avatar}


@router.get("/api/character/equipment")
async def get_character_equipment(session: str, realm_slug: str, name: str, region: str = _DEFAULT_REGION):
    region = region.lower()
    token  = await get_blizzard_token()
    base   = _blizzard_base(region)
    ns     = _namespace(region)
    name_lower = name.lower()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{base}/profile/wow/character/{realm_slug}/{name_lower}/equipment"
            f"?namespace={ns}&locale=en_GB",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code == 404:
            raise HTTPException(404, "Character not found")
        if resp.status_code == 401:
            raise HTTPException(401, "Character data is private")
        resp.raise_for_status()
        data = resp.json()

    equipment = []
    for slot in data.get("equipped_items", []):
        item_data = slot.get("item", {})
        item = {
            "slot":        slot.get("slot", {}).get("name", ""),
            "name":        item_data.get("name", ""),
            "icon":        item_data.get("media", {}).get("id", ""),
            "quality":     item_data.get("quality", {}).get("type", ""),
            "level":       slot.get("level", {}).get("value", 0),
            "stats":       [],
            "spells":      [],
            "description": item_data.get("description", ""),
        }

        for stat in slot.get("stats", []):
            stat_type = stat.get("type", {})
            if isinstance(stat_type, dict):
                stat_label = stat_type.get("display_type", stat_type.get("name", "?"))
            else:
                stat_label = str(stat_type)
            item["stats"].append({"type": stat_label, "value": stat.get("value", 0)})

        enchant = slot.get("enchant", {})
        if enchant:
            item["enchant"] = enchant.get("display_string", "")

        gem = slot.get("gem", {})
        if gem:
            item["gem"] = gem.get("item", {}).get("name", "")

        for spell in slot.get("spells", []):
            item["spells"].append({
                "name":        spell.get("name", ""),
                "description": spell.get("description", ""),
                "icon":        spell.get("icon", ""),
            })

        equipment.append(item)

    return {"equipment": equipment}


@router.get("/api/character/statistics")
async def get_character_statistics(session: str, realm_slug: str, name: str, region: str = _DEFAULT_REGION):
    region = region.lower()
    token  = await get_blizzard_token()
    base   = _blizzard_base(region)
    ns     = _namespace(region)
    name_lower = name.lower()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{base}/profile/wow/character/{realm_slug}/{name_lower}/statistics"
            f"?namespace={ns}&locale=en_GB",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code == 404:
            raise HTTPException(404, "Character not found")
        if resp.status_code == 401:
            raise HTTPException(401, "Character data is private")
        resp.raise_for_status()
        data = resp.json()

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

    def get_stat_val(v):
        if isinstance(v, dict):
            return v.get("effective", v.get("value", v.get("base", "?")))
        return v if v is not None else "?"

    stats = {}
    for key, label in stat_map.items():
        val = data.get(key)
        if val is not None:
            stats[label] = get_stat_val(val)

    return {"statistics": stats}


@router.get("/api/character/talents")
async def get_character_talents(session: str, realm_slug: str, name: str, region: str = _DEFAULT_REGION):
    region = region.lower()
    token  = await get_blizzard_token()
    base   = _blizzard_base(region)
    ns     = _namespace(region)
    name_lower = name.lower()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{base}/profile/wow/character/{realm_slug}/{name_lower}/talents"
            f"?namespace={ns}&locale=en_GB",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code == 404:
            return {"talents": [], "error": "Talents API currently unavailable (Blizzard API issue)"}
        if resp.status_code == 401:
            raise HTTPException(401, "Character data is private")
        resp.raise_for_status()
        data = resp.json()

    talents = []
    for t in data.get("talents", []):
        if t.get("selected"):
            for tier in t.get("tiers", []):
                tier_data = {
                    "tier":  tier.get("tier_index", 0),
                    "spell": None,
                }
                spell = tier.get("spell", {})
                if spell:
                    tier_data["spell"] = {
                        "name": spell.get("name", ""),
                        "icon": spell.get("icon", ""),
                        "id":   spell.get("id", ""),
                    }
                talents.append(tier_data)

    return {"talents": talents}
