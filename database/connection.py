"""Database Connection - Postgres only (no SQLite fallback)."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
import logging
from config.settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()

db_url = settings.DATABASE_URL
engine_kwargs = {"echo": settings.DEBUG, "pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}

try:
    engine = create_engine(db_url, **engine_kwargs)
    # Simple connectivity check at startup
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
except OperationalError as e:
    logger.error(f"Database connection failed for URL {db_url}: {e}")
    raise
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def init_db():
    try:
        from database.base import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        raise

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

