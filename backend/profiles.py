from fastapi import APIRouter, HTTPException, Query
from database import SessionLocal, UserModel, HistoryEntryModel
from sqlalchemy import func

router = APIRouter()


@router.get("/api/profile/{realm}/{name}")
def get_public_profile(realm: str, name: str):
    """
    Publiczny profil użytkownika po nazwie głównej postaci i realmie.
    Zwraca dane profilu + historię symulacji tej postaci.
    """
    with SessionLocal() as db:
        user = db.query(UserModel).filter(
            func.lower(UserModel.main_character_name)  == name.lower(),
            func.lower(UserModel.main_character_realm) == realm.lower(),
        ).first()

        if not user:
            raise HTTPException(404, "Profil nie istnieje lub jest prywatny.")

        if user.profile_private:
            raise HTTPException(404, "Profil nie istnieje lub jest prywatny.")

        # Historia symulacji tej postaci (tylko publiczne)
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

        # Najlepszy DPS na postaci
        best = max((r["dps"] for r in history), default=0.0)

        return {
            "name":            user.main_character_name,
            "realm":           user.main_character_realm,
            "history":         history,
            "best_dps":        best,
            "sim_count":       len(history),
        }
