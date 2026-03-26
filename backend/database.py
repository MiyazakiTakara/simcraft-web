import os
import time
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, Integer, Text, Boolean, DateTime, UniqueConstraint, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://simcraft:simcraft@db:5432/simcraft"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

SESSION_SLIDING_TTL = 30 * 24 * 3600  # 30 dni

# Wersja parsera — zbumpuj przy zmianie logiki parse_results()
PARSER_VERSION = "1"


class UserModel(Base):
    __tablename__ = "users"

    bnet_id                = Column(String(64), primary_key=True)
    main_character_name    = Column(String(128), nullable=True)
    main_character_realm   = Column(String(128), nullable=True)
    profile_private        = Column(Boolean, default=False, nullable=False)
    created_at             = Column(DateTime, default=datetime.utcnow)


class JobModel(Base):
    __tablename__ = "jobs"

    job_id       = Column(String(64), primary_key=True)
    status       = Column(String(16), nullable=False, default="running")
    json_path    = Column(String(256))
    error        = Column(Text)
    started_at   = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class SimResultModel(Base):
    """Niezalezna tabela wynikow symulacji.
    Tworzona od razu po zakonczeniu simc, niezaleznie od history.
    history jest zapisywana przez frontend po otrzymaniu status=done.
    """
    __tablename__ = "sim_results"

    job_id         = Column(String(64), primary_key=True)
    result_data    = Column(Text, nullable=False)
    talents        = Column(Text, nullable=True)
    parser_version = Column(String(8), nullable=False)
    created_at     = Column(DateTime, default=datetime.utcnow)


class HistoryEntryModel(Base):
    __tablename__ = "history"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    job_id               = Column(String(64), unique=True, nullable=False, index=True)
    character_name       = Column(String(128), default="Unknown")
    character_class      = Column(String(64), default="")
    character_spec       = Column(String(64), default="")
    character_spec_id    = Column(Integer, nullable=True)
    character_realm_slug = Column(String(128), default="")
    dps                  = Column(Float, default=0.0)
    role                 = Column(String(16), default="dps")
    fight_style          = Column(String(64), default="Patchwerk")
    user_id              = Column(String(64), nullable=True, index=True)
    is_guest             = Column(Boolean, default=False, nullable=False)
    source               = Column(String(16), default="web", nullable=False)
    is_private           = Column(Boolean, default=False, nullable=False, index=True)
    one_button_mode      = Column(Boolean, default=False, nullable=False)
    # Numer buildu WoW Retail w chwili wykonania symulacji, np. "11.1.5.58979"
    wow_build            = Column(String(32), nullable=True)
    created_at           = Column(DateTime, default=datetime.utcnow)


class SimcRebuildLogModel(Base):
    """Log rekompilacji simc — każdy wpis to jedna próba rebuildu."""
    __tablename__ = "simc_rebuild_log"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    triggered_by = Column(String(64), nullable=False)
    status       = Column(String(16), nullable=False)
    wow_build    = Column(String(32), nullable=True)
    simc_before  = Column(String(64), nullable=True)
    simc_after   = Column(String(64), nullable=True)
    log_output   = Column(Text, nullable=True)
    started_at   = Column(DateTime, default=datetime.utcnow)
    finished_at  = Column(DateTime, nullable=True)


class AppConfigModel(Base):
    __tablename__ = "app_config"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    key        = Column(String(128), unique=True, nullable=False, index=True)
    value      = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReactionModel(Base):
    __tablename__ = "reactions"
    __table_args__ = (UniqueConstraint("job_id", "user_key", name="uq_reaction_per_user"),)

    id         = Column(Integer, primary_key=True, autoincrement=True)
    job_id     = Column(String(64), nullable=False, index=True)
    user_key   = Column(String(64), nullable=False)
    emoji      = Column(String(16), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class SessionModel(Base):
    __tablename__ = "sessions"

    session_id             = Column(String(64), primary_key=True)
    access_token           = Column(Text, nullable=False)
    expires_at             = Column(Float, nullable=False)
    bnet_id                = Column(String(64), nullable=True, index=True)
    main_character_name    = Column(String(128), nullable=True)
    main_character_realm   = Column(String(128), nullable=True)
    is_first_login         = Column(Boolean, default=True)


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


class PageVisitModel(Base):
    __tablename__ = "page_visits"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    path       = Column(String(512), nullable=False, index=True)
    ip_hash    = Column(String(64), nullable=True)
    session_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AdminAuditLogModel(Base):
    __tablename__ = "admin_audit_log"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    username   = Column(String(128), nullable=False, index=True)
    action     = Column(String(128), nullable=False, index=True)
    details    = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AdminAlertModel(Base):
    __tablename__ = "admin_alerts"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    alert_type   = Column(String(64),  nullable=False, index=True)
    message      = Column(Text,        nullable=False)
    resolved     = Column(Boolean,     default=False, nullable=False, index=True)
    triggered_at = Column(DateTime,    default=datetime.utcnow, index=True)
    resolved_at  = Column(DateTime,    nullable=True)


# ---------- app_config helpers ----------

_APP_CONFIG_DEFAULTS = {
    "maintenance_enabled":      "false",
    "maintenance_message":      "",
    "max_concurrent_sims":      "3",
    "job_timeout":              "360",
    "guest_sims_enabled":       "true",
    "history_limit_per_user":   "100",
}


def get_config(key: str, default: str = None) -> str | None:
    try:
        with SessionLocal() as db:
            row = db.query(AppConfigModel).filter(AppConfigModel.key == key).first()
            return row.value if row is not None else default
    except Exception:
        return default


def set_config(key: str, value: str) -> bool:
    try:
        with SessionLocal() as db:
            row = db.query(AppConfigModel).filter(AppConfigModel.key == key).first()
            if row:
                row.value      = value
                row.updated_at = datetime.utcnow()
            else:
                db.add(AppConfigModel(key=key, value=value))
            db.commit()
        return True
    except Exception:
        return False


def _seed_app_config():
    with SessionLocal() as db:
        for key, value in _APP_CONFIG_DEFAULTS.items():
            exists = db.query(AppConfigModel).filter(AppConfigModel.key == key).first()
            if not exists:
                db.add(AppConfigModel(key=key, value=value))
        db.commit()


def init_db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        try:
            db.execute(text("ALTER TABLE history ADD COLUMN IF NOT EXISTS role VARCHAR(16) DEFAULT 'dps'"))
            db.execute(text("ALTER TABLE history ADD COLUMN IF NOT EXISTS is_guest BOOLEAN NOT NULL DEFAULT FALSE"))
            db.execute(text("ALTER TABLE history ADD COLUMN IF NOT EXISTS source VARCHAR(16) NOT NULL DEFAULT 'web'"))
            db.execute(text("ALTER TABLE history ADD COLUMN IF NOT EXISTS is_private BOOLEAN NOT NULL DEFAULT FALSE"))
            db.execute(text("ALTER TABLE history ADD COLUMN IF NOT EXISTS character_spec_id INTEGER"))
            db.execute(text("ALTER TABLE history ADD COLUMN IF NOT EXISTS wow_build VARCHAR(32)"))
            db.execute(text("ALTER TABLE history ADD COLUMN IF NOT EXISTS one_button_mode BOOLEAN NOT NULL DEFAULT FALSE"))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_history_is_private ON history(is_private)"))
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
            db.execute(text("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS main_character_name VARCHAR(128)"))
            db.execute(text("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS main_character_realm VARCHAR(128)"))
            db.execute(text("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS is_first_login BOOLEAN DEFAULT TRUE"))
            db.execute(text("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS bnet_id VARCHAR(64)"))
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    bnet_id VARCHAR(64) PRIMARY KEY,
                    main_character_name VARCHAR(128),
                    main_character_realm VARCHAR(128),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_private BOOLEAN NOT NULL DEFAULT FALSE"))
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS admin_audit_log (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(128) NOT NULL,
                    action VARCHAR(128) NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_username ON admin_audit_log(username)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_action ON admin_audit_log(action)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_created_at ON admin_audit_log(created_at)"))
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS admin_alerts (
                    id SERIAL PRIMARY KEY,
                    alert_type VARCHAR(64) NOT NULL,
                    message TEXT NOT NULL,
                    resolved BOOLEAN NOT NULL DEFAULT FALSE,
                    triggered_at TIMESTAMP DEFAULT NOW(),
                    resolved_at TIMESTAMP
                )
            """))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_alerts_type ON admin_alerts(alert_type)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_alerts_resolved ON admin_alerts(resolved)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_alerts_triggered_at ON admin_alerts(triggered_at)"))
            # indeks na created_at w admin_logs dla wydajnego stronicowania
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_admin_logs_created_at ON admin_logs(created_at)"))
            db.commit()
        except Exception:
            db.rollback()
    _seed_app_config()


# ---------- audit log helper (#67) ----------

def log_audit(username: str, action: str, details: str | dict | None = None) -> None:
    if isinstance(details, dict):
        details = json.dumps(details, ensure_ascii=False)
    try:
        with SessionLocal() as db:
            db.add(AdminAuditLogModel(
                username   = username,
                action     = action,
                details    = details,
                created_at = datetime.utcnow(),
            ))
            db.commit()
    except Exception:
        pass


# ---------- alerts helpers (#58) ----------

def trigger_alert(alert_type: str, message: str) -> int | None:
    try:
        with SessionLocal() as db:
            existing = db.query(AdminAlertModel).filter(
                AdminAlertModel.alert_type == alert_type,
                AdminAlertModel.resolved   == False,
            ).first()
            if existing:
                return None
            alert = AdminAlertModel(
                alert_type   = alert_type,
                message      = message,
                triggered_at = datetime.utcnow(),
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)
            add_log(level="WARN", message=f"[alert] {alert_type}: {message}")
            return alert.id
    except Exception:
        return None


def resolve_alert(alert_id: int) -> bool:
    try:
        with SessionLocal() as db:
            alert = db.query(AdminAlertModel).filter(AdminAlertModel.id == alert_id).first()
            if not alert:
                return False
            alert.resolved    = True
            alert.resolved_at = datetime.utcnow()
            db.commit()
        return True
    except Exception:
        return False


def resolve_alert_by_type(alert_type: str) -> None:
    try:
        with SessionLocal() as db:
            db.query(AdminAlertModel).filter(
                AdminAlertModel.alert_type == alert_type,
                AdminAlertModel.resolved   == False,
            ).update({
                "resolved":    True,
                "resolved_at": datetime.utcnow(),
            })
            db.commit()
    except Exception:
        pass


def get_active_alert_count() -> int:
    try:
        with SessionLocal() as db:
            return db.query(AdminAlertModel).filter(
                AdminAlertModel.resolved == False
            ).count()
    except Exception:
        return 0


def get_or_create_user(bnet_id: str) -> dict:
    with SessionLocal() as db:
        user = db.query(UserModel).filter(UserModel.bnet_id == bnet_id).first()
        if not user:
            user = UserModel(bnet_id=bnet_id)
            db.add(user)
            db.commit()
            db.refresh(user)
        return {
            "bnet_id":              user.bnet_id,
            "main_character_name":  user.main_character_name,
            "main_character_realm": user.main_character_realm,
            "profile_private":      bool(user.profile_private),
        }


def get_user_settings(bnet_id: str) -> dict | None:
    with SessionLocal() as db:
        user = db.query(UserModel).filter(UserModel.bnet_id == bnet_id).first()
        if not user:
            return None
        return {
            "main_character_name":  user.main_character_name,
            "main_character_realm": user.main_character_realm,
            "profile_private":      bool(user.profile_private),
        }


def save_user_settings(bnet_id: str, main_character_name: str | None,
                       main_character_realm: str | None, profile_private: bool) -> dict:
    with SessionLocal() as db:
        user = db.query(UserModel).filter(UserModel.bnet_id == bnet_id).first()
        if not user:
            user = UserModel(bnet_id=bnet_id)
            db.add(user)
        if main_character_name is not None:
            user.main_character_name  = main_character_name.strip() or None
            user.main_character_realm = (main_character_realm or "").strip() or None
        user.profile_private = profile_private
        db.commit()
        db.refresh(user)
        if main_character_name is not None:
            sessions = db.query(SessionModel).filter(SessionModel.bnet_id == bnet_id).all()
            for s in sessions:
                s.main_character_name  = user.main_character_name
                s.main_character_realm = user.main_character_realm
            db.commit()
        return {
            "main_character_name":  user.main_character_name,
            "main_character_realm": user.main_character_realm,
            "profile_private":      bool(user.profile_private),
        }


def is_user_private(bnet_id: str) -> bool:
    if not bnet_id:
        return False
    with SessionLocal() as db:
        user = db.query(UserModel).filter(UserModel.bnet_id == bnet_id).first()
        return bool(user and user.profile_private)


def get_bnet_id_by_session(session_id: str) -> str | None:
    with SessionLocal() as db:
        row = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
        if not row or time.time() > row.expires_at:
            return None
        return row.bnet_id


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


def save_result_data(job_id: str, parsed: dict, talents: str | None) -> bool:
    try:
        with SessionLocal() as db:
            existing = db.query(SimResultModel).filter(
                SimResultModel.job_id == job_id
            ).first()
            if existing:
                existing.result_data    = json.dumps(parsed, ensure_ascii=False)
                existing.talents        = talents
                existing.parser_version = PARSER_VERSION
            else:
                db.add(SimResultModel(
                    job_id         = job_id,
                    result_data    = json.dumps(parsed, ensure_ascii=False),
                    talents        = talents,
                    parser_version = PARSER_VERSION,
                ))
            db.commit()
        return True
    except Exception as e:
        import traceback
        print(f"[save_result_data] error: {e}\n{traceback.format_exc()}")
        return False


def get_result_data(job_id: str) -> dict | None:
    try:
        with SessionLocal() as db:
            row = db.query(SimResultModel).filter(
                SimResultModel.job_id == job_id
            ).first()
            if not row:
                return None
            if row.parser_version != PARSER_VERSION:
                return None
            return json.loads(row.result_data)
    except Exception:
        return None


def get_result_talents(job_id: str) -> str | None:
    try:
        with SessionLocal() as db:
            row = db.query(SimResultModel).filter(
                SimResultModel.job_id == job_id
            ).first()
            return row.talents if row else None
    except Exception:
        return None


def get_result_spec_id(job_id: str) -> int | None:
    try:
        with SessionLocal() as db:
            row = db.query(HistoryEntryModel).filter(
                HistoryEntryModel.job_id == job_id
            ).first()
            return row.character_spec_id if row else None
    except Exception:
        return None


def get_session_info(session_id: str) -> dict | None:
    with SessionLocal() as db:
        row = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
        if not row:
            return None
        now = time.time()
        if now > row.expires_at:
            db.query(SessionModel).filter(SessionModel.session_id == session_id).delete()
            db.commit()
            return None
        new_expires = now + SESSION_SLIDING_TTL
        if new_expires > row.expires_at:
            row.expires_at = new_expires
            db.commit()
        return {
            "main_character_name":  row.main_character_name,
            "main_character_realm": row.main_character_realm,
            "is_first_login":       row.is_first_login if row.is_first_login is not None else True,
            "bnet_id":              row.bnet_id,
        }


def set_main_character(session_id: str, name: str, realm: str):
    with SessionLocal() as db:
        row = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
        if row:
            row.main_character_name  = name
            row.main_character_realm = realm
            row.is_first_login       = False
            if row.bnet_id:
                user = db.query(UserModel).filter(UserModel.bnet_id == row.bnet_id).first()
                if user:
                    user.main_character_name  = name
                    user.main_character_realm = realm
            db.commit()


def clear_first_login(session_id: str):
    with SessionLocal() as db:
        row = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
        if row:
            row.is_first_login = False
            db.commit()


def add_log(level: str, message: str, context: str = None):
    with SessionLocal() as db:
        entry = LogEntryModel(level=level, message=message, context=context)
        db.add(entry)
        db.commit()


def get_logs(limit: int = 50, offset: int = 0, level: str = None):
    """Zwraca stronę logów + total count dla paginacji."""
    with SessionLocal() as db:
        q = db.query(LogEntryModel).order_by(LogEntryModel.created_at.desc())
        if level:
            q = q.filter(LogEntryModel.level == level.upper())
        total = q.count()
        rows  = q.offset(offset).limit(limit).all()
        # detach przed zamknięciem sesji
        result = [
            {
                "id":         r.id,
                "level":      r.level,
                "message":    r.message,
                "context":    r.context,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    return {"total": total, "offset": offset, "limit": limit, "items": result}


def delete_logs(older_than_days: int | None = None) -> int:
    """Usuwa logi. Jeśli older_than_days=None — usuwa wszystkie.
    Zwraca liczbę usuniętych wierszy.
    """
    from datetime import timedelta
    with SessionLocal() as db:
        q = db.query(LogEntryModel)
        if older_than_days is not None:
            cutoff = datetime.utcnow() - timedelta(days=older_than_days)
            q = q.filter(LogEntryModel.created_at < cutoff)
        deleted = q.delete(synchronize_session=False)
        db.commit()
    return deleted
