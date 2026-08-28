"""
State reconstruction and harness alignment.

The two bugs pinned hardest here were both silent and both would have
invalidated every backtest number in the project:

  * nflverse mixes "...T02:08:57Z" and "...T02:10:13.383Z" in one column, and
    pandas infers a single format from the first value. The default parse threw
    away 15% of all timestamps, which then got forward filled, which put early
    third quarter plays BEFORE a halftime odds snapshot.
  * total_home_score is the POST-play running total. Reading it off the row
    trains the model on a state that already contains the touchdown it is
    supposed to be predicting.

Neither raised an error. Both are now tests.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from live_model.backtest.harness import (  # noqa: E402
    LANE_OF_MARKET, _settle, _state_at, _team_side, kill_verdict, summarise,
)
from live_model.backtest.states import build_states  # noqa: E402


def _pbp(rows) -> pd.DataFrame:
    base = {
        "game_id": "G1", "season": 2024, "week": 1, "season_type": "REG",
        "home_team": "KC", "away_team": "BAL", "posteam": "KC", "defteam": "BAL",
        "qtr": 1.0, "quarter_seconds_remaining": 900.0,
        "game_seconds_remaining": 3600.0, "half_seconds_remaining": 1800.0,
        "game_half": "Half1", "down": 1.0, "ydstogo": 10.0, "yardline_100": 75.0,
        "total_home_score": 0.0, "total_away_score": 0.0,
        "home_timeouts_remaining": 3.0, "away_timeouts_remaining": 3.0,
        "spread_line": 3.0, "total_line": 46.0, "roof": "outdoors", "wind": 8.0,
        "home_score": 27, "away_score": 20, "play_type": "pass",
        "pass": 1.0, "rush": 0.0, "penalty": 0.0, "timeout": 0.0, "desc": "",
        "time_of_day": "2024-09-06T00:44:42.100Z",
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def test_scores_are_pre_play_not_post_play():
    """
    The touchdown row must carry the score BEFORE the touchdown. Otherwise the
    target leaks into the features on every scoring play in the dataset.
    """
    df = _pbp([
        {"game_seconds_remaining": 3600.0, "total_home_score": 0.0},
        {"game_seconds_remaining": 3500.0, "total_home_score": 7.0},   # the TD
        {"game_seconds_remaining": 3400.0, "total_home_score": 7.0},
    ])
    st = build_states(df)
    assert list(st["home_score_pre"]) == [0.0, 0.0, 7.0]


def test_remaining_points_targets_reconcile_with_the_final_score():
    df = _pbp([
        {"game_seconds_remaining": 3600.0, "total_home_score": 0.0,
         "total_away_score": 0.0},
        {"game_seconds_remaining": 3000.0, "total_home_score": 14.0,
         "total_away_score": 7.0},
    ])
    st = build_states(df)
    assert st["home_score_pre"].iloc[0] + st["home_remaining_pts"].iloc[0] == 27
    assert st["away_score_pre"].iloc[1] + st["away_remaining_pts"].iloc[1] == 20


def test_fractional_second_timestamps_survive_parsing():
    """
    THE 15% BUG. pandas infers one format from the first non-null value, so a
    whole-second timestamp first makes every fractional one NaT.
    """
    df = _pbp([
        {"game_seconds_remaining": 3600.0, "time_of_day": "2024-09-06T00:44:42Z"},
        {"game_seconds_remaining": 3500.0, "time_of_day": "2024-09-06T00:46:16.737Z"},
        {"game_seconds_remaining": 3400.0, "time_of_day": "2024-09-06T00:47:01.512Z"},
    ])
    st = build_states(df)
    assert st["wall_ts"].notna().all()
    assert st["wall_ts"].is_monotonic_increasing
    assert st["wall_ts"].nunique() == 3          # none collapsed onto another


def test_timestamps_are_not_carried_across_the_halftime_break():
    """A 15 minute break with no plays must not be bridged by forward filling a
    first half timestamp onto a third quarter play."""
    df = _pbp([
        {"game_seconds_remaining": 1900.0, "qtr": 2.0, "game_half": "Half1",
         "time_of_day": "2024-09-06T02:10:45.297Z"},
        {"game_seconds_remaining": 1800.0, "qtr": 2.0, "game_half": "Half1",
         "quarter_seconds_remaining": 0.0, "time_of_day": None,
         "play_type": None},
        {"game_seconds_remaining": 1799.0, "qtr": 3.0, "game_half": "Half2",
         "time_of_day": "2024-09-06T02:25:39.880Z"},
    ])
    st = build_states(df).sort_values("game_seconds_remaining", ascending=False)
    gap = (st["wall_ts"].iloc[2] - st["wall_ts"].iloc[1]).total_seconds()
    assert gap > 600        # a real halftime, not zero


def test_a_wrong_date_component_is_repaired():
    """nflverse carries a full day offset on some rows, producing a 20 hour
    backstep mid quarter. 211 of 3,028 games are affected."""
    df = _pbp([
        {"game_seconds_remaining": 3600.0, "time_of_day": "2015-09-14T13:14:08Z"},
        {"game_seconds_remaining": 3500.0, "time_of_day": "2015-09-13T17:16:38Z"},
        {"game_seconds_remaining": 3400.0, "time_of_day": "2015-09-13T17:17:15Z"},
    ])
    st = build_states(df)
    assert st["wall_ts"].is_monotonic_increasing


def test_the_halftime_score_is_carried_on_every_row():
    df = _pbp([
        {"game_seconds_remaining": 3600.0, "qtr": 1.0, "game_half": "Half1"},
        {"game_seconds_remaining": 1810.0, "qtr": 2.0, "game_half": "Half1",
         "total_home_score": 13.0, "total_away_score": 10.0},
        {"game_seconds_remaining": 1700.0, "qtr": 3.0, "game_half": "Half2",
         "total_home_score": 13.0, "total_away_score": 10.0},
    ])
    st = build_states(df)
    assert set(st["half_home_score"]) == {13.0}
    assert set(st["half_away_score"]) == {10.0}


def test_the_spread_is_flipped_into_standard_form():
    st = build_states(_pbp([{"game_seconds_remaining": 3600.0}]))
    assert st["pregame_spread"].iloc[0] == -3.0     # nflverse +3 means home favored


def test_a_dome_suppresses_wind():
    st = build_states(_pbp([{"game_seconds_remaining": 3600.0, "roof": "closed"}]))
    assert bool(st["is_dome"].iloc[0])
    assert np.isnan(st["wind_mph"].iloc[0])


def test_overtime_is_excluded_from_training_states():
    df = _pbp([
        {"game_seconds_remaining": 100.0, "qtr": 4.0},
        {"game_seconds_remaining": 0.0, "qtr": 5.0, "game_half": "Overtime"},
    ])
    assert set(build_states(df)["qtr"]) == {4.0}


# ----------------------------------------------------------------- harness
def test_alignment_never_looks_forward():
    """
    A snapshot must be priced off a state that had already happened. Taking the
    nearest state in either direction is the in-play form of look-ahead bias
    and would manufacture edge out of nothing.
    """
    ts0 = datetime(2024, 9, 6, 2, 0, tzinfo=timezone.utc)
    g = pd.DataFrame({
        "wall_ts": [ts0, ts0 + timedelta(minutes=5), ts0 + timedelta(minutes=10)],
        "qtr": [1.0, 2.0, 3.0],
    })
    picked = _state_at(g, ts0 + timedelta(minutes=7))
    assert picked["qtr"] == 2.0
    assert _state_at(g, ts0 - timedelta(minutes=1)) is None


def test_settlement_of_each_market():
    row = pd.Series({"home_score_pre": 21.0, "away_score_pre": 17.0,
                     "half_home_score": 13.0, "half_away_score": 10.0})
    # final 27-20: total 47, margin +7, second half 14-10 = 24
    assert _settle("totals", "over", 45.5, row, 27, 20) == 1.0
    assert _settle("totals", "under", 45.5, row, 27, 20) == 0.0
    assert _settle("totals_h2", "over", 22.5, row, 27, 20) == 1.0
    assert _settle("spreads", "home", -3.5, row, 27, 20) == 1.0
    assert _settle("spreads", "away", -3.5, row, 27, 20) == 0.0
    assert _settle("spreads_h2", "home", -1.5, row, 27, 20) == 1.0
    assert _settle("team_totals", "over", 26.5, row, 27, 20,
                   team_side="home") == 1.0
    assert _settle("team_totals", "over", 20.5, row, 27, 20,
                   team_side="away") == 0.0


def test_a_push_settles_to_nan_not_to_a_loss():
    row = pd.Series({"home_score_pre": 0.0, "away_score_pre": 0.0,
                     "half_home_score": 0.0, "half_away_score": 0.0})
    assert np.isnan(_settle("totals", "over", 47.0, row, 27, 20))
    assert np.isnan(_settle("spreads", "home", -7.0, row, 27, 20))


def test_a_team_total_without_a_resolved_team_is_not_adjudicated():
    """Guessing which offence a line refers to is a coin flip. Refusing is the
    only honest option."""
    row = pd.Series({"home_score_pre": 0.0, "away_score_pre": 0.0})
    assert np.isnan(_settle("team_totals", "over", 20.5, row, 27, 20,
                            team_side=None))
    assert _team_side(None, "KC", "BAL") is None
    assert _team_side("KC", "KC", "BAL") == "home"
    assert _team_side("BAL", "KC", "BAL") == "away"
    assert _team_side("SF", "KC", "BAL") is None


def test_anchor_markets_are_never_a_bettable_lane():
    """Constraint 4: the live main line is truth. A backtest that let us bet it
    would be measuring our disagreement with the sharpest number on the board."""
    from live_model.backtest.harness import BETTABLE_LANES
    assert LANE_OF_MARKET["h2h"] == "anchor"
    assert LANE_OF_MARKET["totals"] == "anchor"
    assert "anchor" not in BETTABLE_LANES


def test_the_kill_criterion_cuts_a_lane_without_two_positive_seasons():
    """Encoded as code so it cannot be relitigated by looking at the numbers
    first and choosing a rule afterwards."""
    good = pd.DataFrame([
        {"lane": "halftime_2h", "season": 2023, "pseudo_clv_pp": 0.4},
        {"lane": "halftime_2h", "season": 2024, "pseudo_clv_pp": 0.2},
        {"lane": "derivative", "season": 2023, "pseudo_clv_pp": 0.5},
        {"lane": "derivative", "season": 2024, "pseudo_clv_pp": -0.1},
    ])
    v = kill_verdict(good)
    assert v["halftime_2h"]["status"] == "KEEP"
    assert v["derivative"]["status"] == "CUT"
    assert v["prop"]["status"] == "NO DATA"


def test_summarise_reports_roi_and_clv_per_lane_and_season():
    df = pd.DataFrame([
        {"lane": "halftime_2h", "season": 2024, "won": 1.0, "decimal": 1.91,
         "pseudo_clv": 0.02},
        {"lane": "halftime_2h", "season": 2024, "won": 0.0, "decimal": 1.91,
         "pseudo_clv": -0.01},
    ])
    s = summarise(df).iloc[0]
    assert s["settled"] == 2
    assert s["hit_rate"] == pytest.approx(0.5)
    assert s["roi"] == pytest.approx((0.91 - 1.0) / 2)
    assert s["pseudo_clv_pp"] == pytest.approx(0.5)
