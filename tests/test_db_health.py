"""Database health over time (mike, 2026-11-15): the snapshot tables, the
hourly job that writes them, and its place in the worker's schedule.

data/migrations/db_health_snapshots_2026_11_15.sql builds four insert-only
tables; tracking/db_health.py writes them; the ops dashboard's Database tab
reads them. The SQL tests read the file as text. The job tests run the real
take_snapshot against a connection that RECORDS what it is sent and answers
each read with a fixed row, so nothing reaches Postgres.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from data.view_migrations import ACTIVE_MIGRATIONS  # noqa: E402
from tracking import db_health  # noqa: E402

NAME = "db_health_snapshots_2026_11_15.sql"
SQL = (ROOT / "data" / "migrations" / NAME).read_text(encoding="utf-8")
MARK = re.compile(r"db_health_snapshots [0-9a-f]{12}")
TABLES = ("db_health_snapshots", "db_table_snapshots", "db_query_snapshots", "db_query_texts")


def _code(sql: str) -> str:
    """The SQL with -- comments removed, so a clause in a comment proves nothing."""
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


CODE = _code(SQL)


# ── the migration ────────────────────────────────────────────────────────────

def test_the_marker_is_the_hash_of_the_file():
    found = MARK.findall(SQL)
    assert len(found) == 2 and found[0] == found[1], found
    blank = MARK.sub("db_health_snapshots " + "0" * 12, SQL)
    want = "db_health_snapshots " + hashlib.sha256(blank.encode("utf-8")).hexdigest()[:12]
    assert found[0] == want, f"set the marker to '{want}'"


def test_it_is_one_statement_registered_before_the_posted_stake_pair():
    body = CODE.strip()
    assert body.startswith("DO $mig$") and body.endswith("END $mig$;")
    assert body.count("$mig$") == 2
    assert ACTIVE_MIGRATIONS.count(NAME) == 1
    assert ACTIVE_MIGRATIONS.index(NAME) < ACTIVE_MIGRATIONS.index("published_pick_units_2026_10_17.sql")
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"


def test_it_creates_only_its_four_tables_and_writes_no_rows():
    for verb in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP", "GRANT ", "SECURITY DEFINER",
                 "CREATE OR REPLACE FUNCTION", "CREATE OR REPLACE VIEW", "picks"):
        assert verb not in CODE, verb
    created = set(re.findall(r"CREATE TABLE IF NOT EXISTS public\.(\w+)", CODE))
    assert created == set(TABLES)


def test_the_app_roles_get_nothing_and_rls_is_on():
    skip = CODE[:CODE.index("RETURN;")]
    for table in TABLES:
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;" in CODE
        assert f"REVOKE ALL ON public.{table} FROM anon, authenticated;" in CODE
        # the skip needs the revokes to hold too, so a re-grant is undone next pass
        for role in ("anon", "authenticated"):
            assert f"NOT has_table_privilege('{role}', 'public.{table}', 'SELECT')" in skip, (role, table)
    assert "REVOKE ALL ON SEQUENCE public.db_health_snapshots_snapshot_id_seq FROM anon, authenticated;" in CODE


def test_every_column_the_job_inserts_exists_in_the_migration():
    """A column named in an INSERT and missing from the table fails only in production."""
    for table, insert in (("db_health_snapshots", db_health._INSERT_DB),
                          ("db_table_snapshots", db_health._INSERT_TABLE),
                          ("db_query_snapshots", db_health._INSERT_QUERY),
                          ("db_query_texts", db_health._INSERT_TEXT)):
        block = CODE.split(f"CREATE TABLE IF NOT EXISTS public.{table} (", 1)[1].split(");", 1)[0]
        defined = {ln.split()[0] for ln in block.splitlines() if ln.strip() and not ln.strip().startswith(
            ("PRIMARY", "CONSTRAINT"))}
        named = re.search(r"\((.*?)\) VALUES", insert, re.S).group(1)
        cols = [c.strip() for c in named.split(",")]
        missing = [c for c in cols if c not in defined]
        assert not missing, (table, missing)
        assert insert.count("?") == len(cols), (table, insert.count("?"), len(cols))


# ── the job ──────────────────────────────────────────────────────────────────

NOW = datetime(2026, 11, 16, 3, 41, tzinfo=timezone.utc)


class _Cursor:
    def __init__(self, one=None, many=None):
        self._one, self._many = one, many or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _Recorder:
    """Every statement sent, in order, with a fixed answer for each read."""

    def __init__(self, last_table_snapshot=None):
        self.sql: list[str] = []
        self.many: list[tuple[str, list]] = []
        self.commits = 0
        self.last_table_snapshot = last_table_snapshot

    def execute(self, sql, params=None):
        self.sql.append(sql)
        if "max(taken_at)" in sql:
            return _Cursor(one=(self.last_table_snapshot,))
        if sql is db_health.DB_SQL:
            return _Cursor(one=tuple(range(len(db_health.DB_COLUMNS))))
        if sql is db_health.STMT_TOTALS_SQL:
            return _Cursor(one=(10, 100, 1000.0, NOW))
        if sql is db_health.STORAGE_SQL:
            return _Cursor(many=[("social-post-media", 34, 6701672)])
        if sql is db_health.TABLES_SQL:
            return _Cursor(many=[("public", "odds", "table", *range(13))])
        if sql is db_health.QUERIES_SQL:
            return _Cursor(many=[(7, "postgres", True, *range(8), "SELECT 1")])
        if sql is db_health._INSERT_DB:
            assert len(params) == sql.count("?")
            return _Cursor(one=(41, NOW))
        return _Cursor()

    def executemany(self, sql, rows):
        for r in rows:
            assert len(r) == sql.count("?"), (sql, r)
        self.many.append((sql, list(rows)))

    def commit(self):
        self.commits += 1


def test_a_run_without_the_table_rows_writes_one_row_and_commits_once():
    conn = _Recorder()
    out = db_health.take_snapshot(conn, source="worker", tables=False, now=NOW)
    assert out["snapshot_id"] == 41 and out["tables"] == 0 and out["statements"] == 0
    assert conn.many == [] and conn.commits == 1
    assert db_health.TABLES_SQL not in conn.sql and db_health.QUERIES_SQL not in conn.sql
    assert conn.sql[0].startswith("SET LOCAL statement_timeout")


def test_a_due_run_writes_every_table_and_the_statement_text_once():
    conn = _Recorder(last_table_snapshot=NOW - timedelta(hours=6))
    out = db_health.take_snapshot(conn, source="worker", now=NOW)
    assert out["tables"] == 1 and out["statements"] == 1
    sent = [s for s, _ in conn.many]
    assert sent == [db_health._INSERT_TABLE, db_health._INSERT_TEXT, db_health._INSERT_QUERY]
    assert "ON CONFLICT (queryid) DO NOTHING" in db_health._INSERT_TEXT
    table_row = conn.many[0][1][0]
    assert table_row[:2] == (41, NOW) and table_row[2:4] == ("public", "odds")


@pytest.mark.parametrize("last, due", [
    (None, True),
    (NOW - timedelta(hours=5, minutes=31), True),
    (NOW - timedelta(hours=5, minutes=29), False),
    (NOW - timedelta(minutes=50), False),
])
def test_the_table_rows_are_due_every_six_hours(last, due):
    assert db_health._tables_due(_Recorder(last_table_snapshot=last), NOW) is due


def test_the_job_never_deletes_or_updates_a_row():
    """CLAUDE.md section 1b: snapshot rows are only ever added."""
    conn = _Recorder()
    db_health.take_snapshot(conn, source="worker", tables=True, now=NOW)
    statements = conn.sql + [s for s, _ in conn.many]
    writes = [s for s in statements if re.match(r"\s*INSERT\b", s, re.I)]
    assert len(writes) == 4  # one snapshot row, then three batches
    for s in statements:
        upper = s.upper()
        assert not re.search(r"\bDELETE\s+FROM\b", upper), s
        assert not re.search(r"\bUPDATE\s+[\w.]+\s+SET\b", upper), s
        assert not re.search(r"\bDO\s+UPDATE\b", upper), s
        assert not re.search(r"\bTRUNCATE\b", upper), s


def test_an_unknown_source_is_refused():
    with pytest.raises(ValueError):
        db_health.take_snapshot(_Recorder(), source="cron", tables=False, now=NOW)


def test_the_reads_never_count_rows():
    """Row numbers are Postgres's estimates; a count(*) over odds would scan 58M rows."""
    for sql in (db_health.DB_SQL, db_health.TABLES_SQL):
        assert "count(*) FROM odds" not in sql
        assert "n_live_tup" in sql


# ── the schedule ─────────────────────────────────────────────────────────────

def test_the_worker_runs_it_hourly_at_fifty_past_and_watches_it():
    import scheduler
    from tracking.job_heartbeat import MAX_SILENCE
    from tracking.morning_disk import DEFER_JOBS

    jobs = {j.id: j for j in scheduler.build_scheduler().get_jobs()}
    job = jobs["db_health_snapshot"]
    minute = next(f for f in job.trigger.fields if f.name == "minute")
    assert str(minute) == "50"
    hour = next(f for f in job.trigger.fields if f.name == "hour")
    assert str(hour) == "*"
    assert "db_health_snapshot" in scheduler._PIPELINE_JOBS
    assert "db_health_snapshot" not in scheduler._POLLER_JOBS
    assert "db_health_snapshot" in DEFER_JOBS
    assert MAX_SILENCE["db_health_snapshot"] == 180
