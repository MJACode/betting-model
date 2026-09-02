"""The threshold sweep must measure the population the system will actually bet.

config.MODEL_MIN_ODDS downgrades BET -> NONE when the DK price is juicier than
the floor, and every prop model carries a -140 one. The sweep did not apply it,
so its recommended cuts were chosen on rows the live scorer refuses: measured
against production on 2026-08-31, the floor blocks 24-48% of the settled rows
for eight of the nine prop models. Both the ROI and the projected bets/week
were therefore describing a different system than the one running.
"""

from __future__ import annotations

import config
from scripts.calibrated_threshold_sweep import _apply_price_floor


def _row(odds: float) -> dict:
    return {"date": "2026-08-20", "p": 0.7, "implied": 0.6,
            "odds": odds, "result": "WIN", "units": 1.0}


# Fixtures use mlb_prop_batter_runs: batter_rbi, the original, was RETIRED
# 2026-09-02 and carries no floor any more.
def test_prices_juicier_than_the_floor_are_dropped():
    assert config.MODEL_MIN_ODDS["mlb_prop_batter_runs"] == -140
    kept = _apply_price_floor("mlb_prop_batter_runs",
                              [_row(-120), _row(-140), _row(-141), _row(-472)])
    assert [r["odds"] for r in kept] == [-120, -140]


def test_the_boundary_matches_the_scorer():
    """The scorer blocks on `dk_odds < floor` (_blocked_by_min_odds), so exactly -140 is BET, not NONE.

    An off-by-one here would silently move every prop model's population.
    """
    from models.scorer import _blocked_by_min_odds

    assert _blocked_by_min_odds("mlb_prop_batter_runs", -140) is False
    assert _blocked_by_min_odds("mlb_prop_batter_runs", -141) is True
    kept = [r["odds"] for r in _apply_price_floor("mlb_prop_batter_runs",
                                                  [_row(-140), _row(-141)])]
    assert kept == [-140]


def test_plus_money_always_survives():
    kept = _apply_price_floor("mlb_prop_batter_runs", [_row(500), _row(-110)])
    assert len(kept) == 2


def test_a_model_with_no_floor_is_untouched():
    assert "mlb_f5_moneyline" not in config.MODEL_MIN_ODDS
    rows = [_row(-195), _row(-110), _row(300)]
    assert _apply_price_floor("mlb_f5_moneyline", rows) == rows


def test_every_prop_model_in_the_sweep_has_a_floor_to_apply():
    """If a prop model ever loses its floor entry this test says so, rather
    than the sweep quietly widening that model's population again."""
    props = [m for m in config.ACTION_THRESHOLDS
             if m.startswith(("mlb_prop_", "wnba_prop_"))]
    missing = [m for m in props if m not in config.MODEL_MIN_ODDS]
    assert not missing, f"prop models with no MODEL_MIN_ODDS floor: {missing}"
