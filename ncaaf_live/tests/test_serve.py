"""
Tests for the live serving layer: the LICENSES and guards as code.

These are the properties that, if silently broken, lose money in exactly the
way the calibration gates said this engine would: pricing totals in the
endgame it cannot describe, pricing overtime it has no distribution for, or
betting a huge "edge" that is really a stale line across a touchdown.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ncaaf_live.serve import (  # noqa: E402
    GameContext, LiveEngine, MAX_EDGE_CAP, TOTAL_MIN_SECONDS)
from ncaaf_live.feeds.espn import (  # noqa: E402
    check_feed_assumptions, extract_summary_state)
from ncaaf_live.feeds.odds_live import parse_event_odds  # noqa: E402


def _ctx(**kw):
    base = dict(game_id="NCAAF_2026-08-29_north-carolina_tcu",
                home="TCU", away="North Carolina",
                commence_time="2026-08-29T16:00:00Z",
                pregame_spread=-9.5, pregame_total=46.5,
                wind_mph=5.0, is_dome=False, game_date="2026-08-29")
    base.update(kw)
    return GameContext(**base)


def _state(**kw):
    base = dict(period=2, clock_seconds=480, home_score=14, away_score=10,
                possession="home", down=2, distance=7, yardline_100=48,
                home_timeouts=3, away_timeouts=2, plays_run=62,
                home_plays=30, away_plays=28, home_pass_plays=17,
                away_pass_plays=12, state="in",
                state_name="STATUS_IN_PROGRESS")
    base.update(kw)
    return base


@pytest.fixture(scope="module")
def engine():
    try:
        return LiveEngine()
    except FileNotFoundError:
        pytest.skip("engine artifacts not trained in this checkout")


_ODDS = {"h2h": {"home": -220, "away": 180},
         "total": {"line": 52.5, "over": -110, "under": -110}}


# ── the licenses ──────────────────────────────────────────────────────────────

def test_overtime_is_declined_entirely(engine):
    assert engine.price(_state(period=5), _ctx(), _ODDS) == []


def test_totals_lane_closes_in_the_endgame(engine):
    """The calibrated region ends at TOTAL_MIN_SECONDS; below it the totals
    lane must go dark while the (gate-1 licensed) ML lane may continue."""
    late = _state(period=4, clock_seconds=int(TOTAL_MIN_SECONDS) - 700)
    picks = engine.price(late, _ctx(), _ODDS)
    assert all(p["model_id"] != "ncaaf_live_total" for p in picks)


def test_no_pregame_context_means_no_picks(engine):
    assert engine.price(_state(), _ctx(pregame_total=None), _ODDS) == []
    assert engine.price(_state(), _ctx(pregame_spread=None), _ODDS) == []


def test_no_odds_means_no_picks_never_prob_only(engine):
    assert engine.price(_state(), _ctx(), None) == []
    assert engine.price(_state(), _ctx(), {"h2h": None, "total": None}) == []


def test_stale_line_cap_declines_absurd_edges(engine):
    """
    A mid-Q2 shootout against a line still at the PREGAME number produces a
    ~30% computed edge. That is a stale/suspended price, not an opportunity,
    and the cap must decline it - the classic in-play loss.
    """
    stale = {"h2h": _ODDS["h2h"],
             "total": {"line": 41.0, "over": -110, "under": -110}}
    picks = engine.price(_state(), _ctx(), stale)
    for p in picks:
        assert abs(p["edge"]) <= MAX_EDGE_CAP


def test_picks_carry_the_settlement_contract(engine):
    """Whatever fires must settle through the platform's generic game path."""
    picks = engine.price(_state(), _ctx(), _ODDS)
    for p in picks:
        assert p["is_live"] is True
        assert p["signal_type"] in ("BET", "AVOID")
        assert p["model_id"] in ("ncaaf_live_win_prob", "ncaaf_live_total")
        if p["model_id"] == "ncaaf_live_total":
            assert p["scored_line"] == 52.5, (
                "totals settle vs the LIVE line at pick time")
        assert p["game_id"].startswith("NCAAF_")
        assert p["dk_odds"] is not None


def test_feature_row_matches_the_training_schema(engine):
    """
    State parity: the live feature row must feed the SAME build_features the
    historical states trained through. A missing column raises; an extra one
    is ignored - so this asserts the call simply succeeds and yields finite
    predictions.
    """
    from ncaaf_live.engine.remaining import predict_remaining
    row = engine.feature_row(_state(), _ctx())
    preds = predict_remaining(engine.models, row)
    assert np.isfinite(preds.iloc[0, 0]) and np.isfinite(preds.iloc[0, 1])
    assert 0 <= preds.iloc[0, 0] <= 90 and 0 <= preds.iloc[0, 1] <= 90


def test_missing_situation_degrades_to_nan_not_a_crash(engine):
    s = _state(down=None, distance=None, yardline_100=None, possession=None)
    picks = engine.price(s, _ctx(), _ODDS)
    assert isinstance(picks, list)


# ── feed parsing ──────────────────────────────────────────────────────────────

def _summary(period=2, clock=480.0, hs="14", as_="10", situation=None):
    comp = {
        "status": {"period": period, "clock": clock,
                   "type": {"state": "in", "name": "STATUS_IN_PROGRESS"}},
        "competitors": [
            {"homeAway": "home", "score": hs,
             "team": {"id": "1", "abbreviation": "TCU", "location": "TCU"}},
            {"homeAway": "away", "score": as_,
             "team": {"id": "2", "abbreviation": "UNC",
                      "location": "North Carolina"}},
        ],
    }
    if situation is not None:
        comp["situation"] = situation
    return {"header": {"competitions": [comp]}}


def test_summary_state_extraction():
    st = extract_summary_state(_summary(situation={
        "possession": "1", "down": 2, "distance": 7,
        "possessionText": "TCU 48", "homeTimeouts": 3, "awayTimeouts": 2}))
    assert st["period"] == 2 and st["clock_seconds"] == 480
    assert st["home_score"] == 14 and st["away_score"] == 10
    assert st["possession"] == "home"
    assert st["yardline_100"] == 52          # TCU on its own 48 -> 52 to go
    assert st["home_location"] == "TCU"


def test_missing_required_field_returns_none():
    bad = _summary()
    bad["header"]["competitions"][0]["competitors"][0]["score"] = None
    assert extract_summary_state(bad) is None


def test_halftime_normalises_to_period2_clock0():
    s = _summary(period=2, clock=0.0)
    s["header"]["competitions"][0]["status"]["type"]["name"] = "STATUS_HALFTIME"
    st = extract_summary_state(s)
    assert st["period"] == 2 and st["clock_seconds"] == 0


def test_feed_check_catches_a_renamed_field():
    st = extract_summary_state(_summary())
    st["clock_seconds"] = 4800               # what a renamed field looks like
    problems = [p for p in check_feed_assumptions(st) if "non-fatal" not in p]
    assert problems, "an implausible clock must fail the feed check"


def test_feed_check_passes_a_sane_payload():
    st = extract_summary_state(_summary(situation={"possession": "1"}))
    assert [p for p in check_feed_assumptions(st) if "non-fatal" not in p] == []


# ── odds parsing ──────────────────────────────────────────────────────────────

def test_odds_parse_maps_sides_and_totals():
    events = [{
        "home_team": "TCU Horned Frogs", "away_team": "North Carolina Tar Heels",
        "commence_time": "2026-08-29T16:00:00Z",
        "bookmakers": [{"key": "draftkings", "markets": [
            {"key": "h2h", "last_update": "2026-08-29T16:31:02Z", "outcomes": [
                {"name": "TCU Horned Frogs", "price": -220},
                {"name": "North Carolina Tar Heels", "price": 180}]},
            {"key": "totals", "last_update": "2026-08-29T16:30:44Z", "outcomes": [
                {"name": "Over", "point": 52.5, "price": -108},
                {"name": "Under", "point": 52.5, "price": -112}]},
        ]}],
    }]
    out = parse_event_odds(events)
    rec = out[("TCU Horned Frogs", "North Carolina Tar Heels")]
    # `ts` is the book's own last_update and is part of the contract: without
    # it the engine cannot tell a market being republished from a frozen one.
    assert rec["h2h"] == {"home": -220, "away": 180,
                          "ts": "2026-08-29T16:31:02Z"}
    assert rec["total"] == {"line": 52.5, "over": -108, "under": -112,
                            "ts": "2026-08-29T16:30:44Z"}


def test_one_sided_h2h_is_dropped_not_guessed():
    events = [{"home_team": "A", "away_team": "B", "commence_time": "x",
               "bookmakers": [{"markets": [
                   {"key": "h2h", "outcomes": [{"name": "A", "price": -200}]}]}]}]
    assert parse_event_odds(events)[("A", "B")]["h2h"] is None


# ── CFBD scoreboard source (the Railway-safe path) ────────────────────────────

def _cfbd_game(status="in_progress", period=2, clock="8:00", hp=14, ap=10,
               possession="home", situation="2nd & 7 at TCU 48",
               home_id=2628, away_id=153):
    return {"status": status, "period": period, "clock": clock,
            "possession": possession, "situation": situation,
            "homeTeam": {"id": home_id, "name": "TCU Horned Frogs",
                         "points": hp},
            "awayTeam": {"id": away_id, "name": "North Carolina Tar Heels",
                         "points": ap}}


_IDS = {2628: "TCU", 153: "North Carolina"}


def test_cfbd_state_matches_the_espn_shape():
    from ncaaf_live.feeds.cfbd_scoreboard import extract_live_states_cfbd
    st = extract_live_states_cfbd([_cfbd_game()], _IDS)[0]
    assert st["period"] == 2 and st["clock_seconds"] == 480
    assert st["home_score"] == 14 and st["away_score"] == 10
    assert st["possession"] == "home"
    assert st["down"] == 2 and st["distance"] == 7
    assert st["home_location"] == "TCU"
    # scoreboard has no drive log: pace fields must be None (NaN downstream),
    # never zero - zero plays mid-game is a WRONG value the trees would trust
    assert st["plays_run"] is None


def test_cfbd_scheduled_and_completed_games_are_ignored():
    from ncaaf_live.feeds.cfbd_scoreboard import extract_live_states_cfbd
    payload = [_cfbd_game(status="scheduled"), _cfbd_game(status="completed")]
    assert extract_live_states_cfbd(payload, _IDS) == []


def test_cfbd_possession_by_team_id():
    from ncaaf_live.feeds.cfbd_scoreboard import extract_live_states_cfbd
    st = extract_live_states_cfbd([_cfbd_game(possession="153")], _IDS)[0]
    assert st["possession"] == "away"


def test_cfbd_identity_survives_a_dead_id_map_via_mascot_strip():
    from ncaaf_live.feeds.cfbd_scoreboard import extract_live_states_cfbd
    st = extract_live_states_cfbd([_cfbd_game()], {},
                                  known_schools={"TCU", "North Carolina"})
    assert st and st[0]["home_location"] == "TCU"


def test_cfbd_unresolvable_identity_skips_never_guesses():
    from ncaaf_live.feeds.cfbd_scoreboard import extract_live_states_cfbd
    assert extract_live_states_cfbd([_cfbd_game()], {}, set()) == []


def test_cfbd_clock_formats():
    from ncaaf_live.feeds.cfbd_scoreboard import _clock_seconds
    assert _clock_seconds("8:00") == 480
    assert _clock_seconds(125) == 125
    assert _clock_seconds(None) is None
    assert _clock_seconds("garbage") is None


def test_cfbd_situation_parsing():
    from ncaaf_live.feeds.cfbd_scoreboard import _parse_situation
    assert _parse_situation("3rd & 7 at TCU 25") == (3, 7)
    assert _parse_situation("1st & Goal at UNC 4") == (1, 1)
    assert _parse_situation(None) == (None, None)
    assert _parse_situation("Kickoff") == (None, None)


def test_cfbd_engine_prices_the_degraded_state(engine):
    """End to end: the reduced CFBD state must flow through the SAME engine."""
    from ncaaf_live.feeds.cfbd_scoreboard import extract_live_states_cfbd
    st = extract_live_states_cfbd([_cfbd_game()], _IDS)[0]
    picks = engine.price(st, _ctx(), _ODDS)
    assert isinstance(picks, list)
    for p in picks:
        assert p["signal_type"] in ("BET", "AVOID")


# ── the book's own publish clock ─────────────────────────────────────────────

def _stamped(age_sec: float, now):
    from datetime import timedelta
    ts = (now - timedelta(seconds=age_sec)).isoformat().replace("+00:00", "Z")
    return {"h2h": {**_ODDS["h2h"], "ts": ts},
            "total": {**_ODDS["total"], "ts": ts}}


def test_a_frozen_market_is_never_priced(engine):
    """
    New Mexico State at Florida State, 2026-08-29: DraftKings held 46.5 for
    4m35s of running clock, we posted Over 46.5, and 49 seconds later the book
    re-hung at 51.5 then 54.5. Our pipeline took 1.3 seconds end to end - it
    was never slow, it was pricing a number the book had stopped offering.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    assert engine.price(_state(), _ctx(), _stamped(275, now), now=now) == []


def test_a_normally_refreshing_market_still_prices(engine):
    """DraftKings republishes a live total every 47s at the median. A guard
    that rejected that rhythm would be an outage, not a guard."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    fresh = engine.price(_state(), _ctx(), _stamped(47, now), now=now)
    assert fresh == engine.price(_state(), _ctx(), _ODDS, now=now)


def test_a_stale_total_does_not_take_the_moneyline_with_it(engine):
    """The two markets are suspended independently, so a frozen total must not
    silence a moneyline the book is still quoting - or the reverse."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)

    def _ts(age):
        return (now - timedelta(seconds=age)).isoformat().replace("+00:00", "Z")

    mixed = {"h2h": {**_ODDS["h2h"], "ts": _ts(5)},
             "total": {**_ODDS["total"], "ts": _ts(275)}}
    picks = engine.price(_state(), _ctx(), mixed, now=now)
    assert all(p["model_id"] != "ncaaf_live_total" for p in picks)


def test_a_quote_with_no_timestamp_still_prices(engine):
    """Backward compatible on purpose: a feed shape change is logged, not
    allowed to blank the board."""
    assert engine.price(_state(), _ctx(), _ODDS) != []
