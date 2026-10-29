"""prop_side keeps one prop leg. A prop save requires it.

byom_backtest_prop_dk_prices_2026_10_28.sql counts the over and the
under together. This file is the next body. It is not in
ACTIVE_MIGRATIONS. Scratch Postgres is local. Nothing here writes
production.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SQL_NAME = "byom_prop_side_2026_10_28.sql"
USER = "11111111-1111-1111-1111-111111111111"


def test_the_prop_side_migration_is_not_registered():
    listed = (ROOT / "data/view_migrations.py").read_text(encoding="utf-8")
    assert SQL_NAME not in listed
    sql = (ROOT / "data/migrations" / SQL_NAME).read_text(encoding="utf-8")
    assert "DROP FUNCTION" not in sql
    assert "CREATE OR REPLACE FUNCTION public.byom_backtest" in sql
    assert "CREATE OR REPLACE FUNCTION public.byom_save_model" in sql
    assert "byom_backtest_v1" in sql
    assert "byom_prop_dk_prices" in sql
    assert "byom_prop_side" in sql
    assert "byom_saved_models_v1" in sql
    assert "NOT in data/view_migrations.ACTIVE_MIGRATIONS" in sql
    assert "p.over_price" in sql
    assert "p.under_price" in sql
    assert "'over'::text" in sql
    assert "'under'::text" in sql
    lowered = sql.lower()
    assert "insert into picks" not in lowered
    assert "mkt not in" not in lowered


def test_scratch_prop_side_keeps_one_leg_and_save_requires_it():
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
            "byom_prop_facts_dk_prices_2026_10_28.sql",
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
              'loss', 'win', -110, -110);
            INSERT INTO byom_prop_facts (
              prop_key, canonical_key, sport, season, week, player_name,
              team, market, line, line_basis, log_status,
              over_result, under_result, over_price, under_price)
            VALUES
              ('pass', '2026_01_BAL_KC', 'NFL', 2026, 1, 'Lamar Jackson', 'BAL',
               'player_pass_yds', 220.5, 'DraftKings line at game start', 'logged',
               'loss', 'win', -110, -110),
              ('td', '2026_01_BAL_KC', 'NFL', 2026, 1, 'Zay Flowers', 'BAL',
               'player_anytime_td', 0.5, 'DraftKings line at game start', 'logged',
               'loss', 'win', -150, NULL);
        """)

        def one(payload):
            cur.execute(
                """
                SELECT bets, wins, losses, pushes, ties, units, skipped
                  FROM byom_backtest(2026, %s::jsonb)
                """,
                (payload,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            bets, wins, losses, pushes, ties, units, skipped = row
            return (bets, wins, losses, pushes, ties, Decimal(str(units)), skipped)

        assert one('{"markets":["player_pass_yds"]}') == (
            2, 1, 1, 0, 0, Decimal("-0.1"), 0)
        assert one('{"markets":["player_pass_yds"],"prop_side":"over"}') == (
            1, 0, 1, 0, 0, Decimal("-1.1"), 0)
        assert one('{"markets":["player_pass_yds"],"prop_side":"under"}') == (
            1, 1, 0, 0, 0, Decimal("1"), 0)
        assert one('{"markets":["player_pass_yds"],"prop_side":"over","side":"away"}') == (
            1, 0, 1, 0, 0, Decimal("-1.1"), 0)
        assert one('{"markets":["player_pass_yds"],"prop_side":"over","side":"home"}') is None
        assert one('{"markets":["player_anytime_td"]}') == (
            1, 0, 1, 0, 0, Decimal("-1.5"), 1)
        assert one('{"markets":["player_anytime_td"],"prop_side":"over"}') == (
            1, 0, 1, 0, 0, Decimal("-1.5"), 0)
        assert one('{"markets":["totals"],"side":"over"}') == (
            1, 0, 1, 0, 0, Decimal("-1.1"), 0)
        with pytest.raises(psycopg2.errors.RaiseException, match="Choose over or under"):
            one('{"markets":["player_pass_yds"],"prop_side":"yes"}')

        cur.execute("SELECT set_config('byom.uid', %s, false)", (USER,))
        with pytest.raises(psycopg2.errors.RaiseException, match="Choose over or under"):
            cur.execute(
                "SELECT model_id FROM byom_save_model(%s, %s::jsonb, 2026)",
                ("yards", '{"markets":["player_pass_yds"]}'),
            )
        cur.execute(
            """
            SELECT model_id FROM byom_save_model(
              'yards over',
              '{"markets":["player_pass_yds"],"prop_side":"over","side":"away"}'::jsonb,
              2026)
            """
        )
        cur.fetchone()
        cur.execute(
            "SELECT filters FROM byom_models WHERE name = 'yards over'"
        )
        stored = cur.fetchone()[0]
        assert stored["markets"] == ["player_pass_yds"]
        assert stored["prop_side"] == "over"
        assert stored["side"] == "away"
        cur.execute(
            """
            SELECT model_id FROM byom_save_model(
              'dogs',
              '{"markets":["h2h"],"role":"underdog","prop_side":"over"}'::jsonb,
              2026)
            """
        )
        cur.fetchone()
        cur.execute("SELECT filters FROM byom_models WHERE name = 'dogs'")
        dogs = cur.fetchone()[0]
        assert dogs["role"] == "underdog"
        assert "prop_side" not in dogs
        cur.execute("SELECT prosrc FROM pg_proc WHERE proname = 'byom_backtest'")
        body = cur.fetchone()[0]
        assert "byom_backtest_v1" in body
        assert "byom_prop_side" in body
        assert "p.over_price" in body
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()
