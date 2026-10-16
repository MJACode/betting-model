"""NFL prop facts: 24h lock, log status, no alt ladders.

Pure tests always run. The scratch cluster is local. Nothing here writes
production.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from byom.constants import PROP_LOCK_WINDOW_HOURS
from byom.prop_facts import (
    ANYTIME_TD_MARKET,
    facts_for_game,
    is_standard_market,
)

ROOT = Path(__file__).resolve().parents[1]
KICK = datetime(2024, 9, 8, 17, 0, tzinfo=timezone.utc)


def _game(played=True):
    return {
        "game_id": "NFL_2024_01_BAL_KC",
        "home_score": 24 if played else None,
        "away_score": 16 if played else None,
        "game_date": "2024-09-08",
        "commence_time": KICK,
        "home_team": "KC",
        "away_team": "BAL",
    }


def _q(name, market, book, hours, line, over, under, team="BAL"):
    return {
        "player_name": name,
        "team": team,
        "market": market,
        "bookmaker": book,
        "snapshot_at": KICK - timedelta(hours=hours),
        "commence_time": KICK,
        "point": None if line is None else Decimal(str(line)),
        "price_home": None if over is None else Decimal(str(over)),
        "price_away": None if under is None else Decimal(str(under)),
        "line_source": "player_prop_odds",
    }


def _log(name, **stats):
    row = {"player_name": name, "team": "BAL"}
    row.update(stats)
    return row


def _one(facts, market, name="Lamar Jackson"):
    key = name.lower()
    hits = [f for f in facts if f["market"] == market and key in f["player_key"]]
    assert len(hits) == 1, hits
    return hits[0]


def test_the_prop_lock_is_the_named_unconfirmed_24h_constant():
    text = (ROOT / "byom" / "constants.py").read_text(encoding="utf-8")
    assert PROP_LOCK_WINDOW_HOURS == 24
    assert "PROP_LOCK_WINDOW_HOURS = 24" in text
    assert "UNCONFIRMED" in text.split("PROP_LOCK_WINDOW_HOURS")[0][-400:]


def test_alt_ladders_are_not_facts():
    assert is_standard_market("player_pass_yds")
    assert not is_standard_market("player_pass_yds_alternate")
    facts = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds_alternate", "draftkings",
           10, 300.5, -110, -110),
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 10, 220.5, -115, -105),
    ], [_log("Lamar Jackson", passing_yards=250)])
    assert [f["market"] for f in facts] == ["player_pass_yds"]
    assert facts[0]["line"] == Decimal("220.5")


def test_a_quote_outside_24h_is_not_the_lock():
    facts = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 30, 199.5, -110, -110),
    ], [_log("Lamar Jackson", passing_yards=250)])
    assert facts == []
    facts = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 30, 199.5, -110, -110),
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 20, 220.5, -115, -105),
    ], [_log("Lamar Jackson", passing_yards=250)])
    fact = _one(facts, "player_pass_yds")
    assert fact["line"] == Decimal("220.5")
    assert fact["lock_window_hours"] == 24


def test_anytime_td_is_rush_plus_rec_and_ignores_passing_and_returns():
    """Two passing TDs and no rush or rec TD is not an anytime score.
    A return TD is not in the log, so it cannot be added."""
    facts = facts_for_game(_game(), [
        _q("Lamar Jackson", ANYTIME_TD_MARKET, "draftkings", 10, None, -150, None),
    ], [_log("Lamar Jackson", passing_tds=2, rushing_tds=0, receiving_tds=0)])
    fact = _one(facts, ANYTIME_TD_MARKET)
    assert fact["line"] == Decimal("0.5")
    assert fact["actual"] == Decimal(0)
    assert fact["over_result"] == "loss"
    facts = facts_for_game(_game(), [
        _q("Lamar Jackson", ANYTIME_TD_MARKET, "draftkings", 10, None, -150, None),
    ], [_log("Lamar Jackson", passing_tds=0, rushing_tds=1, receiving_tds=0)])
    assert _one(facts, ANYTIME_TD_MARKET)["over_result"] == "win"
    text = (ROOT / "byom" / "prop_facts.py").read_text(encoding="utf-8")
    assert "Return" in text or "return" in text
    assert "passing_tds" not in text.split("player_anytime_td")[1].split(")")[0]


def test_missing_log_is_not_a_loss_and_a_non_participant_is_zero():
    quotes = [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 10, 220.5, -110, -110),
        _q("Zay Flowers", "player_receptions", "draftkings", 10, 4.5, -120, 100),
    ]
    missing = facts_for_game(_game(), quotes, [])
    assert {f["log_status"] for f in missing} == {"missing_log"}
    assert all(f["over_result"] is None and f["actual"] is None for f in missing)
    logged = facts_for_game(
        _game(), quotes, [_log("Lamar Jackson", passing_yards=180)])
    lamar = _one(logged, "player_pass_yds")
    flowers = _one(logged, "player_receptions", "Zay Flowers")
    assert lamar["log_status"] == "logged"
    assert lamar["actual"] == Decimal(180)
    assert lamar["over_result"] == "loss"
    assert flowers["log_status"] == "non_participant"
    assert flowers["actual"] == Decimal(0)
    assert flowers["over_result"] == "loss"


def test_an_unplayed_game_keeps_the_line_and_nulls_the_result():
    facts = facts_for_game(_game(played=False), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 10, 220.5, -110, -110),
    ], [])
    fact = _one(facts, "player_pass_yds")
    assert fact["log_status"] == "unplayed"
    assert fact["line"] == Decimal("220.5")
    assert fact["over_result"] is None
    assert fact["over_units_uncapped"] is None
    assert fact["over_units_capped"] is None


def test_a_better_fanduel_price_is_not_the_grade():
    facts = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 10, 220.5, -115, -105),
        _q("Lamar Jackson", "player_pass_yds", "fanduel", 10 + 10 / 60,
           220.5, -105, -115),
    ], [_log("Lamar Jackson", passing_yards=250)])
    fact = _one(facts, "player_pass_yds")
    assert fact["grade_over_book"] == "draftkings"
    assert fact["grade_over_price"] == Decimal("-115")
    assert fact["grade_under_book"] == "draftkings"
    assert fact["grade_under_price"] == Decimal("-105")
    assert fact["dk_over_price"] == Decimal("-115")
    assert fact["over_units_uncapped"] == Decimal("1")


def test_a_long_price_stores_both_unit_columns():
    facts = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 10, 300.5, -400, -110),
    ], [_log("Lamar Jackson", passing_yards=100)])
    fact = _one(facts, "player_pass_yds")
    assert fact["over_result"] == "loss"
    assert fact["over_units_uncapped"] == Decimal("-4.0000")
    assert fact["over_units_capped"] == Decimal("-3.0000")


def test_the_builder_reads_one_game_and_casts_inside_a_case():
    text = (ROOT / "byom" / "prop_load.py").read_text(encoding="utf-8")
    assert "p.game_id = %s" in text
    assert "bookmaker = 'draftkings'" in text
    assert "BEST_LINE_BOOKMAKERS" not in text
    assert "ELSE NULL END" in text
    assert "snapshot_at::timestamptz" in text
    assert "AND p.snapshot_at::timestamptz" not in text
    lowered = text.lower() + (ROOT / "byom" / "prop_facts.py").read_text(encoding="utf-8").lower()
    for banned in ("min_odds", "spread_size", "price_band", "insert into picks",
                   "discord"):
        assert banned not in lowered, banned


def test_the_job_ships_disabled():
    from tracking.job_queue import JOBS, _validate_byom_prop_facts

    assert "byom_prop_facts" in JOBS
    assert _validate_byom_prop_facts({})["apply"] is False
    with pytest.raises(ValueError):
        _validate_byom_prop_facts({"season": 2022})
    declared = json.loads(
        (ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    found = [e for e in declared if e["job_type"] == "byom_prop_facts"]
    assert len(found) == 1
    assert found[0]["enabled"] is False
    assert found[0]["args"]["apply"] is False


def test_scratch_prop_build_grades_the_log_and_skips_a_junk_timestamp():
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
                     "byom_prop_facts_units_2026_10_16.sql"):
            text = (ROOT / "data/migrations" / name).read_text(encoding="utf-8")
            cur.execute(text)
            cur.execute(text)
        cur.execute("""
            INSERT INTO games VALUES
              ('NFL_2024_01_BAL_KC', 'NFL', 2024, 1, '2024-09-08', 'KC', 'BAL',
               24, 16, '2024-09-08T17:00:00+00:00');
            INSERT INTO player_prop_odds
              (game_id, game_date, player_name, team, market, bookmaker,
               snapshot_type, snapshot_at, line, over_price, under_price)
            VALUES
              ('NFL_2024_01_BAL_KC', '2024-09-08', 'Lamar Jackson', 'BAL',
               'player_pass_yds', 'draftkings', 'live',
               '2024-09-08T07:00:00+00:00', 220.5, -110, -110),
              ('NFL_2024_01_BAL_KC', '2024-09-08', 'Lamar Jackson', 'BAL',
               'player_pass_yds_alternate', 'draftkings', 'live',
               '2024-09-08T07:00:00+00:00', 300.5, -110, -110),
              ('NFL_2024_01_BAL_KC', '2024-09-08', 'Lamar Jackson', 'BAL',
               'player_pass_yds', 'draftkings', 'live', 'not-a-timestamp',
               199.5, -110, -110);
            INSERT INTO nfl_player_game_log
              (player_id, player_name, team, game_id, game_date, season,
               passing_yards)
            VALUES
              ('p1', 'Lamar Jackson', 'BAL', 'NFL_2024_01_BAL_KC',
               '2024-09-08', 2024, 250);
        """)
        raw.autocommit = False
        from byom.prop_load import build_season

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

        first = build_season(Conn(), 2024, apply=True)
        assert first["written"] == 1
        cur = raw.cursor()
        cur.execute("""
            SELECT market, line, actual, over_result, log_status
              FROM byom_prop_facts
        """)
        row = cur.fetchone()
        assert row[0] == "player_pass_yds"
        assert Decimal(str(row[1])) == Decimal("220.5")
        assert Decimal(str(row[2])) == Decimal("250")
        assert row[3] == "win"
        assert row[4] == "logged"
        again = build_season(Conn(), 2022, apply=True)
        assert again["written"] == 0
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()
