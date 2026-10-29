"""Phase A prop filters. The migration is hand-applied. Scratch Postgres
grades the new keys. Nothing here writes production.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SQL_NAME = "byom_prop_phase_a_filters_2026_10_29.sql"


def test_phase_a_migration_is_hand_applied():
    listed = (ROOT / "data/view_migrations.py").read_text(encoding="utf-8")
    assert SQL_NAME not in listed
    text = (ROOT / "data/migrations" / SQL_NAME).read_text(encoding="utf-8")
    assert "byom_prop_phase_a" in text
    assert "byom_backtest_v1" in text
    assert "kick_hour >= 19" in text
    assert "kick_hour < 14" in text
    assert "byom_player_names" in text
    assert "NOT in data/view_migrations.ACTIVE_MIGRATIONS" in text
    assert "thin sample" not in text.lower()


def test_scratch_phase_a_filters_narrow_the_same_stake():
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
        )
        for name in names:
            cur.execute((ROOT / "data/migrations" / name).read_text(encoding="utf-8"))
        cur.execute("""
            INSERT INTO byom_game_facts (
              canonical_key, sport, season, week, away_team, home_team,
              game_date, commence_time, line_basis,
              home_score, away_score, dk_spread_home, dk_total,
              home_rest_days, away_rest_days, home_role, away_role, is_primetime,
              ou_over_result, ou_under_result, dk_total_over_price, dk_total_under_price)
            VALUES
              ('sun', 'NFL', 2026, 1, 'BAL', 'KC',
               '2026-09-13', '2026-09-13 17:05:00+00',
               'DraftKings line at game start',
               24, 20, -3.5, 45.5,
               7, 4, 'favorite', 'underdog', false,
               'loss', 'win', -110, -110),
              ('thu', 'NFL', 2026, 1, 'CLE', 'CIN',
               '2026-09-10', '2026-09-10 17:00:00+00',
               'DraftKings line at game start',
               21, 17, -2.5, 47.5,
               7, 7, 'favorite', 'underdog', true,
               'win', 'loss', -110, -110);
            INSERT INTO byom_prop_facts (
              prop_key, canonical_key, sport, season, week, player_name,
              team, market, line, line_basis, log_status,
              over_result, under_result, over_price, under_price)
            VALUES
              ('lamar', 'sun', 'NFL', 2026, 1, 'Lamar Jackson', 'BAL',
               'player_pass_yds', 220.5, 'DraftKings line at game start', 'logged',
               'loss', 'win', -110, -110),
              ('mahomes', 'sun', 'NFL', 2026, 1, 'Patrick Mahomes', 'KC',
               'player_pass_yds', 300.5, 'DraftKings line at game start', 'logged',
               'win', 'loss', 120, -140),
              ('burrow', 'thu', 'NFL', 2026, 1, 'Joe Burrow', 'CIN',
               'player_pass_yds', 250.5, 'DraftKings line at game start', 'logged',
               'win', 'loss', -110, -110);
        """)

        def bets(payload):
            cur.execute(
                "SELECT bets, units FROM byom_backtest(2026, %s::jsonb)",
                (payload,),
            )
            rows = cur.fetchall()
            if not rows:
                return (0, Decimal("0"))
            total_bets = sum(row[0] for row in rows)
            total_units = sum(Decimal(str(row[1])) for row in rows)
            return (total_bets, total_units)

        over = '{"markets":["player_pass_yds"],"prop_side":"over"}'
        assert bets(over) == (3, Decimal("0.9"))
        assert bets(over[:-1] + ',"min_line":200,"max_line":240}') == (1, Decimal("-1.1"))
        assert bets(over[:-1] + ',"min_price":101}') == (1, Decimal("1"))
        assert bets(over[:-1] + ',"role":"underdog"}') == (1, Decimal("-1.1"))
        assert bets(over[:-1] + ',"opponents":["KC"]}') == (1, Decimal("-1.1"))
        assert bets(over[:-1] + ',"side":"away"}') == (1, Decimal("-1.1"))
        assert bets(over[:-1] + ',"side":"home"}')[0] == 2
        assert bets(over[:-1] + ',"kick_slots":["early"]}')[0] == 3
        assert bets(over[:-1] + ',"kick_slots":["prime"]}')[0] == 0
        assert bets(over[:-1] + ',"primetime":true}') == (1, Decimal("1"))
        assert bets(over[:-1] + ',"months":[9]}')[0] == 3
        assert bets(over[:-1] + ',"months":[10]}')[0] == 0
        assert bets(over[:-1] + ',"weekdays":[0]}')[0] == 2
        assert bets(over[:-1] + ',"weekdays":[4]}')[0] == 1
        assert bets(over[:-1] + ',"player":"Lamar Jackson"}') == (1, Decimal("-1.1"))
        assert bets(over[:-1] + ',"max_rest_days":6}') == (1, Decimal("-1.1"))
        assert bets(over[:-1] + ',"min_team_spread":0,"max_team_spread":10}') == (1, Decimal("-1.1"))
        assert bets(over[:-1] + ',"min_game_total":46,"max_game_total":50}') == (1, Decimal("1"))
        assert bets('{"markets":["totals"],"side":"over"}')[0] == 2
        with pytest.raises(psycopg2.errors.RaiseException, match="unknown filter key: stake"):
            bets('{"markets":["player_pass_yds"],"prop_side":"over","stake":1}')

        cur.execute("SELECT set_config('byom.uid', %s, false)", (
            "11111111-1111-1111-1111-111111111111",))
        cur.execute(
            """
            SELECT model_id FROM byom_save_model(
              'line band',
              '{"markets":["player_pass_yds"],"prop_side":"over","min_line":200,"max_line":240}'::jsonb,
              2026)
            """
        )
        cur.fetchone()
        cur.execute("SELECT filters FROM byom_models WHERE name = 'line band'")
        stored = cur.fetchone()[0]
        assert stored["min_line"] == 200
        assert stored["max_line"] == 240
        with pytest.raises(psycopg2.errors.RaiseException, match="price, line, and stake filters are not accepted"):
            cur.execute(
                """
                SELECT model_id FROM byom_save_model(
                  'stake',
                  '{"markets":["player_pass_yds"],"prop_side":"over","stake":1}'::jsonb,
                  2026)
                """
            )
        cur.execute("SELECT player_name FROM byom_player_names('NFL', 'lam')")
        assert cur.fetchall() == [("Lamar Jackson",)]
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()
