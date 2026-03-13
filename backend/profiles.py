from fastapi import APIRouter, HTTPException
from database import SessionLocal, UserModel, HistoryEntryModel, SessionModel
from sqlalchemy import func
import time

router = APIRouter()


def _get_favorites_count(db, bnet_id: str) -> int:
    try:
        from favorites import FavoriteModel
        return db.query(func.count(FavoriteModel.id)).filter(
            FavoriteModel.target_bnet_id == bnet_id
        ).scalar() or 0
    except Exception:
        return 0


@router.get("/api/profile/{bnet_id}")
def get_public_profile(bnet_id: str):
    with SessionLocal() as db:
        user = db.query(UserModel).filter(UserModel.bnet_id == bnet_id).first()

        if not user:
            session_exists = db.query(SessionModel).filter(
                SessionModel.bnet_id == bnet_id,
                SessionModel.expires_at > time.time(),
            ).first()
            if not session_exists:
                raise HTTPException(404, "Profil nie istnieje lub jest prywatny.")
            return {
                "bnet_id":         bnet_id,
                "name":            None,
                "realm":           None,
                "history":         [],
                "best_dps":        0.0,
                "sim_count":       0,
                "favorites_count": 0,
            }

        if user.profile_private:
            raise HTTPException(404, "Profil nie istnieje lub jest prywatny.")

        rows = db.query(HistoryEntryModel).filter(
            HistoryEntryModel.user_id == bnet_id,
            HistoryEntryModel.is_private == False,
        ).order_by(HistoryEntryModel.created_at.desc()).limit(50).all()

        history = [
            {
                "job_id":          r.job_id,
                "character_name":  r.character_name,
                "character_class": r.character_class or "",
                "character_spec":  r.character_spec  or "",
                "character_realm": r.character_realm_slug or "",
                "dps":             float(r.dps) if r.dps else 0.0,
                "fight_style":     r.fight_style or "",
                "created_at":      r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

        best = max((r["dps"] for r in history), default=0.0)
        favorites_count = _get_favorites_count(db, bnet_id)

        return {
            "bnet_id":         user.bnet_id,
            "name":            user.main_character_name,
            "realm":           user.main_character_realm,
            "history":         history,
            "best_dps":        best,
            "sim_count":       len(history),
            "favorites_count": favorites_count,
        }
