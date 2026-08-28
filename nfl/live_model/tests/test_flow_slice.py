"""
Guards on the slice that decides whether the lane is structural or narrow.

The statistical trap this file exists for: quotes inside one game share a
single actual final, so resampling QUOTES would shrink every interval by
roughly the square root of quotes per game and manufacture significance in
every bucket. The bootstrap must resample games.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from live_model.backtest.flow_slice import (  # noqa: E402
    _clustered_ci, slice_table, verdict,
)


def _frame(n_games=40, per_game=8, bias=-2.33, seed=0, **cols):
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_games):
        final = 30 + rng.normal(0, 6)
        # A PER GAME miss. Without this the error is iid across quotes and
        # there is no clustering for the bootstrap to respect, which is the
        # bug this fixture originally had: it tested nothing.
        game_miss = rng.normal(0, 3.0)
        for _ in range(per_game):
            rows.append({"game_id": f"g{g}", "actual_final": final,
                         "line": final + bias + game_miss
                                 + rng.normal(0, 0.4)})
    d = pd.DataFrame(rows)
    for k, v in cols.items():
        d[k] = v(d) if callable(v) else v
    return d


def test_bootstrap_resamples_games_not_quotes():
    """
    Same data, told two ways. Widening the interval when quotes are clustered
    is the whole point; a quote-level bootstrap would report a tight interval
    on what is really 40 observations.
    """
    d = _frame(n_games=40, per_game=8)
    err = (d.line - d.actual_final).to_numpy()
    lo_g, hi_g = _clustered_ci(err, d.game_id.to_numpy())
    # Pretend every quote is its own game: the naive, wrong way.
    lo_q, hi_q = _clustered_ci(err, np.arange(len(err)).astype(str))
    assert (hi_g - lo_g) > (hi_q - lo_q) * 2, "clustering must widen the CI"


def test_a_uniform_bias_reads_as_structural():
    # 200 games, not 40. With a realistic per game miss of about 3 attempts,
    # 40 games split four ways leaves each bucket unable to resolve a 2.33
    # bias at all, and the verdict correctly says MIXED. That is a POWER
    # limit rather than a flat bias, and it is the same limit the real pull
    # faces, which is why the report prints games per bucket.
    d = _frame(bias=-2.33, n_games=200)
    d["period"] = np.tile([1, 2, 3, 4], len(d) // 4 + 1)[:len(d)]
    d["season"] = 2024
    v = " ".join(verdict(slice_table(d)))
    assert "STRUCTURAL" in v


def test_a_bias_living_in_one_quarter_reads_as_concentrated():
    """The failure mode worth catching: a pooled number carried by a slice."""
    d = _frame(bias=0.0, n_games=60, per_game=8)
    d["period"] = np.tile([1, 2, 3, 4], len(d) // 4 + 1)[:len(d)]
    d.loc[d.period == 4, "line"] -= 9.0        # all of it in Q4
    d["season"] = 2024
    t = slice_table(d)
    v = " ".join(verdict(t))
    assert "STRUCTURAL" not in v
    assert "CONCENTRATED" in v or "MIXED" in v


def test_a_bucket_on_the_wrong_side_is_called_out():
    d = _frame(bias=-2.5, n_games=60, per_game=8)
    d["period"] = np.tile([1, 2, 3, 4], len(d) // 4 + 1)[:len(d)]
    d.loc[d.period == 1, "line"] += 8.0         # Q1 runs the other way
    d["season"] = 2024
    v = " ".join(verdict(slice_table(d)))
    assert "wrong side" in v


def test_mechanism_verdict_is_falsifiable_both_ways():
    # Flat across pass rate: the stated explanation is not supported.
    flat = _frame(bias=-2.33, n_games=60, per_game=8)
    flat["pass_rate_vs_league"] = np.tile(
        [-0.15, -0.05, 0.05, 0.15], len(flat) // 4 + 1)[:len(flat)]
    flat["season"] = 2024
    assert "MECHANISM NOT SUPPORTED" in " ".join(verdict(slice_table(flat)))

    # Deepening with pass rate: the explanation predicts exactly this.
    deep = flat.copy()
    deep["line"] = deep["line"] - 6.0 * (deep["pass_rate_vs_league"] + 0.15)
    assert "MECHANISM HOLDS" in " ".join(verdict(slice_table(deep)))


def test_thin_buckets_are_reported_but_do_not_vote():
    d = _frame(bias=-2.33, n_games=40, per_game=8)
    d["period"] = 1
    d.loc[d.index[:4], "period"] = 4            # a 4-quote bucket
    d["season"] = 2024
    t = slice_table(d)
    assert (t.quotes < 60).any(), "fixture must contain a thin bucket"
    assert "not enough quotes" not in " ".join(verdict(t))


def test_thin_buckets_trigger_a_power_warning_not_a_false_negative():
    """
    "MIXED" on 10 games a bucket means we could not see, not that there is
    nothing there. Reporting the first as the second is how a real lane gets
    killed by a small sample.
    """
    d = _frame(bias=-2.33, n_games=40)
    d["period"] = np.tile([1, 2, 3, 4], len(d) // 4 + 1)[:len(d)]
    d["season"] = 2024
    v = " ".join(verdict(slice_table(d)))
    assert "POWER WARNING" in v


def _table(rows):
    return pd.DataFrame([{"dimension": "quarter", "bucket": str(i),
                          "quotes": 500, "games": g, "bias": b,
                          "median": b, "ci_lo": lo, "ci_hi": hi,
                          "over_rate": 0.6}
                         for i, (g, b, lo, hi) in enumerate(rows)])


def test_no_power_warning_when_nothing_straddles():
    """Built directly: through a fixture, quartile buckets always vary in size."""
    v = " ".join(verdict(_table([(200, -2.3, -3.0, -1.6)] * 4)))
    assert "POWER WARNING" not in v
    assert "STRUCTURAL" in v


def test_no_power_warning_when_the_straddlers_are_well_populated():
    """
    A well populated bucket that still cannot show the bias is EVIDENCE, not
    a power limit, and must not be excused as one.
    """
    rows = [(200, -2.3, -3.0, -1.6)] * 3 + [(200, -0.1, -0.9, 0.7)]
    v = " ".join(verdict(_table(rows)))
    assert "POWER WARNING" not in v
