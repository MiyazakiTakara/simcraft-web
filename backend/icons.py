import os
import httpx
from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter()

CACHE_DIR   = "/tmp/icon_cache"
ZAMIMG_BASE = "https://wow.zamimg.com/images/wow/icons/medium"

os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(name: str) -> str:
    safe = name.lower().replace("/", "_").replace("..", "_")
    return os.path.join(CACHE_DIR, f"{safe}.jpg")


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
