"""The backtest's universe diagnostic must report what the MODEL said.

The universe block compared the actual over-rate to the book's de-vigged one
and never recorded the model's own mean P(over). So a lane betting under 87%
of the time read as a strategy, when it was ten models putting P(over) 0.5 to
5.3pp below the rate at which overs actually land. The number that would have
said so on day one is `model_over_pct`, and this pins it.
"""
from __future__ import annotations

from models.nfl_prop_backtest import _universe_summary


def _universe(n_over=470, n_under=530, model_over=0.45, pred=57.5, actual=59.5):
    n = n_over + n_under
    return {"over": n_over, "under": n_under, "push": 0, "sum_diff": 0.0,
            "sum_fair_over": 0.501 * n, "priced": n,
            "sum_model_over": model_over * n, "sum_pred": pred * n,
            "sum_actual": actual * n}


def test_model_over_rate_and_its_gap_are_reported():
    out = _universe_summary(_universe())
    assert out["over_pct"] == 47.0
    assert out["model_over_pct"] == 45.0
    # NEGATIVE = the model thinks overs rarer than they are: the 87%-unders bias.
    assert out["model_gap_pp"] == -2.0


def test_mean_projection_and_mean_actual_separate_mean_bias_from_shape_bias():
    out = _universe_summary(_universe(pred=57.55, actual=59.52))
    assert out["mean_pred"] == 57.55
    assert out["mean_actual"] == 59.52


def test_a_universe_without_the_model_sums_still_summarises():
    """Older callers build the dict without the model fields; they must not
    start raising."""
    u = _universe()
    for k in ("sum_model_over", "sum_pred", "sum_actual"):
        u.pop(k)
    out = _universe_summary(u)
    assert out["over_pct"] == 47.0
    assert "model_over_pct" not in out
