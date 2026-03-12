import hashlib
from datetime import datetime
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import Column, Integer, String, DateTime
from database import Base, SessionLocal


class PageVisitModel(Base):
    __tablename__ = "page_visits"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    path       = Column(String(512), nullable=False, index=True)
    ip_hash    = Column(String(64), nullable=True)
    session_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ścieżki które pomijamy (statyczne zasoby, API, admin)
SKIP_PREFIXES = (
    "/admin",
    "/static",
    "/favicon",
    "/_",
)
SKIP_EXTENSIONS = (".js", ".css", ".png", ".ico", ".svg", ".woff", ".woff2", ".map")


class TrafficMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        should_track = (
            not any(path.startswith(p) for p in SKIP_PREFIXES)
            and not any(path.endswith(e) for e in SKIP_EXTENSIONS)
            and request.method == "GET"
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
