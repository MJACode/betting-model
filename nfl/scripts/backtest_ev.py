"""
Walk-forward EV backtest reporting UNITS, not CLV points.

Compares several estimators of the "true" spread mu, to isolate how much of
any edge comes from line shopping versus from the movement model:

  consensus  : trimmed median of bet-time spreads across all books (no model)
  pinnacle   : Pinnacle bet-time spread (sharp book, no model)
  model      : Pinnacle bet-time + predicted movement (movement model)
  oracle     : the actual Pinnacle closing spread (upper bound, not tradable)

The oracle row is the ceiling. If oracle barely clears breakeven, no amount
of modelling saves the strategy and the problem is structural.
"""

from __future__ import annotations

import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.ev_engine import (american_to_decimal, cover_probs, ev_per_unit,
                              fit_margin_pmf, kelly_fraction, margin_pmf_for)

TEST_SEASONS = [2023, 2024, 2025]
MAX_OFF_CONSENSUS = 3.0   # discard quotes this far from consensus as stale/unbettable


def load():
    odds = pd.read_parquet("data/processed/odds_all_books.parquet")
    odds = odds.dropna(subset=["bt_spread", "margin"]).copy()

    # robust consensus at bet time
    cons = odds.groupby("game_id").bt_spread.agg(
        cons_spread=lambda s: s.median(), n_books="size").reset_index()
    odds = odds.merge(cons, on="game_id", how="left")
    odds["off_cons"] = (odds.bt_spread - odds.cons_spread).abs()

    pin = odds[odds.book == "pinnacle"][["game_id", "bt_spread"]].rename(
        columns={"bt_spread": "pin_bt"})
    pcl = pd.read_parquet("data/processed/odds_all_books.parquet")
    pcl = pcl[pcl.book == "pinnacle"][["game_id", "cl_spread"]].rename(
        columns={"cl_spread": "pin_cl"})
    odds = odds.merge(pin, on="game_id", how="left").merge(pcl, on="game_id", how="left")
    return odds


def add_model_mu(odds: pd.DataFrame) -> pd.DataFrame:
    """Attach the walk-forward movement-model prediction, if available."""
    p = "data/processed/backtest_results.parquet"
    if not os.path.exists(p):
        odds["pred_move"] = np.nan
        return odds
    r = pd.read_parquet(p)[["game_id", "pred"]].rename(columns={"pred": "pred_move"})
    return odds.merge(r, on="game_id", how="left")


def run(odds, mu_col, label, min_ev=0.03, stale_filter=True, verbose=True):
    rows = []
    for test_s in TEST_SEASONS:
        tr = odds[odds.season < test_s].drop_duplicates("game_id")
        base_pmf = fit_margin_pmf(tr.margin.values, tr.cl_spread.values)

        te = odds[odds.season == test_s].copy()
        te = te[te[mu_col].notna()]
        if stale_filter:
            te = te[te.off_cons <= MAX_OFF_CONSENSUS]
        if len(te) == 0:
            continue

        pmf = margin_pmf_for(te[mu_col].values, base_pmf)
        p_home, p_push, p_away = cover_probs(pmf, te.bt_spread.values)

        dec_h = american_to_decimal(te.bt_px_home.values)
        dec_a = american_to_decimal(te.bt_px_away.values)
        ev_h = ev_per_unit(p_home, p_push, dec_h)
        ev_a = ev_per_unit(p_away, p_push, dec_a)

        te["ev_home"], te["ev_away"] = ev_h, ev_a
        te["p_home"], te["p_away"], te["p_push"] = p_home, p_away, p_push
        te["dec_home"], te["dec_away"] = dec_h, dec_a
        rows.append(te)

    if not rows:
        return None
    d = pd.concat(rows, ignore_index=True)

    # best available EV per game across all books and both sides
    long = []
    for side in ["home", "away"]:
        s = d[["game_id", "season", "week", "book", "bt_spread", "margin",
               f"ev_{side}", f"p_{side}", "p_push", f"dec_{side}"]].copy()
        s.columns = ["game_id", "season", "week", "book", "line", "margin",
                     "ev", "p_win", "p_push", "dec"]
        s["side"] = side
        long.append(s)
    long = pd.concat(long, ignore_index=True)
    long = long[np.isfinite(long.ev) & np.isfinite(long.dec)]

    best = long.sort_values("ev").groupby("game_id", as_index=False).last()
    bets = best[best.ev >= min_ev].copy()
    if len(bets) == 0:
        return dict(label=label, n=0)

    # settle
    cover = np.where(bets.side == "home", bets.margin > bets.line,
                     bets.margin < bets.line)
    push = bets.margin.values == bets.line.values
    bets["stake"] = kelly_fraction(bets.p_win.values, bets.p_push.values,
                                   bets.dec.values)
    profit = np.where(push, 0.0,
                      np.where(cover, bets.stake * (bets.dec - 1.0), -bets.stake))
    bets["profit"] = profit

    flat = np.where(push, 0.0, np.where(cover, (bets.dec - 1.0), -1.0))
    n_dec = int((~push).sum())
    out = dict(
        label=label, n=len(bets), n_dec=n_dec,
        win_rate=float(cover[~push].mean()) if n_dec else np.nan,
        mean_ev=float(bets.ev.mean()),
        flat_units=float(flat.sum()), flat_roi=float(flat.sum() / max(len(bets), 1)),
        kelly_units=float(profit.sum()),
        kelly_staked=float(bets.stake.sum()),
        mean_stake=float(bets.stake.mean()),
        med_price=float(np.median(bets.dec)),
    )
    if verbose:
        print(f"  {label:34s} n={out['n']:4d}  win={out['win_rate']:6.2%}  "
              f"meanEV={out['mean_ev']:+.3f}  flat_units={out['flat_units']:+7.2f}  "
              f"ROI={out['flat_roi']:+6.2%}  kelly_units={out['kelly_units']:+6.3f}")
    return out, bets


def main():
    odds = add_model_mu(load())
    odds["mu_model"] = odds.pin_bt + odds.pred_move

    variants = [("cons_spread", "consensus (no model)"),
                ("pin_bt", "pinnacle bet-time (no model)"),
                ("mu_model", "pinnacle + movement model"),
                ("pin_cl", "ORACLE: actual close")]

    print("=" * 96)
    print("WALK-FORWARD EV BACKTEST, min EV = 3%, all books, stale filter ON")
    print("=" * 96)
    res = {}
    for col, lab in variants:
        r = run(odds, col, lab)
        if r:
            res[lab] = r

    print("\n" + "=" * 96)
    print("SENSITIVITY: EV threshold (truth = pinnacle bet-time, no model)")
    print("=" * 96)
    for thr in [0.01, 0.02, 0.03, 0.05, 0.08, 0.12]:
        run(odds, "pin_bt", f"minEV={thr:.0%}", min_ev=thr)

    print("\n" + "=" * 96)
    print("STALE-QUOTE FILTER OFF (measures phantom-edge contamination)")
    print("=" * 96)
    run(odds, "pin_bt", "pinnacle, no stale filter", stale_filter=False)

    return res


if __name__ == "__main__":
    main()
