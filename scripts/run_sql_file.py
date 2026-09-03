"""Execute a .sql file as ONE transaction. For migrations run on the worker.

    python -m scripts.run_sql_file data/migrations/fix_scored_pick_outcomes_lateral.sql
    python -m scripts.run_sql_file <file> --dry-run   # parse + print, execute nothing

WHY NOT data.db.executescript. That helper splits on ';' and runs each fragment
in its own savepoint, swallowing "already exists" errors. That is right for
idempotent schema setup and WRONG here: a migration that drops a matview and
rebuilds it must be all-or-nothing, and a half-applied rebuild would leave the
dependent views missing while the app keeps reading them.

WHY NOT psql. The worker image is a Python runtime; psql is not guaranteed to
be on it. psycopg2 sends a multi-statement string in one round trip and wraps
it in a single implicit transaction, which is exactly the semantics wanted.

The file's own BEGIN/COMMIT are stripped: psycopg2 already opens a transaction,
and a nested explicit BEGIN warns. The transaction is committed here only if
every statement succeeded; any exception rolls the whole file back.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

import psycopg2
from loguru import logger


def _strip_outer_tx(sql: str) -> str:
    """Remove a leading BEGIN; and trailing COMMIT; — psycopg2 owns the tx."""
    sql = re.sub(r"^\s*BEGIN\s*;", "", sql, count=1, flags=re.I)
    sql = re.sub(r"COMMIT\s*;\s*$", "", sql, count=1, flags=re.I)
    return sql.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the statement count and exit without executing")
    args = ap.parse_args()

    sql = _strip_outer_tx(open(args.path, encoding="utf-8").read())
    # Rough count for the log line only; ';' inside a literal would skew it, so
    # it is never used to split the SQL — the whole file goes over as one string.
    approx = sql.count(";")
    logger.info(f"{args.path}: {len(sql)} chars, ~{approx} statements")

    if args.dry_run:
        logger.info("DRY RUN — nothing executed.")
        return 0

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL is not set")
        return 2

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)          # no params: '%' in LIKE stays literal
        conn.commit()
        logger.info("Applied and committed.")
        return 0
    except Exception as exc:                                   # noqa: BLE001
        conn.rollback()
        logger.error(f"FAILED, rolled back the whole file: {exc}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
