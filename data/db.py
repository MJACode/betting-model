"""
data/db.py — Database connection factory.

Returns a psycopg2-backed connection that is API-compatible with the
sqlite3 connection the rest of the codebase already uses.  Call sites
change only their import and connect call — all SQL, fetch calls, and
commit/rollback patterns stay the same.

Environment variable required:
    DATABASE_URL  — postgres connection string
                    e.g. postgresql://user:pass@host:5432/dbname
                    Supabase format: postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres

Usage:
    from data.db import get_connection

    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM picks WHERE game_date = %s", ("2026-04-04",)).fetchall()
        conn.commit()
    finally:
        conn.close()
"""

import os
import re
import sys
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── SQL dialect adapters ──────────────────────────────────────────────────────

_NAMED_PARAM_RE = re.compile(r":([A-Za-z_]\w*)")


def _adapt_sql(sql: str) -> str | None:
    """
    Convert SQLite-dialect SQL to psycopg2 format.

    Changes:
      - PRAGMA ...          → None (caller skips these)
      - :name params        → %(name)s
      - ? positional params → %s
      - datetime('now')     → NOW()::TEXT
      - INSERT OR IGNORE    → INSERT ... ON CONFLICT DO NOTHING
      - INSERT OR REPLACE   → left as-is (callers handle explicitly)
    """
    stripped = sql.strip()
    if stripped.upper().startswith("PRAGMA"):
        return None  # silently skip

    # datetime('now') SQL function → Postgres equivalent
    stripped = stripped.replace("datetime('now')", "NOW()::TEXT")

    # INSERT OR IGNORE → standard upsert
    stripped = re.sub(
        r"INSERT\s+OR\s+IGNORE\s+INTO",
        "INSERT INTO",
        stripped,
        flags=re.IGNORECASE,
    )

    # Named params first (:name → %(name)s) then positional (? → %s)
    stripped = _NAMED_PARAM_RE.sub(r"%(\1)s", stripped)
    stripped = stripped.replace("?", "%s")

    return stripped


# ── Cursor wrapper ────────────────────────────────────────────────────────────

class _CursorResult:
    """
    Wraps a psycopg2 cursor to mimic sqlite3's cursor return style.
    sqlite3: conn.execute(sql).fetchone()  — returns cursor from execute()
    psycopg2: cursor.execute(sql); cursor.fetchone()  — execute returns None
    This wrapper makes the psycopg2 cursor chainable.
    """

    def __init__(self, cursor: psycopg2.extensions.cursor):
        self._cur = cursor

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def fetchmany(self, size: int = None):
        return self._cur.fetchmany(size) if size else self._cur.fetchmany()

    def __iter__(self):
        return iter(self._cur)


# ── Connection wrapper ────────────────────────────────────────────────────────

class DBConnection:
    """
    Wraps a psycopg2 connection with a sqlite3-compatible execute() interface.

    Differences from bare psycopg2:
    - conn.execute(sql, params) → _CursorResult  (not None)
    - conn.executemany(sql, rows) uses psycopg2.extras.execute_batch for speed
    - conn.executescript(sql) executes multiple ;-separated statements
    - PRAGMA statements are silently skipped
    - ? and :name param styles are auto-converted to %s / %(name)s
    """

    def __init__(self, pg_conn: psycopg2.extensions.connection):
        self._conn = pg_conn

    def execute(self, sql: str, params=None) -> _CursorResult:
        adapted = _adapt_sql(sql)
        cur = self._conn.cursor()
        if adapted is None:
            return _CursorResult(cur)  # PRAGMA — return empty cursor
        if params is not None:
            cur.execute(adapted, params)
        else:
            cur.execute(adapted)
        return _CursorResult(cur)

    def executemany(self, sql: str, params_list) -> None:
        adapted = _adapt_sql(sql)
        if adapted is None or not params_list:
            return
        cur = self._conn.cursor()
        psycopg2.extras.execute_batch(cur, adapted, params_list)
        cur.close()

    def executescript(self, sql: str) -> None:
        """
        Execute multiple semicolon-separated SQL statements.
        Used by db_setup.py to create schema.
        Each statement runs in its own savepoint so one failure
        doesn't abort the whole transaction.
        """
        cur = self._conn.cursor()
        for raw_stmt in sql.split(";"):
            stmt = raw_stmt.strip()
            if not stmt or stmt.startswith("--"):
                continue
            adapted = _adapt_sql(stmt)
            if adapted is None:
                continue
            try:
                cur.execute(adapted)
            except psycopg2.Error as exc:
                # IF NOT EXISTS clauses mean these should rarely fail;
                # roll back the failed statement and continue.
                self._conn.rollback()
                if "already exists" not in str(exc).lower():
                    raise
        cur.close()

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        self.close()
        return False


# ── Factory ───────────────────────────────────────────────────────────────────

def get_connection() -> DBConnection:
    """
    Open and return a wrapped Postgres connection.

    Reads DATABASE_URL from the environment (loaded via .env by config.py).
    Raises ValueError if DATABASE_URL is not set.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise ValueError(
            "DATABASE_URL is not set. "
            "Add it to your .env file or Railway environment variables.\n"
            "Format: postgresql://user:password@host:5432/dbname"
        )
    pg_conn = psycopg2.connect(url)
    # Autocommit off — callers manage transactions with conn.commit() / conn.rollback()
    pg_conn.autocommit = False
    return DBConnection(pg_conn)
