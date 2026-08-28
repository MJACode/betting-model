"""
THE CONTRACT: the backtest state builder and the live state builder must emit
identical schemas.

If they drift, the model is trained on one thing and served another, and every
backtest number in the project becomes a claim about a system that does not
exist. This is the single most important test in the package, which is why it
is the first file in it.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from live_model.state import (  # noqa: E402
    GAME_STATE_FIELDS, GameState, from_espn, from_pbp_row, smooth_pass_rate,
)

NOW = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)

PBP_ROW = {
    "game_id": "2024_01_BAL_KC", "home_team": "KC", "away_team": "BAL",
    "posteam": "KC", "qtr": 3.0, "quarter_seconds_remaining": 412.0,
    "home_score_pre": 21.0, "away_score_pre": 17.0,
    "down": 2.0, "ydstogo": 7.0, "yardline_100": 65.0,
    "home_timeouts_remaining": 2.0, "away_timeouts_remaining": 3.0,
    "spread_line": 3.0,          # nflverse form: positive means HOME favored
    "total_line": 46.0, "roof": "outdoors", "wind": 8.0,
    "plays_run": 90.0, "home_pass_rate": 0.61, "away_pass_rate": 0.55,
}

ESPN_SUMMARY = {
    "header": {"competitions": [{
        "status": {"period": 3, "clock": 412.0, "displayClock": "6:52",
                   "type": {"state": "in", "name": "STATUS_IN_PROGRESS"}},
        "competitors": [
            {"homeAway": "home", "score": "21",
             "team": {"id": "12", "abbreviation": "KC"}},
            {"homeAway": "away", "score": "17",
             "team": {"id": "33", "abbreviation": "BAL"}},
        ],
        "situation": {"possession": "12", "down": 2, "distance": 7,
                      "possessionText": "KC 35",
                      "homeTimeouts": 2, "awayTimeouts": 3},
    }]},
    "drives": {"previous": [{"team": {"abbreviation": "KC"}, "plays": [
        {"type": {"text": "Pass Reception"}}, {"type": {"text": "Rush"}},
        {"type": {"text": "Kickoff"}}]}]},
}


def test_both_builders_emit_the_same_schema():
    a = from_pbp_row(PBP_ROW, ts=NOW)
    b = from_espn(ESPN_SUMMARY, game_id="2024_01_BAL_KC", pregame_spread=-3.0,
                  pregame_total=46.0, wind_mph=8.0, is_dome=False, ts=NOW)
    assert b is not None
    assert tuple(a.__dataclass_fields__) == GAME_STATE_FIELDS
    assert tuple(b.__dataclass_fields__) == GAME_STATE_FIELDS


def test_the_same_game_moment_produces_the_same_state():
    """
    Not just the same field names: the same VALUES for the fields both feeds
    genuinely observe. Pass rate and play count are excluded because the two
    sources count plays differently by construction; everything a bet depends
    on must agree exactly.
    """
    a = from_pbp_row(PBP_ROW, ts=NOW)
    b = from_espn(ESPN_SUMMARY, game_id="2024_01_BAL_KC", pregame_spread=-3.0,
                  pregame_total=46.0, wind_mph=8.0, is_dome=False, ts=NOW)
    for f in ("game_id", "period", "clock_seconds", "home_score", "away_score",
              "possession", "down", "distance", "yardline_100",
              "home_timeouts", "away_timeouts", "pregame_spread",
              "pregame_total", "wind_mph", "is_dome"):
        assert getattr(a, f) == getattr(b, f), f


def test_spread_convention_is_negated_from_nflverse():
    """
    nflverse spread_line is POSITIVE when the home team is favored; our
    standard form is NEGATIVE when home is laying. Session 128 established
    that a league-wide ATS split cannot tell the two apart, so this is pinned
    by test rather than left to be re-derived by whoever touches it next.
    """
    assert from_pbp_row(PBP_ROW, ts=NOW).pregame_spread == -3.0


def test_derived_clock_fields():
    s = from_pbp_row(PBP_ROW, ts=NOW)
    assert s.seconds_remaining == 412 + 900          # Q3 plus Q4
    assert s.half_seconds_remaining == 412 + 900
    assert s.score_diff == 4
    assert not s.is_halftime


def test_halftime_is_detected_from_both_feeds():
    row = dict(PBP_ROW, qtr=2.0, quarter_seconds_remaining=0.0, posteam=None)
    assert from_pbp_row(row, ts=NOW).is_halftime

    payload = {"header": {"competitions": [{
        "status": {"period": 2, "type": {"state": "in",
                                         "name": "STATUS_HALFTIME"}},
        "competitors": [
            {"homeAway": "home", "score": "14", "team": {"id": "1"}},
            {"homeAway": "away", "score": "10", "team": {"id": "2"}}],
    }]}}
    s = from_espn(payload, game_id="g", pregame_spread=-3.0, pregame_total=46.0,
                  wind_mph=None, is_dome=True, ts=NOW)
    assert s is not None and s.is_halftime


def test_espn_refuses_to_build_a_state_from_a_broken_payload():
    """
    A half-built state that silently defaults to 0-0 in the first quarter is
    far worse than no state, because the engine would happily price it.
    """
    assert from_espn({"header": {"competitions": [{"status": {}}]}},
                     game_id="g", pregame_spread=0.0, pregame_total=44.0,
                     wind_mph=None, is_dome=True) is None
    assert from_espn({}, game_id="g", pregame_spread=0.0, pregame_total=44.0,
                     wind_mph=None, is_dome=True) is None


def test_dome_suppresses_wind_on_both_paths():
    row = dict(PBP_ROW, roof="closed", wind=18.0)
    s = from_pbp_row(row, ts=NOW)
    assert s.is_dome and s.wind_mph is None

    b = from_espn(ESPN_SUMMARY, game_id="g", pregame_spread=-3.0,
                  pregame_total=46.0, wind_mph=18.0, is_dome=True, ts=NOW)
    assert b.is_dome and b.wind_mph is None


@pytest.mark.parametrize("passes,plays,lo,hi", [
    (5, 5, 0.55, 0.75),        # tiny sample stays near the prior
    (0, 3, 0.45, 0.60),        # and never collapses to zero
    (70, 100, 0.60, 0.72),     # a real sample moves it
])
def test_pass_rate_shrinks_toward_the_league_prior(passes, plays, lo, hi):
    assert lo <= smooth_pass_rate(passes, plays) <= hi


def test_pass_rate_survives_garbage_input():
    for bad in (None, float("nan"), -1):
        assert 0.0 < smooth_pass_rate(0, bad) < 1.0
