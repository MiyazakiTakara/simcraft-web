import os
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import SessionLocal, HistoryEntryModel, JobModel, get_bnet_id_by_session

router = APIRouter()

RESULTS_DIR = os.environ.get("RESULTS_DIR", "/app/results")


class HistoryEntry(BaseModel):
    job_id: str
    character_name: Optional[str] = "Unknown"
    character_class: Optional[str] = ""
    character_spec: Optional[str] = ""
    character_realm_slug: Optional[str] = ""
    dps: Optional[float] = 0.0
    fight_style: Optional[str] = "Patchwerk"
    user_id: Optional[str] = None  # session_id z frontendu; zamieniany na bnet_id w backendzie


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
        "created_at":           e.created_at.isoformat() if e.created_at else None,
    }


@router.get("/api/history")
async def get_history(page: int = 1, limit: int = 50):
    """Publiczna historia — ostatnie wpisy wszystkich uzytkownikow."""
    offset = (page - 1) * limit
    with SessionLocal() as db:
        rows = (
            db.query(HistoryEntryModel)
            .order_by(HistoryEntryModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        total = db.query(HistoryEntryModel).count()
    return {
        "items":       [_entry_to_dict(r) for r in rows],
        "page":        page,
        "limit":       limit,
        "total":       total,
        "total_pages": (total + limit - 1) // limit,
    }


@router.get("/api/history/mine")
async def get_my_history(session: str, page: int = 1, limit: int = 20):
    """Historia zalogowanego uzytkownika — filtrowana po bnet_id."""
    if not session:
        raise HTTPException(400, "Brak session")
    bnet_id = get_bnet_id_by_session(session)
    if not bnet_id:
        # fallback: stare wpisy zapisane pod session_id (przed migracją)
        user_filter = session
    else:
        user_filter = bnet_id
    offset = (page - 1) * limit
    with SessionLocal() as db:
        query = db.query(HistoryEntryModel).filter(HistoryEntryModel.user_id == user_filter)
        rows  = (
            query
            .order_by(HistoryEntryModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        total = query.count()
    return {
        "items":       [_entry_to_dict(r) for r in rows],
        "page":        page,
        "limit":       limit,
        "total":       total,
        "total_pages": (total + limit - 1) // limit,
    }


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
    # Zamien session_id na bnet_id jesli mozliwe
    resolved_user_id = entry.user_id
    if entry.user_id:
        bnet_id = get_bnet_id_by_session(entry.user_id)
        if bnet_id:
            resolved_user_id = bnet_id

    with SessionLocal() as db:
        job_exists = db.query(JobModel).filter(JobModel.job_id == entry.job_id).first()
        if not job_exists:
            raise HTTPException(404, "Job not found — cannot add to history")

        exists = db.query(HistoryEntryModel).filter(HistoryEntryModel.job_id == entry.job_id).first()
        if not exists:
            row = HistoryEntryModel(
                job_id               = entry.job_id,
                character_name       = entry.character_name,
                character_class      = entry.character_class,
                character_spec       = entry.character_spec,
                character_realm_slug = entry.character_realm_slug or "",
                dps                  = entry.dps,
                role                 = "dps",
                fight_style          = entry.fight_style,
                user_id              = resolved_user_id,
            )
            db.add(row)
            db.commit()
    return {"ok": True}


@router.get("/api/history/trend")
async def get_character_trend(
    session: str,
    character_name: str,
    character_realm_slug: str,
    fight_style: str = "Patchwerk",
    limit: int = 50
):
    """Pobiera dane do wykresu DPS w czasie dla konkretnej postaci."""
    if not session:
        raise HTTPException(400, "Brak session")

    bnet_id = get_bnet_id_by_session(session)
    user_filter = bnet_id if bnet_id else session

    with SessionLocal() as db:
        rows = (
            db.query(HistoryEntryModel)
            .filter(
                HistoryEntryModel.user_id == user_filter,
                HistoryEntryModel.character_name == character_name,
                HistoryEntryModel.character_realm_slug == character_realm_slug,
                HistoryEntryModel.fight_style == fight_style,
            )
            .order_by(HistoryEntryModel.created_at.asc())
            .limit(limit)
            .all()
        )

    return {
        "character_name":       character_name,
        "character_realm_slug": character_realm_slug,
        "fight_style":          fight_style,
        "points": [
            {
                "timestamp": r.created_at.isoformat() if r.created_at else None,
                "dps":       r.dps,
                "job_id":    r.job_id,
            }
            for r in rows
        ],
    }
