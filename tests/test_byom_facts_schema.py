"""byom_game_facts and byom_prop_facts: empty, readable, not a pick store.

The migration is unapplied on production. These tests read the file and,
when initdb is installed, apply it twice to a scratch cluster.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data" / "migrations" / "byom_facts_schema_2026_10_16.sql"
SQL = MIG.read_text(encoding="utf-8")


def _code(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def test_the_migration_is_one_statement_and_registered():
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert MIG.name in ACTIVE_MIGRATIONS
    assert SQL.count("DO $mig$") == 1
    assert SQL.strip().endswith(";")
    code = _code(SQL)
    assert code.count("$mig$") == 2
    assert "CONCURRENTLY" not in code.upper()
    assert "FORCE ROW LEVEL SECURITY" not in code.upper()
    # A facts table is not the pick store and not a publisher.
    assert "public.picks" not in code
    assert "discord" not in code.lower()


def test_the_second_pass_returns_before_it_locks():
    """ENABLE ROW LEVEL SECURITY takes ACCESS EXCLUSIVE every time. The
    catalog check has to RETURN before CREATE, REVOKE, or ENABLE."""
    code = _code(SQL)
    ret = code.index("RETURN;")
    for marker in ("CREATE TABLE", "REVOKE ALL", "ENABLE ROW LEVEL SECURITY",
                   "CREATE POLICY"):
        assert ret < code.index(marker), marker
    assert "to_regclass('public.byom_game_facts')" in code
    assert "to_regclass('public.byom_prop_facts')" in code
    assert "anon read byom_game_facts" in SQL
    assert "anon read byom_prop_facts" in SQL


def test_the_windows_are_not_check_constraints():
    """120 and 24 are UNCONFIRMED. A constraint would freeze the placeholder."""
    code = _code(SQL)
    assert "120" not in code
    assert "24" not in code
    assert "lock_window_hours" in code
    assert "near_window_hours" in code
    assert "UNCONFIRMED" in SQL


def test_results_keep_pushes_and_ties_and_carry_no_stake():
    code = _code(SQL)
    assert "'push'" in code
    assert "'tie'" in code
    for banned in ("kelly", "stake", "recommended_bet", "bankroll"):
        assert banned not in code.lower(), banned


def test_both_tables_are_on_the_anon_read_list():
    from data.anon_readable import AHEAD_OF_THE_APP, ANON_READABLE

    for rel in ("byom_game_facts", "byom_prop_facts"):
        assert rel in ANON_READABLE
        assert rel in AHEAD_OF_THE_APP
    # The app does not read them yet. The shop table is the third exemption.
    assert AHEAD_OF_THE_APP == (
        "byom_game_facts", "byom_lock_shop", "byom_prop_facts")


def test_schema_applies_twice_on_scratch_postgres_and_anon_can_only_read():
    psycopg2 = pytest.importorskip("psycopg2")
    from psycopg2.errors import InsufficientPrivilege

    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")

    cluster = ScratchPostgres()
    conn = None
    try:
        dsn = cluster.start()
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
            END $$
        """)
        cur.execute(SQL)
        cur.execute(SQL)  # second pass: catalog return, no error
        cur.execute("""
            SELECT c.relname, c.relrowsecurity
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
               AND c.relname IN ('byom_game_facts', 'byom_prop_facts')
             ORDER BY c.relname
        """)
        rows = cur.fetchall()
        assert rows == [("byom_game_facts", True), ("byom_prop_facts", True)]
        cur.execute("SELECT count(*) FROM public.byom_game_facts")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM public.byom_prop_facts")
        assert cur.fetchone()[0] == 0
        cur.execute("SET ROLE anon")
        cur.execute("SELECT count(*) FROM public.byom_game_facts")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM public.byom_prop_facts")
        assert cur.fetchone()[0] == 0
        with pytest.raises(InsufficientPrivilege):
            cur.execute(
                "INSERT INTO public.byom_game_facts (canonical_key, sport, "
                "season, week, away_team, home_team, lock_window_hours, "
                "near_window_hours, line_source) "
                "VALUES ('2024_01_BAL_KC', 'NFL', 2024, 1, 'BAL', 'KC', "
                "120, 24, 'test')")
        cur.execute("RESET ROLE")
        # A push and a tie are legal result values. A stake column is not.
        cur.execute("""
            INSERT INTO public.byom_game_facts (
              canonical_key, sport, season, week, away_team, home_team,
              lock_window_hours, near_window_hours, line_source,
              ats_home_result, ats_home_units, ml_home_result, ml_home_units)
            VALUES ('2024_01_BAL_KC', 'NFL', 2024, 1, 'BAL', 'KC',
                    120, 24, 'nfl_odds_history', 'push', 0, 'tie', 0)
        """)
        cur.execute(
            "SELECT ats_home_result, ml_home_result FROM public.byom_game_facts")
        assert cur.fetchone() == ("push", "tie")
    finally:
        if conn is not None:
            conn.close()
        cluster.stop()
