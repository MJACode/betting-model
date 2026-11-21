"""The PC copy table and its one writer, on a real Postgres.

WHY A REAL DATABASE. Whether a later pass repairs drift is decided by the
migration's skip check, which is catalog SQL: row level security and the
access lists of the table, its columns and its sequence. And whether the
report's row lands with every value in its own column is a claim about the
server. This runs data/view_migrations._apply_one, the worker's own path, and
scripts/local_mirror_report.insert_row, the PC's own path, on a scratch
database per test. Runs against LATEST_LINE_TEST_DSN or a throwaway cluster
from tests/_pg.py, and SKIPS only where neither exists. Nothing here reaches
production.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from data.db import DBConnection  # noqa: E402
from data.view_migrations import _apply_one  # noqa: E402
from scripts import local_mirror_report as rep  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NAME = "pc_copy_snapshots_2026_11_16.sql"
TABLE = "public.pc_copy_snapshots"
SEQUENCE = "public.pc_copy_snapshots_snapshot_id_seq"
ROLES = ("anon", "authenticated")
UTC = dt.timezone.utc


def _migration() -> str:
    return (ROOT / "data" / "migrations" / NAME).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cluster():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("pc-copy-pg-") as d:
        yield d


_COUNTER = {"n": 0}


@pytest.fixture()
def db(cluster):
    """(the worker's connection wrapper, the raw connection) on a fresh database
    with the two app roles, Supabase's default grants to them, and a DDL counter.

    Supabase grants anon and authenticated rights on every new table and
    sequence in public by default, so the first build's REVOKEs have real
    grants to remove here, as they do in production. The per-test address is
    built with make_dsn, so a URL-style LATEST_LINE_TEST_DSN works too, and
    everything after CREATE DATABASE is inside the cleanup."""
    _COUNTER["n"] += 1
    name = f"pc_copy_t{_COUNTER['n']}_{int(time.time() * 1000) % 10_000_000}"
    dsn = psycopg2.extensions.make_dsn(cluster, dbname=name)
    assert dsn != cluster
    admin = psycopg2.connect(cluster)
    admin.autocommit = True
    raw = None
    try:
        with admin.cursor() as cur:
            for role in ROLES:
                cur.execute(f"DO $$ BEGIN CREATE ROLE {role} NOLOGIN; "
                            "EXCEPTION WHEN duplicate_object THEN NULL; END $$")
            cur.execute(f"CREATE DATABASE {name}")
        raw = psycopg2.connect(dsn)
        with raw.cursor() as cur:
            cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated")
            cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated")
            cur.execute("CREATE TABLE ddl_seen (n integer NOT NULL)")
            cur.execute("INSERT INTO ddl_seen VALUES (0)")
            cur.execute("""CREATE FUNCTION count_ddl() RETURNS event_trigger LANGUAGE plpgsql AS
                           $$ BEGIN UPDATE ddl_seen SET n = n + 1; END $$""")
            cur.execute("CREATE EVENT TRIGGER count_ddl ON ddl_command_start EXECUTE FUNCTION count_ddl()")
        raw.commit()
        yield DBConnection(raw, url=dsn), raw
    finally:
        try:
            if raw is not None:
                raw.close()
        finally:
            with admin.cursor() as cur:
                cur.execute(f"DROP DATABASE IF EXISTS {name}")
                for role in ROLES:
                    cur.execute(f"DO $$ BEGIN REVOKE pg_read_all_data FROM {role}; "
                                "EXCEPTION WHEN OTHERS THEN NULL; END $$")
            admin.close()


def _ddl_seen(conn) -> int:
    n = conn.execute("SELECT n FROM ddl_seen").fetchone()[0]
    conn.commit()
    return int(n)


def _apply(conn) -> None:
    err = _apply_one(conn, NAME, _migration())
    assert err is None, err


def _open(conn) -> list[str]:
    """Every entry on the table's, its columns' or its sequence's access list
    that names anon, authenticated or PUBLIC, plus row level security off."""
    rows = conn.execute(f"""
        SELECT c.relname, a.grantee, a.privilege_type
          FROM pg_class c, aclexplode(c.relacl) a
         WHERE c.oid IN ('{TABLE}'::regclass, '{SEQUENCE}'::regclass)
           AND a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)
        UNION ALL
        SELECT att.attname, a.grantee, a.privilege_type
          FROM pg_attribute att, aclexplode(att.attacl) a
         WHERE att.attrelid = '{TABLE}'::regclass
           AND a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)""").fetchall()
    out = [f"{r[0]} {r[2]} to {'PUBLIC' if int(r[1]) == 0 else r[1]}" for r in rows]
    if not conn.execute(f"SELECT relrowsecurity FROM pg_class WHERE oid = '{TABLE}'::regclass").fetchone()[0]:
        out.append("row level security off")
    conn.commit()
    return sorted(out)


def test_it_builds_the_table_closed_and_a_second_pass_runs_no_ddl(db):
    conn, _ = db
    _apply(conn)
    assert _open(conn) == []
    first = _ddl_seen(conn)
    assert first > 0
    _apply(conn)
    assert _ddl_seen(conn) == first, "the second pass ran DDL: the skip check did not hold"


@pytest.mark.parametrize("drift", [
    f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY",
    f"GRANT SELECT ON {TABLE} TO anon",
    f"GRANT INSERT, UPDATE, DELETE ON {TABLE} TO authenticated",
    f"GRANT TRUNCATE ON {TABLE} TO anon",
    f"GRANT MAINTAIN ON {TABLE} TO authenticated",
    f"GRANT SELECT (pass_id, host) ON {TABLE} TO authenticated",
    f"GRANT UPDATE (disk_free_bytes) ON {TABLE} TO anon",
    f"GRANT USAGE ON SEQUENCE {SEQUENCE} TO anon",
    f"GRANT SELECT ON {TABLE} TO PUBLIC",
    f"GRANT TRUNCATE ON {TABLE} TO PUBLIC",
    f"GRANT SELECT (pass_id) ON {TABLE} TO PUBLIC",
    f"GRANT USAGE ON SEQUENCE {SEQUENCE} TO PUBLIC",
])
def test_the_next_pass_undoes_any_opening_and_the_one_after_skips(db, drift):
    conn, _ = db
    _apply(conn)
    conn.execute(drift)
    conn.commit()
    assert _open(conn) != [], f"the drift opened nothing: {drift}"
    before = _ddl_seen(conn)
    _apply(conn)
    assert _ddl_seen(conn) > before, "the pass after the drift skipped"
    assert _open(conn) == [], drift
    after = _ddl_seen(conn)
    _apply(conn)
    assert _ddl_seen(conn) == after, "the pass after the repair ran DDL again"


def test_an_older_marker_makes_the_next_pass_run_the_file_and_restamp_it(db):
    """An edit to the file changes its marker. The next pass must run the body
    and store the new marker; with the marker check switched off, nothing would
    ever re-run (the review of #1412)."""
    conn, _ = db
    _apply(conn)
    conn.execute(f"COMMENT ON TABLE {TABLE} IS 'pc_copy_snapshots 000000000000'")
    conn.commit()
    before = _ddl_seen(conn)
    _apply(conn)
    assert _ddl_seen(conn) > before, "the pass after an edit skipped"
    marker = re.search(r"pc_copy_snapshots [0-9a-f]{12}", _migration()).group(0)
    got = conn.execute(f"SELECT obj_description('{TABLE}'::regclass, 'pg_class')").fetchone()[0]
    conn.commit()
    assert got == marker


def test_a_privilege_only_inherited_does_not_rerun_the_file_every_pass(db):
    """A membership is not on the table's access list and no REVOKE here can
    remove it. The skip must not keep failing on it (the database health
    file's gap, found in the review of #1391). Row level security still
    keeps every row from the role."""
    conn, raw = db
    _apply(conn)
    conn.execute("GRANT pg_read_all_data TO anon")
    conn.commit()
    before = _ddl_seen(conn)
    _apply(conn)
    _apply(conn)
    assert _ddl_seen(conn) == before
    with raw.cursor() as cur:
        cur.execute(f"INSERT INTO {TABLE} (source, pass_id) VALUES ('manual', 'x')")
        cur.execute("SET ROLE anon")
        cur.execute(f"SELECT count(*) FROM {TABLE}")
        assert cur.fetchone()[0] == 0
        cur.execute("RESET ROLE")
    raw.rollback()


def _row(pass_id: str, source: str = "nightly") -> dict:
    row = {c: None for c in rep.COLUMNS}
    row.update(
        source=source, pass_id=pass_id, host="TESTPC",
        pass_started_at=dt.datetime(2026, 11, 16, 5, 43, 24, tzinfo=UTC),
        copy_run_id="20261116T055813Z",
        copy_started_at=dt.datetime(2026, 11, 16, 5, 58, 13, tzinfo=UTC),
        copy_finished_at=dt.datetime(2026, 11, 16, 13, 40, tzinfo=UTC),
        copy_tables=311, copy_rows_pulled=23_833_580, copy_db_seconds=9000, copy_paused_seconds=3053,
        copy_this_pass=True,
        failed_tables=json.dumps(["public.nfl_research_data_backup"]),
        differing_tables=json.dumps([{"table": "public.odds", "local_rows": 500, "supabase_rows": 497,
                                      "ranges_differ": 2, "ranges_not_counted": 0,
                                      "checked_at": "2026-11-16T07:00:00+00:00"}]),
        github_exit=1, supabase_exit=0, duckdb_exit=0,
        github_finished_at=dt.datetime(2026, 11, 16, 5, 50, tzinfo=UTC), github_repos=3, github_repos_failed=2,
        local_tables=311, local_rows=257_971_441,
        tables_bytes=6_584_000_001, schema_bytes=34_000_002, storage_bytes=7_000_003,
        github_bytes=613_000_004, duckdb_bytes=2_895_872, other_bytes=3_840_000_005,
        total_bytes=11_082_000_006, total_files=21_171,
        disk_total_bytes=999_000_000_007, disk_free_bytes=529_600_000_008, report_ms=1400,
        copy_kind="full",
        schedule=json.dumps({"task": "\\BettingModel\\LocalMirror", "state": "Ready",
                             "next_run_at": "2026-11-17T05:30:00+00:00",
                             "last_full": "2026-11-16T05:43:24+00:00",
                             "next_full_from": "2026-12-01",
                             "triggers": [{"kind": "daily", "at": "00:30"}]}),
    )
    return row


def test_the_report_adds_one_row_and_a_second_report_of_the_pass_keeps_it(db):
    conn, raw = db
    _apply(conn)
    first = rep.insert_row(raw, _row("20261116T054324Z"))
    assert isinstance(first, int)
    changed = _row("20261116T054324Z")
    changed["disk_free_bytes"] = 1
    assert rep.insert_row(raw, changed) is None  # kept, not replaced
    with raw.cursor() as cur:
        cur.execute(f"SELECT count(*), max(disk_free_bytes) FROM {TABLE}")
        assert cur.fetchone() == (1, 529_600_000_008)
    # a manual row for the same stamp is a different row
    assert isinstance(rep.insert_row(raw, _row("20261116T054324Z", source="manual")), int)
    raw.rollback()


def test_the_catch_up_adds_no_second_row_for_a_copy_a_report_by_hand_recorded(db):
    """2026-11-21, rows 10 and 11: the 11-20 full was reported by hand under
    its own stamp, then the next pass's catch-up reported the same copy run
    under the pass's stamp. The catch-up now finds the first row and stops; a
    nightly report still records the run again (its copy did not finish)."""
    conn, raw = db
    _apply(conn)
    by_hand = _row("20261120T233329Z", source="manual")
    by_hand.update(copy_run_id="20261120T194438Z", copy_this_pass=None)
    assert isinstance(rep.insert_row(raw, by_hand), int)
    catch_up = _row("20261120T194436Z")
    catch_up.update(copy_run_id="20261120T194438Z")
    assert rep.insert_row(raw, catch_up, unless_copy_recorded=True) is None
    with raw.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {TABLE} WHERE copy_run_id = '20261120T194438Z'")
        assert cur.fetchone()[0] == 1
    other = _row("20261121T053003Z")
    other.update(copy_run_id="20261121T053019Z")
    assert isinstance(rep.insert_row(raw, other, unless_copy_recorded=True), int)  # a new run lands
    again = _row("20261122T053003Z")
    again.update(copy_run_id="20261121T053019Z", copy_this_pass=False)
    assert isinstance(rep.insert_row(raw, again), int)  # a pass whose own copy did not finish
    raw.rollback()


def test_each_value_lands_in_the_column_of_its_name(db):
    """Every value distinct, so a swapped pair of columns shows."""
    conn, raw = db
    _apply(conn)
    want = _row("20261116T054324Z")
    snapshot_id = rep.insert_row(raw, want)
    with raw.cursor() as cur:
        cur.execute(f"SELECT row_to_json(s) FROM {TABLE} s WHERE snapshot_id = %s", (snapshot_id,))
        got = cur.fetchone()[0]
    raw.rollback()
    for col in rep.COLUMNS:
        w, g = want[col], got[col]
        if col in rep.JSON_COLUMNS:
            assert g == json.loads(w), col
        elif isinstance(w, dt.datetime):
            assert dt.datetime.fromisoformat(g) == w, col
        else:
            assert g == w, col
    assert got["taken_at"] is not None and got["snapshot_id"] == snapshot_id
