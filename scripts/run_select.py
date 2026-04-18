"""
Run a SELECT query against the configured Postgres DATABASE_URL and print rows.

PowerShell:
  $env:DATABASE_URL="postgresql://synth_user:...@.../synthdb?sslmode=require"
  python scripts/run_select.py "select now();"

Notes:
- This is intentionally read-only: it rejects non-SELECT queries.
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text


def _require_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"Missing required env var: {name}")
    return v


def _is_select(sql: str) -> bool:
    s = (sql or "").lstrip().lower()
    return s.startswith("select") or s.startswith("with")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/run_select.py \"select ...\"")
    sql = sys.argv[1]
    if not _is_select(sql):
        raise SystemExit("Only SELECT/WITH queries are allowed.")

    url = _require_env("DATABASE_URL")
    engine = create_engine(url)

    with engine.connect() as c:
        rows = c.execute(text(sql)).mappings().all()
        print(f"rows={len(rows)}")
        for r in rows:
            print(dict(r))


if __name__ == "__main__":
    main()

