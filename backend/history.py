import json
import os
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import SessionLocal, HistoryEntryModel, detect_role_from_result

router = APIRouter()

RESULTS_DIR = os.environ.get("RESULTS_DIR", "/results")


class HistoryEntry(BaseModel):
    job_id: str
    character_name: Optional[str] = "Unknown"
    character_class: Optional[str] = ""
    character_spec: Optional[str] = ""
    character_realm_slug: Optional[str] = ""
    dps: Optional[float] = 0.0
    hps: Optional[float] = 0.0
    dtps: Optional[float] = 0.0
    role: Optional[str] = None  # None = auto-detect z pliku JSON
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
        "hps":                  e.hps,
        "dtps":                 e.dtps,
        "role":                 e.role,
        "fight_style":          e.fight_style,
        "user_id":              e.user_id,
        "created_at":           e.created_at,
    }


@router.get("/api/history")
async def get_history(page: int = 1, limit: int = 50):
    """Publiczna historia — ostatnie wpisy wszystkich użytkowników."""
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
        "items": [_entry_to_dict(r) for r in rows],
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": (total + limit - 1) // limit
    }


@router.get("/api/history/mine")
async def get_my_history(session: str, page: int = 1, limit: int = 20):
    """Historia zalogowanego użytkownika — filtrowana po session_id."""
    if not session:
        raise HTTPException(400, "Brak session")
    offset = (page - 1) * limit
    with SessionLocal() as db:
        query = db.query(HistoryEntryModel).filter(HistoryEntryModel.user_id == session)
        rows = (
            query
            .order_by(HistoryEntryModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        total = query.count()
    return {
        "items": [_entry_to_dict(r) for r in rows],
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": (total + limit - 1) // limit
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
    with SessionLocal() as db:
        exists = db.query(HistoryEntryModel).filter(HistoryEntryModel.job_id == entry.job_id).first()
        if not exists:
            role = entry.role
            hps  = entry.hps or 0.0
            dtps = entry.dtps or 0.0

            if role is None:
                # POPRAWIONA sciezka: wyniki sa w {RESULTS_DIR}/{job_id}/output.json
                result_path = os.path.join(RESULTS_DIR, entry.job_id, "output.json")
                try:
                    with open(result_path) as f:
                        raw_simc = json.load(f)
                    # Wyciagnij hps/dtps z SimC JSON (collected_data gracza)
                    players = raw_simc.get("sim", {}).get("players", [])
                    if players:
                        cd = players[0].get("collected_data", {})
                        hps_data  = cd.get("hps") or cd.get("hpse") or {}
                        dtps_data = cd.get("dtps") or {}
                        tmi_data  = cd.get("tmi") or {}
                        hps  = float(hps_data.get("mean",  0) if isinstance(hps_data,  dict) else hps_data)
                        dtps = float(dtps_data.get("mean", 0) if isinstance(dtps_data, dict) else dtps_data)
                        tmi  = float(tmi_data.get("mean",  0) if isinstance(tmi_data,  dict) else tmi_data)
                        # Auto-detect roli
                        if hps > 100:
                            role = "healer"
                        elif dtps > 0 or tmi > 0:
                            role = "tank"
                        else:
                            role = "dps"
                    else:
                        role = "dps"
                except Exception:
                    role = "dps"

            row = HistoryEntryModel(
                job_id               = entry.job_id,
                character_name       = entry.character_name,
                character_class      = entry.character_class,
                character_spec       = entry.character_spec,
                character_realm_slug = entry.character_realm_slug or "",
                dps                  = entry.dps,
                hps                  = round(hps, 1),
                dtps                 = round(dtps, 1),
                role                 = role,
                fight_style          = entry.fight_style,
                user_id              = entry.user_id,
                created_at           = int(time.time()),
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
    """Pobiera dane do wykresu DPS/HPS/DTPS w czasie dla konkretnej postaci."""
    if not session:
        raise HTTPException(400, "Brak session")

    with SessionLocal() as db:
        rows = (
            db.query(HistoryEntryModel)
            .filter(
                HistoryEntryModel.user_id == session,
                HistoryEntryModel.character_name == character_name,
                HistoryEntryModel.character_realm_slug == character_realm_slug,
                HistoryEntryModel.fight_style == fight_style,
            )
            .order_by(HistoryEntryModel.created_at.asc())
            .limit(limit)
            .all()
        )

    return {
        "character_name": character_name,
        "character_realm_slug": character_realm_slug,
        "fight_style": fight_style,
        "points": [
            {
                "timestamp": r.created_at,
                "dps":  r.dps,
                "hps":  r.hps,
                "dtps": r.dtps,
                "role": r.role,
                "job_id": r.job_id,
            }
            for r in rows
        ]
    }
