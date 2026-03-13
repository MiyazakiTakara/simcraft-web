from fastapi import APIRouter, HTTPException
from database import SessionLocal, UserModel, SessionModel, get_bnet_id_by_session
from sqlalchemy import Column, String, DateTime, UniqueConstraint, Integer, func
from sqlalchemy.orm import declarative_base
from database import Base, engine, init_db
import time
from datetime import datetime

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
        raise HTTPException(401, "Sesja wygasła lub nie istnieje.")
    if bnet_id == target_bnet_id:
        raise HTTPException(400, "Nie możesz dodać siebie do ulubionych.")
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
        raise HTTPException(401, "Sesja wygasła lub nie istnieje.")
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
    """Zwraca listę ulubionych profili zalogowanego usera."""
    bnet_id = get_bnet_id_by_session(session)
    if not bnet_id:
        raise HTTPException(401, "Sesja wygasła lub nie istnieje.")
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
            count = db.query(func.count(FavoriteModel.id)).filter(
                FavoriteModel.target_bnet_id == row.target_bnet_id
            ).scalar() or 0
            result.append({
                "bnet_id":    row.target_bnet_id,
                "name":       user.main_character_name,
                "realm":      user.main_character_realm,
                "added_at":   row.created_at.isoformat() if row.created_at else None,
                "favorites_count": count,
            })

    return {"favorites": result}


@router.get("/api/favorites/count/{target_bnet_id}")
def get_favorites_count(target_bnet_id: str):
    """Publiczny licznik ulubionych dla danego profilu."""
    ensure_table()
    with SessionLocal() as db:
        count = db.query(func.count(FavoriteModel.id)).filter(
            FavoriteModel.target_bnet_id == target_bnet_id
        ).scalar() or 0
    return {"count": count}


@router.get("/api/favorites/check/{target_bnet_id}")
def check_favorite(target_bnet_id: str, session: str):
    """Sprawdza czy zalogowany user ma ten profil w ulubionych."""
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
