import re
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from database import SessionLocal, HistoryEntryModel, get_bnet_id_by_session
from sqlalchemy import text, func

router = APIRouter()

_UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)

EMOJI_MAP = {"fire": "🔥", "strong": "💪", "sad": "😢", "skull": "💀", "rofl": "🤣"}


def _fetch_reactions_for_jobs(db, job_ids: list) -> dict:
    """Zwraca {job_id: {emoji_key: count}} dla listy job_ids. Tylko wpisy z count > 0."""
    if not job_ids:
        return {}
    rows = db.execute(
        text("""
            SELECT job_id, emoji, COUNT(*) AS cnt
            FROM reactions
            WHERE job_id = ANY(:ids)
            GROUP BY job_id, emoji
        """),
        {"ids": job_ids},
    ).fetchall()
    result = {}
    for r in rows:
        result.setdefault(r.job_id, {})[r.emoji] = r.cnt
    return result


class HistorySaveRequest(BaseModel):
    job_id:               str
    character_name:       Optional[str] = "Unknown"
    character_class:      Optional[str] = ""
    character_spec:       Optional[str] = ""
    character_spec_id:    Optional[int] = None
    character_realm_slug: Optional[str] = ""
    dps:                  Optional[float] = 0.0
    hps:                  Optional[float] = 0.0
    dtps:                 Optional[float] = 0.0
    role:                 Optional[str] = "dps"
    fight_style:          Optional[str] = "Patchwerk"
    user_id:              Optional[str] = None
    source:               Optional[str] = "web"
    is_private:           Optional[bool] = False
    wow_build:            Optional[str]  = None
    one_button_mode:      Optional[bool] = False


@router.post("/api/history", status_code=201)
def save_history(body: HistorySaveRequest):
    """Zapisuje wynik symulacji do historii."""
    source = body.source if body.source in ("web", "addon") else "web"

    resolved_user_id = body.user_id
    if resolved_user_id and _UUID_RE.match(resolved_user_id):
        resolved_user_id = get_bnet_id_by_session(resolved_user_id) or None

    wow_build = body.wow_build
    if not wow_build:
        try:
            from admin import get_wow_build_cached
            wow_build = get_wow_build_cached()
        except Exception:
            pass

    with SessionLocal() as db:
        existing = db.query(HistoryEntryModel).filter(
            HistoryEntryModel.job_id == body.job_id
        ).first()
        if existing:
            return {"ok": True, "duplicate": True}

        is_guest = not bool(resolved_user_id)
        entry = HistoryEntryModel(
            job_id               = body.job_id,
            character_name       = (body.character_name or "Unknown").strip() or "Unknown",
            character_class      = body.character_class or "",
            character_spec       = body.character_spec  or "",
            character_spec_id    = body.character_spec_id,
            character_realm_slug = body.character_realm_slug or "",
            dps                  = body.dps or 0.0,
            role                 = body.role or "dps",
            fight_style          = body.fight_style or "Patchwerk",
            user_id              = resolved_user_id,
            is_guest             = is_guest,
            source               = source,
            is_private           = body.is_private or False,
            wow_build            = wow_build,
            one_button_mode      = body.one_button_mode or False,
        )
        db.add(entry)
        db.commit()

    return {"ok": True, "duplicate": False}


@router.get("/api/history")
def get_public_history(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Publiczna historia — wyklucza prywatnych uzytkownikow i symulacje addon export."""
    offset = (page - 1) * limit

    count_sql = text("""
        SELECT COUNT(*)
        FROM history h
        LEFT JOIN users u ON u.bnet_id = h.user_id
        WHERE (u.profile_private IS NULL OR u.profile_private = FALSE OR h.is_guest = TRUE)
        AND COALESCE(h.is_private, FALSE) = FALSE
        AND COALESCE(h.source, 'web') != 'addon'
    """)
    rows_sql = text("""
        SELECT h.job_id, h.character_name, h.character_class, h.character_spec,
               h.character_realm_slug, h.dps, h.fight_style, h.wow_build,
               h.one_button_mode, h.created_at
        FROM history h
        LEFT JOIN users u ON u.bnet_id = h.user_id
        WHERE (u.profile_private IS NULL OR u.profile_private = FALSE OR h.is_guest = TRUE)
        AND COALESCE(h.is_private, FALSE) = FALSE
        AND COALESCE(h.source, 'web') != 'addon'
        ORDER BY h.created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    with SessionLocal() as db:
        total = db.execute(count_sql).scalar()
        rows  = db.execute(rows_sql, {"limit": limit, "offset": offset}).fetchall()
        job_ids = [r.job_id for r in rows]
        reactions_map = _fetch_reactions_for_jobs(db, job_ids)

    return {
        "results": [
            {
                "job_id":           r.job_id,
                "character_name":   r.character_name,
                "character_class":  r.character_class or "",
                "character_spec":   r.character_spec  or "",
                "character_realm":  r.character_realm_slug or "",
                "dps":              float(r.dps) if r.dps else 0.0,
                "fight_style":      r.fight_style or "",
                "wow_build":        r.wow_build or None,
                "one_button_mode":  bool(r.one_button_mode),
                "created_at":       r.created_at.isoformat() if r.created_at else None,
                "reactions":        reactions_map.get(r.job_id, {}),
            }
            for r in rows
        ],
        "total": total,
        "page":  page,
        "pages": max(1, -(-total // limit)),
    }


@router.get("/api/history/mine")
def get_my_history(
    session: str = Query(...),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Historia zalogowanego uzytkownika — zawsze widoczna bez wzgledu na prywatnosc."""
    bnet_id = get_bnet_id_by_session(session)
    if not bnet_id:
        raise HTTPException(401, "Sesja wygasla lub nie istnieje.")

    offset = (page - 1) * limit

    with SessionLocal() as db:
        total = db.query(HistoryEntryModel).filter(
            HistoryEntryModel.user_id == bnet_id
        ).count()
        rows = db.query(HistoryEntryModel).filter(
            HistoryEntryModel.user_id == bnet_id
        ).order_by(HistoryEntryModel.created_at.desc()).offset(offset).limit(limit).all()
        job_ids = [r.job_id for r in rows]
        reactions_map = _fetch_reactions_for_jobs(db, job_ids)

    return {
        "results": [
            {
                "job_id":           r.job_id,
                "character_name":   r.character_name,
                "character_class":  r.character_class or "",
                "character_spec":   r.character_spec  or "",
                "character_realm":  r.character_realm_slug or "",
                "dps":              float(r.dps) if r.dps else 0.0,
                "fight_style":      r.fight_style or "",
                "wow_build":        r.wow_build or None,
                "one_button_mode":  bool(r.one_button_mode),
                "created_at":       r.created_at.isoformat() if r.created_at else None,
                "reactions":        reactions_map.get(r.job_id, {}),
            }
            for r in rows
        ],
        "total": total,
        "page":  page,
        "pages": max(1, -(-total // limit)),
    }


@router.get("/api/history/trend")
def get_dps_trend(
    session: str = Query(...),
    character_name: str = Query(...),
    realm: str = Query(default=""),
    fight_style: str = Query(default="Patchwerk"),
):
    """Trend DPS w czasie dla konkretnej postaci — tylko dla zalogowanego wlasciciela."""
    bnet_id = get_bnet_id_by_session(session)
    if not bnet_id:
        raise HTTPException(401, "Sesja wygasla lub nie istnieje.")

    with SessionLocal() as db:
        rows = db.query(HistoryEntryModel).filter(
            HistoryEntryModel.user_id == bnet_id,
            func.lower(HistoryEntryModel.character_name)  == character_name.lower(),
            func.lower(HistoryEntryModel.fight_style)     == fight_style.lower(),
        ).order_by(HistoryEntryModel.created_at.asc()).limit(50).all()

    return {
        "trend": [
            {
                "job_id":     r.job_id,
                "dps":        float(r.dps) if r.dps else 0.0,
                "wow_build":  r.wow_build or None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }
