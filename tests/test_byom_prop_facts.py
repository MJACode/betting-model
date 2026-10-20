"""NFL prop facts: the line at game start, log status, no alt ladders.

Pure tests always run. The scratch cluster is local. Nothing here writes
production.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from byom.constants import LINE_BASIS
from byom.prop_facts import (
    ANYTIME_TD_MARKET,
    backtest,
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


def test_the_line_basis_is_a_label():
    text = (ROOT / "byom" / "constants.py").read_text(encoding="utf-8")
    assert LINE_BASIS == "DraftKings line at game start"
    assert "PROP_LOCK_WINDOW" not in text
    assert "24" not in text


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


def test_the_line_is_the_last_pre_start_snapshot():
    """A quote older than any former window is the line when it is the
    latest one. A later snapshot replaces it. An in-play quote does not."""
    facts = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 30, 199.5, -110, -110),
    ], [_log("Lamar Jackson", passing_yards=250)])
    fact = _one(facts, "player_pass_yds")
    assert fact["line"] == Decimal("199.5")
    assert fact["line_basis"] == LINE_BASIS
    assert fact["over_result"] == "win"
    facts = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 30, 199.5, -110, -110),
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 20, 220.5, -115, -105),
    ], [_log("Lamar Jackson", passing_yards=250)])
    fact = _one(facts, "player_pass_yds")
    assert fact["line"] == Decimal("220.5")
    assert len(facts) == 1
    in_play = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 20, 220.5, -115, -105),
        _q("Lamar Jackson", "player_pass_yds", "draftkings", -1, 280.5, -110, -110),
    ], [_log("Lamar Jackson", passing_yards=250)])
    assert _one(in_play, "player_pass_yds")["line"] == Decimal("220.5")


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


def test_missing_log_is_not_a_loss_and_a_non_participant_is_ungraded():
    quotes = [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 10, 220.5, -110, -110),
        _q("Zay Flowers", "player_receptions", "draftkings", 10, 4.5, -120, 100),
    ]
    missing = facts_for_game(_game(), quotes, [])
    assert {f["log_status"] for f in missing} == {"missing_log"}
    assert all(
        f["over_result"] is None and f["under_result"] is None and f["actual"] is None
        for f in missing
    )
    logged = facts_for_game(
        _game(), quotes, [_log("Lamar Jackson", passing_yards=180)])
    lamar = _one(logged, "player_pass_yds")
    flowers = _one(logged, "player_receptions", "Zay Flowers")
    assert lamar["log_status"] == "logged"
    assert lamar["actual"] == Decimal(180)
    assert lamar["over_result"] == "loss"
    assert flowers["log_status"] == "non_participant"
    assert flowers["actual"] is None
    assert flowers["over_result"] is None
    assert flowers["under_result"] is None


def test_missing_log_over_and_under_stay_ungraded_and_anytime_no_is_not_a_win():
    """A missing log grades neither side. Anytime TD 'No' is not a win
    when the player has no log row."""
    quotes = [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 10, 220.5, -110, -110),
        _q("Lamar Jackson", ANYTIME_TD_MARKET, "draftkings", 10, None, -150, 120),
    ]
    facts = facts_for_game(_game(), quotes, [])
    assert {f["log_status"] for f in facts} == {"missing_log"}
    yards = _one(facts, "player_pass_yds")
    td = _one(facts, ANYTIME_TD_MARKET)
    assert yards["line"] == Decimal("220.5")
    assert yards["over_result"] is None
    assert yards["under_result"] is None
    assert yards["actual"] is None
    assert td["line"] == Decimal("0.5")
    assert td["over_result"] is None
    assert td["under_result"] is None
    assert td["under_result"] != "win"
    scored = backtest(facts)
    assert scored["totals"] == 0
    assert scored["over_wins"] == 0
    assert scored["under_wins"] == 0
    assert scored["over_success"] is None
    assert scored["under_success"] is None
    assert scored["total_actual"] == Decimal(0)
    assert scored["record_over"] == "0-0-0"
    assert scored["record_under"] == "0-0-0"


def test_a_player_who_did_not_play_is_excluded_from_scoring():
    """Matt, 2026-10-20: a player who did not play is out of the record,
    the success stats, and the totals. A logged zero is still a result."""
    quotes = [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 10, 220.5, -110, -110),
        _q("Zay Flowers", ANYTIME_TD_MARKET, "draftkings", 10, 0.5, -140, 110),
        _q("Mark Andrews", ANYTIME_TD_MARKET, "draftkings", 10, 0.5, -130, 100),
    ]
    facts = facts_for_game(_game(), quotes, [
        _log("Lamar Jackson", passing_yards=280),
        _log("Mark Andrews", rushing_tds=0, receiving_tds=0),
    ])
    lamar = _one(facts, "player_pass_yds")
    flowers = _one(facts, ANYTIME_TD_MARKET, "Zay Flowers")
    andrews = _one(facts, ANYTIME_TD_MARKET, "Mark Andrews")
    assert lamar["log_status"] == "logged"
    assert lamar["over_result"] == "win"
    assert flowers["log_status"] == "non_participant"
    assert flowers["actual"] is None
    assert flowers["over_result"] is None
    assert flowers["under_result"] is None
    assert andrews["log_status"] == "logged"
    assert andrews["actual"] == Decimal(0)
    assert andrews["under_result"] == "win"
    played = backtest([lamar, andrews])
    with_scratch = backtest(facts)
    assert with_scratch == played
    assert with_scratch["totals"] == 2
    assert with_scratch["under_wins"] == 1
    assert with_scratch["over_wins"] == 1
    assert with_scratch["over_success"] == 0.5
    assert with_scratch["record_over"] == "1-1-0"
    assert with_scratch["total_actual"] == Decimal(280)
    scratch_only = backtest([flowers])
    assert scratch_only["totals"] == 0
    assert scratch_only["under_wins"] == 0
    assert scratch_only["under_success"] is None
    assert scratch_only["record_under"] == "0-0-0"


def test_a_row_with_no_posted_line_is_skipped_not_graded():
    """The backtest includes a prop only where a line existed. A quote
    with no line is not graded into a win or a loss."""
    facts = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 10, None, -110, -110),
        _q("Mark Andrews", "player_receptions", "draftkings", 10, 3.5, -110, -110),
    ], [
        _log("Lamar Jackson", passing_yards=250),
        _log("Mark Andrews", receptions=5),
    ])
    assert len(facts) == 1
    assert facts[0]["market"] == "player_receptions"
    assert facts[0]["line"] == Decimal("3.5")
    assert facts[0]["over_result"] == "win"
    phantom = {
        "line": None,
        "log_status": "logged",
        "actual": Decimal(0),
        "over_result": "win",
        "under_result": "loss",
    }
    scored = backtest(facts + [phantom])
    assert scored["totals"] == 1
    assert scored["over_wins"] == 1
    assert scored["over_losses"] == 0
    assert scored["over_success"] == 1.0
    assert scored["record_over"] == "1-0-0"
    assert scored["total_actual"] == Decimal(5)
    assert backtest([phantom])["totals"] == 0


def test_an_unplayed_game_keeps_the_line_and_nulls_the_result():
    facts = facts_for_game(_game(played=False), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 10, 220.5, -110, -110),
    ], [])
    fact = _one(facts, "player_pass_yds")
    assert fact["log_status"] == "unplayed"
    assert fact["line"] == Decimal("220.5")
    assert fact["line_basis"] == LINE_BASIS
    assert fact["over_result"] is None
    for key in ("over_units_uncapped", "grade_over_price", "dk_over_price",
                "lock_window_hours", "line_source", "close_over_price"):
        assert key not in fact


def test_another_book_does_not_set_the_line():
    facts = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 10, 220.5, -115, -105),
        _q("Lamar Jackson", "player_pass_yds", "fanduel", 1, 300.5, -105, -115),
    ], [_log("Lamar Jackson", passing_yards=250)])
    fact = _one(facts, "player_pass_yds")
    assert fact["line"] == Decimal("220.5")
    assert fact["over_result"] == "win"
    assert fact["line_basis"] == LINE_BASIS


def test_a_long_line_is_still_graded():
    facts = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 10, 300.5, -400, -110),
    ], [_log("Lamar Jackson", passing_yards=100)])
    fact = _one(facts, "player_pass_yds")
    assert fact["over_result"] == "loss"
    assert fact["under_result"] == "win"
    assert "over_units_uncapped" not in fact


def test_a_nickname_miss_is_a_non_participant():
    """Josh and Joshua do not meet. Matt, 2026-10-20: the miss is ungraded.
    It is not an under win."""
    facts = facts_for_game(_game(), [
        _q("Josh Allen", "player_pass_yds", "draftkings", 10, 220.5, -110, -110,
           team="BUF"),
    ], [_log("Joshua Allen", team="BUF", passing_yards=300)])
    fact = _one(facts, "player_pass_yds", "Josh Allen")
    assert fact["log_status"] == "non_participant"
    assert fact["actual"] is None
    assert fact["over_result"] is None
    assert fact["under_result"] is None
    assert backtest([fact])["totals"] == 0


def test_an_offense_only_log_leaves_a_defender_as_a_non_participant():
    facts = facts_for_game(_game(), [
        _q("Kyle Hamilton", "player_sacks", "draftkings", 10, 0.5, -120, 100,
           team="BAL"),
    ], [_log("Lamar Jackson", passing_yards=250)])
    fact = _one(facts, "player_sacks", "Kyle Hamilton")
    assert fact["log_status"] == "non_participant"
    assert fact["actual"] is None
    assert fact["over_result"] is None
    assert fact["under_result"] is None


def test_the_quote_team_breaks_a_shared_name():
    facts = facts_for_game(_game(), [
        _q("Josh Allen", "player_pass_yds", "draftkings", 10, 220.5, -110, -110,
           team="BUF"),
    ], [
        _log("Josh Allen", team="BUF", passing_yards=280),
        _log("Josh Allen", team="NYJ", passing_yards=40),
    ])
    fact = _one(facts, "player_pass_yds", "Josh Allen")
    assert fact["log_status"] == "logged"
    assert fact["actual"] == Decimal(280)
    tied = facts_for_game(_game(), [
        _q("Josh Allen", "player_pass_yds", "draftkings", 10, 220.5, -110, -110,
           team="BAL"),
    ], [
        _log("Josh Allen", team="BUF", passing_yards=280),
        _log("Josh Allen", team="NYJ", passing_yards=40),
    ])
    assert _one(tied, "player_pass_yds", "Josh Allen")["log_status"] == "ambiguous"


def test_220_50_and_220_5_are_one_prop_key():
    from byom.prop_facts import line_key

    assert line_key(Decimal("220.50")) == line_key(Decimal("220.5")) == "220.5"
    first = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 10,
           Decimal("220.50"), -110, -110),
    ], [_log("Lamar Jackson", passing_yards=250)])
    second = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 10,
           Decimal("220.5"), -110, -110),
    ], [_log("Lamar Jackson", passing_yards=250)])
    assert first[0]["prop_key"] == second[0]["prop_key"]
    assert first[0]["prop_key"].endswith("|220.5")


def test_a_later_number_replaces_the_earlier_line():
    """One line. The last pre-start snapshot is the fact."""
    facts = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 20, 220.5, -110, -110),
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 5, 220.5, -120, 100),
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 1, 240.5, -130, 110),
    ], [_log("Lamar Jackson", passing_yards=250)])
    assert len(facts) == 1
    assert facts[0]["line"] == Decimal("240.5")
    assert facts[0]["over_result"] == "win"
    assert "close_over_price" not in facts[0]


def test_the_builder_reads_one_game_and_casts_inside_a_case():
    text = (ROOT / "byom" / "prop_load.py").read_text(encoding="utf-8")
    assert "p.game_id = %s" in text
    assert "bookmaker = 'draftkings'" in text
    assert "BEST_LINE_BOOKMAKERS" not in text
    assert "ELSE NULL END" in text
    assert '_ts_case("p.snapshot_at")' in text
    assert '_ts_case("g.commence_time")' in text
    assert "THEN {expr}::timestamptz" in text
    assert "AND p.snapshot_at::timestamptz" not in text
    assert "AND g.commence_time::timestamptz" not in text
    assert "(0[1-9]|1[0-2])" in text
    assert "DELETE FROM byom_prop_facts WHERE canonical_key" in text
    assert "make_interval" not in text
    assert "over_price" not in text
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
    assert all(e["key"] != "byom-nfl-game-facts-shop" for e in declared)
    assert not (ROOT / "tests" / "test_byom_lock_shop.py").exists()
    assert not (ROOT / "data" / "migrations" / "byom_lock_shop_2026_10_16.sql").exists()
    assert not (ROOT / "data" / "migrations" / "byom_prop_facts_units_2026_10_16.sql").exists()


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
        text = (ROOT / "data/migrations" / "byom_facts_schema_2026_10_16.sql").read_text(
            encoding="utf-8")
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
               199.5, -110, -110),
              ('NFL_2024_01_BAL_KC', '2024-09-08', 'Lamar Jackson', 'BAL',
               'player_pass_yds', 'draftkings', 'live', '2024-13-45',
               188.5, -110, -110);
            INSERT INTO games VALUES
              ('NFL_2024_02_BUF_NYJ', 'NFL', 2024, 2, '2024-09-15', 'NYJ', 'BUF',
               10, 20, '2024-13-45');
            INSERT INTO player_prop_odds
              (game_id, game_date, player_name, team, market, bookmaker,
               snapshot_type, snapshot_at, line, over_price, under_price)
            VALUES
              ('NFL_2024_02_BUF_NYJ', '2024-09-15', 'Josh Allen', 'BUF',
               'player_pass_yds', 'draftkings', 'live',
               '2024-09-15T07:00:00+00:00', 220.5, -110, -110);
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
            SELECT market, line, actual, over_result, log_status, line_basis
              FROM byom_prop_facts
        """)
        row = cur.fetchone()
        assert row[0] == "player_pass_yds"
        assert Decimal(str(row[1])) == Decimal("220.5")
        assert Decimal(str(row[2])) == Decimal("250")
        assert row[3] == "win"
        assert row[4] == "logged"
        assert row[5] == "DraftKings line at game start"
        cur.execute("""
            INSERT INTO byom_prop_facts
              (prop_key, canonical_key, sport, season, week, player_name,
               player_key, market, line, line_basis)
            VALUES
              ('2024_01_BAL_KC|player_pass_yds|lamar jackson|199.5',
               '2024_01_BAL_KC', 'NFL', 2024, 1, 'Lamar Jackson',
               'lamar jackson', 'player_pass_yds', 199.5,
               'DraftKings line at game start')
        """)
        cur.execute("""
            UPDATE player_prop_odds
               SET line = 240.5
             WHERE game_id = 'NFL_2024_01_BAL_KC'
               AND market = 'player_pass_yds'
               AND line = 220.5
        """)
        rebuilt = build_season(Conn(), 2024, apply=True)
        assert rebuilt["written"] == 1
        cur.execute("""
            SELECT line FROM byom_prop_facts
             WHERE canonical_key = '2024_01_BAL_KC'
             ORDER BY line
        """)
        lines = [Decimal(str(item[0])) for item in cur.fetchall()]
        assert lines == [Decimal("240.5")]
        again = build_season(Conn(), 2022, apply=True)
        assert again["written"] == 0
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()
