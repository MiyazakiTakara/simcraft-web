import os
import json
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from database import (
    SessionLocal,
    get_bnet_id_by_session,
    HistoryEntryModel,
    ReactionModel,
    SessionModel,
    SimResultModel,
    UserModel,
)
from favorites import FavoriteModel

router = APIRouter()

# Rate limit: max 1 eksport / 24h per użytkownik
_EXPORT_COOLDOWN = 24 * 3600
_export_timestamps: dict[str, float] = {}

RESULTS_DIR = os.environ.get("RESULTS_DIR", "/app/results")


# ---------------------------------------------------------------------------
# GET /api/user/export
# ---------------------------------------------------------------------------

@router.get("/api/user/export")
async def export_user_data(session: str):
    bnet_id = get_bnet_id_by_session(session)
    if not bnet_id:
        raise HTTPException(401, "Sesja wygasła lub nie istnieje.")

    now = time.time()
    last = _export_timestamps.get(bnet_id, 0)
    remaining = _EXPORT_COOLDOWN - (now - last)
    if remaining > 0:
        minutes = int(remaining // 60) + 1
        raise HTTPException(
            429,
            f"Eksport możliwy raz na 24h. Spróbuj za {minutes} minut.",
        )

    with SessionLocal() as db:
        user = db.query(UserModel).filter(UserModel.bnet_id == bnet_id).first()

        history_rows = (
            db.query(HistoryEntryModel)
            .filter(HistoryEntryModel.user_id == bnet_id)
            .order_by(HistoryEntryModel.created_at.desc())
            .all()
        )

        reaction_rows = (
            db.query(ReactionModel)
            .filter(ReactionModel.user_key == bnet_id)
            .all()
        )

        favorite_rows = (
            db.query(FavoriteModel)
            .filter(FavoriteModel.bnet_id == bnet_id)
            .all()
        )

    export = {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "processing_info": (
            "SimCraft przechowuje dane na podstawie uzasadnionego interesu "
            "w celu świadczenia usługi symulacji DPS (RODO Art. 6 ust. 1 lit. f). "
            "Dane nie są przekazywane podmiotom trzecim."
        ),
        "account": {
            "bnet_id": bnet_id,
            "main_character_name": user.main_character_name if user else None,
            "main_character_realm": user.main_character_realm if user else None,
            "profile_private": bool(user.profile_private) if user else False,
            "registered_at": user.created_at.isoformat() if user and user.created_at else None,
        },
        "simulations": [
            {
                "job_id": h.job_id,
                "character_name": h.character_name,
                "character_class": h.character_class,
                "character_spec": h.character_spec,
                "realm": h.character_realm_slug,
                "dps": h.dps,
                "fight_style": h.fight_style,
                "is_private": bool(h.is_private),
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in history_rows
        ],
        "reactions": [
            {
                "job_id": r.job_id,
                "emoji": r.emoji,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reaction_rows
        ],
        "followed_profiles": [
            {
                "target_bnet_id": f.target_bnet_id,
                "added_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in favorite_rows
        ],
    }

    _export_timestamps[bnet_id] = now

    return JSONResponse(
        content=export,
        headers={
            "Content-Disposition": 'attachment; filename="simcraft-data-export.json"',
        },
    )


# ---------------------------------------------------------------------------
# DELETE /api/user/account
# ---------------------------------------------------------------------------

class DeleteAccountRequest(BaseModel):
    confirmation: str  # musi być dokładnie "USUŃ KONTO"


@router.delete("/api/user/account")
async def delete_account(body: DeleteAccountRequest, session: str):
    if body.confirmation != "USUŃ KONTO":
        raise HTTPException(400, "Nieprawidłowe potwierdzenie.")

    bnet_id = get_bnet_id_by_session(session)
    if not bnet_id:
        raise HTTPException(401, "Sesja wygasła lub nie istnieje.")

    with SessionLocal() as db:
        # Zbierz job_id żeby później usunąć pliki z dysku
        job_ids = [
            row.job_id
            for row in db.query(HistoryEntryModel.job_id)
            .filter(HistoryEntryModel.user_id == bnet_id)
            .all()
        ]

        # Usuń dane z tabel
        db.query(ReactionModel).filter(ReactionModel.user_key == bnet_id).delete()
        db.query(FavoriteModel).filter(
            (FavoriteModel.bnet_id == bnet_id) |
            (FavoriteModel.target_bnet_id == bnet_id)
        ).delete(synchronize_session="fetch")
        db.query(HistoryEntryModel).filter(HistoryEntryModel.user_id == bnet_id).delete()

        # Usuń wyniki symulacji powiązane z historią użytkownika
        if job_ids:
            db.query(SimResultModel).filter(
                SimResultModel.job_id.in_(job_ids)
            ).delete(synchronize_session="fetch")

        db.query(UserModel).filter(UserModel.bnet_id == bnet_id).delete()

        # Unieważnij wszystkie sesje użytkownika
        db.query(SessionModel).filter(SessionModel.bnet_id == bnet_id).delete()

        db.commit()

    # Usuń pliki wyników z dysku
    deleted_files = 0
    for job_id in job_ids:
        path = os.path.join(RESULTS_DIR, f"{job_id}.json")
        try:
            os.remove(path)
            deleted_files += 1
        except FileNotFoundError:
            pass
        except Exception as e:
            # Nie przerywaj — loguj i kontynuuj
            print(f"[gdpr] delete file error {path}: {e}")

    # TODO: usunięcie konta z Keycloak gdy będzie skonfigurowany service account
    # DELETE /admin/realms/{realm}/users/{userId}

    # Wyczyść rate-limit cache dla tego użytkownika
    _export_timestamps.pop(bnet_id, None)

    return {"ok": True, "deleted_simulations": len(job_ids), "deleted_files": deleted_files}
