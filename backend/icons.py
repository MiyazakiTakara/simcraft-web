import os
import re
import logging
import httpx
from fastapi import APIRouter
from fastapi.responses import Response, JSONResponse

router = APIRouter()
logger = logging.getLogger("icons")

CACHE_DIR   = "/tmp/icon_cache"
ZAMIMG_BASE = "https://wow.zamimg.com/images/wow/icons/medium"

os.makedirs(CACHE_DIR, exist_ok=True)

# In-memory cache: spell_id (int) -> icon slug (str) lub None
_spell_icon_cache: dict[int, str | None] = {}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.wowhead.com/",
}


def _cache_path(name: str) -> str:
    safe = name.lower().replace("/", "_").replace("..", "_")
    return os.path.join(CACHE_DIR, f"{safe}.jpg")


async def _resolve_icon(spell_id: int) -> str | None:
    """Zwraca slug ikony dla spell_id.
    Metoda 1: nether.wowhead.com tooltip JSON
    Metoda 2: wowhead XML fallback
    """
    if spell_id in _spell_icon_cache:
        return _spell_icon_cache[spell_id]

    # Metoda 1: nether.wowhead.com/tooltip/spell/{id}?json
    try:
        url = f"https://nether.wowhead.com/tooltip/spell/{spell_id}?json"
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=HEADERS) as client:
            r = await client.get(url)
        logger.info("nether spell=%d status=%d", spell_id, r.status_code)
        if r.status_code == 200:
            data = r.json()
            icon = data.get("icon", "").lower().strip()
            if icon and icon != "inv_misc_questionmark":
                _spell_icon_cache[spell_id] = icon
                return icon
    except Exception as e:
        logger.warning("nether failed spell=%d: %s", spell_id, e)

    # Metoda 2: wowhead XML
    try:
        url = f"https://www.wowhead.com/spell={spell_id}&xml"
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=HEADERS) as client:
            r = await client.get(url)
        logger.info("wowhead xml spell=%d status=%d body_len=%d", spell_id, r.status_code, len(r.text))
        if r.status_code == 200:
            m = re.search(r"<icon[^>]*>([^<]+)</icon>", r.text, re.IGNORECASE)
            if m:
                icon = m.group(1).strip().lower()
                if icon and icon != "inv_misc_questionmark":
                    _spell_icon_cache[spell_id] = icon
                    return icon
            else:
                logger.warning("wowhead xml: no <icon> tag for spell=%d, snippet: %s", spell_id, r.text[:200])
    except Exception as e:
        logger.warning("wowhead xml failed spell=%d: %s", spell_id, e)

    _spell_icon_cache[spell_id] = None
    return None


async def _fetch_zamimg(icon: str) -> bytes | None:
    cache = _cache_path(icon)
    if os.path.exists(cache):
        with open(cache, "rb") as f:
            return f.read()
    url = f"{ZAMIMG_BASE}/{icon}.jpg"
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            r = await client.get(url)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            try:
                with open(cache, "wb") as f:
                    f.write(r.content)
            except OSError:
                pass
            return r.content
    except Exception as e:
        logger.warning("zamimg failed icon=%s: %s", icon, e)
    return None


@router.get("/api/icon-by-spell/{spell_id}")
async def get_icon_by_spell(spell_id: int):
    """Zwraca image/jpeg dla danego spell_id."""
    icon = await _resolve_icon(spell_id)
    if not icon:
        logger.warning("icon-by-spell: no icon for spell_id=%d", spell_id)
        return Response(status_code=404)
    data = await _fetch_zamimg(icon)
    if not data:
        return Response(status_code=404)
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"})


@router.get("/api/spell-icon/{spell_id}")
async def get_spell_icon(spell_id: int):
    """Zwraca { icon: 'slug' } dla danego spell_id."""
    icon = await _resolve_icon(spell_id)
    if icon:
        return JSONResponse({"icon": icon})
    return JSONResponse(status_code=404, content={"error": "not found"})


@router.get("/api/icon/{name}.jpg")
async def get_icon(name: str):
    """Proxy dla ikonek zamimg po nazwie."""
    data = await _fetch_zamimg(name.lower().strip())
    if data:
        return Response(content=data, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})
    return Response(status_code=404)
