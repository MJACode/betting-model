"""
Guards on the grading join.

The first real grading run reported 78% hit rates and +47% ROI, in the CONTROL
arm as well as the full one. That is not an edge, it is a broken join: quotes
were matched to model states from later in the game, and every proposition was
graded twice, once at the price of the side it did not take.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from live_model.backtest import flow_validate as fv


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    """One game, one player, states every 300 seconds of a 2015 week 1 game."""
    kickoff = pd.Timestamp("2015-09-13T17:00:00Z")
    secs = [2700, 2100, 1800, 1500, 900, 600, 300]
    states = pd.DataFrame({
        "game_id": ["2015_01_BAL_DEN"] * len(secs),
        "seconds_remaining": [float(s) for s in secs],
        # Clock runs down as wall time runs up.
        "wall_ts": [kickoff + pd.Timedelta(seconds=(2700 - s) * 2)
                    for s in secs],
    })
    monkeypatch.setattr(fv, "ARTIFACT_DIR", tmp_path)
    states.to_parquet(tmp_path / "states_all.parquet", index=False)
    return kickoff


def _preds(decision_points, arm="full"):
    return pd.DataFrame({
        "game_id": ["2015_01_BAL_DEN"] * len(decision_points),
        "player_id": ["00-0000001"] * len(decision_points),
        "market": ["player_pass_attempts"] * len(decision_points),
        "decision_point": [int(d) for d in decision_points],
        "model_final": [30.0 + i for i in range(len(decision_points))],
        "actual_final": [33.0] * len(decision_points),
        "arm": [arm] * len(decision_points),
    })


def _quote(ts, line=31.5, home="Denver Broncos", away="Baltimore Ravens",
           commence="2015-09-13T17:00:00Z"):
    return pd.DataFrame([{
        "ts": ts, "commence_time": commence,
        "home_team": home, "away_team": away,
        "book": "draftkings", "market": "player_pass_attempts",
        "player_name": "Test Player", "line": line,
        "over_price": -115.0, "under_price": -105.0,
        "player_id": "00-0000001",
    }])


def test_never_prices_against_a_later_state(synthetic):
    """A quote must never be matched to a state the book had not yet seen."""
    kickoff = synthetic
    # Quote published two minutes in, when 2700 seconds remained.
    quote_ts = (kickoff + pd.Timedelta(seconds=120)).isoformat().replace(
        "+00:00", "Z")
    out = fv.match_to_flow(_quote(quote_ts), _preds([2700, 1800, 600]))
    assert len(out) == 1
    assert out.iloc[0]["decision_point"] == 2700.0
    assert out.iloc[0]["wall_ts"] <= out.iloc[0]["ts_dt"]


def test_uses_the_freshest_state_the_clock_allows(synthetic):
    kickoff = synthetic
    # 2700 seconds of wall time in, the 900 mark has passed but 600 has not.
    quote_ts = (kickoff + pd.Timedelta(seconds=3700)).isoformat().replace(
        "+00:00", "Z")
    out = fv.match_to_flow(_quote(quote_ts), _preds([2700, 1800, 900, 600]))
    assert len(out) == 1
    assert out.iloc[0]["decision_point"] == 900.0


def test_a_quote_before_any_state_is_dropped(synthetic):
    kickoff = synthetic
    pregame = (kickoff - pd.Timedelta(hours=1)).isoformat().replace(
        "+00:00", "Z")
    out = fv.match_to_flow(_quote(pregame), _preds([2700, 1800]))
    assert out.empty


def test_cannot_match_a_different_game(synthetic):
    """The same player in another matchup must not resolve to this game."""
    kickoff = synthetic
    quote_ts = (kickoff + pd.Timedelta(seconds=600)).isoformat().replace(
        "+00:00", "Z")
    other = _quote(quote_ts, home="Green Bay Packers", away="Chicago Bears")
    assert fv.match_to_flow(other, _preds([2700, 1800])).empty


def test_a_far_away_kickoff_is_a_different_season(synthetic):
    kickoff = synthetic
    quote_ts = (kickoff + pd.Timedelta(seconds=600)).isoformat().replace(
        "+00:00", "Z")
    stale = _quote(quote_ts, commence="2016-09-11T17:00:00Z")
    assert fv.match_to_flow(stale, _preds([2700, 1800])).empty


def test_each_arm_keeps_its_own_row(synthetic):
    kickoff = synthetic
    quote_ts = (kickoff + pd.Timedelta(seconds=3700)).isoformat().replace(
        "+00:00", "Z")
    preds = pd.concat([_preds([2700, 900], "full"),
                       _preds([2700, 900], "control")], ignore_index=True)
    out = fv.match_to_flow(_quote(quote_ts), preds)
    assert sorted(out["arm"]) == ["control", "full"]
    assert set(out["decision_point"]) == {900.0}


def test_grades_at_the_price_of_the_side_taken():
    d = pd.DataFrame([
        # Model above the line -> over, must use the over price.
        {"model_final": 34.0, "line": 31.5, "actual_final": 33.0,
         "over_price": 100.0, "under_price": -500.0},
        # Model below the line -> under, must use the under price.
        {"model_final": 28.0, "line": 31.5, "actual_final": 33.0,
         "over_price": -500.0, "under_price": 100.0},
    ])
    g = fv.grade_real(d)
    assert list(g["bet_side"]) == ["over", "under"]
    assert list(g["price"]) == [100.0, 100.0]
    # The over won at +100; the under lost.
    assert g.iloc[0]["won"] == 1.0 and g.iloc[0]["profit"] == pytest.approx(1.0)
    assert g.iloc[1]["won"] == 0.0 and g.iloc[1]["profit"] == pytest.approx(-1.0)


def test_a_push_is_not_a_loss():
    d = pd.DataFrame([{"model_final": 34.0, "line": 33.0, "actual_final": 33.0,
                       "over_price": -110.0, "under_price": -110.0}])
    g = fv.grade_real(d)
    assert np.isnan(g.iloc[0]["won"]) and g.iloc[0]["profit"] == 0.0
