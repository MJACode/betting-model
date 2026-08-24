"""
Pure-math tests for the NCAAF margin/total regression harness — the grading
conventions here are the same §29 conventions a sign bug once corrupted in the
runline views, so they are pinned before the harness ever sees real data.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ncaaf_margin_eval import (  # noqa: E402
    BREAKEVEN, MARGIN_FEATURES, TOTAL_FEATURES,
    rmse, sweep_spread, sweep_total, verdict)


def test_market_numbers_are_not_regression_features():
    assert "spread_home" not in MARGIN_FEATURES
    assert "total_line" not in TOTAL_FEATURES


def test_spread_grading_home_and_away_sides():
    # Game 1: model says home by 10, spread home -3 (home favoured by 3),
    #   d = +7 → bet HOME -3; actual margin 7 → home covers → WIN.
    # Game 2: model says home by 1, spread home -6, d = -5 → bet AWAY +6;
    #   actual margin 3 → home wins by 3 but does NOT cover → away covers → WIN.
    # Game 3: model says home by 8, spread home -3, d = +5 → bet HOME -3;
    #   actual margin 2 → home fails to cover → LOSS.
    rows = sweep_spread(pred_margin=[10, 1, 8],
                        spread_home=[-3, -6, -3],
                        actual_margin=[7, 3, 2],
                        thresholds=[0, 5])
    at0 = rows[0]
    assert (at0["bets"], at0["wins"]) == (3, 2)
    at5 = rows[1]                      # all three have |d| >= 5
    assert (at5["bets"], at5["wins"]) == (3, 2)


def test_spread_push_excluded_from_record():
    # actual margin 3 vs home -3 → push: not a bet, not a loss.
    rows = sweep_spread([10], [-3], [3], thresholds=[0])
    assert rows[0]["bets"] == 0 and rows[0]["pushes"] == 1


def test_threshold_filters_small_disagreements():
    # d = +1 only — at threshold 3 no bet fires.
    rows = sweep_spread([4], [-3], [10], thresholds=[3])
    assert rows[0]["bets"] == 0


def test_total_grading_both_sides_and_push():
    # Over pick wins, under pick wins, push excluded.
    # Third game: the model DOES disagree (53 vs 50) but the game lands
    # exactly on the line — a selected bet that pushes.
    rows = sweep_total(pred_total=[60, 40, 53],
                       total_line=[52.5, 48.5, 50],
                       actual_total=[55, 41, 50],
                       thresholds=[0])
    assert (rows[0]["bets"], rows[0]["wins"], rows[0]["pushes"]) == (2, 2, 1)


def test_verdict_enforces_volume_and_breakeven():
    rows = [
        {"threshold": 1, "bets": 200, "wins": 100, "pushes": 0, "win_rate": 0.50},
        {"threshold": 5, "bets": 10, "wins": 9, "pushes": 0, "win_rate": 0.90},
    ]
    assert verdict(rows) is None          # 50% fails breakeven; 90% fails volume
    rows.append({"threshold": 3, "bets": 60, "wins": 33, "pushes": 0,
                 "win_rate": 33 / 60})
    best = verdict(rows)
    assert best is not None and best["threshold"] == 3
    assert 33 / 60 >= BREAKEVEN


def test_rmse():
    assert rmse([0, 0], [3, 4]) == pytest.approx((12.5) ** 0.5)
