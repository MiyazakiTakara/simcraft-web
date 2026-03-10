import os
from sqlalchemy import create_engine, Column, String, Float, Integer, Text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://simcraft:simcraft@db:5432/simcraft"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class HistoryEntryModel(Base):
    __tablename__ = "history"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    job_id         = Column(String(64), unique=True, nullable=False, index=True)
    character_name = Column(String(128), default="Unknown")
    character_class= Column(String(64), default="")
    character_spec = Column(String(64), default="")
    character_realm_slug = Column(String(128), default="")
    dps            = Column(Float, default=0.0)
    fight_style    = Column(String(64), default="Patchwerk")
    user_id        = Column(String(64), nullable=True, index=True)  # session_id lub None (guest)
    created_at     = Column(Integer, default=0)  # unix timestamp


class SessionModel(Base):
    __tablename__ = "sessions"

    session_id   = Column(String(64), primary_key=True)
    access_token = Column(Text, nullable=False)
    expires_at   = Column(Float, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)
