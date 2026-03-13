import os
import httpx
from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter()

CACHE_DIR = "/tmp/icon_cache"
ZAMIMG_BASE = "https://wow.zamimg.com/images/wow/icons/medium"
FALLBACK_ICON = "inv_misc_questionmark"
DEFAULT_PNG: bytes | None = None

os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(name: str) -> str:
    safe = name.lower().replace("/", "_").replace("..", "_")
    return os.path.join(CACHE_DIR, f"{safe}.jpg")


async def _fetch_icon(name: str) -> bytes | None:
    """Pobiera ikonę z zamimg. Próbuje podaną nazwę, potem fallback."""
    for attempt in (name, FALLBACK_ICON):
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
    name = name.lower().strip()
    cache = _cache_path(name)

    # cache hit
    if os.path.exists(cache):
        with open(cache, "rb") as f:
            data = f.read()
        return Response(
            content=data,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    # fetch
    data = await _fetch_icon(name)
    if data:
        try:
            with open(cache, "wb") as f:
                f.write(data)
        except OSError:
            pass
        return Response(
            content=data,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    return Response(status_code=404)
