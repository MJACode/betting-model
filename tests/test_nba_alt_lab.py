"""The sixth search's lab: rules its synthetic market does not reach (docs/nba_models_2026.md 10.4, 11.5)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts import nba_game6_alt as A
from scripts import nba_game_harness as H

T = pd.Timestamp("2025-01-15T23:05:56Z")


def _q(book, market, line, pa, pb, at):
    return {"game_id": "G1", "season": 2025, "game_date": "2025-01-15", "tip": pd.Timestamp("2025-01-16T00:10:00Z"),
            "market": market, "book": book, "snapshot_at": at, "fetch_at": at, "line": line,
            "price_a": pa, "price_b": pb, "coherent": True}


def test_a_book_s_main_is_its_main_market_quote_not_a_ladder_rung():
    """DraftKings' ladder skips its main (-1.0): the ladder's closest-to-even rung is -2.5.
    The main must come from the main-market quote, so -1.0 rungs are not 'alternates' and
    the ladder is not dropped as unmoved against Pinnacle's -1.0."""
    ladder = pd.DataFrame([_q("draftkings", "spreads", ln, pa, pb, T) for ln, pa, pb in
                           ((-2.5, 100, -135), (1.5, -140, 105), (-5.5, 150, -190), (4.5, -200, 160))]
                          + [_q("pinnacle", "spreads", -1.0, -102, -108, T)])
    full = pd.DataFrame([_q("draftkings", "spreads", -1.0, -110, -110, pd.Timestamp("2025-01-15T23:00:00Z"))])
    mains = A.book_mains(ladder, full, None)
    assert mains.set_index("book")["line"].to_dict() == {"draftkings": -1.0}
    pins = pd.DataFrame({"game_id": ["G1"], "market": ["spreads"], "pin_line": [-1.0]})
    off = A.eligible_offers(ladder, pins, mains)
    got = sorted(set(off["line"]))
    # 1.5 from -1.0 is 2.5 off (eligible); -2.5 is 1.5 off (eligible); the ladder is not dropped
    assert got == [-5.5, -2.5, 1.5, 4.5]


def test_a_book_with_no_main_quote_is_not_bet():
    ladder = pd.DataFrame([_q("draftkings", "spreads", -5.5, 150, -190, T)])
    mains = A.book_mains(ladder, pd.DataFrame(columns=H.QUOTE_COLS), None)
    pins = pd.DataFrame({"game_id": ["G1"], "market": ["spreads"], "pin_line": [-1.0]})
    assert A.eligible_offers(ladder, pins, mains).empty


def test_the_shape_placebo_swaps_the_shape_and_keeps_pinnacle_s_price():
    rng = np.random.default_rng(3)
    thin, fat = H.ResidDist(rng.normal(0, 9, 5000), "thin"), H.ResidDist(rng.normal(0, 16, 5000), "fat")
    fair = pd.DataFrame({"game_id": ["G1", "G2"], "season": [2025, 2025], "game_date": ["d", "d"],
                         "market": ["spreads", "spreads"], "pin_line": [-7.5, -7.5], "pin_fa": [0.5, 0.6],
                         "sigma": [thin, thin], "mu": [7.5, 9.0]})
    pools = {(2025, "spreads"): [fat]}
    p = A.shape_placebo(fair, 1, pools)
    assert all(s is fat for s in p["sigma"])
    # the centre is re-solved so Pinnacle's own price still holds at its number under the new shape
    w, push, l = fat.probs(p["mu"].to_numpy(), H.threshold(p["market"], p["pin_line"]))
    assert np.allclose(w / (w + l), fair["pin_fa"].to_numpy(), atol=2e-3)
