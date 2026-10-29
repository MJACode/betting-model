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
        "over_price": None if over is None else Decimal(str(over)),
        "under_price": None if under is None else Decimal(str(under)),
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


def test_a_quote_with_no_line_is_dropped_before_the_rank():
    """On the last snapshot, a later capture with no point does not win.
    The line beside it stays. Anytime TD still fills 0.5 when the feed
    omits the point, and that 0.5 is a line that can win the rank."""
    log = [_log("Lamar Jackson", passing_yards=250, rushing_tds=1, receiving_tds=0)]
    lined = _q("Lamar Jackson", "player_pass_yds", "draftkings", 1, 240.5, -110, -110)
    blank = _q("Lamar Jackson", "player_pass_yds", "draftkings", 1, None, -110, -110)
    lined["captured_at"] = KICK - timedelta(hours=3)
    lined["prop_id"] = 1
    blank["captured_at"] = KICK - timedelta(hours=1)
    blank["prop_id"] = 99
    facts = facts_for_game(_game(), [blank, lined], log)
    assert len(facts) == 1
    assert facts[0]["line"] == Decimal("240.5")
    assert facts[0]["over_result"] == "win"

    earlier = _q("Lamar Jackson", ANYTIME_TD_MARKET, "draftkings", 1, 1.5, -150, None)
    omitted = _q("Lamar Jackson", ANYTIME_TD_MARKET, "draftkings", 1, None, -140, None)
    earlier["captured_at"] = KICK - timedelta(hours=3)
    earlier["prop_id"] = 2
    omitted["captured_at"] = KICK - timedelta(hours=1)
    omitted["prop_id"] = 3
    td = facts_for_game(_game(), [earlier, omitted], log)
    assert _one(td, ANYTIME_TD_MARKET)["line"] == Decimal("0.5")
    assert _one(td, ANYTIME_TD_MARKET)["over_result"] == "win"

    text = (ROOT / "byom" / "prop_facts.py").read_text(encoding="utf-8")
    rank = text.index("quote = max(at_line, key=_capture_rank)")
    before = text[text.rindex("def facts_for_game", 0, rank):rank]
    assert 'quote.get("point") is not None' in before


def test_two_lines_on_the_last_snapshot_keep_the_latest_capture():
    """One fact per player and market. The later captured_at wins.
    A tie breaks on prop_id, then the line text. Anytime TD's 0.5
    fill is unchanged."""
    log = [_log("Lamar Jackson", passing_yards=250)]
    older = _q("Lamar Jackson", "player_pass_yds", "draftkings", 1, 220.5, -110, -110)
    newer = _q("Lamar Jackson", "player_pass_yds", "draftkings", 1, 240.5, -115, -105)
    older["captured_at"] = KICK - timedelta(hours=4)
    older["prop_id"] = 30
    newer["captured_at"] = KICK - timedelta(hours=2)
    newer["prop_id"] = 4
    facts = facts_for_game(_game(), [older, newer], log)
    assert len(facts) == 1
    assert facts[0]["line"] == Decimal("240.5")
    assert facts[0]["over_result"] == "win"
    assert facts[0]["over_price"] == Decimal("-115")
    assert facts[0]["under_price"] == Decimal("-105")

    older["captured_at"] = newer["captured_at"]
    older["prop_id"] = 40
    newer["prop_id"] = 4
    tied_time = facts_for_game(_game(), [newer, older], log)
    assert len(tied_time) == 1
    assert tied_time[0]["line"] == Decimal("220.5")
    assert tied_time[0]["over_price"] == Decimal("-110")
    assert tied_time[0]["under_price"] == Decimal("-110")

    older["prop_id"] = 7
    newer["prop_id"] = 7
    tied_id = facts_for_game(_game(), [older, newer], log)
    assert len(tied_id) == 1
    assert tied_id[0]["line"] == Decimal("240.5")
    assert tied_id[0]["over_price"] == Decimal("-115")
    assert tied_id[0]["under_price"] == Decimal("-105")

    td = facts_for_game(_game(), [
        _q("Lamar Jackson", ANYTIME_TD_MARKET, "draftkings", 10, None, -150, None),
    ], [_log("Lamar Jackson", rushing_tds=1, receiving_tds=0)])
    assert _one(td, ANYTIME_TD_MARKET)["line"] == Decimal("0.5")
    assert _one(td, ANYTIME_TD_MARKET)["over_result"] == "win"


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


def test_the_price_is_the_quote_that_supplied_the_line():
    """The winning quote's prices are stored. An earlier quote does not
    fill a side the winner left empty. A price that is not American is
    null. Anytime TD under with no price stays null and still grades."""
    log = [_log("Lamar Jackson", passing_yards=250, rushing_tds=0, receiving_tds=0)]
    facts = facts_for_game(_game(), [
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 8, 199.5, -110, -110),
        _q("Lamar Jackson", "player_pass_yds", "draftkings", 1, 240.5, -130, None),
        _q("Lamar Jackson", "player_pass_yds", "fanduel", 0.5, 300.5, -200, -200),
    ], log)
    fact = _one(facts, "player_pass_yds")
    assert fact["line"] == Decimal("240.5")
    assert fact["over_price"] == Decimal("-130")
    assert fact["under_price"] is None

    decimal = _q("Lamar Jackson", "player_pass_yds", "draftkings", 1,
                 250.5, Decimal("1.91"), -50)
    earlier = _q("Lamar Jackson", "player_pass_yds", "draftkings", 6,
                 220.5, -115, -105)
    bare = facts_for_game(_game(), [earlier, decimal], log)
    row = _one(bare, "player_pass_yds")
    assert row["line"] == Decimal("250.5")
    assert row["over_price"] is None
    assert row["under_price"] is None

    td = facts_for_game(_game(), [
        _q("Lamar Jackson", ANYTIME_TD_MARKET, "draftkings", 2, None, -150, None),
    ], log)
    anytime = _one(td, ANYTIME_TD_MARKET)
    assert anytime["line"] == Decimal("0.5")
    assert anytime["over_price"] == Decimal("-150")
    assert anytime["under_price"] is None
    assert anytime["under_result"] == "win"
    text = (ROOT / "byom" / "prop_facts.py").read_text(encoding="utf-8")
    assert "american_odds(quote.get(\"over_price\"))" in text
    assert "american_odds(quote.get(\"under_price\"))" in text


def test_the_builder_reads_one_game_and_casts_inside_a_case():
    text = (ROOT / "byom" / "prop_load.py").read_text(encoding="utf-8")
    assert "p.game_id = %s" in text
    assert "p.prop_id" in text
    assert "p.created_at" in text
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
    assert "p.over_price" in text
    assert "p.under_price" in text
    assert "PROP_HISTORY_START_DATE" in text
    assert "PROP_HISTORY_START_SEASON" in text
    assert "game_date >= %s" in text
    assert "season >= %s" in text
    assert "-110" not in text
    lowered = text.lower() + (ROOT / "byom" / "prop_facts.py").read_text(encoding="utf-8").lower()
    for banned in ("min_odds", "spread_size", "price_band", "insert into picks",
                   "discord"):
        assert banned not in lowered, banned


def test_prop_facts_normalizes_sport_the_same_way_as_game_facts(monkeypatch):
    from tracking.job_queue import JOBS

    seen = {}

    def build_seasons(conn, seasons, apply=False, sport="NFL"):
        seen["sport"] = sport
        return {"apply": apply, "sport": sport, "seasons": []}

    class Conn:
        def close(self):
            seen["closed"] = True

    monkeypatch.setattr("byom.prop_load.build_seasons", build_seasons)
    monkeypatch.setattr("data.db.get_connection", lambda: Conn())
    fn, validate = JOBS["byom_prop_facts"]
    stored = validate({"sport": " nba ", "apply": False})
    out = fn(**stored)
    assert stored["sport"] == "NBA"
    assert seen["sport"] == "NBA"
    assert seen["closed"] is True
    assert out["sport"] == "NBA"
    seen.clear()
    fn(sport="nba", season=None, apply=False)
    assert seen["sport"] == "NBA"


def test_the_job_is_enabled_and_the_price_migrations_are_hand_applied():
    from data.view_migrations import ACTIVE_MIGRATIONS
    from tracking.job_queue import JOBS, _validate_byom_prop_facts
    from byom.constants import PROP_HISTORY_START_DATE, PROP_HISTORY_START_SEASON

    assert "byom_prop_facts" in JOBS
    # Omitted apply still writes nothing. The declaration sets it true.
    assert _validate_byom_prop_facts({})["apply"] is False
    assert _validate_byom_prop_facts({"apply": True})["season"] is None
    assert _validate_byom_prop_facts({"apply": True})["apply"] is True
    with pytest.raises(ValueError):
        _validate_byom_prop_facts({"season": 2022})
    assert PROP_HISTORY_START_DATE == "2023-09-01"
    assert PROP_HISTORY_START_SEASON == 2023
    declared = json.loads(
        (ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    found = [e for e in declared if e["key"] == "byom-nfl-prop-facts"]
    assert len(found) == 1
    assert found[0]["job_type"] == "byom_prop_facts"
    assert found[0]["enabled"] is True
    assert found[0]["args"]["apply"] is True
    assert found[0]["args"]["sport"] == "NFL"
    assert "season" not in found[0]["args"]
    nba = [e for e in declared if e["key"] == "byom-nba-prop-facts"]
    assert len(nba) == 1
    assert nba[0]["job_type"] == "byom_prop_facts"
    assert nba[0]["enabled"] is False
    assert nba[0]["requested_by"] == "owner"
    assert nba[0]["args"] == {"sport": "NBA", "apply": False}
    assert "season" not in nba[0]["args"]
    assert "byom_nba_props_2026_10_29.sql" in nba[0]["note"]
    assert "byom-nba-game-facts" in nba[0]["note"]
    assert "own change" in nba[0]["note"]
    assert "Do not enable both" in nba[0]["note"]
    assert _validate_byom_prop_facts({"sport": " nba "})["sport"] == "NBA"
    assert _validate_byom_prop_facts({"sport": "nfl"})["sport"] == "NFL"
    assert all(e["key"] != "byom-nfl-game-facts-shop" for e in declared)
    assert not (ROOT / "tests" / "test_byom_lock_shop.py").exists()
    assert not (ROOT / "data" / "migrations" / "byom_lock_shop_2026_10_16.sql").exists()
    assert not (ROOT / "data" / "migrations" / "byom_prop_facts_units_2026_10_16.sql").exists()
    columns = "byom_prop_facts_dk_prices_2026_10_28.sql"
    backtest = "byom_backtest_prop_dk_prices_2026_10_28.sql"
    assert columns not in ACTIVE_MIGRATIONS
    assert backtest not in ACTIVE_MIGRATIONS
    column_sql = (ROOT / "data" / "migrations" / columns).read_text(encoding="utf-8")
    backtest_sql = (ROOT / "data" / "migrations" / backtest).read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS over_price NUMERIC" in column_sql
    assert "ADD COLUMN IF NOT EXISTS under_price NUMERIC" in column_sql
    assert "NOT NULL" not in column_sql.split("BEGIN", 1)[1]
    assert "byom_backtest_v1" in backtest_sql
    assert "byom_prop_dk_prices" in backtest_sql
    assert "p.over_price" in backtest_sql
    assert "p.under_price" in backtest_sql
    code = "\n".join(ln.split("--", 1)[0] for ln in backtest_sql.splitlines())
    assert "mkt NOT IN" not in code
    assert "NULL::numeric" not in code
    assert "DROP FUNCTION" not in backtest_sql
    assert "CREATE OR REPLACE FUNCTION public.byom_backtest" in backtest_sql
    assert "CREATE OR REPLACE FUNCTION public.byom_save_model" not in code
    assert "RETURNS TABLE" in backtest_sql
    assert "units numeric" in backtest_sql
    assert "skipped bigint" in backtest_sql


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
              over_price numeric, under_price numeric, created_at text);
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
        prices = (ROOT / "data/migrations" / "byom_prop_facts_dk_prices_2026_10_28.sql").read_text(
            encoding="utf-8")
        cur.execute(prices)
        cur.execute(prices)
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
               '2024-09-08T02:00:00+00:00', 199.5, -105, -115),
              ('NFL_2024_01_BAL_KC', '2024-09-08', 'Lamar Jackson', 'BAL',
               'player_pass_yds', 'draftkings', 'live',
               '2024-09-08T07:00:00+00:00', 220.5, -110, -110),
              ('NFL_2024_01_BAL_KC', '2024-09-08', 'Lamar Jackson', 'BAL',
               'player_pass_yds', 'fanduel', 'live',
               '2024-09-08T16:00:00+00:00', 300.5, -200, -200),
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
            SELECT market, line, actual, over_result, log_status, line_basis,
                   over_price, under_price
              FROM byom_prop_facts
        """)
        row = cur.fetchone()
        assert row[0] == "player_pass_yds"
        assert Decimal(str(row[1])) == Decimal("220.5")
        assert Decimal(str(row[2])) == Decimal("250")
        assert row[3] == "win"
        assert row[4] == "logged"
        assert row[5] == "DraftKings line at game start"
        assert Decimal(str(row[6])) == Decimal("-110")
        assert Decimal(str(row[7])) == Decimal("-110")
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
            SELECT line, over_price, under_price FROM byom_prop_facts
             WHERE canonical_key = '2024_01_BAL_KC'
             ORDER BY line
        """)
        rebuilt_rows = cur.fetchall()
        assert len(rebuilt_rows) == 1
        assert Decimal(str(rebuilt_rows[0][0])) == Decimal("240.5")
        assert Decimal(str(rebuilt_rows[0][1])) == Decimal("-110")
        assert Decimal(str(rebuilt_rows[0][2])) == Decimal("-110")
        again = build_season(Conn(), 2022, apply=True)
        assert again["written"] == 0
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()


def _scratch_roles(cur):
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


class _Conn:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=None):
        c = self.raw.cursor()
        c.execute(sql, params)
        return c

    def executemany(self, sql, seq):
        c = self.raw.cursor()
        c.executemany(sql, seq)
        return c

    def commit(self):
        self.raw.commit()


def test_scratch_backfill_starts_on_2023_09_01_and_writes_nothing_when_dry():
    """No season argument is the 2023-now backfill. apply false counts
    and does not write. A 2023 game before 2023-09-01 is not a fact.
    A season before 2023 is not in the result."""
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
            CREATE TABLE games (
              game_id text PRIMARY KEY, sport text, season int, week int,
              game_date text, home_team text, away_team text,
              home_score numeric, away_score numeric, commence_time text);
            CREATE TABLE player_prop_odds (
              prop_id bigserial PRIMARY KEY, game_id text, game_date text,
              player_name text, team text, market text, bookmaker text,
              snapshot_type text, snapshot_at text, line numeric,
              over_price numeric, under_price numeric, created_at text);
            CREATE TABLE nfl_player_game_log (
              log_id bigserial PRIMARY KEY, player_id text, player_name text,
              team text, game_id text, game_date text, season int,
              passing_yards numeric, attempts int, completions int,
              passing_tds int, rushing_yards numeric, carries int,
              rushing_tds int, receiving_yards numeric, receptions int,
              receiving_tds int, def_sacks numeric, def_tackles_solo numeric,
              def_tackle_assists numeric);
        """)

        def add(game_id, season, day, home, away, line, over, under):
            cur.execute("""
                INSERT INTO games VALUES
                  (%s, 'NFL', %s, 1, %s, %s, %s, 24, 16, %s)
            """, (game_id, season, day, home, away, day + "T17:00:00+00:00"))
            cur.execute("""
                INSERT INTO player_prop_odds
                  (game_id, game_date, player_name, team, market, bookmaker,
                   snapshot_type, snapshot_at, line, over_price, under_price)
                VALUES
                  (%s, %s, 'Lamar Jackson', %s, 'player_pass_yds', 'draftkings',
                   'live', %s, %s, %s, %s)
            """, (game_id, day, away, day + "T07:00:00+00:00", line, over, under))

        add("NFL_2022_01_BAL_KC", 2022, "2022-09-11", "KC", "BAL", 220.5, -110, -110)
        add("NFL_2023_04_BUF_NYJ", 2023, "2023-08-20", "NYJ", "BUF", 199.5, -105, -115)
        add("NFL_2023_01_BAL_KC", 2023, "2023-09-01", "KC", "BAL", 220.5, -110, None)
        add("NFL_2024_01_DAL_PHI", 2024, "2024-09-08", "PHI", "DAL", 240.5, -130, -110)
        raw.autocommit = False
        from byom.prop_load import build_seasons

        result = build_seasons(_Conn(raw), None, apply=False)
        assert result["apply"] is False
        by_season = {row["season"]: row for row in result["seasons"]}
        assert list(by_season) == [2023, 2024]
        assert by_season[2023]["facts"] == 1
        assert by_season[2023]["written"] == 0
        assert by_season[2023]["canonical_keys"] == ["2023_01_BAL_KC"]
        assert by_season[2024]["facts"] == 1
        assert by_season[2024]["written"] == 0
        assert by_season[2024]["canonical_keys"] == ["2024_01_DAL_PHI"]
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()


def test_scratch_backtest_stakes_the_stored_prop_price_and_skips_a_bare_side():
    """A priced prop leg is 1u to win. A graded side with no American
    price is skipped. An ungraded prop is neither. The registered
    migration does not put the old body back."""
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
        _scratch_roles(cur)
        names = (
            "byom_facts_schema_2026_10_16.sql",
            "byom_dk_start_price_2026_10_23.sql",
            "byom_prop_facts_dk_prices_2026_10_28.sql",
            "byom_backtest_prop_dk_prices_2026_10_28.sql",
            "byom_backtest_prop_dk_prices_2026_10_28.sql",
        )
        for name in names:
            cur.execute((ROOT / "data/migrations" / name).read_text(encoding="utf-8"))
        cur.execute("""
            INSERT INTO byom_game_facts (
              canonical_key, sport, season, week, away_team, home_team,
              line_basis, home_score, away_score, dk_spread_home,
              ats_home_result, ats_away_result,
              dk_spread_home_price, dk_spread_away_price)
            VALUES (
              '2026_01_BAL_KC', 'NFL', 2026, 1, 'BAL', 'KC',
              'DraftKings line at game start', 24, 20, -3.5,
              'win', 'loss', -110, -110);
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
               'loss', 'win', -150, NULL),
              ('rec', '2026_01_BAL_KC', 'NFL', 2026, 1, 'Mark Andrews', 'BAL',
               'player_receptions', 4.5, 'DraftKings line at game start', 'logged',
               'win', 'loss', 1.91, -110),
              ('rush', '2026_01_BAL_KC', 'NFL', 2026, 1, 'Derrick Henry', 'BAL',
               'player_rush_yds', 60.5, 'DraftKings line at game start',
               'non_participant', NULL, NULL, -110, -110),
              ('sack', '2026_01_BAL_KC', 'NFL', 2026, 1, 'Kyle Hamilton', 'BAL',
               'player_sacks', 0.5, 'DraftKings line at game start', 'logged',
               'push', 'push', -110, -110);
        """)

        def one(market):
            cur.execute("""
                SELECT bets, wins, losses, pushes, ties, units, skipped
                  FROM byom_backtest(2026, %s::jsonb)
            """, (json.dumps({"markets": [market]}),))
            row = cur.fetchone()
            if row is None:
                return None
            bets, wins, losses, pushes, ties, units, skipped = row
            return (
                bets, wins, losses, pushes, ties,
                Decimal(str(units)), skipped,
            )

        assert one("spreads") == (2, 1, 1, 0, 0, Decimal("-0.1"), 0)
        assert one("player_pass_yds") == (2, 1, 1, 0, 0, Decimal("-0.1"), 0)
        assert one("player_anytime_td") == (1, 0, 1, 0, 0, Decimal("-1.5"), 1)
        assert one("player_receptions") == (1, 0, 1, 0, 0, Decimal("-1.1"), 1)
        assert one("player_rush_yds") is None
        assert one("player_sacks") == (2, 0, 0, 2, 0, Decimal("0"), 0)
        cur.execute((ROOT / "data/migrations" / "byom_backtest_rpc_2026_10_16.sql").read_text(
            encoding="utf-8"))
        cur.execute("SELECT prosrc FROM pg_proc WHERE proname = 'byom_backtest'")
        body = cur.fetchone()[0]
        assert "byom_backtest_v1" in body
        assert "byom_prop_dk_prices" in body
        assert "p.over_price" in body
        assert "p.under_price" in body
        assert "mkt NOT IN" not in body
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()
