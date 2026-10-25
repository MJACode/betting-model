"""Forward migration: total legs are over and under, and save refuses a missing side.

byom_dk_price_fallback_2026_10_23.sql is applied in production as version
20261023225630. byom_saved_models_2026_10_16.sql is applied as version
20261023222927. Neither file is edited here. The new file is not in
ACTIVE_MIGRATIONS. Scratch Postgres is local. Nothing here writes production.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SQL_NAME = "byom_total_side_2026_10_25.sql"
USER = "11111111-1111-1111-1111-111111111111"


def test_the_forward_migration_is_not_registered():
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert SQL_NAME not in ACTIVE_MIGRATIONS
    sql = (ROOT / "data/migrations" / SQL_NAME).read_text(encoding="utf-8")
    assert "DROP FUNCTION" not in sql
    assert "CREATE OR REPLACE FUNCTION public.byom_backtest" in sql
    assert "CREATE OR REPLACE FUNCTION public.byom_save_model" in sql
    assert "byom_list_models" not in sql
    lowered = sql.lower()
    assert "insert into picks" not in lowered


def test_scratch_total_legs_match_a_saved_side_and_a_missing_side_is_refused():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")

    cluster = ScratchPostgres()
    raw = None
    try:
        raw = psycopg2.connect(cluster.start())
        raw.autocommit = True
        cur = raw.cursor()
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
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS auth;
            CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
            LANGUAGE sql STABLE AS $$
              SELECT NULLIF(current_setting('byom.uid', true), '')::uuid
            $$;
            GRANT USAGE ON SCHEMA auth TO anon, authenticated;
            GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated;
        """)
        names = (
            "byom_facts_schema_2026_10_16.sql",
            "byom_dk_start_price_2026_10_23.sql",
            "byom_saved_models_2026_10_16.sql",
            SQL_NAME,
            SQL_NAME,
        )
        for name in names:
            cur.execute((ROOT / "data/migrations" / name).read_text(encoding="utf-8"))
        cur.execute("""
            INSERT INTO byom_game_facts (
              canonical_key, sport, season, week, away_team, home_team,
              line_basis, home_score, away_score, dk_total,
              ou_over_result, ou_under_result,
              dk_total_over_price, dk_total_under_price)
            VALUES (
              '2026_01_BAL_KC', 'NFL', 2026, 1, 'BAL', 'KC',
              'DraftKings line at game start', 24, 20, 45.5,
              'loss', 'win', -110, -110)
        """)
        cur.execute("""
            SELECT bets, wins, losses
              FROM byom_backtest(2026, '{"markets":["totals"]}'::jsonb)
        """)
        assert cur.fetchone() == (2, 1, 1)
        cur.execute("""
            SELECT bets, wins, losses
              FROM byom_backtest(2026, '{"markets":["totals"],"side":"over"}'::jsonb)
        """)
        assert cur.fetchone() == (1, 0, 1)
        cur.execute("""
            SELECT bets, wins, losses
              FROM byom_backtest(2026, '{"markets":["totals"],"side":"under"}'::jsonb)
        """)
        assert cur.fetchone() == (1, 1, 0)

        cur.execute("SELECT set_config('byom.uid', %s, false)", (USER,))
        for name, payload, match in (
            ("ml any", '{"markets":["h2h"]}', "Choose a team"),
            ("spread any", '{"markets":["spreads"]}', "Choose a team"),
            ("both totals", '{"markets":["totals"]}', "Choose over or under"),
        ):
            with pytest.raises(psycopg2.errors.RaiseException, match=match):
                cur.execute(
                    "SELECT model_id FROM byom_save_model(%s, %s::jsonb, 2026)",
                    (name, payload))
        cur.execute("""
            SELECT model_id FROM byom_save_model(
              'dogs', '{"markets":["h2h"],"role":"underdog"}'::jsonb, 2026)
        """)
        cur.fetchone()
        cur.execute("""
            SELECT model_id FROM byom_save_model(
              'overs', '{"markets":["totals"],"side":"over"}'::jsonb, 2026)
        """)
        cur.fetchone()
        cur.execute("SELECT filters->>'side' FROM byom_models WHERE name = 'overs'")
        assert cur.fetchone()[0] == "over"
        cur.execute("""
            SELECT model_id FROM byom_save_model(
              'both markets', '{"markets":["h2h","spreads"]}'::jsonb, 2026)
        """)
        cur.fetchone()
        cur.execute("SELECT model_id FROM byom_save_model('empty', '{}'::jsonb, 2026)")
        cur.fetchone()

        for name in (
            "byom_saved_models_2026_10_16.sql",
            "byom_backtest_rpc_2026_10_16.sql",
        ):
            cur.execute((ROOT / "data/migrations" / name).read_text(encoding="utf-8"))
        cur.execute("SELECT prosrc FROM pg_proc WHERE proname = 'byom_backtest'")
        backtest = cur.fetchone()[0]
        assert "byom_backtest_v1" in backtest
        assert "'over'" in backtest
        cur.execute("SELECT prosrc FROM pg_proc WHERE proname = 'byom_save_model'")
        save = cur.fetchone()[0]
        assert "byom_saved_models_v1" in save
        assert "Choose a team, or a favorite or underdog." in save
        assert "Choose over or under." in save
        with pytest.raises(psycopg2.errors.RaiseException, match="Choose over or under"):
            cur.execute("""
                SELECT model_id FROM byom_save_model(
                  'still both', '{"markets":["totals"]}'::jsonb, 2026)
            """)
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()
