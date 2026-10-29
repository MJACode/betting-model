"""NBA prop facts: fourteen markets, DK price on the same quote, yes-only doubles.

Pure tests always run. The scratch cluster is local. Nothing here writes
production. The migration is not in ACTIVE_MIGRATIONS.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from byom.prop_facts import (
    DOUBLE_DOUBLE_MARKET,
    LINE_BASIS,
    NBA_MARKET_COLUMNS,
    TRIPLE_DOUBLE_MARKET,
    facts_for_game,
    is_standard_market,
)
from byom.season import current_nba_season

ROOT = Path(__file__).resolve().parents[1]
SQL_NAME = "byom_nba_props_2026_10_29.sql"
KICK = datetime(2024, 10, 22, 23, 30, tzinfo=timezone.utc)
USER = "11111111-1111-1111-1111-111111111111"


def _game(played=True):
    return {
        "game_id": "NBA_2024-10-22_BOS_NYK",
        "sport": "NBA",
        "season": 2025,
        "home_score": 110 if played else None,
        "away_score": 104 if played else None,
        "game_date": "2024-10-22",
        "commence_time": KICK,
        "home_team": "NYK",
        "away_team": "BOS",
    }


def _q(name, market, book, hours, line, over, under, team="NYK"):
    return {
        "player_name": name,
        "team": team,
        "market": market,
        "bookmaker": book,
        "snapshot_at": KICK - timedelta(hours=hours),
        "commence_time": KICK,
        "point": None if line is None else Decimal(str(line)),
        "over_price": None if over is None else Decimal(str(over)),
        "under_price": None if under is None else Decimal(str(under)),
    }


def _log(**stats):
    row = {
        "player_name": "Jalen Brunson",
        "team": "NYK",
        "points": 32,
        "rebounds": 4,
        "assists": 11,
        "steals": 1,
        "blocks": 0,
        "turnovers": 3,
        "fg3_made": 4,
    }
    row.update(stats)
    return row


def _one(facts, market, name="Jalen Brunson"):
    hits = [f for f in facts if f["market"] == market and name.lower() in f["player_key"]]
    assert len(hits) == 1, hits
    return hits[0]


def test_nba_season_is_the_ending_year():
    from datetime import date
    assert current_nba_season(date(2026, 10, 29)) == 2027
    assert current_nba_season(date(2027, 1, 15)) == 2027
    assert current_nba_season(date(2026, 9, 15)) == 2026
    assert len(NBA_MARKET_COLUMNS) == 14


def test_the_nba_migration_is_not_registered_and_does_not_drop():
    listed = (ROOT / "data/view_migrations.py").read_text(encoding="utf-8")
    assert SQL_NAME not in listed
    sql = (ROOT / "data/migrations" / SQL_NAME).read_text(encoding="utf-8")
    assert "DROP FUNCTION" not in sql
    assert "ALTER TABLE public.byom_prop_facts ALTER COLUMN week DROP NOT NULL" in sql
    assert "byom_nba_props" in sql
    assert "byom_backtest_v1" in sql
    assert "byom_prop_side" in sql
    assert "NOT in data/view_migrations.ACTIVE_MIGRATIONS" in sql
    assert "player_double_double" in sql
    assert "player_triple_double" in sql
    assert "unknown sport" in sql
    lowered = sql.lower()
    assert "insert into picks" not in lowered
    from tracking.job_queue import _validate_byom_prop_facts
    assert _validate_byom_prop_facts({"sport": "NBA"})["sport"] == "NBA"
    assert _validate_byom_prop_facts({})["sport"] == "NFL"
    with pytest.raises(ValueError):
        _validate_byom_prop_facts({"sport": "MLB"})
    declared = json.loads((ROOT / "jobs/declared_jobs.json").read_text(encoding="utf-8"))
    nba_jobs = [e for e in declared if e.get("args", {}).get("sport") == "NBA"
                and e.get("job_type") == "byom_prop_facts"]
    assert len(nba_jobs) == 1
    assert nba_jobs[0]["key"] == "byom-nba-prop-facts"
    assert nba_jobs[0]["enabled"] is False
    assert nba_jobs[0]["args"]["apply"] is False
    assert "byom_nba_props_2026_10_29.sql" in nba_jobs[0]["note"]
    game = [e for e in declared if e.get("key") == "byom-nba-game-facts"]
    assert len(game) == 1
    assert game[0]["enabled"] is False
    assert game[0]["job_type"] == "byom_game_facts"
    assert game[0]["args"] == {"sport": "NBA", "apply": False}


def test_alt_ladders_and_other_books_are_not_nba_facts():
    assert is_standard_market("player_points")
    assert not is_standard_market("player_points_alternate")
    facts = facts_for_game(_game(), [
        _q("Jalen Brunson", "player_points_alternate", "draftkings", 2, 40.5, -110, -110),
        _q("Jalen Brunson", "player_points", "fanduel", 1, 30.5, -105, -115),
        _q("Jalen Brunson", "player_points", "draftkings", 3, 27.5, -115, -105),
    ], [_log()])
    fact = _one(facts, "player_points")
    assert fact["line"] == Decimal("27.5")
    assert fact["over_price"] == Decimal("-115")
    assert fact["under_price"] == Decimal("-105")
    assert fact["sport"] == "NBA"
    assert fact["week"] is None
    assert fact["canonical_key"] == "NBA_2024-10-22_BOS_NYK"
    assert fact["line_basis"] == LINE_BASIS


def test_points_pra_and_yes_only_doubles_grade_the_log():
    facts = facts_for_game(_game(), [
        _q("Jalen Brunson", "player_points", "draftkings", 2, 27.5, -115, -105),
        _q("Jalen Brunson", "player_points_rebounds_assists", "draftkings", 2, 44.5, -110, -110),
        _q("Jalen Brunson", "player_threes", "draftkings", 2, 3.5, -120, 100),
        _q("Jalen Brunson", DOUBLE_DOUBLE_MARKET, "draftkings", 2, None, -150, None),
        _q("Jalen Brunson", TRIPLE_DOUBLE_MARKET, "draftkings", 2, None, 220, None),
        _q("Jalen Brunson", "player_points", "draftkings", 2, None, -110, -110),
    ], [_log()])
    points = _one(facts, "player_points")
    assert points["actual"] == Decimal("32")
    assert points["over_result"] == "win"
    assert points["under_result"] == "loss"
    pra = _one(facts, "player_points_rebounds_assists")
    assert pra["actual"] == Decimal("47")
    assert pra["over_result"] == "win"
    threes = _one(facts, "player_threes")
    assert threes["actual"] == Decimal("4")
    assert threes["over_result"] == "win"
    double = _one(facts, DOUBLE_DOUBLE_MARKET)
    assert double["line"] == Decimal("0.5")
    assert double["actual"] == Decimal("1")
    assert double["over_result"] == "win"
    assert double["under_price"] is None
    triple = _one(facts, TRIPLE_DOUBLE_MARKET)
    assert triple["actual"] == Decimal("0")
    assert triple["over_result"] == "loss"
    assert len([f for f in facts if f["market"] == "player_points"]) == 1


def test_a_player_who_did_not_play_stays_ungraded():
    facts = facts_for_game(_game(), [
        _q("Josh Hart", "player_rebounds", "draftkings", 2, 7.5, -110, -110),
    ], [_log()])
    fact = _one(facts, "player_rebounds", "Josh Hart")
    assert fact["log_status"] == "non_participant"
    assert fact["actual"] is None
    assert fact["over_result"] is None
    assert fact["under_result"] is None


def test_a_counting_market_with_no_line_is_not_a_fact():
    facts = facts_for_game(_game(), [
        _q("Jalen Brunson", "player_rebounds", "draftkings", 2, None, -110, -110),
    ], [_log()])
    assert facts == []


def test_scratch_nba_backtest_is_its_own_sport_and_save_stores_it():
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
            "byom_prop_side_2026_10_28.sql",
            SQL_NAME,
        )
        for name in names:
            cur.execute((ROOT / "data/migrations" / name).read_text(encoding="utf-8"))
        cur.execute("""
            INSERT INTO byom_game_facts (
              canonical_key, sport, season, week, away_team, home_team,
              line_basis, home_score, away_score,
              home_rest_days, away_rest_days)
            VALUES
              ('2026_01_BAL_KC', 'NFL', 2026, 1, 'BAL', 'KC',
               'DraftKings line at game start', 24, 20, 7, 7),
              ('NBA_2026-10-22_BOS_NYK', 'NBA', 2027, NULL, 'BOS', 'NYK',
               'DraftKings line at game start', 110, 104, 1, 4);
            INSERT INTO byom_prop_facts (
              prop_key, canonical_key, sport, season, week, player_name,
              team, market, line, line_basis, log_status,
              over_result, under_result, over_price, under_price)
            VALUES
              ('nfl', '2026_01_BAL_KC', 'NFL', 2026, 1, 'Lamar Jackson', 'BAL',
               'player_pass_yds', 220.5, 'DraftKings line at game start', 'logged',
               'loss', 'win', -110, -110),
              ('home', 'NBA_2026-10-22_BOS_NYK', 'NBA', 2027, NULL, 'Jalen Brunson', 'NYK',
               'player_points', 27.5, 'DraftKings line at game start', 'logged',
               'win', 'loss', -115, -105),
              ('away', 'NBA_2026-10-22_BOS_NYK', 'NBA', 2027, NULL, 'Jayson Tatum', 'BOS',
               'player_points', 26.5, 'DraftKings line at game start', 'logged',
               'loss', 'win', -110, -110);
        """)

        def one(season, payload):
            cur.execute(
                """
                SELECT bets, wins, losses, pushes, ties, units, skipped
                  FROM byom_backtest(%s, %s::jsonb)
                """,
                (season, payload),
            )
            row = cur.fetchone()
            if row is None:
                return None
            bets, wins, losses, pushes, ties, units, skipped = row
            return (bets, wins, losses, pushes, ties, Decimal(str(units)), skipped)

        assert one(2026, '{"markets":["player_pass_yds"],"prop_side":"over"}') == (
            1, 0, 1, 0, 0, Decimal("-1.1"), 0)
        assert one(2027, '{"markets":["player_points"],"prop_side":"over"}') is None
        assert one(2027, '{"markets":["player_points"],"prop_side":"over","sport":"NBA"}') == (
            2, 1, 1, 0, 0, Decimal("-0.1"), 0)
        b2b = one(
            2027,
            '{"markets":["player_points"],"prop_side":"over","sport":"NBA",'
            '"min_rest_days":1,"max_rest_days":1}',
        )
        assert b2b == (1, 1, 0, 0, 0, Decimal("1"), 0)
        rested = one(
            2027,
            '{"markets":["player_points"],"prop_side":"over","sport":"NBA","min_rest_days":2}',
        )
        assert rested == (1, 0, 1, 0, 0, Decimal("-1.1"), 0)
        with pytest.raises(psycopg2.errors.RaiseException, match="unknown sport"):
            one(2027, '{"markets":["player_points"],"sport":"MLB"}')

        cur.execute("SELECT set_config('byom.uid', %s, false)", (USER,))
        with pytest.raises(psycopg2.errors.RaiseException, match="Choose over or under"):
            cur.execute(
                "SELECT model_id FROM byom_save_model(%s, %s::jsonb, 2027)",
                ("dd", '{"markets":["player_double_double"],"sport":"NBA"}'),
            )
        cur.execute(
            """
            SELECT model_id FROM byom_save_model(
              'points over',
              '{"markets":["player_points"],"prop_side":"over","sport":"NBA"}'::jsonb,
              2027)
            """
        )
        cur.fetchone()
        cur.execute(
            "SELECT sport, filters FROM byom_models WHERE name = 'points over'"
        )
        sport, stored = cur.fetchone()
        assert sport == "NBA"
        assert stored["markets"] == ["player_points"]
        assert stored["prop_side"] == "over"
        assert "sport" not in stored
        cur.execute(
            """
            SELECT model_id FROM byom_save_model(
              'yes',
              '{"markets":["player_double_double"],"prop_side":"over","sport":"NBA"}'::jsonb,
              2027)
            """
        )
        cur.fetchone()
        cur.execute("SELECT sport FROM byom_models WHERE name = 'yes'")
        assert cur.fetchone()[0] == "NBA"
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()
