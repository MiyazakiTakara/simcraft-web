import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, Integer, Text, Boolean, DateTime, text
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

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    job_id               = Column(String(64), unique=True, nullable=False, index=True)
    character_name       = Column(String(128), default="Unknown")
    character_class      = Column(String(64), default="")
    character_spec       = Column(String(64), default="")
    character_realm_slug = Column(String(128), default="")
    dps                  = Column(Float, default=0.0)
    role                 = Column(String(16), default="dps")
    fight_style          = Column(String(64), default="Patchwerk")
    user_id              = Column(String(64), nullable=True, index=True)
    created_at           = Column(DateTime, default=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)


class LogEntryModel(Base):
    __tablename__ = "admin_logs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    level      = Column(String(8), nullable=False)
    message    = Column(Text, nullable=False)
    context    = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        try:
            db.execute(text("ALTER TABLE history ADD COLUMN IF NOT EXISTS role VARCHAR(16) DEFAULT 'dps'"))
            db.execute(text("""
                DO $$ BEGIN
                    IF (SELECT data_type FROM information_schema.columns
                        WHERE table_name='history' AND column_name='created_at') = 'integer' THEN
                        ALTER TABLE history
                            ALTER COLUMN created_at TYPE TIMESTAMP
                            USING to_timestamp(created_at);
                    END IF;
                END $$;
            """))
            db.execute(text("""
                DO $$ BEGIN
                    IF (SELECT data_type FROM information_schema.columns
                        WHERE table_name='news' AND column_name='created_at') = 'integer' THEN
                        ALTER TABLE news
                            ALTER COLUMN created_at TYPE TIMESTAMP
                            USING to_timestamp(created_at);
                    END IF;
                END $$;
            """))
            db.commit()
        except Exception:
            db.rollback()


def create_job(job_id: str, json_path: str):
    with SessionLocal() as db:
        existing = db.query(JobModel).filter(JobModel.job_id == job_id).first()
        if existing:
            return
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


def get_job(job_id: str) -> dict | None:
    with SessionLocal() as db:
        job = db.query(JobModel).filter(JobModel.job_id == job_id).first()
        if not job:
            return None
        return {
            "job_id":       job.job_id,
            "status":       job.status,
            "json_path":    job.json_path,
            "error":        job.error,
            "started_at":   job.started_at,
            "completed_at": job.completed_at,
        }


def add_log(level: str, message: str, context: str = None):
    with SessionLocal() as db:
        entry = LogEntryModel(level=level, message=message, context=context)
        db.add(entry)
        db.commit()


def get_logs(limit: int = 100, level: str = None):
    with SessionLocal() as db:
        query = db.query(LogEntryModel).order_by(LogEntryModel.created_at.desc())
        if level:
            query = query.filter(LogEntryModel.level == level.upper())
        return query.limit(limit).all()
