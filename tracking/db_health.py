"""Database health over time: one snapshot of Supabase, written to Supabase.

mike, 2026-11-15: "I want to add a section on database health, size and any
other metrics you think are cool and change over time. both locals and
supabase". The ops dashboard's Database tab reads what this writes.

WHAT ONE RUN WRITES (tables: data/migrations/db_health_snapshots_2026_11_15.sql)
  * db_health_snapshots, one row: the database's size, the sum of every
    table's size split into table, index and toast bytes, Postgres's row
    estimates, client connections, the oldest open transaction, and
    Postgres's own running counters exactly as it reports them.
  * Every six hours (the first run with no table snapshot in the last 5.5
    hours): db_table_snapshots, one row per table, and db_query_snapshots,
    the statements that have used the most database time, with their text
    stored once in db_query_texts.

WHY THE COUNTERS ARE STORED RAW. pg_stat_database and pg_stat_statements
count from their last reset (measured 2026-11-16: 2026-03-30 and 2026-04-04),
so a lifetime ratio such as the 93% cache hit rate barely moves. The change
between two rows is what happened in between, and a counter that went down
was reset; the dashboard leaves that gap blank.

LOAD. Catalog and statistics reads only: no count(*), no table scan.
pg_database_size and pg_total_relation_size read file sizes. Every read runs
with a 30-second statement timeout. The worker job is deferred in the morning
disk window like the other recorders (tracking/morning_disk.py).

NEVER DELETES OR UPDATES A ROW (CLAUDE.md section 1b). A statement's text is
inserted once and kept (ON CONFLICT DO NOTHING).

    python -m tracking.db_health                 # one run, source 'manual'
    python -m tracking.db_health --tables        # force the per-table rows
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone

from loguru import logger

# Statements stored per six-hour run: the most total time, plus the slowest
# per call among those run at least MIN_CALLS times. Measured 2026-11-16: the
# top 100 by total time hold 86% of all statement time recorded since
# 2026-04-04 (1,568,104,216 of 1,818,104,794 ms, 4,985 statements).
TOP_BY_TOTAL = 100
TOP_BY_MEAN = 25
MIN_CALLS = 5
# The longest statement text stored. Measured 2026-11-16: the top 100 average
# 1,878 characters, the longest is 59,142.
MAX_QUERY_CHARS = 8000
TABLE_EVERY = timedelta(hours=5, minutes=30)
STATEMENT_TIMEOUT = "30s"

# Schemas that hold app data. Postgres's own catalogs and temp schemas are
# left out; everything else in the database is in (public, auth, storage,
# realtime, vault, supabase_migrations on 2026-11-16).
_SCHEMA_FILTER = (
    "n.nspname NOT IN ('pg_catalog', 'information_schema') "
    "AND n.nspname !~ '^pg_(toast|temp)'"
)

DB_SQL = f"""
SELECT
  pg_database_size(current_database()) AS db_bytes,
  (SELECT sum(pg_relation_size(c.oid)) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relkind IN ('r', 'm') AND {_SCHEMA_FILTER}) AS table_bytes,
  (SELECT sum(pg_indexes_size(c.oid)) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relkind IN ('r', 'm') AND {_SCHEMA_FILTER}) AS index_bytes,
  (SELECT sum(pg_total_relation_size(c.reltoastrelid)) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relkind IN ('r', 'm') AND c.reltoastrelid <> 0 AND {_SCHEMA_FILTER}) AS toast_bytes,
  (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relkind IN ('r', 'm') AND {_SCHEMA_FILTER}) AS relations,
  (SELECT sum(n_live_tup) FROM pg_stat_user_tables) AS live_rows_est,
  (SELECT sum(n_dead_tup) FROM pg_stat_user_tables) AS dead_rows_est,
  (SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend') AS connections,
  (SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend' AND state = 'active') AS connections_active,
  (SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend' AND state = 'idle') AS connections_idle,
  (SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend'
     AND state IN ('idle in transaction', 'idle in transaction (aborted)')) AS connections_idle_in_tx,
  current_setting('max_connections')::int AS max_connections,
  (SELECT max(extract(epoch FROM now() - xact_start)) FROM pg_stat_activity
     WHERE backend_type = 'client backend' AND xact_start IS NOT NULL AND pid <> pg_backend_pid()) AS longest_xact_s,
  (SELECT count(*) FROM pg_locks WHERE NOT granted) AS waiting_locks,
  (SELECT age(datfrozenxid) FROM pg_database WHERE datname = current_database()) AS xid_age,
  current_setting('autovacuum_freeze_max_age')::bigint AS freeze_max_age,
  d.blks_hit, d.blks_read, d.xact_commit, d.xact_rollback,
  d.tup_inserted, d.tup_updated, d.tup_deleted,
  d.temp_files, d.temp_bytes, d.deadlocks, d.stats_reset,
  (SELECT count(*) FROM pg_stat_user_indexes s JOIN pg_index i ON i.indexrelid = s.indexrelid
     WHERE s.idx_scan = 0 AND NOT i.indisunique AND NOT i.indisprimary) AS unused_indexes,
  (SELECT sum(pg_relation_size(s.indexrelid)) FROM pg_stat_user_indexes s JOIN pg_index i ON i.indexrelid = s.indexrelid
     WHERE s.idx_scan = 0 AND NOT i.indisunique AND NOT i.indisprimary) AS unused_index_bytes
FROM pg_stat_database d
WHERE d.datname = current_database()
"""

DB_COLUMNS = (
    "db_bytes", "table_bytes", "index_bytes", "toast_bytes", "relations",
    "live_rows_est", "dead_rows_est", "connections", "connections_active",
    "connections_idle", "connections_idle_in_tx", "max_connections",
    "longest_xact_s", "waiting_locks", "xid_age", "freeze_max_age",
    "blks_hit", "blks_read", "xact_commit", "xact_rollback",
    "tup_inserted", "tup_updated", "tup_deleted",
    "temp_files", "temp_bytes", "deadlocks", "stats_reset",
    "unused_indexes", "unused_index_bytes",
)

# pg_stat_statements lives in the `extensions` schema on Supabase; an
# unqualified name does not resolve (measured 2026-11-16).
STMT_TOTALS_SQL = """
SELECT count(*), sum(calls), sum(total_exec_time),
       (SELECT stats_reset FROM extensions.pg_stat_statements_info)
FROM extensions.pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
"""

STORAGE_SQL = """
SELECT bucket_id, count(*), COALESCE(sum((metadata->>'size')::bigint), 0)
FROM storage.objects GROUP BY bucket_id ORDER BY bucket_id
"""

TABLES_SQL = f"""
SELECT n.nspname, c.relname,
       CASE c.relkind WHEN 'm' THEN 'matview' ELSE 'table' END,
       pg_total_relation_size(c.oid), pg_relation_size(c.oid), pg_indexes_size(c.oid),
       CASE WHEN c.reltoastrelid <> 0 THEN pg_total_relation_size(c.reltoastrelid) ELSE 0 END,
       s.n_live_tup, s.n_dead_tup, s.n_tup_ins, s.n_tup_upd, s.n_tup_del,
       s.seq_scan, s.idx_scan,
       GREATEST(s.last_vacuum, s.last_autovacuum),
       GREATEST(s.last_analyze, s.last_autoanalyze)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_stat_all_tables s ON s.relid = c.oid
WHERE c.relkind IN ('r', 'm') AND {_SCHEMA_FILTER}
ORDER BY 1, 2
"""

QUERIES_SQL = f"""
WITH s AS (
  SELECT s.queryid, COALESCE(r.rolname, s.userid::text) AS role_name, s.toplevel,
         s.calls, s.total_exec_time, s.mean_exec_time, s.max_exec_time, s.rows,
         s.shared_blks_hit, s.shared_blks_read, s.temp_blks_written, s.query,
         row_number() OVER (ORDER BY s.total_exec_time DESC) AS by_total,
         row_number() OVER (ORDER BY CASE WHEN s.calls >= {MIN_CALLS} THEN s.mean_exec_time END
                            DESC NULLS LAST) AS by_mean
  FROM extensions.pg_stat_statements s
  LEFT JOIN pg_roles r ON r.oid = s.userid
  WHERE s.dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
    AND s.queryid IS NOT NULL
)
SELECT queryid, role_name, toplevel, calls, total_exec_time, mean_exec_time,
       max_exec_time, rows, shared_blks_hit, shared_blks_read, temp_blks_written,
       left(query, {MAX_QUERY_CHARS})
FROM s
WHERE by_total <= {TOP_BY_TOTAL} OR (by_mean <= {TOP_BY_MEAN} AND calls >= {MIN_CALLS})
ORDER BY total_exec_time DESC
"""

_INSERT_DB = (
    "INSERT INTO db_health_snapshots (source, duration_ms, "
    + ", ".join(DB_COLUMNS)
    + ", stmt_count, stmt_calls, stmt_exec_ms, stmt_reset,"
    " storage_objects, storage_bytes, storage_buckets, table_rows_taken) VALUES ("
    + ", ".join(["?"] * (2 + len(DB_COLUMNS) + 4 + 4))
    + ") RETURNING snapshot_id, taken_at"
)

_INSERT_TABLE = (
    "INSERT INTO db_table_snapshots (snapshot_id, taken_at, schema_name, table_name, kind,"
    " total_bytes, heap_bytes, index_bytes, toast_bytes, live_rows_est, dead_rows_est,"
    " n_tup_ins, n_tup_upd, n_tup_del, seq_scan, idx_scan, last_vacuum, last_analyze)"
    " VALUES (" + ", ".join(["?"] * 18) + ")"
)

_INSERT_QUERY = (
    "INSERT INTO db_query_snapshots (snapshot_id, taken_at, queryid, role_name, toplevel,"
    " calls, total_exec_ms, mean_exec_ms, max_exec_ms, rows, shared_blks_hit,"
    " shared_blks_read, temp_blks_written) VALUES (" + ", ".join(["?"] * 13) + ")"
)

_INSERT_TEXT = (
    "INSERT INTO db_query_texts (queryid, query) VALUES (?, ?)"
    " ON CONFLICT (queryid) DO NOTHING"
)


def _tables_due(conn, now: datetime) -> bool:
    """True when no run in the last 5.5 hours wrote the per-table rows."""
    row = conn.execute(
        "SELECT max(taken_at) FROM db_health_snapshots WHERE table_rows_taken"
    ).fetchone()
    last = row[0] if row else None
    return last is None or now - last >= TABLE_EVERY


def _storage(conn) -> tuple[int, int, list[dict]]:
    buckets = [
        {"bucket": b, "objects": int(n), "bytes": int(size)}
        for b, n, size in conn.execute(STORAGE_SQL).fetchall()
    ]
    return (sum(b["objects"] for b in buckets), sum(b["bytes"] for b in buckets), buckets)


def take_snapshot(conn, *, source: str = "worker", tables: bool | None = None,
                  now: datetime | None = None) -> dict:
    """Read the database's own statistics and insert one snapshot.

    `tables=None` writes the per-table and per-statement rows only when they
    are due (every six hours); True or False forces it. Commits once, at the
    end, so a failed read leaves no half-written snapshot.
    """
    if source not in ("worker", "manual"):
        raise ValueError(f"source must be 'worker' or 'manual', not {source!r}")
    started = time.monotonic()
    now = now or datetime.now(timezone.utc)

    conn.execute(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'")
    if tables is None:
        tables = _tables_due(conn, now)

    db_row = conn.execute(DB_SQL).fetchone()
    stmt_count, stmt_calls, stmt_ms, stmt_reset = conn.execute(STMT_TOTALS_SQL).fetchone()
    storage_objects, storage_bytes, buckets = _storage(conn)
    table_rows = conn.execute(TABLES_SQL).fetchall() if tables else []
    query_rows = conn.execute(QUERIES_SQL).fetchall() if tables else []
    duration_ms = int((time.monotonic() - started) * 1000)

    snapshot_id, taken_at = conn.execute(
        _INSERT_DB,
        (source, duration_ms, *db_row, stmt_count, stmt_calls, stmt_ms, stmt_reset,
         storage_objects, storage_bytes, json.dumps(buckets), bool(tables)),
    ).fetchone()

    if table_rows:
        conn.executemany(_INSERT_TABLE, [(snapshot_id, taken_at, *r) for r in table_rows])
    if query_rows:
        conn.executemany(_INSERT_TEXT, [(r[0], r[11]) for r in query_rows])
        conn.executemany(_INSERT_QUERY, [(snapshot_id, taken_at, *r[:11]) for r in query_rows])
    conn.commit()

    summary = {
        "snapshot_id": snapshot_id,
        "taken_at": taken_at.isoformat() if hasattr(taken_at, "isoformat") else str(taken_at),
        "source": source,
        "db_bytes": db_row[0],
        "tables": len(table_rows),
        "statements": len(query_rows),
        "read_ms": duration_ms,
    }
    logger.info(f"db_health snapshot {summary}")
    return summary


def run_db_health_snapshot(source: str = "worker", tables: bool | None = None) -> dict:
    """The worker job: open a connection, take one snapshot, close it."""
    from data.db import get_connection

    with get_connection() as conn:
        return take_snapshot(conn, source=source, tables=tables)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tables", action="store_true",
                    help="write the per-table and per-statement rows even if one was written in the last 5.5 hours")
    ap.add_argument("--source", default="manual", choices=["manual", "worker"])
    args = ap.parse_args(argv)
    summary = run_db_health_snapshot(source=args.source, tables=True if args.tables else None)
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
