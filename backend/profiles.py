from fastapi import APIRouter, HTTPException
from database import SessionLocal, UserModel, HistoryEntryModel

router = APIRouter()


@router.get("/api/profile/{bnet_id}")
def get_public_profile(bnet_id: str):
    """
    Publiczny profil użytkownika po bnet_id (zapisywanym przy pierwszym logowaniu).
    Zwraca dane profilu + historię symulacji.
    """
    with SessionLocal() as db:
        user = db.query(UserModel).filter(UserModel.bnet_id == bnet_id).first()

        if not user:
            raise HTTPException(404, "Profil nie istnieje lub jest prywatny.")

        if user.profile_private:
            raise HTTPException(404, "Profil nie istnieje lub jest prywatny.")

        rows = db.query(HistoryEntryModel).filter(
            HistoryEntryModel.user_id == user.bnet_id,
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

        return {
            "bnet_id":   user.bnet_id,
            "name":      user.main_character_name,
            "realm":     user.main_character_realm,
            "history":   history,
            "best_dps":  best,
            "sim_count": len(history),
        }
