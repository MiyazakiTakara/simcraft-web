from fastapi import APIRouter, HTTPException
from sqlalchemy import Column, String, DateTime, UniqueConstraint, Integer, func
from datetime import datetime

from database import (
    Base, engine, SessionLocal,
    UserModel, get_bnet_id_by_session,
    HistoryEntryModel,
)

router = APIRouter()


class FavoriteModel(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("bnet_id", "target_bnet_id", name="uq_favorite"),)

    id             = Column(Integer, primary_key=True, autoincrement=True)
    bnet_id        = Column(String(64), nullable=False, index=True)
    target_bnet_id = Column(String(64), nullable=False, index=True)
    created_at     = Column(DateTime, default=datetime.utcnow)


def ensure_table():
    FavoriteModel.__table__.create(bind=engine, checkfirst=True)


@router.post("/api/favorites/{target_bnet_id}")
def add_favorite(target_bnet_id: str, session: str):
    bnet_id = get_bnet_id_by_session(session)
    if not bnet_id:
        raise HTTPException(401, "Session expired or not found.")
    if bnet_id == target_bnet_id:
        raise HTTPException(400, "You cannot follow yourself.")
    ensure_table()
    with SessionLocal() as db:
        exists = db.query(FavoriteModel).filter(
            FavoriteModel.bnet_id == bnet_id,
            FavoriteModel.target_bnet_id == target_bnet_id,
        ).first()
        if not exists:
            db.add(FavoriteModel(bnet_id=bnet_id, target_bnet_id=target_bnet_id))
            db.commit()
    return {"ok": True}


@router.delete("/api/favorites/{target_bnet_id}")
def remove_favorite(target_bnet_id: str, session: str):
    bnet_id = get_bnet_id_by_session(session)
    if not bnet_id:
        raise HTTPException(401, "Session expired or not found.")
    ensure_table()
    with SessionLocal() as db:
        db.query(FavoriteModel).filter(
            FavoriteModel.bnet_id == bnet_id,
            FavoriteModel.target_bnet_id == target_bnet_id,
        ).delete()
        db.commit()
    return {"ok": True}


@router.get("/api/favorites")
def get_favorites(session: str):
    """Returns list of followed profiles with stats."""
    bnet_id = get_bnet_id_by_session(session)
    if not bnet_id:
        raise HTTPException(401, "Session expired or not found.")
    ensure_table()
    with SessionLocal() as db:
        rows = db.query(FavoriteModel).filter(
            FavoriteModel.bnet_id == bnet_id,
        ).order_by(FavoriteModel.created_at.desc()).all()

        result = []
        for row in rows:
            user = db.query(UserModel).filter(UserModel.bnet_id == row.target_bnet_id).first()
            if not user or user.profile_private:
                continue

            followers_count = db.query(func.count(FavoriteModel.id)).filter(
                FavoriteModel.target_bnet_id == row.target_bnet_id
            ).scalar() or 0

            # HistoryEntryModel używa user_id (= bnet_id) i nie ma kolumny status
            sim_stats = db.query(
                func.max(HistoryEntryModel.dps).label("best_dps"),
                func.count(HistoryEntryModel.id).label("sim_count"),
            ).filter(
                HistoryEntryModel.user_id == row.target_bnet_id,
                HistoryEntryModel.is_guest == False,  # noqa: E712
            ).first()

            result.append({
                "bnet_id":         row.target_bnet_id,
                "name":            user.main_character_name,
                "realm":           user.main_character_realm,
                "added_at":        row.created_at.isoformat() if row.created_at else None,
                "favorites_count": followers_count,
                "best_dps":        float(sim_stats.best_dps) if sim_stats and sim_stats.best_dps else None,
                "sim_count":       sim_stats.sim_count if sim_stats else 0,
            })

    return {"favorites": result}


@router.get("/api/favorites/count/{target_bnet_id}")
def get_favorites_count(target_bnet_id: str):
    """Public follower count for a given profile."""
    ensure_table()
    with SessionLocal() as db:
        count = db.query(func.count(FavoriteModel.id)).filter(
            FavoriteModel.target_bnet_id == target_bnet_id
        ).scalar() or 0
    return {"count": count}


@router.get("/api/favorites/check/{target_bnet_id}")
def check_favorite(target_bnet_id: str, session: str):
    """Checks if the logged-in user follows a given profile."""
    bnet_id = get_bnet_id_by_session(session)
    if not bnet_id:
        return {"is_favorite": False}
    ensure_table()
    with SessionLocal() as db:
        exists = db.query(FavoriteModel).filter(
            FavoriteModel.bnet_id == bnet_id,
            FavoriteModel.target_bnet_id == target_bnet_id,
        ).first()
    return {"is_favorite": bool(exists)}
