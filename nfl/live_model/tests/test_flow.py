"""
Live prop flow: the correctness properties that took three wrong answers to find.

Every test here corresponds to a bug that produced a plausible looking but
false result. In order of how badly each one lied:

  1. Snapping to a player's LAST INVOLVEMENT instead of computing his accrual
     AS OF the decision point. A receiver whose final target came in the second
     quarter carried a second quarter accrual at the two minute warning while
     his remaining-production target still counted everything from the second
     quarter on. Production that had already happened was labelled as still to
     come. It made a receiver look like he had a third of his game left with
     five minutes to play.
  2. A degenerate anchor. The calibrated share fell to zero late, so the line
     sat exactly on the accrued total and "over" became "does he touch the ball
     once more". The model went 65 for 65.
  3. A strawman anchor. Pricing a back who already had five first quarter
     carries off his season average, which no live book does. Worth roughly six
     points of fake edge.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from live_model.backtest.flow_dataset import (  # noqa: E402
    MIN_BASELINE, accrual_at, build_baselines,
)
from live_model.backtest.flow_eval import (  # noqa: E402
    ANCHOR_ONLY_FEATURES, BREAKEVEN, apply_anchor, drop_degenerate,
    fit_time_curve, grade,
)
from live_model.engine.prop_flow import FEATURES, FLOW_MARKETS, naive_line  # noqa: E402


def _long():
    """A receiver whose only targets come early, plus one who plays throughout."""
    rows = [
        # early-only receiver: two catches in the first quarter
        {"game_id": "G", "player_id": "early", "seconds_remaining": 3400,
         "receptions": 1.0, "rec_yds": 12.0, "targets": 1.0},
        {"game_id": "G", "player_id": "early", "seconds_remaining": 3100,
         "receptions": 1.0, "rec_yds": 18.0, "targets": 1.0},
        # steady receiver: one catch per quarter
        {"game_id": "G", "player_id": "steady", "seconds_remaining": 3000,
         "receptions": 1.0, "rec_yds": 10.0, "targets": 1.0},
        {"game_id": "G", "player_id": "steady", "seconds_remaining": 1700,
         "receptions": 1.0, "rec_yds": 20.0, "targets": 1.0},
        {"game_id": "G", "player_id": "steady", "seconds_remaining": 500,
         "receptions": 1.0, "rec_yds": 30.0, "targets": 1.0},
    ]
    df = pd.DataFrame(rows)
    # accrual_at sums every tracked stat, so the frame has to carry them all.
    for col in ("pass_yds", "pass_att", "pass_cmp", "rush_yds", "rush_att"):
        df[col] = 0.0
    return df


def test_accrual_is_as_of_the_mark_not_the_last_involvement():
    """
    THE BUG THAT INFLATED EVERY LATE DECISION POINT.

    At the five minute mark the early-only receiver must show BOTH of his
    catches as already accrued. Snapping to his last row would have credited
    him with one and left the other in his remaining-production target.
    """
    long = _long()
    acc = accrual_at(long, 300).set_index("player_id")
    # Both of the early receiver's catches are behind him and must be accrued,
    # not sitting in his remaining-production target.
    assert acc.loc["early", "acc_receptions"] == 2.0
    assert acc.loc["early", "acc_rec_yds"] == 30.0

    # At the ten minute mark the steady receiver's 500-second catch has NOT
    # happened yet, so it belongs to remaining production and not to accrual.
    earlier = accrual_at(long, 600).set_index("player_id")
    assert earlier.loc["steady", "acc_receptions"] == 2.0
    assert acc.loc["steady", "acc_receptions"] == 3.0


def test_accrual_is_monotone_as_the_game_progresses():
    long = _long()
    prev = -1.0
    for mark in (3600, 2700, 1800, 900, 300, 0):
        acc = accrual_at(long, mark)
        total = float(acc["acc_receptions"].sum())
        assert total >= prev
        prev = total


def test_baselines_never_see_the_game_they_price():
    """A baseline that contains the game being predicted makes every measured
    edge fiction."""
    totals = pd.DataFrame([
        {"player_id": "p", "season": 2024, "game_id": "2024_01_A_B",
         "total_receptions": 2.0},
        {"player_id": "p", "season": 2024, "game_id": "2024_02_A_B",
         "total_receptions": 4.0},
        {"player_id": "p", "season": 2024, "game_id": "2024_03_A_B",
         "total_receptions": 12.0},
    ])
    for stat in ("pass_yds", "pass_att", "pass_cmp", "rush_yds", "rush_att",
                 "rec_yds", "targets"):
        totals[f"total_{stat}"] = 0.0
    b = build_baselines(totals).set_index("game_id")
    assert np.isnan(b.loc["2024_01_A_B", "baseline_receptions"])   # no history
    assert b.loc["2024_02_A_B", "baseline_receptions"] == 2.0      # game 1 only
    assert b.loc["2024_03_A_B", "baseline_receptions"] == 3.0      # games 1-2
    # The 12-reception game never appears in its own baseline.
    assert b.loc["2024_03_A_B", "baseline_receptions"] < 12.0


def test_prior_games_counts_only_prior_games():
    totals = pd.DataFrame([
        {"player_id": "p", "season": 2024, "game_id": f"2024_{i:02d}_A_B",
         **{f"total_{s}": 1.0 for s in
            ("pass_yds", "pass_att", "pass_cmp", "rush_yds", "rush_att",
             "rec_yds", "receptions", "targets")}}
        for i in range(1, 5)
    ])
    b = build_baselines(totals)
    assert list(b["prior_games"]) == [0, 1, 2, 3]


# ------------------------------------------------------------------ anchor
def _anchor_frame(accrued, baseline, frac):
    return pd.DataFrame([{
        "accrued": accrued, "baseline_per_game": baseline,
        "frac_remaining": frac, "decision_point": int(frac * 3600),
    }])


def test_the_anchor_blends_in_todays_pace():
    """
    A back with five first quarter carries against a 7.8 carry season average
    is having a bigger day than his average, and any live book's number
    reflects that. An anchor that ignores it is a strawman worth about six
    points of fake edge.
    """
    curve = {900: 0.25, 2700: 0.70}
    hot = apply_anchor(_anchor_frame(accrued=8.0, baseline=8.0, frac=0.75), curve)
    cold = apply_anchor(_anchor_frame(accrued=1.0, baseline=8.0, frac=0.75), curve)
    assert hot["anchor_baseline"].iloc[0] > cold["anchor_baseline"].iloc[0]
    assert hot["naive_remaining"].iloc[0] > cold["naive_remaining"].iloc[0]


def test_the_pace_blend_grows_as_the_game_is_observed():
    curve = {2700: 0.70, 900: 0.25}
    early = apply_anchor(_anchor_frame(8.0, 8.0, 0.75), curve)
    late = apply_anchor(_anchor_frame(24.0, 8.0, 0.25), curve)
    # Late, with three quarters observed, today's pace should dominate.
    assert late["anchor_baseline"].iloc[0] > early["anchor_baseline"].iloc[0]


def test_a_degenerate_line_is_dropped():
    """
    When the anchor's remaining component collapses, the line sits on the
    accrued total and "over" degenerates into "does he touch the ball once
    more". Measured, the model went 65 for 65 on those.
    """
    d = pd.DataFrame({
        "naive_remaining": [0.0, 0.4, 3.0],
        "market": ["player_receptions"] * 3,
    })
    kept = drop_degenerate(d, "player_receptions")
    assert list(kept["naive_remaining"]) == [3.0]


def test_every_market_has_a_degeneracy_floor_and_a_population_floor():
    from live_model.backtest.flow_eval import MIN_LIVE_REMAINING
    for market, stat in FLOW_MARKETS.items():
        assert market in MIN_LIVE_REMAINING, market
        assert stat in MIN_BASELINE, stat


def test_the_time_curve_is_fitted_only_on_training_rows():
    train = pd.DataFrame({
        "decision_point": [1800] * 5,
        "actual_remaining": [5.0, 5.0, 5.0, 5.0, 5.0],
        "baseline_per_game": [10.0] * 5,
    })
    assert fit_time_curve(train)[1800] == pytest.approx(0.5)


def test_naive_line_is_accrued_plus_a_prorate():
    assert naive_line(55, 70, 0.5) == pytest.approx(90.0)
    assert naive_line(70, 70, 0.0) == pytest.approx(70.0)


# ------------------------------------------------------------------ grading
def test_grading_picks_the_side_the_model_disagrees_on():
    d = pd.DataFrame({
        "model_final": [12.0, 6.0, 9.0],
        "naive_final": [9.0, 9.0, 9.0],
        "actual_final": [14.0, 14.0, 9.0],
    })
    g = grade(d)
    assert list(g["side"]) == ["over", "under", "under"]
    assert g["won"].iloc[0] == 1.0      # bet over, went over
    assert g["won"].iloc[1] == 0.0      # bet under, went over
    assert np.isnan(g["won"].iloc[2])   # landed on the number: a push


def test_deviation_is_scale_free():
    """One gate grid has to work across receptions (~2) and passing yards
    (~250), so the deviation is a fraction of the line, not an absolute."""
    d = pd.DataFrame({
        "model_final": [3.0, 300.0],
        "naive_final": [2.0, 200.0],
        "actual_final": [3.0, 300.0],
    })
    g = grade(d)
    assert g["dev_frac"].iloc[0] == pytest.approx(g["dev_frac"].iloc[1])


# ------------------------------------------------------------------ control
def test_the_control_carries_no_game_flow_features():
    """
    The control exists so the headline can never be read as the edge. If a
    score, pace or usage feature leaks into it, the decomposition silently
    stops measuring anything.
    """
    banned = ("margin", "pass_rate", "pace", "usage", "trailing", "leading",
              "spread", "total", "wind", "dome", "home")
    for f in ANCHOR_ONLY_FEATURES:
        assert not any(b in f for b in banned), f
    assert set(ANCHOR_ONLY_FEATURES) < set(FEATURES)


def test_the_control_is_strictly_smaller_than_the_full_model():
    assert len(ANCHOR_ONLY_FEATURES) < len(FEATURES)
    flow_features = set(FEATURES) - set(ANCHOR_ONLY_FEATURES)
    # The thesis lives in these. If this set empties, the experiment is void.
    assert {"team_margin", "team_margin_x_frac", "team_pass_rate"} <= flow_features


def test_breakeven_is_the_real_vig_hurdle():
    """52.38% is -110 both ways. Anything below is a losing bet however
    impressive it looks next to 50%."""
    assert BREAKEVEN == pytest.approx(110 / 210, abs=1e-4)


# ------------------------------------------------ validation against real lines
def test_name_normalisation_handles_the_real_hard_cases():
    from live_model.backtest.flow_validate import norm_name
    assert norm_name("Amon-Ra St. Brown") == "amon ra st brown"
    assert norm_name("Ja'Marr Chase") == "jamarr chase"
    assert norm_name("A.J. Brown") == "a j brown"
    assert norm_name("Odell Beckham Jr.") == norm_name("Odell Beckham")
    assert norm_name(None) == ""


def test_an_ambiguous_name_resolves_to_nothing_without_era_context():
    """
    Suffix stripping collides fathers with sons. Marvin Harrison Jr. normalises
    onto his father. Guessing is worse than dropping: a prop matched to the
    wrong player is a silently wrong bet.
    """
    import live_model.backtest.flow_validate as fv

    fake = pd.DataFrame([
        {"gsis_id": "00-0000001", "display_name": "Marvin Harrison"},
        {"gsis_id": "00-0039849", "display_name": "Marvin Harrison Jr."},
        {"gsis_id": "00-0033873", "display_name": "Patrick Mahomes"},
    ])
    orig = pd.read_parquet
    try:
        pd.read_parquet = lambda *a, **k: fake            # noqa: E731
        fv.PLAYERS.parent.mkdir(parents=True, exist_ok=True)
        fv.PLAYERS.touch()
        idx = fv.name_index()
        assert "marvin harrison" not in idx               # refused
        assert idx["patrick mahomes"] == "00-0033873"     # unambiguous

        # With era context exactly one candidate played, so it resolves.
        idx2 = fv.name_index(era_ids={"00-0039849"})
        assert idx2["marvin harrison"] == "00-0039849"

        # Two candidates in the era is still ambiguous, so still refused.
        idx3 = fv.name_index(era_ids={"00-0000001", "00-0039849"})
        assert "marvin harrison" not in idx3
    finally:
        pd.read_parquet = orig


def test_real_line_grading_uses_the_quoted_price_not_a_flat_vig():
    """
    Books juice prop overs. An edge measured at an assumed -110 can vanish once
    the actual number is used, so ROI is computed on the price that was
    actually on the board.
    """
    from live_model.backtest.flow_validate import grade_real
    d = pd.DataFrame({
        "model_final": [6.0, 6.0, 2.0],
        "line": [4.5, 4.5, 4.5],
        "actual_final": [6.0, 3.0, 3.0],
        "price": [-140.0, -140.0, 120.0],
    })
    g = grade_real(d)
    assert list(g["bet_side"]) == ["over", "over", "under"]
    assert list(g["won"]) == [1.0, 0.0, 1.0]
    assert g["profit"].iloc[0] == pytest.approx(100 / 140, abs=1e-6)  # juiced win
    assert g["profit"].iloc[1] == pytest.approx(-1.0)
    assert g["profit"].iloc[2] == pytest.approx(1.2)                   # plus money


def test_a_push_on_a_whole_number_line_is_not_a_loss():
    from live_model.backtest.flow_validate import grade_real
    d = pd.DataFrame({"model_final": [6.0], "line": [4.0],
                      "actual_final": [4.0], "price": [-110.0]})
    g = grade_real(d)
    assert np.isnan(g["won"].iloc[0])
    assert g["profit"].iloc[0] == 0.0
