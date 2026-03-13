import os
import json
import httpx
from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter()

CACHE_DIR      = "/tmp/icon_cache"
ZAMIMG_BASE    = "https://wow.zamimg.com/images/wow/icons/medium"
WOWHEAD_API    = "https://www.wowhead.com/tooltip/spell/{name}?dataEnv=4&locale=0"
FALLBACK_ICON  = "inv_misc_questionmark"
# cache dla mapowania slug->pełna nazwa ikony (in-memory, przeżywa do restartu)
_name_cache: dict[str, str] = {}

os.makedirs(CACHE_DIR, exist_ok=True)


def _img_cache_path(icon_name: str) -> str:
    safe = icon_name.lower().replace("/", "_").replace("..", "_")
    return os.path.join(CACHE_DIR, f"{safe}.jpg")


def _name_cache_path(slug: str) -> str:
    safe = slug.lower().replace("/", "_").replace("..", "_")
    return os.path.join(CACHE_DIR, f"_name_{safe}.txt")


async def _resolve_icon_name(slug: str) -> str:
    """Zamienia skrócony slug SimCrafta (np. 'blizzard') na pełną nazwę zamimg
    (np. 'spell_frost_blizzard') przez Wowhead tooltip API.
    Zwraca slug bez zmian jeśli lookup się nie powiedzie."""

    # 1. in-memory cache
    if slug in _name_cache:
        return _name_cache[slug]

    # 2. disk cache
    nc = _name_cache_path(slug)
    if os.path.exists(nc):
        with open(nc) as f:
            resolved = f.read().strip()
        _name_cache[slug] = resolved
        return resolved

    # 3. Wowhead lookup
    try:
        url = WOWHEAD_API.format(name=slug)
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "SimCraftWeb/1.0"})
        if r.status_code == 200:
            data = r.json()
            icon = data.get("icon", "").lower().strip()
            if icon:
                _name_cache[slug] = icon
                try:
                    with open(nc, "w") as f:
                        f.write(icon)
                except OSError:
                    pass
                return icon
    except Exception:
        pass

    # 4. fallback — zwróć slug bez zmian (może pasować bezpośrednio)
    _name_cache[slug] = slug
    return slug


async def _fetch_zamimg(icon_name: str) -> bytes | None:
    """Pobiera JPG z zamimg. Przy 404 próbuje fallback inv_misc_questionmark."""
    for attempt in (icon_name, FALLBACK_ICON):
        url = f"{ZAMIMG_BASE}/{attempt}.jpg"
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                r = await client.get(url)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                return r.content
        except Exception:
            pass
    return None


@router.get("/api/icon/{name}.jpg")
async def get_icon(name: str):
    slug = name.lower().strip()

    # sprawdź cache obrazka dla slug (może być już wcześniej zapisany)
    img_path = _img_cache_path(slug)
    if os.path.exists(img_path):
        with open(img_path, "rb") as f:
            data = f.read()
        return Response(content=data, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})

    # rozwiąż pełną nazwę ikony przez Wowhead
    icon_name = await _resolve_icon_name(slug)

    # sprawdź cache obrazka dla pełnej nazwy
    img_path_full = _img_cache_path(icon_name)
    if os.path.exists(img_path_full):
        with open(img_path_full, "rb") as f:
            data = f.read()
        # zapisz też pod oryginalnym slugiem żeby następnym razem trafić od razu
        try:
            with open(img_path, "wb") as f:
                f.write(data)
        except OSError:
            pass
        return Response(content=data, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})

    # pobierz z zamimg
    data = await _fetch_zamimg(icon_name)
    if data:
        for path in (img_path, img_path_full):
            try:
                with open(path, "wb") as f:
                    f.write(data)
            except OSError:
                pass
        return Response(content=data, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})

    return Response(status_code=404)
