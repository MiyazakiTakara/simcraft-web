import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from database import init_db, get_config
from traffic import TrafficMiddleware

import admin
import admin_docs
import auth
import simulation
import results
import history
import rankings
import reactions
import characters
import profiles
import favorites
import icons
import talents
import system_message
import gdpr
import vault
import scheduler as _scheduler_module


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    favorites.ensure_table()
    _scheduler_module.start_scheduler()
    # Pre-fill wow_build cache so first simulations after restart get correct wow_build in history
    try:
        await admin.get_wow_retail_build()
    except Exception:
        pass
    yield
    _scheduler_module.stop_scheduler()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TrafficMiddleware)


# ---------- Maintenance Middleware ----------

_MAINTENANCE_CACHE: dict = {"ts": 0.0, "enabled": False, "message": ""}
_MAINTENANCE_CACHE_TTL = 5  # sekund

# Ŝieżki blokowane podczas maintenance
_MAINTENANCE_BLOCKED_PREFIXES = (
    "/sim",
    "/api/simulate",
    "/api/job",
)

_MAINTENANCE_HTML = """\
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SimCraft — Przerwa techniczna</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{min-height:100vh;display:flex;align-items:center;justify-content:center;
        background:#0e1117;color:#e8e6e3;font-family:'Segoe UI',sans-serif}}
  .card{{background:#1a1d23;border:1px solid #2a2d35;border-radius:16px;
         padding:48px 40px;max-width:480px;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.5)}}
  h1{{font-size:2rem;margin-bottom:12px}}  
  .icon{{font-size:3rem;margin-bottom:16px}}
  p{{color:#9a9a9a;line-height:1.6;margin-bottom:8px}}
  .msg{{color:#e8c57a;font-weight:600;margin-top:16px}}
</style>
</head>
<body>
<div class="card">
  <div class="icon">⚔️</div>
  <h1>Przerwa techniczna</h1>
  <p>Serwis jest tymczasowo niedostępny.<br>Wracamy wkrótce!</p>
  {msg_block}
</div>
</body>
</html>
"""


def _get_maintenance_state() -> tuple[bool, str]:
    """Zwraca (enabled, message) z cache lub bazy (maks. 1 zapytanie co 5s)."""
    now = time.monotonic()
    if now - _MAINTENANCE_CACHE["ts"] < _MAINTENANCE_CACHE_TTL:
        return _MAINTENANCE_CACHE["enabled"], _MAINTENANCE_CACHE["message"]
    enabled = get_config("maintenance.enabled") in ("true", "1")
    message = get_config("maintenance.message") or ""
    _MAINTENANCE_CACHE.update({"ts": now, "enabled": enabled, "message": message})
    return enabled, message


class MaintenanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Przepuszczamy admin, auth, healthcheck i publiczne API
        if path.startswith(("/admin", "/auth", "/api/maintenance", "/api/appearance", "/api/config/public")):
            return await call_next(request)

        if any(path.startswith(p) for p in _MAINTENANCE_BLOCKED_PREFIXES):
            try:
                enabled, message = _get_maintenance_state()
            except Exception:
                return await call_next(request)

            if enabled:
                accept = request.headers.get("accept", "")
                is_api = "application/json" in accept or path.startswith("/api/")

                if is_api:
                    return JSONResponse(
                        status_code=503,
                        content={
                            "detail": message or "Serwis jest tymczasowo niedostępny.",
                            "maintenance": True,
                        },
                    )

                msg_block = f'<p class="msg">{message}</p>' if message else ""
                html = _MAINTENANCE_HTML.format(msg_block=msg_block)
                return HTMLResponse(content=html, status_code=503)

        return await call_next(request)


app.add_middleware(MaintenanceMiddleware)


# ---------- Reszta aplikacji ----------

FRONTEND_DIR = "/app/frontend"
RESULT_PANEL_PATH = os.path.join(FRONTEND_DIR, "result-panel.html")


def _render_with_panel(page_path: str, og_meta: str = "") -> HTMLResponse:
    with open(page_path, "r", encoding="utf-8") as f:
        page = f.read()
    with open(RESULT_PANEL_PATH, "r", encoding="utf-8") as f:
        panel = f.read()
    html = page.replace("<!-- RESULT_PANEL -->", panel)
    html = html.replace("<!-- OG_META_PLACEHOLDER -->", og_meta)
    return HTMLResponse(content=html)


def _build_og_meta(job_id: str) -> str:
    try:
        from database import SessionLocal, HistoryEntryModel, get_result_data

        entry = None
        with SessionLocal() as db:
            entry = db.query(HistoryEntryModel).filter(
                HistoryEntryModel.job_id == job_id
            ).first()

        if not entry:
            return ""

        data = get_result_data(job_id)
        dps_str = ""
        if data and data.get("dps"):
            dps_val = data["dps"]
            if dps_val >= 1_000_000:
                dps_str = f"{dps_val/1_000_000:.2f}M DPS"
            elif dps_val >= 1_000:
                dps_str = f"{dps_val/1_000:.1f}k DPS"
            else:
                dps_str = f"{int(dps_val)} DPS"

        name  = entry.character_name or "Unknown"
        spec  = entry.character_spec  or ""
        cls   = entry.character_class or ""
        style = entry.fight_style     or "Patchwerk"
        realm = entry.character_realm_slug or ""

        parts = [p for p in [spec, cls] if p]
        char_str = name
        if parts:
            char_str += " · " + " ".join(parts)
        if realm:
            char_str += f" ({realm})"

        title = f"⚔️ {dps_str} — {char_str}" if dps_str else f"⚔️ {char_str}"
        desc  = f"{char_str} • {style} • SimCraft"
        url   = f"https://simcraft.app/result/{job_id}"

        def esc(s: str) -> str:
            return s.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')

        return "\n".join([
            f'<meta property="og:title"       content="{esc(title)}"/>',
            f'<meta property="og:description" content="{esc(desc)}"/>',
            f'<meta property="og:url"         content="{esc(url)}"/>',
            f'<meta property="og:type"        content="website"/>',
            f'<meta property="og:site_name"   content="SimCraft"/>',
            f'<meta name="twitter:card"       content="summary"/>',
            f'<meta name="twitter:title"      content="{esc(title)}"/>',
            f'<meta name="twitter:description" content="{esc(desc)}"/>',
            f'<title>{esc(title)}</title>',
        ])
    except Exception:
        return ""


app.include_router(admin.router)
app.include_router(admin_docs.router)
app.include_router(auth.router)
app.include_router(simulation.router)
app.include_router(results.router)
app.include_router(history.router)
app.include_router(rankings.router)
app.include_router(reactions.router)
app.include_router(characters.router)
app.include_router(profiles.router)
app.include_router(favorites.router)
app.include_router(icons.router)
app.include_router(talents.router)
app.include_router(system_message.router)
app.include_router(gdpr.router)
app.include_router(vault.router)


# --- Publiczny endpoint wyglądu ---
@app.get("/api/appearance")
async def public_appearance():
    return admin.load_appearance_config()


# --- Publiczny endpoint maintenance ---
@app.get("/api/maintenance")
async def public_maintenance():
    enabled = get_config("maintenance.enabled") in ("true", "1")
    message = get_config("maintenance.message") or ""
    return {"enabled": enabled, "message": message}


# --- Publiczny endpoint konfiguracji (flagi UI dla frontendu) ---
@app.get("/api/config/public")
async def public_config():
    """Zwraca publiczne flagi konfiguracyjne odczytywane przez frontend."""
    def _bool(key: str, default: bool) -> bool:
        raw = get_config(f"app.{key}")
        if raw is None:
            return default
        return str(raw).lower() in ("true", "1", "yes")

    def _int(key: str, default: int) -> int:
        raw = get_config(f"app.{key}")
        if raw is None:
            return default
        try:
            return int(raw)
        except (ValueError, TypeError):
            return default

    return {
        "one_button_mode_enabled": _bool("one_button_mode_enabled", False),
        "public_history_limit":    _int("public_history_limit",    20),
        "user_history_limit":      _int("user_history_limit",      20),
    }


# --- Strony HTML (MPA) ---
@app.get("/rankings")
async def page_rankings():
    return FileResponse(os.path.join(FRONTEND_DIR, "rankings.html"))

@app.get("/result/{job_id}")
async def page_result(job_id: str):
    og_meta = _build_og_meta(job_id)
    return _render_with_panel(os.path.join(FRONTEND_DIR, "result.html"), og_meta)

@app.get("/u/{bnet_id}")
async def page_user_profile(bnet_id: str):
    return FileResponse(os.path.join(FRONTEND_DIR, "profile.html"))

@app.get("/u/{bnet_id}/character/{realm}/{name}")
async def page_character(bnet_id: str, realm: str, name: str):
    return FileResponse(os.path.join(FRONTEND_DIR, "character.html"))

@app.get("/sim")
async def page_sim():
    return _render_with_panel(os.path.join(FRONTEND_DIR, "sim.html"))

@app.get("/profil")
async def page_profil():
    return FileResponse(os.path.join(FRONTEND_DIR, "profil-page.html"))

@app.get("/info")
async def page_info():
    return FileResponse(os.path.join(FRONTEND_DIR, "info.html"))

@app.get("/vault")
async def page_vault():
    return FileResponse(os.path.join(FRONTEND_DIR, "vault.html"))

# --- SPA fallback (musi byc ostatni) ---
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
