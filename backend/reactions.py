from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import SessionLocal, ReactionModel, HistoryEntryModel, get_bnet_id_by_session

router = APIRouter()

VALID_EMOJIS = {"fire", "strong", "sad", "skull", "rofl"}
EMOJI_MAP    = {"fire": "🔥", "strong": "💪", "sad": "😢", "skull": "💀", "rofl": "🤣"}


def _counts(job_id: str) -> dict:
    with SessionLocal() as db:
        rows = db.query(ReactionModel).filter(ReactionModel.job_id == job_id).all()
    counts = {k: 0 for k in VALID_EMOJIS}
    for r in rows:
        if r.emoji in counts:
            counts[r.emoji] += 1
    return counts


@router.get("/api/reactions/{job_id}")
async def get_reactions(job_id: str, session: Optional[str] = None):
    """Zwraca liczniki reakcji + aktualną reakcję zalogowanego usera."""
    counts = _counts(job_id)
    my_reaction = None
    if session:
        bnet_id = get_bnet_id_by_session(session)
        if bnet_id:
            with SessionLocal() as db:
                row = db.query(ReactionModel).filter(
                    ReactionModel.job_id  == job_id,
                    ReactionModel.user_key == bnet_id,
                ).first()
            my_reaction = row.emoji if row else None
    return {"counts": counts, "my_reaction": my_reaction, "emoji_map": EMOJI_MAP}


class ReactionPayload(BaseModel):
    session: str
    emoji: str  # klucz: fire | strong | sad | skull | rofl


@router.post("/api/reactions/{job_id}")
async def set_reaction(job_id: str, payload: ReactionPayload):
    """Ustaw/zmień/usuń reakcję. Tylko zalogowani użytkownicy."""
    if payload.emoji not in VALID_EMOJIS:
        raise HTTPException(400, f"Nieprawidłowe emoji. Dozwolone: {', '.join(VALID_EMOJIS)}")

    bnet_id = get_bnet_id_by_session(payload.session)
    if not bnet_id:
        raise HTTPException(401, "Musisz być zalogowany, aby reagować")

    # Sprawdź czy wynik istnieje
    with SessionLocal() as db:
        exists = db.query(HistoryEntryModel).filter(HistoryEntryModel.job_id == job_id).first()
    if not exists:
        raise HTTPException(404, "Wynik nie istnieje")

    with SessionLocal() as db:
        existing = db.query(ReactionModel).filter(
            ReactionModel.job_id   == job_id,
            ReactionModel.user_key == bnet_id,
        ).first()

        if existing:
            if existing.emoji == payload.emoji:
                # Toggle off — usuń reakcję
                db.delete(existing)
                db.commit()
                return {"ok": True, "action": "removed", "my_reaction": None, "counts": _counts(job_id)}
            else:
                # Zmiana reakcji
                existing.emoji = payload.emoji
                db.commit()
                return {"ok": True, "action": "changed", "my_reaction": payload.emoji, "counts": _counts(job_id)}
        else:
            # Nowa reakcja
            row = ReactionModel(job_id=job_id, user_key=bnet_id, emoji=payload.emoji)
            db.add(row)
            db.commit()
            return {"ok": True, "action": "added", "my_reaction": payload.emoji, "counts": _counts(job_id)}
