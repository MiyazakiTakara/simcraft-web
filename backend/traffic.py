import hashlib
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from database import SessionLocal, PageVisitModel


SKIP_PREFIXES = (
    "/admin",
    "/static",
    "/favicon",
    "/_",
    "/api",
)
SKIP_EXTENSIONS = (".js", ".css", ".png", ".ico", ".svg", ".woff", ".woff2", ".map")

# strony które chcemy śledzic (prefix)
TRACK_PATHS = ("/", "/rankings", "/history", "/result", "/profile", "/news")


class TrafficMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        should_track = (
            request.method == "GET"
            and not any(path.startswith(p) for p in SKIP_PREFIXES)
            and not any(path.endswith(e) for e in SKIP_EXTENSIONS)
            and any(path == p or path.startswith(p + "/") for p in TRACK_PATHS)
        )
        if should_track:
            try:
                ip = request.client.host if request.client else None
                ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else None
                session_id = request.cookies.get("session")
                with SessionLocal() as db:
                    db.add(PageVisitModel(
                        path=path,
                        ip_hash=ip_hash,
                        session_id=session_id,
                    ))
                    db.commit()
            except Exception:
                pass
        return await call_next(request)
