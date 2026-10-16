"""Incremental refresh: due games only, freshness reads no odds.

The declared job ships enabled false and apply false. Nothing here
writes production.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 16)
BOOKS = ["draftkings"]


def test_the_job_ships_disabled_and_does_not_write_by_default():
    from tracking.job_queue import JOBS, _validate_byom_refresh

    assert "byom_refresh" in JOBS
    assert _validate_byom_refresh({}) == {"sport": "NFL", "apply": False}
    with pytest.raises(ValueError):
        _validate_byom_refresh({"sport": "NBA"})
    with pytest.raises(ValueError):
        _validate_byom_refresh({"apply": "yes"})
    declared = json.loads(
        (ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    found = [entry for entry in declared if entry["job_type"] == "byom_refresh"]
    assert len(found) == 1
    assert found[0]["key"] == "byom-nfl-refresh"
    assert found[0]["enabled"] is False
    assert found[0]["args"]["apply"] is False
    assert found[0]["args"]["sport"] == "NFL"
    text = (ROOT / "byom" / "refresh.py").read_text(encoding="utf-8").lower()
    for banned in ("min_odds", "spread_size", "price_band", "insert into picks",
                   "discord"):
        assert banned not in text, banned


def test_apply_false_is_the_report_and_apply_true_rebuilds_only_the_due_set():
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
              total_line numeric, over_price numeric, under_price numeric);
            CREATE TABLE player_prop_odds (
              prop_id bigserial PRIMARY KEY, game_id text, game_date text,
              player_name text, team text, market text, bookmaker text,
              snapshot_type text, snapshot_at text, line numeric,
              over_price numeric, under_price numeric);
            CREATE TABLE nfl_player_game_log (
              log_id bigserial PRIMARY KEY, player_id text, player_name text,
              team text, game_id text, game_date text, season int,
              passing_yards numeric, attempts int, completions int,
              passing_tds int, rushing_yards numeric, carries int,
              rushing_tds int, receiving_yards numeric, receptions int,
              receiving_tds int, def_sacks numeric, def_tackles_solo numeric,
              def_tackle_assists numeric);
        """)
        for name in ("byom_facts_schema_2026_10_16.sql",
                     "byom_game_facts_units_2026_10_16.sql",
                     "byom_lock_shop_2026_10_16.sql",
                     "byom_prop_facts_units_2026_10_16.sql"):
            text = (ROOT / "data/migrations" / name).read_text(encoding="utf-8")
            cur.execute(text)
            cur.execute(text)
        _load(cur)
        raw.autocommit = False

        class Conn:
            def __init__(self):
                self.calls = []

            def execute(self, sql, params=None):
                self.calls.append((sql, params))
                c = raw.cursor()
                c.execute(sql, params)
                return c

            def executemany(self, sql, seq):
                self.calls.append((sql, None))
                c = raw.cursor()
                c.executemany(sql, seq)
                return c

            def commit(self):
                raw.commit()

        from byom.refresh import refresh

        conn = Conn()
        dry = refresh(conn, apply=False, today=AS_OF, books=BOOKS)
        assert dry["season"] == 2026
        assert dry["as_of"] == "2026-10-16"
        assert dry["apply"] is False
        assert dry["writes"] is False
        assert dry["written_game_facts"] == 0
        assert dry["written_prop_facts"] == 0
        assert dry["due"] == 3
        assert dry["in_window"] == 2
        assert dry["missing_game_facts"] == 2
        assert dry["stale_game_facts"] == 1
        assert dry["window_missing_prop_facts"] == 2
        joined = "\n".join(sql.lower() for sql, _params in conn.calls)
        for banned in ("nfl_odds_history", "player_prop_odds", "from odds"):
            assert banned not in joined, banned
        cur = raw.cursor()
        cur.execute("SELECT count(*) FROM byom_game_facts")
        assert cur.fetchone()[0] == 2

        conn.calls.clear()
        wrote = refresh(conn, apply=True, today=AS_OF, books=BOOKS)
        assert wrote["written_game_facts"] == 3
        assert wrote["written_prop_facts"] == 1
        touched = set()
        for _sql, params in conn.calls:
            if not params:
                continue
            for value in params:
                if isinstance(value, str) and value.startswith("NFL_"):
                    touched.add(value)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        if isinstance(item, str) and item.startswith("NFL_"):
                            touched.add(item)
        assert "NFL_2026_12_DAL_PHI" not in touched
        assert "NFL_2025_05_ATL_NO" not in touched
        assert "NFL_2026_05_BAL_KC" in touched
        cur = raw.cursor()
        cur.execute("SELECT canonical_key, built_at::text FROM byom_game_facts "
                    "ORDER BY canonical_key")
        rows = dict(cur.fetchall())
        assert set(rows) == {
            "2026_01_DET_GB", "2026_02_NYJ_SF", "2026_05_BAL_KC", "2026_06_BUF_MIA",
        }
        assert rows["2026_02_NYJ_SF"].startswith("2026-10-01")
        assert rows["2026_06_BUF_MIA"].startswith("2026-10-14") is False
        cur.execute("SELECT canonical_key FROM byom_prop_facts")
        assert [row[0] for row in cur.fetchall()] == ["2026_05_BAL_KC"]
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()


def _game(cur, game_id, season, day, home, away):
    commence = f"{day}T17:00:00+00:00"
    cur.execute("""
        INSERT INTO games (game_id, sport, season, week, game_date,
                           home_team, away_team, home_score, away_score,
                           commence_time)
        VALUES (%s, 'NFL', %s, 99, %s, %s, %s, 27, 20, %s)
    """, (game_id, season, day, home, away, commence))
    snap = f"{day}T07:00:00+00:00"
    cur.execute("""
        INSERT INTO nfl_odds_history
          (snapshot_at, game_id, season, week, commence_time, bookmaker,
           market, point, price_home, price_away, lead_hours)
        VALUES (%s, %s, %s, 99, %s, 'draftkings', 'spreads', -3, -110, -110, 10)
    """, (snap, game_id, season, commence))


def _load(cur):
    _game(cur, "NFL_2026_05_BAL_KC", 2026, "2026-10-15", "KC", "BAL")
    _game(cur, "NFL_2026_06_BUF_MIA", 2026, "2026-10-20", "MIA", "BUF")
    _game(cur, "NFL_2026_01_DET_GB", 2026, "2026-09-10", "GB", "DET")
    _game(cur, "NFL_2026_02_NYJ_SF", 2026, "2026-09-17", "SF", "NYJ")
    _game(cur, "NFL_2026_12_DAL_PHI", 2026, "2026-11-26", "PHI", "DAL")
    _game(cur, "NFL_2025_05_ATL_NO", 2025, "2026-10-15", "NO", "ATL")
    cur.execute("""
        INSERT INTO byom_game_facts (
          canonical_key, sport, season, week, away_team, home_team,
          lock_window_hours, near_window_hours, line_source, built_at)
        VALUES
          ('2026_02_NYJ_SF', 'NFL', 2026, 2, 'NYJ', 'SF', 120, 24, 'test',
           '2026-10-01T00:00:00Z'),
          ('2026_06_BUF_MIA', 'NFL', 2026, 6, 'BUF', 'MIA', 120, 24, 'test',
           '2026-10-14T00:00:00Z')
    """)
    cur.execute("""
        INSERT INTO player_prop_odds
          (game_id, game_date, player_name, team, market, bookmaker,
           snapshot_type, snapshot_at, line, over_price, under_price)
        VALUES
          ('NFL_2026_05_BAL_KC', '2026-10-15', 'Lamar Jackson', 'BAL',
           'player_pass_yds', 'draftkings', 'live',
           '2026-10-15T07:00:00+00:00', 220.5, -110, -110),
          ('NFL_2026_12_DAL_PHI', '2026-11-26', 'Dak Prescott', 'DAL',
           'player_pass_yds', 'draftkings', 'live',
           '2026-11-26T07:00:00+00:00', 240.5, -110, -110)
    """)
