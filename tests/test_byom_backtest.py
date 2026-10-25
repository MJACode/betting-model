"""byom_backtest: current season, win/loss/push counts, no price filter.

The migration is unapplied on production. Scratch Postgres is local.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from byom.season import current_nfl_season

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "data/migrations/byom_backtest_rpc_2026_10_16.sql").read_text(
    encoding="utf-8")


def _code(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def test_the_season_label_is_the_year_the_season_starts():
    assert current_nfl_season(date(2026, 10, 16)) == 2026
    assert current_nfl_season(date(2027, 2, 1)) == 2026
    assert current_nfl_season(date(2026, 8, 1)) == 2025


def test_the_function_is_invoker_and_has_no_price_or_line_filter():
    from data.anon_readable import RPC_ANON_CALLABLE
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert "byom_backtest_rpc_2026_10_16.sql" in ACTIVE_MIGRATIONS
    assert "byom_backtest" in RPC_ANON_CALLABLE
    code = _code(SQL)
    assert "SECURITY INVOKER" in code
    assert "byom_backtest_v1" in SQL
    assert "units_uncapped" not in code
    assert "units_capped" not in code
    assert "wins bigint" in code
    assert "pushes bigint" in code
    lowered = code.lower()
    for banned in ("minodds", "maxodds", "minline", "maxline", "spread_size",
                   "price_band", "kelly", "stake", "public.picks"):
        assert banned not in lowered, banned
    assert code.index("RETURN;") < code.index("CREATE OR REPLACE FUNCTION")
    assert "SET statement_timeout = '3s'" in code
    assert "in-function 3s timeout does not apply" in SQL
    assert "anon 3s" in SQL and "authenticated 8s" in SQL
    assert "v_month >= 9" in code
    assert "v_season := v_year - 1" in code
    assert "America/New_York" in code
    assert "empty filter" in SQL.lower() or "An empty filter" in SQL


def test_scratch_backtest_defaults_to_the_current_season_and_filters():
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
        for name in ("byom_facts_schema_2026_10_16.sql",
                     "byom_backtest_rpc_2026_10_16.sql"):
            text = (ROOT / "data/migrations" / name).read_text(encoding="utf-8")
            cur.execute(text)
            cur.execute(text)
        cur.execute("""
            INSERT INTO byom_game_facts (
              canonical_key, sport, season, week, away_team, home_team,
              line_basis,
              ats_home_result, ats_away_result,
              home_role, away_role, home_rest_days, away_rest_days,
              is_primetime)
            VALUES
              ('2026_01_BAL_KC', 'NFL', 2026, 1, 'BAL', 'KC',
               'DraftKings line at game start',
               'win', 'loss',
               'favorite', 'underdog', 7, 7, true),
              ('2025_01_BUF_NYJ', 'NFL', 2025, 1, 'BUF', 'NYJ',
               'DraftKings line at game start',
               'win', 'loss',
               'favorite', 'underdog', 10, 10, false);
            INSERT INTO byom_prop_facts (
              prop_key, canonical_key, sport, season, week, player_name,
              team, market, line, line_basis,
              over_result, under_result)
            VALUES
              ('2026_01_BAL_KC|player_pass_yds|lamar jackson|220.5',
               '2026_01_BAL_KC', 'NFL', 2026, 1, 'Lamar Jackson', 'BAL',
               'player_pass_yds', 220.5, 'DraftKings line at game start',
               'loss', 'win');
        """)
        cur.execute("SET statement_timeout = '3s'")
        cur.execute("SET ROLE anon")
        cur.execute("SELECT market, bets, wins, losses, pushes, ties "
                    "FROM byom_backtest(NULL, '{}'::jsonb) ORDER BY market")
        rows = cur.fetchall()
        markets = {row[0]: row for row in rows}
        assert "2025" not in str(rows)
        assert markets["spreads"][1] == 2
        assert markets["spreads"][2] == 1
        assert markets["spreads"][3] == 1
        assert markets["player_pass_yds"][1] == 2
        assert markets["player_pass_yds"][2] == 1
        assert markets["player_pass_yds"][3] == 1
        cur.execute("""
            SELECT coalesce(sum(bets), 0)
              FROM byom_backtest(2026, '{"role":"favorite","side":"home"}'::jsonb)
        """)
        assert cur.fetchone()[0] == 1
        cur.execute("""
            SELECT coalesce(sum(wins), 0), coalesce(sum(losses), 0)
              FROM byom_backtest(2025, '{}'::jsonb)
        """)
        prior = cur.fetchone()
        assert prior[0] == 1 and prior[1] == 1
        cur.execute("RESET ROLE")
        cur.execute("""
            UPDATE byom_game_facts SET
              ml_home_result = 'win',
              ml_away_result = 'loss',
              ou_over_result = 'loss',
              ou_under_result = 'win'
             WHERE canonical_key = '2026_01_BAL_KC'
        """)
        cur.execute("""
            INSERT INTO byom_game_facts (
              canonical_key, sport, season, week, away_team, home_team,
              line_basis,
              ats_home_result, ats_away_result,
              home_role, away_role, home_rest_days, away_rest_days,
              is_primetime)
            VALUES
              ('2026_02_DET_GB', 'NFL', 2026, 2, 'DET', 'GB',
               'DraftKings line at game start',
               'loss', 'win',
               'favorite', 'underdog', 3, 10, false)
        """)
        cur.execute("SET ROLE anon")
        cur.execute("""
            SELECT bets, wins, losses
              FROM byom_backtest(2026, '{"markets":["totals"]}'::jsonb)
        """)
        totals = cur.fetchone()
        assert totals[0] == 2
        assert totals[1] == 1
        assert totals[2] == 1
        cur.execute("""
            SELECT bets, wins, losses
              FROM byom_backtest(2026, '{"markets":["totals"],"side":"over"}'::jsonb)
        """)
        over = cur.fetchone()
        assert over == (1, 0, 1)
        cur.execute("""
            SELECT bets, wins, losses
              FROM byom_backtest(2026, '{"markets":["totals"],"side":"under"}'::jsonb)
        """)
        under = cur.fetchone()
        assert under == (1, 1, 0)
        cur.execute("""
            SELECT coalesce(sum(bets), 0)
              FROM byom_backtest(2026, '{"markets":["h2h"]}'::jsonb)
        """)
        assert cur.fetchone()[0] == 2
        cur.execute("""
            SELECT coalesce(sum(bets), 0)
              FROM byom_backtest(2026, '{"markets":["spreads"],"weeks":[1]}'::jsonb)
        """)
        assert cur.fetchone()[0] == 2
        cur.execute("""
            SELECT coalesce(sum(bets), 0)
              FROM byom_backtest(2026, '{"markets":["spreads"],"weeks":[2]}'::jsonb)
        """)
        assert cur.fetchone()[0] == 2
        cur.execute("""
            SELECT coalesce(sum(bets), 0)
              FROM byom_backtest(2026,
                '{"markets":["spreads"],"primetime":true}'::jsonb)
        """)
        assert cur.fetchone()[0] == 2
        cur.execute("""
            SELECT coalesce(sum(bets), 0)
              FROM byom_backtest(2026,
                '{"markets":["spreads"],"primetime":false}'::jsonb)
        """)
        assert cur.fetchone()[0] == 2
        cur.execute("""
            SELECT coalesce(sum(bets), 0)
              FROM byom_backtest(2026,
                '{"role":"underdog","min_rest_days":7,"markets":["spreads"]}'::jsonb)
        """)
        assert cur.fetchone()[0] == 2
        cur.execute("""
            SELECT coalesce(sum(bets), 0)
              FROM byom_backtest(2026,
                '{"side":"away","markets":["player_pass_yds"]}'::jsonb)
        """)
        assert cur.fetchone()[0] == 2
        cur.execute("""
            SELECT coalesce(sum(bets), 0)
              FROM byom_backtest(2026,
                '{"side":"home","markets":["player_pass_yds"]}'::jsonb)
        """)
        assert cur.fetchone()[0] == 0
        cur.execute("""
            SELECT prosrc, proconfig::text
              FROM pg_proc WHERE proname = 'byom_backtest'
        """)
        body, config = cur.fetchone()
        assert "byom_backtest_v1" in body
        assert "statement_timeout=3s" in config
        for year, month, day in (
                (2026, 9, 1), (2026, 10, 16), (2026, 8, 31), (2027, 2, 1)):
            stamp = f"{year:04d}-{month:02d}-{day:02d}T16:00:00Z"
            cur.execute("""
                SELECT CASE
                         WHEN EXTRACT(MONTH FROM (%s::timestamptz
                              AT TIME ZONE 'America/New_York'))::int >= 9
                         THEN EXTRACT(YEAR FROM (%s::timestamptz
                              AT TIME ZONE 'America/New_York'))::int
                         ELSE EXTRACT(YEAR FROM (%s::timestamptz
                              AT TIME ZONE 'America/New_York'))::int - 1
                       END
            """, (stamp, stamp, stamp))
            assert cur.fetchone()[0] == current_nfl_season(date(year, month, day))
        cur.execute("RESET ROLE")
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()
