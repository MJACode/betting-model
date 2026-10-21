"""member_sportsbooks: the member's own books, behind two device-scoped RPCs.

Display only. The migration is unapplied on production until the worker's
next pass. These tests read the file and, when initdb is installed, apply it
twice to a scratch cluster and drive the RPCs as anon.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data" / "migrations" / "member_sportsbooks_2026_10_19.sql"
SQL = MIG.read_text(encoding="utf-8")


def _code(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def test_the_migration_is_one_statement_and_registered():
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert MIG.name in ACTIVE_MIGRATIONS
    # The posted-stake record patch must stay last (its own comment says so).
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"
    code = _code(SQL)
    assert code.count("$mig$") == 2
    assert SQL.strip().endswith(";")
    assert "CONCURRENTLY" not in code.upper()
    # Display only: it never touches a pick, a threshold or a publisher.
    for word in ("public.picks", "model_action_thresholds", "push_sent", "discord"):
        assert word not in code.lower()


def test_the_second_pass_returns_before_it_locks():
    """ENABLE ROW LEVEL SECURITY takes ACCESS EXCLUSIVE every time, so the
    catalog check must RETURN before any DDL."""
    code = _code(SQL)
    ret = code.index("RETURN;")
    for ddl in ("CREATE TABLE", "ENABLE ROW LEVEL SECURITY", "REVOKE", "GRANT",
                "CREATE OR REPLACE FUNCTION"):
        assert ret < code.index(ddl), ddl


def test_rpcs_on_scratch_postgres():
    psycopg2 = pytest.importorskip("psycopg2")
    from psycopg2.errors import InsufficientPrivilege, InvalidParameterValue

    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")

    cluster = ScratchPostgres()
    conn = None
    try:
        try:
            dsn = cluster.start()
        except Exception as exc:  # initdb refuses to run as root
            pytest.skip(f"scratch cluster did not start: {exc}")
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                CREATE ROLE anon NOLOGIN;
              END IF;
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                CREATE ROLE authenticated NOLOGIN;
              END IF;
            END $$;
            CREATE SCHEMA IF NOT EXISTS auth;
            GRANT USAGE ON SCHEMA auth TO anon, authenticated;
            CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS
              $$ SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
            GRANT USAGE ON SCHEMA public TO anon, authenticated;
        """)
        cur.execute(SQL)
        cur.execute(SQL)  # second pass: catalog return, no error

        dev_a = "11111111-aaaa-4aaa-8aaa-111111111111"
        dev_b = "22222222-bbbb-4bbb-8bbb-222222222222"
        user = "33333333-cccc-4ccc-8ccc-333333333333"

        cur.execute("SET ROLE anon")
        # Never chosen: NULL, so the app asks.
        cur.execute("SELECT public.member_books_get(%s)", (dev_a,))
        assert cur.fetchone()[0] is None
        # Junk keys are dropped, duplicates collapse, order is stable.
        cur.execute("SELECT public.member_books_set(%s, %s)",
                    (dev_a, ["fanduel", "draftkings", "fanduel", "DROP TABLE"]))
        cur.execute("SELECT public.member_books_get(%s)", (dev_a,))
        assert cur.fetchone()[0] == ["draftkings", "fanduel"]
        # Another install does not see it.
        cur.execute("SELECT public.member_books_get(%s)", (dev_b,))
        assert cur.fetchone()[0] is None
        # An empty set is refused, not stored.
        with pytest.raises(InvalidParameterValue):
            cur.execute("SELECT public.member_books_set(%s, %s::text[])", (dev_a, []))
        # The table itself is closed to anon.
        with pytest.raises(InsufficientPrivilege):
            cur.execute("SELECT * FROM public.member_sportsbooks")
        cur.execute("RESET ROLE")

        # Signed in on device A: saved under the member too, so device B
        # (same member) reads it.
        cur.execute("SET request.jwt.claim.sub = %s", (user,))
        cur.execute("SET ROLE authenticated")
        cur.execute("SELECT public.member_books_set(%s, %s)", (dev_a, ["betmgm"]))
        cur.execute("SELECT public.member_books_get(%s)", (dev_b,))
        assert cur.fetchone()[0] == ["betmgm"]
        cur.execute("RESET ROLE")
        cur.execute("RESET request.jwt.claim.sub")

        cur.execute("SELECT owner_key, books FROM public.member_sportsbooks ORDER BY owner_key")
        assert cur.fetchall() == [
            (f"device:{dev_a}", ["betmgm"]),
            (f"user:{user}", ["betmgm"]),
        ]
    finally:
        if conn is not None:
            conn.close()
        cluster.stop()
