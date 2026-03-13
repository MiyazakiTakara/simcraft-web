import os
import re
import httpx
from fastapi import APIRouter
from fastapi.responses import Response, JSONResponse

router = APIRouter()

CACHE_DIR   = "/tmp/icon_cache"
ZAMIMG_BASE = "https://wow.zamimg.com/images/wow/icons/medium"

os.makedirs(CACHE_DIR, exist_ok=True)

# In-memory cache: spell_id (int) -> icon slug (str) lub None
_spell_icon_cache: dict[int, str | None] = {}


def _cache_path(name: str) -> str:
    safe = name.lower().replace("/", "_").replace("..", "_")
    return os.path.join(CACHE_DIR, f"{safe}.jpg")


@router.get("/api/spell-icon/{spell_id}")
async def get_spell_icon(spell_id: int):
    """Zwraca { icon: 'slug' } dla danego spell_id.
    Odpytuje Wowhead XML API raz i cache'uje w pamięci."""
    if spell_id in _spell_icon_cache:
        icon = _spell_icon_cache[spell_id]
        if icon:
            return JSONResponse({"icon": icon})
        return JSONResponse(status_code=404, content={"error": "not found"})

    url = f"https://www.wowhead.com/spell={spell_id}&xml"
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; SimCraftWeb/1.0)"
        }) as client:
            r = await client.get(url)

        if r.status_code == 200:
            m = re.search(r"<icon[^>]*>([^<]+)</icon>", r.text, re.IGNORECASE)
            if m:
                icon = m.group(1).strip().lower()
                _spell_icon_cache[spell_id] = icon
                return JSONResponse({"icon": icon})

    except Exception:
        pass

    _spell_icon_cache[spell_id] = None
    return JSONResponse(status_code=404, content={"error": "not found"})


@router.get("/api/icon/{name}.jpg")
async def get_icon(name: str):
    """Proxy dla ikonek zamimg — używane tylko jako fallback.
    Główna ścieżka to Wowhead po spell_id bezpośrednio w przegladarce."""
    slug = name.lower().strip()
    cache = _cache_path(slug)

    if os.path.exists(cache):
        with open(cache, "rb") as f:
            data = f.read()
        return Response(content=data, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})

    url = f"{ZAMIMG_BASE}/{slug}.jpg"
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            r = await client.get(url)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            try:
                with open(cache, "wb") as f:
                    f.write(r.content)
            except OSError:
                pass
            return Response(content=r.content, media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        pass

    return Response(status_code=404)
