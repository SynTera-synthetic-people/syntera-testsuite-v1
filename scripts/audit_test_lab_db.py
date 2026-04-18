"""
Audit Test Lab tables in the connected Postgres database.

Expected layout: docs/TEST_LAB_DATABASE_SCHEMA.md

Usage (PowerShell):
  $env:DATABASE_URL="postgresql://..."; python scripts/audit_test_lab_db.py
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text


def _require_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"Missing required env var: {name}")
    return v


def main() -> None:
    url = _require_env("DATABASE_URL")
    engine = create_engine(url)

    with engine.connect() as c:
        for table in ("test_lab_profiles", "test_lab_leads", "test_lab_reports"):
            cols = c.execute(
                text(
                    """
                    select column_name, data_type, is_nullable
                    from information_schema.columns
                    where table_schema='public' and table_name=:t
                    order by ordinal_position
                    """
                ),
                {"t": table},
            ).fetchall()
            print(f"{table} columns: {len(cols)}")
            for column_name, data_type, is_nullable in cols:
                print(f" - {column_name} {data_type} nullable={is_nullable}")

        stats = c.execute(
            text(
                """
                select
                  count(*) as profiles,
                  sum(case when geography is null or btrim(geography)='' then 1 else 0 end) as geo_missing,
                  sum(case when industry is null or btrim(industry)='' then 1 else 0 end) as industry_missing,
                  sum(case when scenario is null or btrim(scenario)='' then 1 else 0 end) as scenario_missing,
                  sum(case when human_study is null then 1 else 0 end) as human_missing,
                  sum(case when synthetic_study is null then 1 else 0 end) as synth_missing,
                  sum(case when verdict is null then 1 else 0 end) as verdict_missing
                from test_lab_profiles
                """
            )
        ).mappings().one()
        print("profile null stats:", dict(stats))

        missing_keys = c.execute(
            text(
                """
                select
                  sum(case when human_study->>'survey_name' is null or human_study->>'survey_name'='' then 1 else 0 end) as human_survey_name_missing,
                  sum(case when human_study->>'target_audience' is null or human_study->>'target_audience'='' then 1 else 0 end) as human_target_missing,
                  sum(case when human_study->>'geography' is null or human_study->>'geography'='' then 1 else 0 end) as human_geo_missing,
                  sum(case when human_study->>'sample_size' is null or human_study->>'sample_size'='' then 1 else 0 end) as human_sample_missing,
                  sum(case when human_study->>'total_questions' is null or human_study->>'total_questions'='' then 1 else 0 end) as human_questions_missing,
                  sum(case when human_study->'economics' is null then 1 else 0 end) as human_econ_missing,
                  sum(case when synthetic_study->>'sample_size' is null or synthetic_study->>'sample_size'='' then 1 else 0 end) as synth_sample_missing,
                  sum(case when synthetic_study->'economics' is null then 1 else 0 end) as synth_econ_missing
                from test_lab_profiles
                """
            )
        ).mappings().one()
        print("profile json key missing stats:", dict(missing_keys))


if __name__ == "__main__":
    main()

