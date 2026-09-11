#!/usr/bin/env python3
"""
Sweep a STRICTER cut for the opener, on the selection the live card actually runs.

    python scripts/opener_cut_sweep.py                 # 2020-2025, bettable books
    python scripts/opener_cut_sweep.py --all-books     # every clean book (the backtest's view)

WHY THIS EXISTS (mike, 2026-09-11: "the opener needs to be more aggressive, way
too many picks, I need statistical profitability").

`backtest_opener.py` reports the rule at |dev| thresholds over EVERY clean book.
The deployed card is narrower in two ways that matter for a cut:

  1. it only takes a bet at a book the reader can place it at
     (data_ingest/books.py — twelve US books, not 34), and
  2. it prices each bet through `models/opener_spread.model_prob_for_dev` and
     SKIPS anything `stake_units` sizes below 0.25u, so the population the
     platform gate sees is already edge-filtered by the juice quoted.

So the sweep replicates that selection on the snapshot cache and then applies
the two platform gates — `min_prob` (equivalently a |dev| floor, since the
probability is a monotone table of |dev|) and `min_edge` (model_prob minus the
quoted price's implied probability) — and reports, per cell:

  n, W-L, ROI at the ACTUAL quoted price with a game-clustered bootstrap CI,
  and the season split, because this project has been burned by a single
  season carrying a result.

"First qualifying moment" is at snapshot resolution, same as the backtest. The
model_prob table itself was fitted on this same sample (opener_spread.py says
so), so the probabilities are partly in-sample; the ROI is not — it is the
realised return of the bets the cut would have taken.

Zero Odds API credits — everything comes from data/processed/dev_long.parquet.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)
sys.path.insert(0, HERE)

# By absolute path, never `from models import ...`: the platform's own
# top-level `models` package wins that name whenever the repo root is on
# sys.path (nfl/_nfl_models.py explains; tests/test_nfl_model_imports.py pins it).
from _nfl_models import load_nfl_model  # noqa: E402
from data_ingest.books import bettable_books  # noqa: E402

om = load_nfl_model("opener_spread")

RNG = np.random.default_rng(20260911)


def _load_backtest():
    spec = importlib.util.spec_from_file_location(
        "bo_sweep", os.path.join(HERE, "backtest_opener.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    mod.RESID = mod.residuals()
    return mod


def candidate_rows(bo, seasons, all_books: bool) -> pd.DataFrame:
    """Every (snapshot, game, book) row the live card could have bet, priced."""
    w = bo.price(bo.load("spreads", "pinnacle", 48.0, 168.0, seasons), "spreads")
    if not all_books:
        w = w[w.book.isin(bettable_books())]
    w = w[w.px.notna()].copy()
    w["model_prob"] = [om.model_prob_for_dev(d) for d in w.adev]
    w["market_prob"] = [om.american_to_prob(float(p)) for p in w.px]
    w["edge"] = w.model_prob - w.market_prob
    w["units"] = [om.stake_units(mp, int(p)) for mp, p in zip(w.model_prob, w.px)]
    w["ret"] = np.where(w.win == 1, np.where(w.px > 0, w.px / 100, 100 / -w.px),
                        np.where(w.win == 0.5, 0.0, -1.0))
    return w


def select(w: pd.DataFrame, dev_thr: float, min_edge: float, min_prob: float) -> pd.DataFrame:
    """The live card's rule: first qualifying snapshot, largest |dev| there, one per game."""
    q = w[(w.adev >= dev_thr) & (w.units > 0) & (w.edge >= min_edge) & (w.model_prob >= min_prob)]
    if q.empty:
        return q
    return (q.sort_values(["game_id", "snap_ts", "adev", "book"],
                          ascending=[True, True, False, True])
            .groupby("game_id", as_index=False).first())


def boot_ci(s: pd.DataFrame, b: int = 3000) -> tuple[float, float]:
    vals = s.ret.values
    if len(vals) < 5:
        return (float("nan"), float("nan"))
    draws = [vals[RNG.integers(0, len(vals), len(vals))].mean() for _ in range(b)]
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return float(lo), float(hi)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", type=int, nargs=2, default=[2020, 2025])
    ap.add_argument("--all-books", action="store_true")
    ap.add_argument("--dev", type=float, nargs="+", default=[1.0, 1.5, 2.0, 2.5, 3.0])
    ap.add_argument("--edge", type=float, nargs="+", default=[0.0, 0.02, 0.03, 0.04, 0.05])
    a = ap.parse_args()

    bo = _load_backtest()
    w = candidate_rows(bo, a.seasons, a.all_books)
    books = "all clean books" if a.all_books else "bettable books only"
    print(f"=== OPENER CUT SWEEP, {a.seasons[0]}-{a.seasons[1]}, {books}: "
          f"{w.game_id.nunique()} games, {w.book.nunique()} books ===")
    print(f"  books present: {sorted(w.book.unique())}")

    rows = []
    for dt in a.dev:
        for me in a.edge:
            s = select(w, dt, me, 0.0)
            d = s[s.win != 0.5]
            if len(d) < 5:
                rows.append(dict(dev=dt, edge=me, n=len(d)))
                continue
            lo, hi = boot_ci(s)
            per = s.groupby("season").ret.agg(["size", "sum", "mean"])
            pos = int((per["sum"] > 0).sum())
            rows.append(dict(
                dev=dt, edge=me, n=len(d),
                W=int((d.win == 1).sum()), L=int((d.win == 0).sum()),
                mean_prob=round(float(s.model_prob.mean()), 4),
                units=round(float(s.ret.sum()), 2),
                roi=round(float(s.ret.mean()) * 100, 2),
                ci=f"[{lo*100:+.1f},{hi*100:+.1f}]",
                pos_seasons=f"{pos}/{len(per)}",
                by_season=" ".join(f"{int(y)}:{r['mean']*100:+.1f}%/{int(r['size'])}"
                                   for y, r in per.iterrows()),
            ))
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(out.to_string(index=False))
    print("\nA cell is a plateau only if its neighbours agree. Read `ci` and "
          "`pos_seasons` before `roi`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
