"""One-time migration of surveys/validation runs from local SQLite to shared Postgres.

Usage (local dev):
1. Start your SSH tunnel in one terminal and keep it open:

   ssh -i /c/Users/Poornachand/Downloads/SynTera/jaga.pem -L 5435:10.10.28.45:5432 ubuntu@15.207.222.237

2. From the project root (where this file lives), run:

   python migrate_to_postgres.py

This will copy all rows from the SQLite tables `test_lab_surveys` and
`test_lab_validation_runs` into the Postgres database `synthdb` via the tunnel.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.survey import Survey, ValidationRun
from backend.utils.json_helpers import sanitize_for_json
from database.connection import _SQLITE_URL


# Target Postgres URL for local (via SSH tunnel on localhost:5435)
PG_URL = "postgresql://synth_user:synth_pass@localhost:5435/synthdb?sslmode=require"


def migrate_table(model):
    """Copy all rows from a SQLite-backed model table into Postgres."""
    sqlite_engine = create_engine(_SQLITE_URL)
    pg_engine = create_engine(PG_URL)

    SQLiteSession = sessionmaker(bind=sqlite_engine)
    PGSession = sessionmaker(bind=pg_engine)

    # Ensure target table exists in Postgres
    model.__table__.create(pg_engine, checkfirst=True)

    src = SQLiteSession()
    dst = PGSession()
    try:
        rows = src.query(model).all()
        print(f"Migrating {len(rows)} rows from {model.__tablename__}...")

        for row in rows:
            # For Survey rows, sanitize JSON to be Postgres-compatible (no NaN/inf)
            if isinstance(row, Survey):
                row.synthetic_personas = sanitize_for_json(row.synthetic_personas)
                row.survey_questions = sanitize_for_json(row.survey_questions)
                row.synthetic_responses = sanitize_for_json(row.synthetic_responses)
                row.real_responses = sanitize_for_json(row.real_responses)
                row.test_suite_report = sanitize_for_json(row.test_suite_report)

            # Detach from SQLite session and merge into Postgres session
            src.expunge(row)
            dst.merge(row)

        dst.commit()
        print(f"Done: {model.__tablename__}")
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    migrate_table(Survey)
    migrate_table(ValidationRun)


