"""The pass/fail script judges every band a lab writes (docs/nba_models_2026.md 9.1 bar 5, 10.6).

The sixth search writes six bands for its lowest cut, [0.10, inf) the sixth; a verdict that
read a fixed five would pass a cell whose highest-EV band lost.
"""
import numpy as np
import pandas as pd

from scripts import nba_game2_verdict as V


def _row(top_roi):
    r = {f"band{i}_n": 100 for i in range(6)}
    r.update({f"band{i}_roi": 0.05 for i in range(6)})
    r["band5_roi"] = top_roi
    return pd.Series(r)


def test_a_losing_sixth_band_fails_the_cell():
    assert V.bands_ok(_row(0.04))
    assert not V.bands_ok(_row(-0.08))


def test_a_thin_band_is_reported_not_judged():
    r = _row(-0.50)
    r["band5_n"] = V.BAND_MIN_BETS - 1
    assert V.bands_ok(r)


def test_the_earlier_five_band_rows_read_the_same():
    r = pd.Series({**{f"band{i}_n": 100 for i in range(5)}, **{f"band{i}_roi": 0.01 for i in range(5)}})
    assert V.band_slots(r) == 5 and V.bands_ok(r)
    r["band4_roi"] = np.nan
    assert not V.bands_ok(r)
