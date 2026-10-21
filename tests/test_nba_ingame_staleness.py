"""The staleness gate's scoring (scripts/nba_ingame_staleness.py,
docs/nba_models_2026.md 7.1 Step 0), on synthetic quotes.

Pinned: points are signed toward side A (home for the moneyline and spread,
both teams for the total); a push leaves the sample; a price that has not
absorbed recent scoring gives a slope whose interval sits above zero, and a
price that has absorbed it gives one that covers zero; a quote at another
number than Pinnacle's is left out of the panels measured against Pinnacle."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts import nba_ingame_staleness as S


def test_points_are_signed_toward_side_a():
    m = pd.Series(["h2h", "spreads", "totals"])
    x = S.signed_points(m, pd.Series([2, 2, 2]), pd.Series([3, 3, 3]))
    assert list(x) == [-1, -1, 5]


def test_a_push_leaves_the_sample():
    q = pd.DataFrame({"market": ["spreads", "spreads", "totals", "h2h"],
                      "line": [-3.0, -2.5, 211.0, np.nan],
                      "final_home": [103, 103, 110, 99], "final_away": [100, 100, 100, 100]})
    assert list(S.outcome(q).fillna(-1)) == [-1, 1, 0, 0]


def _synthetic(stale: bool, n_days: int = 300, per_day: int = 40, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = n_days * per_day
    x = rng.integers(-3, 4, size=n).astype(float)
    p = np.full(n, 0.5)
    true_p = np.clip(p + (0.04 * x if stale else 0.0), 0.01, 0.99)
    y = (rng.random(n) < true_p).astype(float)
    return pd.DataFrame({"game_date": np.repeat(np.arange(n_days), per_day),
                         "game_id": np.arange(n), "x": x, "resid": y - p})


def test_an_unabsorbed_score_gives_an_interval_above_zero():
    r = S.slope_ci(_synthetic(stale=True))
    assert r["lo"] > 0 and abs(r["slope"] - 0.04) < 0.01


def test_an_absorbed_score_gives_an_interval_that_covers_zero():
    r = S.slope_ci(_synthetic(stale=False))
    assert r["lo"] < 0 < r["hi"]


def test_a_quote_off_pinnacles_number_is_left_out_of_the_pinnacle_panels():
    base = {"coherent": True, "pin_fa": 0.5, "fa": 0.5, "final_home": 110, "final_away": 100,
            "season": 2024, "game_date": "2024-01-01", "game_id": "G"}
    q = pd.DataFrame([
        {**base, "book": "pinnacle", "market": "totals", "line": 220.5, "pin_line": 220.5},
        {**base, "book": "draftkings", "market": "totals", "line": 221.5, "pin_line": 220.5},
        {**base, "book": "fanduel", "market": "h2h", "line": np.nan, "pin_line": np.nan},
    ])
    p = S.panels(q)
    assert sorted(p["1 every book vs Pinnacle (pre-registered)"]["book"]) == ["fanduel", "pinnacle"]
    assert sorted(p["4 deciding books vs their own no-vig"]["book"]) == ["draftkings", "fanduel"]


def test_a_uniformly_miscalibrated_price_is_not_read_as_stale():
    # totals-shaped: points in the window are never negative, and the price is
    # 10 points too low on every quote whatever was scored. That is a level,
    # not staleness; the intercept must take it.
    rng = np.random.default_rng(3)
    n_days, per_day = 300, 40
    n = n_days * per_day
    x = rng.integers(0, 5, size=n).astype(float)
    y = (rng.random(n) < 0.6).astype(float)
    df = pd.DataFrame({"game_date": np.repeat(np.arange(n_days), per_day), "game_id": np.arange(n),
                       "x": x, "resid": y - 0.5})
    r = S.slope_ci(df)
    assert r["lo"] < 0 < r["hi"]
