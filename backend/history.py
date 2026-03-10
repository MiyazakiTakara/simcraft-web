import os
import json
import time
import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

RESULTS_DIR  = os.environ.get("RESULTS_DIR", "/app/results")
HISTORY_FILE = os.path.join(RESULTS_DIR, "history.json")
_lock = threading.Lock()


def _load() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _save(data: list):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f)


class HistoryEntry(BaseModel):
    job_id: str
    character_name: Optional[str] = "Unknown"
    character_class: Optional[str] = ""
    character_spec: Optional[str] = ""
    character_realm_slug: Optional[str] = ""
    dps: Optional[float] = 0.0
    fight_style: Optional[str] = "Patchwerk"
    user_id: Optional[str] = None  # session_id z Battle.net OAuth (None = guest)


@router.get("/api/history")
async def get_history():
    """Publiczna historia — ostatnie 50 wpisow wszystkich uzytkownikow."""
    with _lock:
        data = _load()
    return sorted(data, key=lambda x: x.get("created_at", 0), reverse=True)[:50]


@router.get("/api/history/mine")
async def get_my_history(session: str):
    """Historia zalogowanego uzytkownika — filtrowana po session_id."""
    if not session:
        raise HTTPException(400, "Brak session")
    with _lock:
        data = _load()
    mine = [e for e in data if e.get("user_id") == session]
    return sorted(mine, key=lambda x: x.get("created_at", 0), reverse=True)[:200]


@router.get("/api/result/{job_id}/meta")
async def get_result_meta(job_id: str):
    """Publiczny endpoint – zwraca metadane symulacji (bez auth)."""
    with _lock:
        data = _load()
    entry = next((e for e in data if e.get("job_id") == job_id), None)
    if not entry:
        raise HTTPException(404, "Result meta not found")
    return {
        "job_id":               entry.get("job_id"),
        "character_name":       entry.get("character_name"),
        "character_class":      entry.get("character_class"),
        "character_spec":       entry.get("character_spec"),
        "character_realm_slug": entry.get("character_realm_slug", ""),
        "dps":                  entry.get("dps"),
        "fight_style":          entry.get("fight_style"),
        "created_at":           entry.get("created_at"),
    }


@router.post("/api/history")
async def add_history(entry: HistoryEntry):
    with _lock:
        data = _load()
        if not any(e["job_id"] == entry.job_id for e in data):
            data.append({
                "job_id":               entry.job_id,
                "character_name":       entry.character_name,
                "character_class":      entry.character_class,
                "character_spec":       entry.character_spec,
                "character_realm_slug": entry.character_realm_slug or "",
                "dps":                  entry.dps,
                "fight_style":          entry.fight_style,
                "user_id":              entry.user_id,  # None dla guestow
                "created_at":           int(time.time()),
            })
            data = sorted(data, key=lambda x: x.get("created_at", 0), reverse=True)[:500]
            _save(data)
    return {"ok": True}
