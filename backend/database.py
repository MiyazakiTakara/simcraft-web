import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, Integer, Text, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://simcraft:simcraft@db:5432/simcraft"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class JobModel(Base):
    __tablename__ = "jobs"

    job_id       = Column(String(64), primary_key=True)
    status       = Column(String(16), nullable=False, default="running")
    json_path    = Column(String(256))
    error        = Column(Text)
    started_at   = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


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
    user_id        = Column(String(64), nullable=True, index=True)
    created_at     = Column(Integer, default=0)


class SessionModel(Base):
    __tablename__ = "sessions"

    session_id   = Column(String(64), primary_key=True)
    access_token = Column(Text, nullable=False)
    expires_at   = Column(Float, nullable=False)


class AdminSessionModel(Base):
    __tablename__ = "admin_sessions"

    session_id = Column(String(64), primary_key=True)
    username   = Column(String(128), nullable=False)
    expires_at = Column(Float, nullable=False)


class NewsModel(Base):
    __tablename__ = "news"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    title      = Column(String(256), nullable=False)
    body       = Column(Text, nullable=False)
    published  = Column(Boolean, default=True)
    created_at = Column(Integer, default=0)


def init_db():
    Base.metadata.create_all(bind=engine)


def create_job(job_id: str, json_path: str):
    with SessionLocal() as db:
        job = JobModel(job_id=job_id, status="running", json_path=json_path)
        db.add(job)
        db.commit()


def update_job_status(job_id: str, status: str, error: str = None):
    with SessionLocal() as db:
        job = db.query(JobModel).filter(JobModel.job_id == job_id).first()
        if job:
            job.status = status
            job.error = error
            if status in ("done", "error"):
                job.completed_at = datetime.utcnow()
            db.commit()


def get_job(job_id: str):
    with SessionLocal() as db:
        return db.query(JobModel).filter(JobModel.job_id == job_id).first()
