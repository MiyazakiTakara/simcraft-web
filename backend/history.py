import os
import json
import time
import threading

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

RESULTS_DIR = os.environ.get("RESULTS_DIR", "/app/results")
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
    dps: Optional[float] = 0.0
    fight_style: Optional[str] = "Patchwerk"


@router.get("/api/history")
async def get_history():
    with _lock:
        data = _load()
    return sorted(data, key=lambda x: x.get("created_at", 0), reverse=True)[:50]


@router.post("/api/history")
async def add_history(entry: HistoryEntry):
    with _lock:
        data = _load()
        if not any(e["job_id"] == entry.job_id for e in data):
            data.append({
                "job_id":           entry.job_id,
                "character_name":   entry.character_name,
                "character_class":  entry.character_class,
                "character_spec":   entry.character_spec,
                "dps":              entry.dps,
                "fight_style":      entry.fight_style,
                "created_at":       int(time.time()),
            })
            data = sorted(data, key=lambda x: x.get("created_at", 0), reverse=True)[:200]
            _save(data)
    return {"ok": True}
