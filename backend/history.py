import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import SessionLocal, HistoryEntryModel

router = APIRouter()


class HistoryEntry(BaseModel):
    job_id: str
    character_name: Optional[str] = "Unknown"
    character_class: Optional[str] = ""
    character_spec: Optional[str] = ""
    character_realm_slug: Optional[str] = ""
    dps: Optional[float] = 0.0
    fight_style: Optional[str] = "Patchwerk"
    user_id: Optional[str] = None


def _entry_to_dict(e: HistoryEntryModel) -> dict:
    return {
        "job_id":               e.job_id,
        "character_name":       e.character_name,
        "character_class":      e.character_class,
        "character_spec":       e.character_spec,
        "character_realm_slug": e.character_realm_slug,
        "dps":                  e.dps,
        "fight_style":          e.fight_style,
        "user_id":              e.user_id,
        "created_at":           e.created_at,
    }


@router.get("/api/history")
async def get_history():
    """Publiczna historia — ostatnie 50 wpisow wszystkich uzytkownikow."""
    with SessionLocal() as db:
        rows = (
            db.query(HistoryEntryModel)
            .order_by(HistoryEntryModel.created_at.desc())
            .limit(50)
            .all()
        )
    return [_entry_to_dict(r) for r in rows]


@router.get("/api/history/mine")
async def get_my_history(session: str):
    """Historia zalogowanego uzytkownika — filtrowana po session_id."""
    if not session:
        raise HTTPException(400, "Brak session")
    with SessionLocal() as db:
        rows = (
            db.query(HistoryEntryModel)
            .filter(HistoryEntryModel.user_id == session)
            .order_by(HistoryEntryModel.created_at.desc())
            .limit(200)
            .all()
        )
    return [_entry_to_dict(r) for r in rows]


@router.get("/api/result/{job_id}/meta")
async def get_result_meta(job_id: str):
    """Zwraca metadane symulacji."""
    with SessionLocal() as db:
        entry = db.query(HistoryEntryModel).filter(HistoryEntryModel.job_id == job_id).first()
    if not entry:
        raise HTTPException(404, "Result meta not found")
    return _entry_to_dict(entry)


@router.post("/api/history")
async def add_history(entry: HistoryEntry):
    with SessionLocal() as db:
        exists = db.query(HistoryEntryModel).filter(HistoryEntryModel.job_id == entry.job_id).first()
        if not exists:
            row = HistoryEntryModel(
                job_id               = entry.job_id,
                character_name       = entry.character_name,
                character_class      = entry.character_class,
                character_spec       = entry.character_spec,
                character_realm_slug = entry.character_realm_slug or "",
                dps                  = entry.dps,
                fight_style          = entry.fight_style,
                user_id              = entry.user_id,
                created_at           = int(time.time()),
            )
            db.add(row)
            db.commit()
    return {"ok": True}
