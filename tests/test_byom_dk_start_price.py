"""DraftKings game-start prices, 1u-to-win units, and skipped unpriced bets.

The migration is not in ACTIVE_MIGRATIONS. Scratch Postgres is local.
Nothing here writes production.
"""
from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from byom.constants import LINE_BASIS
from byom.game_facts import assemble_game
from scripts.byom_game_facts import sports_requested
from tests.test_byom_game_facts import KICK, _game, _q

ROOT = Path(__file__).resolve().parents[1]
SQL_NAME = "byom_dk_start_price_2026_10_23.sql"
SQL = (ROOT / "data/migrations" / SQL_NAME).read_text(encoding="utf-8")


def _near(got, expected) -> None:
    assert abs(Decimal(str(got)) - Decimal(str(expected))) < Decimal("0.0000001")


def test_the_migration_is_hand_applied_and_the_refresh_stays_off():
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert SQL_NAME not in ACTIVE_MIGRATIONS
    assert "byom_facts_schema_2026_10_16.sql" in ACTIVE_MIGRATIONS
    assert "ADD COLUMN IF NOT EXISTS dk_ml_home_price" in SQL
    assert "ADD COLUMN IF NOT EXISTS dk_spread_away_price" in SQL
    assert "ADD COLUMN IF NOT EXISTS dk_total_under_price" in SQL
    assert "CREATE OR REPLACE FUNCTION public.byom_backtest" in SQL
    assert "DROP FUNCTION IF EXISTS public.byom_backtest(integer, jsonb)" in SQL
    assert "ALTER COLUMN week DROP NOT NULL" in SQL
    body = SQL.split("AS $body$", 1)[1]
    assert "byom_backtest_v1" in body
    assert "byom_dk_start_price" in body
    assert "unknown filter key" in body
    assert "anon 3s" in SQL and "authenticated 8s" in SQL
    assert "SET statement_timeout = '3s'" in SQL
    schema = (ROOT / "data/migrations" / "byom_facts_schema_2026_10_16.sql").read_text(
        encoding="utf-8")
    assert "dk_ml_home_price" not in schema
    assert not (ROOT / "data/migrations" / "byom_book_quotes_2026_10_21.sql").exists()
    declared = json.loads(
        (ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    refresh = next(row for row in declared if row["job_type"] == "byom_refresh")
    assert refresh["enabled"] is False
    assert refresh["args"]["apply"] is False
    assert sports_requested(None) == ["NFL"]
    assert sports_requested(["nba"]) == ["NBA"]
    assert sports_requested(["all"]) is None


def test_the_price_is_the_last_draftkings_quote_at_or_before_start():
    played = {"BAL": [], "KC": []}
    at_start = _q(0, "draftkings", "spreads", -3, home=-115, away=-105)
    after = _q(-0.25, "draftkings", "spreads", -14, home=-800, away=600)
    older = _q(5, "draftkings", "spreads", -2, home=-110, away=-110)
    other = _q(0, "fanduel", "spreads", -3, home=-101, away=-101)
    fact = assemble_game(_game(), [older, other, after, at_start], played)
    assert fact is not None
    assert fact["dk_spread_home"] == Decimal("-3")
    assert fact["dk_spread_home_price"] == Decimal("-115")
    assert fact["dk_spread_away_price"] == Decimal("-105")
    assert fact["line_basis"] == LINE_BASIS

    # A DraftKings line with no price does not take the other book's price.
    bare = _q(2, "draftkings", "spreads", -6)
    fanduel = _q(1, "fanduel", "spreads", -6, home=-105, away=-115)
    missing = assemble_game(_game(), [bare, fanduel], played)
    assert missing["dk_spread_home"] == Decimal("-6")
    assert missing["dk_spread_home_price"] is None
    assert missing["dk_spread_away_price"] is None
    assert missing["ats_home_result"] == "win"


def test_tie_break_is_created_at_then_id_then_line_text():
    played = {"BAL": [], "KC": []}
    early = _q(4, "draftkings", "spreads", -3, home=-200, away=170)
    late = _q(4, "draftkings", "spreads", -7, home=-110, away=-110)
    early["created_at"] = KICK - timedelta(hours=10)
    late["created_at"] = KICK - timedelta(hours=6)
    early["quote_id"] = 50
    late["quote_id"] = 1
    fact = assemble_game(_game(), [early, late], played)
    assert fact["dk_spread_home"] == Decimal("-7")
    assert fact["dk_spread_home_price"] == Decimal("-110")
    assert fact["dk_spread_away_price"] == Decimal("-110")

    low = _q(4, "draftkings", "totals", 47, home=-115, away=-105)
    high = _q(4, "draftkings", "totals", 44, home=-105, away=-115)
    stamp = KICK - timedelta(hours=8)
    low["created_at"] = stamp
    high["created_at"] = stamp
    low["quote_id"] = 2
    high["quote_id"] = 9
    fact = assemble_game(_game(), [low, high], played)
    assert fact["dk_total"] == Decimal("44")
    assert fact["dk_total_over_price"] == Decimal("-105")
    assert fact["dk_total_under_price"] == Decimal("-115")

    left = _q(4, "draftkings", "h2h", -3, home=-150, away=130)
    right = _q(4, "draftkings", "h2h", -4, home=-160, away=140)
    left["created_at"] = stamp
    right["created_at"] = stamp
    fact = assemble_game(_game(), [left, right], played)
    # No id. "-4" sorts after "-3", so that quote is the price.
    assert fact["dk_ml_home_price"] == Decimal("-160")
    assert fact["dk_ml_away_price"] == Decimal("140")


def test_scratch_units_skipped_shape_unknown_keys_and_a_non_nfl_game():
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
            CREATE TABLE games (
              game_id text PRIMARY KEY, sport text, season int, week int,
              game_date text, home_team text, away_team text,
              home_score numeric, away_score numeric, commence_time text);
            CREATE TABLE nfl_odds_history (
              snapshot_at timestamptz NOT NULL, game_id text NOT NULL,
              season smallint, week smallint, commence_time timestamptz,
              bookmaker text NOT NULL, market text NOT NULL,
              point numeric, price_home numeric, price_away numeric,
              lead_hours numeric,
              PRIMARY KEY (snapshot_at, game_id, bookmaker, market));
            CREATE TABLE odds (
              odds_id bigserial PRIMARY KEY, game_id text, sport text,
              market text, bookmaker text, snapshot_type text, snapshot_at text,
              home_price numeric, away_price numeric, spread_home numeric,
              total_line numeric, over_price numeric, under_price numeric,
              created_at text);
        """)
        schema = (ROOT / "data/migrations" / "byom_facts_schema_2026_10_16.sql").read_text(
            encoding="utf-8")
        cur.execute(schema)
        cur.execute(SQL)
        cur.execute(SQL)
        cur.execute("""
            INSERT INTO games (
              game_id, sport, season, week, game_date, home_team, away_team,
              home_score, away_score, commence_time)
            VALUES
              ('NBA_2026-01-15_BOS_NYK', 'NBA', 2026, NULL, '2026-01-15',
               'NYK', 'BOS', 110, 105, '2026-01-15T00:30:00Z'),
              ('NBA_2018-10-16_OKC_GSW', 'NBA', 2018, NULL, '2018-10-16',
               'GSW', 'OKC', 108, 100, '2018-10-17T02:00:00Z');
            INSERT INTO odds (
              game_id, sport, market, bookmaker, snapshot_type, snapshot_at,
              home_price, away_price, spread_home, over_price, under_price,
              total_line, created_at)
            VALUES
              ('NBA_2026-01-15_BOS_NYK', 'NBA', 'spreads', 'draftkings', 'open',
               '2026-01-15T00:00:00Z', -110, -110, -7, NULL, NULL, NULL,
               '2026-01-14T22:00:00Z'),
              ('NBA_2026-01-15_BOS_NYK', 'NBA', 'spreads', 'draftkings', 'open',
               '2026-01-15T00:00:00Z', -200, 170, -3.5, NULL, NULL, NULL,
               '2026-01-14T20:00:00Z'),
              ('NBA_2026-01-15_BOS_NYK', 'NBA', 'spreads', 'fanduel', 'open',
               '2026-01-15T00:00:00Z', -105, -115, -1, NULL, NULL, NULL,
               '2026-01-14T23:00:00Z'),
              ('NBA_2026-01-15_BOS_NYK', 'NBA', 'spreads', 'draftkings', 'in_play',
               '2026-01-15T00:20:00Z', -500, 400, -20, NULL, NULL, NULL,
               '2026-01-15T00:20:00Z'),
              ('NBA_2026-01-15_BOS_NYK', 'NBA', 'spreads', 'draftkings', 'open',
               '2026-01-15T01:00:00Z', -900, 700, -14, NULL, NULL, NULL,
               '2026-01-15T01:00:00Z'),
              ('NBA_2026-01-15_BOS_NYK', 'NBA', 'h2h', 'draftkings', 'open',
               '2026-01-14T18:00:00Z', -180, 155, NULL, NULL, NULL, NULL,
               '2026-01-14T18:00:00Z'),
              ('NBA_2026-01-15_BOS_NYK', 'NBA', 'totals', 'draftkings', 'open',
               '2026-01-14T18:00:00Z', NULL, NULL, NULL, -105, -115, 220.5,
               '2026-01-14T18:00:00Z'),
              ('NBA_2018-10-16_OKC_GSW', 'NBA', 'h2h', 'draftkings', 'open',
               '2018-10-17T01:00:00Z', -130, 110, NULL, NULL, NULL, NULL,
               '2018-10-16T18:00:00Z');
            INSERT INTO byom_game_facts (
              canonical_key, sport, season, week, away_team, home_team, line_basis,
              ats_home_result, ats_away_result,
              dk_spread_home_price, dk_spread_away_price,
              ou_over_result, ou_under_result,
              dk_total_over_price, dk_total_under_price,
              ml_home_result, ml_away_result,
              dk_ml_home_price, dk_ml_away_price,
              home_role, away_role, home_rest_days, away_rest_days, is_primetime)
            VALUES
              ('2026_01_BAL_KC', 'NFL', 2026, 1, 'BAL', 'KC',
               'DraftKings line at game start',
               'win', 'loss', 180, -110,
               'push', 'push', -105, -105,
               'win', 'loss', NULL, 150,
               'favorite', 'underdog', 7, 7, true),
              ('2026_02_DET_GB', 'NFL', 2026, 2, 'DET', 'GB',
               'DraftKings line at game start',
               'loss', 'win', NULL, NULL,
               NULL, NULL, NULL, NULL,
               'tie', 'tie', 100, -110,
               'favorite', 'underdog', 3, 10, false);
            INSERT INTO byom_prop_facts (
              prop_key, canonical_key, sport, season, week, player_name,
              team, market, line, line_basis, over_result, under_result,
              log_status)
            VALUES
              ('2026_01_BAL_KC|player_pass_yds|lamar jackson|220.5',
               '2026_01_BAL_KC', 'NFL', 2026, 1, 'Lamar Jackson', 'BAL',
               'player_pass_yds', 220.5, 'DraftKings line at game start',
               'win', 'loss', 'logged'),
              ('2026_01_BAL_KC|player_pass_yds|out|199.5',
               '2026_01_BAL_KC', 'NFL', 2026, 1, 'Did Not Play', 'BAL',
               'player_pass_yds', 199.5, 'DraftKings line at game start',
               NULL, NULL, 'non_participant');
        """)
        raw.autocommit = False

        class Conn:
            def execute(self, sql, params=None):
                c = raw.cursor()
                c.execute(sql, params)
                return c

            def executemany(self, sql, seq):
                c = raw.cursor()
                c.executemany(sql, seq)
                return c

            def commit(self):
                raw.commit()

        from byom.load import build_season

        conn = Conn()
        nba = build_season(conn, 2026, apply=True, sport="NBA")
        assert nba["written"] == 1
        old = build_season(conn, 2018, apply=True, sport="NBA")
        assert old["written"] == 1
        cur = raw.cursor()
        cur.execute("""
            SELECT week, dk_spread_home, dk_spread_home_price, dk_spread_away_price,
                   dk_ml_home_price, dk_ml_away_price,
                   dk_total_over_price, dk_total_under_price, dk_total
              FROM byom_game_facts
             WHERE canonical_key = 'NBA_2026-01-15_BOS_NYK'
        """)
        row = cur.fetchone()
        assert row[0] is None
        assert Decimal(str(row[1])) == Decimal("-7")
        assert Decimal(str(row[2])) == Decimal("-110")
        assert Decimal(str(row[3])) == Decimal("-110")
        assert Decimal(str(row[4])) == Decimal("-180")
        assert Decimal(str(row[5])) == Decimal("155")
        assert Decimal(str(row[6])) == Decimal("-105")
        assert Decimal(str(row[7])) == Decimal("-115")
        assert Decimal(str(row[8])) == Decimal("220.5")
        cur.execute("""
            SELECT dk_ml_home_price, dk_ml_away_price
              FROM byom_game_facts
             WHERE canonical_key = 'NBA_2018-10-16_OKC_GSW'
        """)
        early = cur.fetchone()
        assert Decimal(str(early[0])) == Decimal("-130")
        assert Decimal(str(early[1])) == Decimal("110")

        cur.execute("SET ROLE anon")
        cur.execute("""
            SELECT market, bets, wins, losses, pushes, ties, units, skipped
              FROM byom_backtest(2026, '{}'::jsonb)
             ORDER BY market
        """)
        names = [item[0] for item in cur.description]
        assert names == [
            "market", "bets", "wins", "losses", "pushes", "ties",
            "units", "skipped",
        ]
        rows = {row[0]: row for row in cur.fetchall()}
        spreads = rows["spreads"]
        assert spreads[1:][:5] == (2, 1, 1, 0, 0)
        _near(spreads[6], Decimal(1) + (Decimal("-110") / Decimal(100)))
        assert spreads[7] == 2
        totals = rows["totals"]
        assert totals[1] == 2 and totals[4] == 2 and totals[7] == 0
        _near(totals[6], 0)
        h2h = rows["h2h"]
        assert (h2h[1], h2h[2], h2h[3], h2h[5], h2h[7]) == (3, 0, 1, 2, 1)
        _near(h2h[6], -(Decimal(100) / Decimal(150)))
        props = rows["player_pass_yds"]
        assert props[1:][:5] == (2, 1, 1, 0, 0)
        _near(props[6], 0)
        assert props[7] == 0
        cur.execute("""
            SELECT bets, wins, units, skipped
              FROM byom_backtest(2026, '{"markets":["spreads"],"side":"home",
                                         "role":"favorite"}'::jsonb)
        """)
        home_fav = cur.fetchone()
        assert home_fav[0] == 1 and home_fav[1] == 1 and home_fav[3] == 1
        _near(home_fav[2], 1)
        with pytest.raises(psycopg2.Error) as exc:
            cur.execute("""
                SELECT * FROM byom_backtest(2026, '{"stake": 1}'::jsonb)
            """)
        assert "unknown filter key: stake" in str(exc.value)
        raw.rollback()
        cur.execute("RESET ROLE")
        cur.execute("""
            SELECT prosrc, proconfig::text
              FROM pg_proc WHERE proname = 'byom_backtest'
        """)
        body, config = cur.fetchone()
        assert "byom_backtest_v1" in body
        assert "byom_dk_start_price" in body
        assert "statement_timeout=3s" in config
        assert "SECURITY INVOKER" in SQL
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()
