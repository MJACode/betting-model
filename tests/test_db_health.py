"""Database health over time (mike, 2026-11-15): the snapshot tables, the
hourly job that writes them, and its place in the worker's schedule.

data/migrations/db_health_snapshots_2026_11_15.sql builds four insert-only
tables; tracking/db_health.py writes them; the ops dashboard's Database tab
reads them. The SQL tests read the file as text, and
tests/test_db_health_pg.py runs it on a real Postgres. The job tests run the
real take_snapshot against a connection that RECORDS what it is sent and
answers each read with a fixed row, so nothing reaches Postgres.
"""
from __future__ import annotations

import hashlib
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.view_migrations import ACTIVE_MIGRATIONS  # noqa: E402
from tracking import db_health  # noqa: E402

NAME = "db_health_snapshots_2026_11_15.sql"
SQL = (ROOT / "data" / "migrations" / NAME).read_text(encoding="utf-8")
MARK = re.compile(r"db_health_snapshots [0-9a-f]{12}")
TABLES = ("db_health_snapshots", "db_table_snapshots", "db_query_snapshots", "db_query_texts")
SEQUENCE = "public.db_health_snapshots_snapshot_id_seq"
TABLE_PRIVILEGES = "SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER"
COLUMN_PRIVILEGES = "SELECT, INSERT, UPDATE, REFERENCES"
SEQUENCE_PRIVILEGES = "USAGE, SELECT, UPDATE"


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
    # The privilege checks name INSERT, UPDATE and so on as privileges, not as
    # statements, so they are taken out before the statement words are looked for.
    statements = re.sub(r"has_\w+_privilege\([^)]*\)", "", CODE)
    for verb in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP", "GRANT ", "SECURITY DEFINER",
                 "CREATE OR REPLACE FUNCTION", "CREATE OR REPLACE VIEW", "picks"):
        assert verb not in statements, verb
    created = set(re.findall(r"CREATE TABLE IF NOT EXISTS public\.(\w+)", CODE))
    assert created == set(TABLES)


def test_the_app_roles_get_nothing_and_rls_is_on():
    for table in TABLES:
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;" in CODE
        assert f"REVOKE ALL ON public.{table} FROM anon, authenticated;" in CODE
    assert f"REVOKE ALL ON SEQUENCE {SEQUENCE} FROM anon, authenticated;" in CODE


def test_the_skip_holds_only_while_rls_is_on_and_the_app_roles_have_nothing():
    """The skip is what decides whether a later pass repairs drift. It must
    re-check everything the body sets: RLS on every table, and no table,
    column or sequence privilege for either app role. The behaviour, drift
    and repair included, is run on a real Postgres in test_db_health_pg.py."""
    skip = CODE[:CODE.index("RETURN;")]
    guard_end = skip.index("THEN")
    for name in (*(f"public.{t}" for t in TABLES), SEQUENCE):
        assert f"to_regclass('{name}') IS NOT NULL" in skip[:guard_end], name
    checks = skip[guard_end:]
    assert "bool_and(relrowsecurity)" in checks
    for table in TABLES:
        assert f"'public.{table}'::regclass" in checks, table
        for role in ("anon", "authenticated"):
            assert (f"NOT has_table_privilege('{role}', 'public.{table}', '{TABLE_PRIVILEGES}')"
                    in checks), (role, table)
            assert (f"NOT has_any_column_privilege('{role}', 'public.{table}', '{COLUMN_PRIVILEGES}')"
                    in checks), (role, table)
    for role in ("anon", "authenticated"):
        assert f"NOT has_sequence_privilege('{role}', '{SEQUENCE}', '{SEQUENCE_PRIVILEGES}')" in checks, role


def test_every_column_the_job_inserts_exists_in_the_migration():
    """A column named in an INSERT and missing from the table fails only in production."""
    for table, insert in (("db_health_snapshots", db_health._INSERT_DB),
                          ("db_table_snapshots", db_health._INSERT_TABLE),
                          ("db_query_snapshots", db_health._INSERT_QUERY),
                          ("db_query_texts", db_health._INSERT_TEXT)):
        block = CODE.split(f"CREATE TABLE IF NOT EXISTS public.{table} (", 1)[1].split(");", 1)[0]
        defined = {ln.split()[0] for ln in block.splitlines() if ln.strip() and not ln.strip().startswith(
            ("PRIMARY", "CONSTRAINT"))}
        missing = [c for c in _insert_columns(insert) if c not in defined]
        assert not missing, (table, missing)
        assert insert.count("?") == len(_insert_columns(insert)), table


# ── the select lists and the insert lists ────────────────────────────────────

def _insert_columns(insert: str) -> list[str]:
    named = re.search(r"\((.*?)\) VALUES", insert, re.S).group(1)
    return [c.strip() for c in named.split(",")]


def _top_level(sql: str):
    """Yield (index, char, depth) outside string literals."""
    depth, quoted = 0, False
    for i, ch in enumerate(sql):
        if ch == "'":
            quoted = not quoted
            continue
        if quoted:
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        yield i, ch, depth


def _select_names(sql: str) -> list:
    """The output name of each item in the outermost SELECT list, in order:
    its alias, or the column it names, or None for an unnamed expression."""
    flat = sql
    starts = [m.start() for m in re.finditer(r"\bSELECT\b", flat)]
    froms = [m.start() for m in re.finditer(r"\bFROM\b", flat)]
    depth_at = {i: d for i, _, d in _top_level(flat)}
    start = next(s for s in starts if depth_at.get(s, 0) == 0) + len("SELECT")
    end = next(f for f in froms if f > start and depth_at.get(f, 0) == 0)
    items, last = [], start
    for i, ch, d in _top_level(flat):
        if start <= i < end and ch == "," and d == 0:
            items.append(flat[last:i])
            last = i + 1
    items.append(flat[last:end])
    names = []
    for item in (it.strip() for it in items):
        alias = re.search(r"\bAS\s+(\w+)\s*$", item, re.I)
        bare = re.fullmatch(r"(?:\w+\.)?(\w+)", item)
        names.append(alias.group(1) if alias else bare.group(1) if bare else None)
    return names


def test_every_selected_column_is_named_for_the_column_it_is_inserted_into():
    """The select lists and the insert lists are kept by hand, side by side.
    A select reordered without its insert writes one counter into another's
    column, with no error: both are numbers."""
    assert _select_names(db_health.DB_SQL) == list(db_health.DB_COLUMNS)
    assert _select_names(db_health.TABLES_SQL) == _insert_columns(db_health._INSERT_TABLE)[2:]
    assert _select_names(db_health.QUERIES_SQL) == _insert_columns(db_health._INSERT_QUERY)[2:] + ["query"]
    assert _insert_columns(db_health._INSERT_TEXT) == ["queryid", "query"]


def test_the_name_reader_reads_names_not_positions():
    """The reader itself: an alias wins, a bare column is its name, and an
    unnamed expression is None (which fails the test above)."""
    assert _select_names("SELECT a.x, y AS z, f(a, b), (SELECT 1 FROM t) AS q, 'a,(b' AS s FROM t") == [
        "x", "z", None, "q", "s"]


# ── the job ──────────────────────────────────────────────────────────────────

NOW = datetime(2026, 11, 16, 3, 41, tzinfo=timezone.utc)


def _named_row(sql: str) -> tuple:
    """One value per selected column, carrying that column's name."""
    return tuple(f"v:{n}" for n in _select_names(sql))


class _Cursor:
    def __init__(self, one=None, many=None):
        self._one, self._many = one, many or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _Recorder:
    """Every statement sent, in order, with a fixed answer for each read.

    `snapshots` are stored (taken_at, table_rows_taken) rows. The due check is
    answered from them, with its WHERE clause applied only if the SQL carries
    it, so a due check that stops filtering gets a different answer.
    """

    def __init__(self, last_table_snapshot=None, snapshots=None):
        self.sql: list[str] = []
        self.params: dict[str, tuple] = {}
        self.many: list[tuple[str, list]] = []
        self.commits = 0
        self.snapshots = list(snapshots or [])
        if last_table_snapshot is not None:
            self.snapshots.append((last_table_snapshot, True))

    def execute(self, sql, params=None):
        self.sql.append(sql)
        if "max(taken_at)" in sql:
            rows = self.snapshots
            if re.search(r"\bWHERE\s+table_rows_taken\b", sql):
                rows = [r for r in rows if r[1]]
            return _Cursor(one=(max((r[0] for r in rows), default=None),))
        if sql is db_health.DB_SQL:
            return _Cursor(one=_named_row(sql))
        if sql is db_health.STMT_TOTALS_SQL:
            return _Cursor(one=(10, 100, 1000.0, NOW, 437))
        if sql is db_health.STORAGE_SQL:
            return _Cursor(many=[("social-post-media", 34, 6701672)])
        if sql is db_health.TABLES_SQL:
            return _Cursor(many=[_named_row(sql)])
        if sql is db_health.QUERIES_SQL:
            return _Cursor(many=[_named_row(sql)])
        if sql is db_health._INSERT_DB:
            assert len(params) == sql.count("?")
            self.params[sql] = params
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
    assert table_row[:2] == (41, NOW) and table_row[2:4] == ("v:schema_name", "v:table_name")


def test_each_value_is_inserted_into_the_column_of_its_name():
    """Through the real take_snapshot: every value a read returns lands in the
    insert column that has its name, including the statement text, which is
    split off into db_query_texts."""
    conn = _Recorder()
    db_health.take_snapshot(conn, source="worker", tables=True, now=NOW)

    cols = _insert_columns(db_health._INSERT_DB)
    params = conn.params[db_health._INSERT_DB]
    for name in db_health.DB_COLUMNS:
        assert params[cols.index(name)] == f"v:{name}", name

    batches = dict(conn.many)
    for insert in (db_health._INSERT_TABLE, db_health._INSERT_QUERY):
        cols = _insert_columns(insert)
        (row,) = batches[insert]
        assert row[:2] == (41, NOW)
        assert list(row[2:]) == [f"v:{c}" for c in cols[2:]], insert
    assert batches[db_health._INSERT_TEXT] == [("v:queryid", "v:query")]


@pytest.mark.parametrize("last, due", [
    (None, True),
    (NOW - timedelta(hours=5, minutes=31), True),
    (NOW - timedelta(hours=5, minutes=29), False),
    (NOW - timedelta(minutes=50), False),
])
def test_the_table_rows_are_due_every_six_hours(last, due):
    assert db_health._tables_due(_Recorder(last_table_snapshot=last), NOW) is due


def test_only_a_run_that_took_the_table_rows_restarts_the_six_hours():
    """Every hourly row is newer than 5.5 hours. If the due check stopped
    filtering on table_rows_taken, the per-table and per-statement history
    would stop after its first day and every run would still beat ok."""
    hourly = [(NOW - timedelta(hours=h), False) for h in (1, 2, 3, 4, 5)]
    assert db_health._tables_due(_Recorder(snapshots=[(NOW - timedelta(hours=6), True), *hourly]), NOW)
    assert not db_health._tables_due(_Recorder(snapshots=[(NOW - timedelta(hours=2), True), *hourly]), NOW)


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


def test_the_oldest_transaction_is_aged_at_the_read_not_at_the_runs_start():
    """now() is when this run's own transaction began, before pg_stat_activity
    is read, so a transaction that started in between came out negative."""
    xact = re.search(r"\(SELECT max\(extract\(epoch FROM (.+?) - xact_start\)\)", db_health.DB_SQL)
    assert xact and xact.group(1) == "clock_timestamp()"


# ── the schedule ─────────────────────────────────────────────────────────────

def test_the_worker_runs_it_hourly_at_fifty_past_and_watches_it(monkeypatch):
    import scheduler
    from tracking import job_heartbeat as jh
    from tracking.job_heartbeat import MAX_SILENCE
    from tracking.morning_disk import DEFER_JOBS

    # build_scheduler seeds a heartbeat row for every watched job it registers
    # and marks the rest disabled. On a machine with a .env each of those is a
    # write to production, so all three are stubbed. The role is pinned
    # because another test reloads the scheduler as the pollers service.
    seeded: list[str] = []
    monkeypatch.setattr(jh, "seed", lambda job_id, *a, **k: seeded.append(job_id))
    monkeypatch.setattr(jh, "beat", lambda *a, **k: None)
    monkeypatch.setattr(jh, "mark_disabled", lambda *a, **k: None)
    monkeypatch.setattr(scheduler, "SERVICE_ROLE", "pipeline")

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
    assert "db_health_snapshot" in seeded
