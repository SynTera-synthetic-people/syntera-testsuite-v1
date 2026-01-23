"""Database Connection"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
from config.settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()

engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_pre_ping=True,
                      pool_size=10, max_overflow=20)
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

