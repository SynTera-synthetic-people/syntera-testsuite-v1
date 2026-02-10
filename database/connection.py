"""Database Connection"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import OperationalError
import logging
from config.settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SQLITE_PATH = os.path.join(_PROJECT_ROOT, "syntera.db")
_SQLITE_URL = f"sqlite:///{_SQLITE_PATH}"

def _make_sqlite_engine_kw():
    return {
        "echo": settings.DEBUG,
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }

def _make_pg_engine_kw():
    return {"echo": settings.DEBUG, "pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}

_db_url = settings.DATABASE_URL
_engine_kw = None

if _db_url.startswith("sqlite"):
    _engine_kw = _make_sqlite_engine_kw()
    if _db_url.startswith("sqlite:///./"):
        _db_url = _SQLITE_URL
else:
    # PostgreSQL (or other): try to connect; if unreachable, fall back to SQLite for local dev
    _engine_kw = _make_pg_engine_kw()
    try:
        _probe = create_engine(_db_url, **_engine_kw)
        with _probe.connect() as _conn:
            pass
        _probe.dispose()
    except (OperationalError, OSError) as e:
        logger.warning(
            "PostgreSQL not available (%s). Using SQLite at %s. Set DATABASE_URL=sqlite:///./syntera.db in .env to silence.",
            e,
            _SQLITE_PATH,
        )
        _db_url = _SQLITE_URL
        _engine_kw = _make_sqlite_engine_kw()

engine = create_engine(_db_url, **_engine_kw)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def init_db():
    try:
        from database.base import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized")
        
        # Initialize default users
        from backend.routers.auth import init_default_users
        db = SessionLocal()
        try:
            init_default_users(db)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        raise

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

