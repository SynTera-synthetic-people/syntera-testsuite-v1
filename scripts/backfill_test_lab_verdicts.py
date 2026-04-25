"""
Backfill dedicated test_lab_verdict table from existing TestLabProfile.verdict values.

Usage:
  set DATABASE_URL=postgresql://...
  python scripts/backfill_test_lab_verdicts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.models.survey import TestLabProfile, TestLabVerdict  # noqa: E402
from backend.utils.json_helpers import sanitize_for_json  # noqa: E402
from database.connection import SessionLocal  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        profiles = db.query(TestLabProfile).all()
        created = 0
        updated = 0
        for p in profiles:
            if not p.survey_id:
                continue
            verdict_payload = sanitize_for_json(p.verdict) if p.verdict is not None else None
            row = db.query(TestLabVerdict).filter(TestLabVerdict.survey_id == p.survey_id).first()
            if row is None:
                db.add(TestLabVerdict(survey_id=p.survey_id, verdict=verdict_payload))
                created += 1
            else:
                row.verdict = verdict_payload
                updated += 1
        db.commit()
        print(f"OK profiles={len(profiles)} verdict_rows_created={created} verdict_rows_updated={updated}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

