"""nhl_goalie_designations must apply on a database that does not have it.

The goalie gate fails closed (models/nhl_goalie_gate.py): until this table
exists, every NHL model except the shots-on-goal props refuses every bet. So a
migration that cannot create it pauses NHL betting until someone notices.

A 'rel'::regclass cast is resolved while the statement is planned, so an IF
that uses one errors before it can fall through to CREATE. Production had no
such table on 2026-10-21 (to_regclass returned NULL), which is exactly the
case that broke. to_regclass returns NULL instead, and the privilege checks
run only after it says the table is there (has_table_privilege errors on a
missing relation too). Same shape as social_post_queue after #1014.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "data" / "migrations" / "add_nhl_goalie_designations_2026_10_20.sql"
SQL = FILE.read_text(encoding="utf-8")


def _code(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def test_it_is_registered_and_the_record_patch_stays_last():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert FILE.name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"


def test_the_skip_check_cannot_fail_on_a_missing_table():
    code = _code(SQL)
    assert "::regclass" not in code, "a regclass cast errors before the IF can reach CREATE"
    assert "IF to_regclass('public.nhl_goalie_designations') IS NOT NULL THEN" in code
    # The privilege reads sit inside that IF, never beside it in one AND.
    outer = code.index("IF to_regclass('public.nhl_goalie_designations') IS NOT NULL THEN")
    assert outer < code.index("has_table_privilege(")
    assert code.index("RETURN;") < code.index("CREATE TABLE IF NOT EXISTS public.nhl_goalie_designations")
    assert code.count("$mig$") == 2


def test_the_table_carries_the_column_the_gate_reads_for_freshness():
    code = _code(SQL)
    assert "last_seen_at" in code.split("CREATE TABLE IF NOT EXISTS", 1)[1]
    # A table created before the column existed gets it too, and the skip
    # check does not return early on such a table.
    assert "ADD COLUMN IF NOT EXISTS last_seen_at" in code
    assert "attname = 'last_seen_at'" in code


def _scratch():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")
    cluster = ScratchPostgres()
    try:
        dsn = cluster.start()
    except Exception as exc:
        cluster.stop()
        pytest.skip(f"scratch cluster did not start: {exc}")
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    return cluster, conn


def test_it_applies_on_an_empty_database_and_again():
    cluster, conn = _scratch()
    try:
        cur = conn.cursor()
        cur.execute("""
            DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                CREATE ROLE anon NOLOGIN;
              END IF;
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                CREATE ROLE authenticated NOLOGIN;
              END IF;
            END $$
        """)
        cur.execute(SQL)
        cur.execute(SQL)
        cur.execute("""
            SELECT c.relrowsecurity FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relname = 'nhl_goalie_designations'
        """)
        assert cur.fetchone() == (True,)
        cur.execute("""
            SELECT column_name FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = 'nhl_goalie_designations'
               AND column_name = 'last_seen_at'
        """)
        assert cur.fetchone() == ("last_seen_at",)
        for role in ("anon", "authenticated"):
            for verb in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                cur.execute("SELECT has_table_privilege(%s, 'public.nhl_goalie_designations', %s)",
                            (role, verb))
                assert cur.fetchone()[0] is False, (role, verb)
    finally:
        conn.close()
        cluster.stop()
