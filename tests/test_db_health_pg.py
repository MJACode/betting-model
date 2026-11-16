"""The database health migration and reads on a real Postgres.

WHY A REAL DATABASE. Whether a later pass repairs drift is decided by the
migration's skip check, which is catalog SQL: row level security, table,
column and sequence privileges. And the snapshot's select lists are matched to
its insert lists by the names Postgres gives each output column. Both are
claims about the server. This runs data/view_migrations._apply_one, the
worker's own path, on a scratch database per test. Runs against
LATEST_LINE_TEST_DSN or a throwaway cluster from tests/_pg.py, and SKIPS only
where neither exists. Nothing here reaches production.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from data.db import DBConnection  # noqa: E402
from data.view_migrations import _apply_one  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402
from tracking import db_health  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NAME = "db_health_snapshots_2026_11_15.sql"
TABLES = ("db_health_snapshots", "db_table_snapshots", "db_query_snapshots", "db_query_texts")
SEQUENCE = "public.db_health_snapshots_snapshot_id_seq"
ROLES = ("anon", "authenticated")


def _migration() -> str:
    return (ROOT / "data" / "migrations" / NAME).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cluster():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("db-health-pg-") as d:
        yield d


_COUNTER = {"n": 0}


@pytest.fixture()
def db(cluster):
    """A fresh database with the two app roles and a DDL counter."""
    _COUNTER["n"] += 1
    name = f"db_health_t{_COUNTER['n']}_{int(time.time() * 1000) % 10_000_000}"
    admin = psycopg2.connect(cluster)
    admin.autocommit = True
    with admin.cursor() as cur:
        for role in ROLES:
            cur.execute(f"DO $$ BEGIN CREATE ROLE {role} NOLOGIN; "
                        "EXCEPTION WHEN duplicate_object THEN NULL; END $$")
        cur.execute(f"CREATE DATABASE {name}")
    dsn = cluster.replace("dbname=postgres", f"dbname={name}")
    raw = psycopg2.connect(dsn)
    with raw.cursor() as cur:
        cur.execute("CREATE TABLE ddl_seen (n integer NOT NULL)")
        cur.execute("INSERT INTO ddl_seen VALUES (0)")
        cur.execute("""CREATE FUNCTION count_ddl() RETURNS event_trigger LANGUAGE plpgsql AS
                       $$ BEGIN UPDATE ddl_seen SET n = n + 1; END $$""")
        cur.execute("CREATE EVENT TRIGGER count_ddl ON ddl_command_start EXECUTE FUNCTION count_ddl()")
    raw.commit()
    conn = DBConnection(raw, url=dsn)
    try:
        yield conn
    finally:
        try:
            raw.close()
        finally:
            with admin.cursor() as cur:
                cur.execute(f"DROP DATABASE IF EXISTS {name}")
            admin.close()


def _ddl_seen(conn) -> int:
    n = conn.execute("SELECT n FROM ddl_seen").fetchone()[0]
    conn.commit()
    return int(n)


def _apply(conn) -> None:
    err = _apply_one(conn, NAME, _migration())
    assert err is None, err


def _open_to_app_roles(conn) -> list[str]:
    """Everything that would let anon or authenticated reach a row."""
    out = []
    for table in TABLES:
        rls = conn.execute("SELECT relrowsecurity FROM pg_class WHERE oid = %s::regclass",
                           (f"public.{table}",)).fetchone()[0]
        if not rls:
            out.append(f"RLS off on {table}")
        for role in ROLES:
            for priv in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                if conn.execute("SELECT has_table_privilege(%s, %s, %s)",
                                (role, f"public.{table}", priv)).fetchone()[0]:
                    out.append(f"{role} {priv} on {table}")
            for priv in ("SELECT", "INSERT", "UPDATE", "REFERENCES"):
                if conn.execute("SELECT has_any_column_privilege(%s, %s, %s)",
                                (role, f"public.{table}", priv)).fetchone()[0]:
                    out.append(f"{role} column {priv} on {table}")
    for role in ROLES:
        for priv in ("USAGE", "SELECT", "UPDATE"):
            if conn.execute("SELECT has_sequence_privilege(%s, %s, %s)",
                            (role, SEQUENCE, priv)).fetchone()[0]:
                out.append(f"{role} {priv} on the sequence")
    conn.commit()
    return sorted(set(out))


def test_it_builds_the_tables_closed_and_a_second_pass_runs_no_ddl(db):
    _apply(db)
    assert _open_to_app_roles(db) == []
    first = _ddl_seen(db)
    assert first > 0
    _apply(db)
    assert _ddl_seen(db) == first, "the second pass ran DDL: the skip check did not hold"


@pytest.mark.parametrize("drift", [
    "ALTER TABLE public.db_query_texts DISABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.db_health_snapshots DISABLE ROW LEVEL SECURITY",
    "GRANT INSERT, UPDATE, DELETE ON public.db_health_snapshots TO anon",
    "GRANT TRUNCATE ON public.db_table_snapshots TO authenticated",
    "GRANT SELECT (queryid, query) ON public.db_query_texts TO authenticated",
    "GRANT UPDATE (calls) ON public.db_query_snapshots TO anon",
    f"GRANT USAGE ON SEQUENCE {SEQUENCE} TO anon",
    "GRANT SELECT ON public.db_query_snapshots TO anon",
])
def test_the_next_pass_undoes_any_opening_to_the_app_roles(db, drift):
    _apply(db)
    db.execute(drift)
    db.commit()
    assert _open_to_app_roles(db) != [], "the drift statement opened nothing"
    _apply(db)
    assert _open_to_app_roles(db) == []


def test_the_reads_name_every_column_for_the_column_it_is_inserted_into(db):
    """Postgres's own output names, not a reading of the SQL text."""
    _apply(db)
    raw = db._conn
    with raw.cursor() as c:
        c.execute(db_health.DB_SQL)
        assert [d.name for d in c.description] == list(db_health.DB_COLUMNS)
        c.execute(db_health.TABLES_SQL)
        insert = db_health._INSERT_TABLE
        cols = [x.strip() for x in insert[insert.index("(") + 1:insert.index(")")].split(",")]
        assert [d.name for d in c.description] == cols[2:]
    raw.rollback()


def test_the_live_and_dead_row_estimates_land_in_their_own_columns(db):
    """A table with 10 rows inserted and 3 deleted: the per-table read must put
    7 under live_rows_est and 3 under dead_rows_est, not the other way."""
    _apply(db)
    raw = db._conn
    with raw.cursor() as c:
        c.execute("CREATE TABLE public.counted (x integer)")
        c.execute("INSERT INTO public.counted SELECT g FROM generate_series(1, 10) g")
        c.execute("DELETE FROM public.counted WHERE x <= 3")
    raw.commit()
    row = None
    for _ in range(50):
        with raw.cursor() as c:
            c.execute("SELECT pg_stat_force_next_flush()")
        raw.commit()
        with raw.cursor() as c:
            c.execute(db_health.TABLES_SQL)
            names = [d.name for d in c.description]
            found = [dict(zip(names, r)) for r in c.fetchall()
                     if r[0] == "public" and r[1] == "counted"]
        raw.commit()
        if found and found[0]["n_tup_ins"] == 10 and found[0]["n_tup_del"] == 3:
            row = found[0]
            break
        time.sleep(0.1)
    assert row is not None, "the statistics for the test table never arrived"
    assert (row["live_rows_est"], row["dead_rows_est"]) == (7, 3)
    assert row["kind"] == "table" and row["table_name"] == "counted"
