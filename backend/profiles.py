from fastapi import APIRouter, HTTPException
from database import SessionLocal, UserModel, HistoryEntryModel, SessionModel, get_result_data, get_result_talents
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


def _unique_characters(history: list) -> list:
    """Zwraca listę unikalnych postaci z historii, posortowanych po best DPS."""
    chars = {}
    for h in history:
        key = (h["character_name"], h["character_realm"])
        if key not in chars or h["dps"] > chars[key]["best_dps"]:
            chars[key] = {
                "name":       h["character_name"],
                "realm":      h["character_realm"],
                "class":      h["character_class"],
                "spec":       h["character_spec"],
                "best_dps":   h["dps"],
                "sim_count":  sum(1 for x in history if x["character_name"] == h["character_name"] and x["character_realm"] == h["character_realm"]),
                "last_sim":   h["created_at"],
            }
    return sorted(chars.values(), key=lambda c: c["best_dps"], reverse=True)


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
                "characters":      [],
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
                "job_id":           r.job_id,
                "character_name":   r.character_name,
                "character_class":  r.character_class or "",
                "character_spec":   r.character_spec  or "",
                "character_realm":  r.character_realm_slug or "",
                "dps":              float(r.dps) if r.dps else 0.0,
                "fight_style":      r.fight_style or "",
                "created_at":       r.created_at.isoformat() if r.created_at else None,
                "one_button_mode":  bool(r.one_button_mode),
            }
            for r in rows
        ]

        best = max((r["dps"] for r in history), default=0.0)
        favorites_count = _get_favorites_count(db, bnet_id)
        characters = _unique_characters(history)

        return {
            "bnet_id":         user.bnet_id,
            "name":            user.main_character_name,
            "realm":           user.main_character_realm,
            "history":         history,
            "characters":      characters,
            "best_dps":        best,
            "sim_count":       len(history),
            "favorites_count": favorites_count,
        }


@router.get("/api/character/{realm}/{name}")
def get_character_page(realm: str, name: str, bnet_id: str = None):
    """Dane dla strony mini armory postaci.
    Zwraca historię symulacji, staty i ekwipunek z ostatniej symulacji.
    bnet_id opcjonalne — jeśli podane, filtruje po właścicielu.
    """
    with SessionLocal() as db:
        query = db.query(HistoryEntryModel).filter(
            HistoryEntryModel.character_name.ilike(name),
            HistoryEntryModel.character_realm_slug.ilike(realm),
            HistoryEntryModel.is_private == False,
        )
        if bnet_id:
            query = query.filter(HistoryEntryModel.user_id == bnet_id)

        rows = query.order_by(HistoryEntryModel.created_at.desc()).limit(100).all()

        if not rows:
            raise HTTPException(404, "Brak danych dla tej postaci.")

        history = [
            {
                "job_id":           r.job_id,
                "character_name":   r.character_name,
                "character_class":  r.character_class or "",
                "character_spec":   r.character_spec  or "",
                "character_realm":  r.character_realm_slug or "",
                "dps":              float(r.dps) if r.dps else 0.0,
                "fight_style":      r.fight_style or "",
                "created_at":       r.created_at.isoformat() if r.created_at else None,
                "user_id":          r.user_id or "",
                "one_button_mode":  bool(r.one_button_mode),
            }
            for r in rows
        ]

        # Pobierz dane z ostatniej symulacji (staty, ekwipunek, talenty)
        latest_job_id = rows[0].job_id
        result_data   = get_result_data(latest_job_id)
        talents       = get_result_talents(latest_job_id)

        stats    = None
        items    = None
        avg_ilvl = None

        if result_data:
            stats    = result_data.get("stats")
            items    = result_data.get("items")
            avg_ilvl = result_data.get("avg_item_level") or result_data.get("item_level")

        best_dps = max(h["dps"] for h in history)

        return {
            "name":       rows[0].character_name,
            "realm":      rows[0].character_realm_slug or "",
            "class":      rows[0].character_class or "",
            "spec":       rows[0].character_spec  or "",
            "avg_ilvl":   avg_ilvl,
            "best_dps":   best_dps,
            "sim_count":  len(history),
            "history":    history,
            "stats":      stats,
            "items":      items,
            "talents":    talents,
            "latest_job": latest_job_id,
        }
