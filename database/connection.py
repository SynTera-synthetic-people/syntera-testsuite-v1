"""Database Connection - Postgres only (no SQLite fallback).

Test Lab table/column additions: follow `docs/TEST_LAB_DATABASE_SCHEMA.md` and add
idempotent ALTERs in `init_db` below (Base.metadata.create_all does not alter existing tables).
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging
from config.settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()

db_url = settings.DATABASE_URL
engine_kwargs = {"echo": settings.DEBUG, "pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}

# No import-time connect: scripts and tests can import without a live DB; first real use validates.
engine = create_engine(db_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def init_db():
    try:
        from database.base import Base
        import backend.models.survey  # noqa: F401 — register tables on Base.metadata

        Base.metadata.create_all(bind=engine)
        # create_all does not add new columns to existing tables
        _mre_alters = [
            "ALTER TABLE market_research_extractions ADD COLUMN IF NOT EXISTS result_data JSONB",
        ]
        _profile_alters = [
            "ALTER TABLE test_lab_profiles ADD COLUMN IF NOT EXISTS geography VARCHAR(512)",
            "ALTER TABLE test_lab_profiles ADD COLUMN IF NOT EXISTS industry VARCHAR(120)",
            "ALTER TABLE test_lab_profiles ADD COLUMN IF NOT EXISTS scenario VARCHAR(120)",
            "ALTER TABLE test_lab_profiles ADD COLUMN IF NOT EXISTS human_study JSONB",
            "ALTER TABLE test_lab_profiles ADD COLUMN IF NOT EXISTS synthetic_study JSONB",
            "ALTER TABLE test_lab_profiles ADD COLUMN IF NOT EXISTS verdict JSONB",
            'ALTER TABLE test_lab_profiles ADD COLUMN IF NOT EXISTS "metadata" JSONB',
        ]
        _lead_alters = [
            'ALTER TABLE test_lab_leads ADD COLUMN IF NOT EXISTS "metadata" JSONB',
        ]
        _report_creates = [
            """
            CREATE TABLE IF NOT EXISTS test_lab_reports (
              id VARCHAR PRIMARY KEY,
              survey_id VARCHAR NOT NULL UNIQUE,
              report JSONB NOT NULL,
              created_at TIMESTAMPTZ DEFAULT now(),
              updated_at TIMESTAMPTZ DEFAULT now()
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_test_lab_reports_survey_id ON test_lab_reports (survey_id)",
        ]
        _verdict_creates = [
            """
            CREATE TABLE IF NOT EXISTS test_lab_verdict (
              survey_id VARCHAR PRIMARY KEY,
              verdict JSONB NULL
            )
            """,
            """
            INSERT INTO test_lab_verdict (survey_id, verdict)
            SELECT survey_id, verdict
            FROM test_lab_profiles
            WHERE survey_id IS NOT NULL
            ON CONFLICT (survey_id) DO UPDATE
            SET verdict = EXCLUDED.verdict
            """,
        ]
        _survey_alters = [
            "ALTER TABLE test_lab_surveys ADD COLUMN IF NOT EXISTS avg_similarity DOUBLE PRECISION",
            "ALTER TABLE test_lab_surveys ADD COLUMN IF NOT EXISTS actions_data_points INTEGER",
            "ALTER TABLE test_lab_surveys ADD COLUMN IF NOT EXISTS neuroscience_data_points INTEGER",
            "ALTER TABLE test_lab_surveys ADD COLUMN IF NOT EXISTS contextual_layer_data_points INTEGER",
            "ALTER TABLE test_lab_surveys ADD COLUMN IF NOT EXISTS directional_alignment DOUBLE PRECISION",
            "ALTER TABLE test_lab_surveys ADD COLUMN IF NOT EXISTS avg_prediction_accuracy DOUBLE PRECISION",
            "ALTER TABLE test_lab_surveys ADD COLUMN IF NOT EXISTS avg_relationship_strength DOUBLE PRECISION",
            "ALTER TABLE test_lab_surveys ADD COLUMN IF NOT EXISTS checks_passed INTEGER",
        ]
        try:
            with engine.begin() as conn:
                for stmt in _report_creates:
                    conn.execute(text(stmt))
                for stmt in _verdict_creates:
                    conn.execute(text(stmt))
                for stmt in _profile_alters:
                    conn.execute(text(stmt))
                for stmt in _lead_alters:
                    conn.execute(text(stmt))
                for stmt in _mre_alters:
                    conn.execute(text(stmt))
                for stmt in _survey_alters:
                    conn.execute(text(stmt))
        except Exception as col_err:
            logger.warning("Schema ensure (ALTER columns): %s", col_err)
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

