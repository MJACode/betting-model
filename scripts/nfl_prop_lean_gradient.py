#!/usr/bin/env python3
"""Does the over-lean gradient replicate in EVERY season, and does the top cell pay?

    python -m scripts.nfl_prop_lean_gradient --rows data/local/over_lean.csv

WHAT CAME BEFORE. `nfl_prop_lean_concentration.py` found the same ordering on
train and on test for two dimensions -- unders on big-line, widely-quoted
propositions beat unders on obscure ones -- but the LEVEL moved ~3.6pp between
2023-24 (-3.15%) and 2025 (+0.50%), so no cell was positive on both sides of
the split.

An ordering that replicates once can still be luck. This asks the harder
question, and asks it the way CLAUDE.md §7 demands:

  1. Does the gradient hold in EACH season separately -- 2023, 2024, 2025 --
     rather than in one pooled train block and one test block? Three
     independent replications of an ordering is evidence; one is a coin flip.
  2. Does the INTERSECTION (big line AND widely quoted) concentrate it further,
     and does that cell clear zero with an interval excluding zero in a season
     it was not chosen on?
  3. Is the gradient just the PRICE? A widely-quoted proposition has more books
     to shop, so the best price is better by construction. If the gradient
     disappears once every cell is graded at a FIXED price, it was never a
     market lean -- it was line shopping, which is worth having but is a
     different claim and does not need the lean at all.

Question 3 is the one that decides what this is. It is reported first.

Tercile edges come from 2023-24 and are carried unchanged into 2025.
Zero credits; reads the CSV `nfl_prop_over_lean.py` dumps.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd


def profit(price: float, won: bool) -> float:
    p = float(price)
    return (p / 100.0 if p > 0 else 100.0 / abs(p)) if won else -1.0


def boot(prof: np.ndarray, games: np.ndarray, rng, n: int = 6000) -> tuple[float, float]:
    uniq = np.unique(games)
    idx = {g: np.where(games == g)[0] for g in uniq}
    out = []
    for _ in range(n):
        pick = rng.choice(uniq, len(uniq), replace=True)
        out.append(prof[np.concatenate([idx[g] for g in pick])].mean())
    return float(np.percentile(out, 5) * 100), float(np.percentile(out, 95) * 100)


def grade(df: pd.DataFrame, label: str, rng, price_col: str = "under_price",
          thin: int = 80) -> float:
    d = df[df.actual != df.under_line]
    if len(d) < thin:
        print(f"  {label:40s} {len(d):>6}   (thin)")
        return float("nan")
    prof = np.array([profit(p, a < l) for p, a, l
                     in zip(d[price_col], d.actual, d.under_line)])
    lo, hi = boot(prof, d.game_id.values, rng)
    star = " *" if lo > 0 else ""
    print(f"  {label:40s} {len(prof):>6} {100*(prof > 0).mean():>6.1f}% "
          f"{prof.sum():>+9.2f} {100*prof.mean():>+7.2f}% "
          f"{'('+format(lo,'+.1f')+', '+format(hi,'+.1f')+')':>17}{star}")
    return float(prof.mean() * 100)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", default="data/local/over_lean.csv")
    ap.add_argument("--train", nargs="+", type=int, default=[2023, 2024])
    a = ap.parse_args()
    rng = np.random.default_rng(20260912)

    df = pd.read_csv(a.rows)
    df["line_pct"] = df.groupby("market").line.rank(pct=True)
    train = df[df.season.isin(a.train)]

    # tercile edges from TRAIN only, carried everywhere
    lp_lo, lp_hi = train.line_pct.quantile([1 / 3, 2 / 3])
    nb_lo, nb_hi = train.n_books.quantile([1 / 3, 2 / 3])
    df["prom"] = np.where(df.line_pct <= lp_lo, "low",
                          np.where(df.line_pct <= lp_hi, "mid", "high"))
    df["att"] = np.where(df.n_books <= nb_lo, "low",
                         np.where(df.n_books <= nb_hi, "mid", "high"))
    print(f"{len(df):,} propositions. Tercile edges from {a.train}: "
          f"line_pct {lp_lo:.2f}/{lp_hi:.2f}, n_books {nb_lo:.0f}/{nb_hi:.0f}")

    # ---- 3. is the gradient just the price? --------------------------------
    # A FIXED price for every bet removes shopping entirely. -110 is the
    # conventional flat price and is what the repo's own flat grading uses.
    df["flat"] = -110.0
    print(f"\n{'='*100}")
    print("IS THE GRADIENT THE MARKET, OR IS IT THE SHOPPING?")
    print("  Same bets, graded twice: at the best bettable price, and at a FLAT -110.")
    print("  If the gradient survives at a flat price it is a real lean in the LINE.")
    print(f"  {'cell':40s} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8} {'90% CI':>17}")
    print("  " + "-" * 98)
    for p in ("low", "mid", "high"):
        grade(df[df.prom == p], f"prominence {p} @ best price", rng)
    print("  " + "-" * 98)
    for p in ("low", "mid", "high"):
        grade(df[df.prom == p], f"prominence {p} @ FLAT -110", rng, price_col="flat")
    print("  " + "-" * 98)
    for p in ("low", "mid", "high"):
        d = df[df.prom == p]
        d = d[d.actual != d.under_line]
        print(f"  {'prominence ' + p + ' — under hit rate':40s} {len(d):>6} "
              f"{100*(d.actual < d.under_line).mean():>6.1f}%   "
              f"(break-even at -110 is 52.4%)")

    # ---- 1. does the ordering replicate every season? ----------------------
    print(f"\n{'='*100}")
    print("DOES THE ORDERING HOLD IN EVERY SEASON? (best price)")
    print(f"  {'cell':40s} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8} {'90% CI':>17}")
    print("  " + "-" * 98)
    for s in sorted(df.season.unique()):
        vals = {}
        for p in ("low", "mid", "high"):
            vals[p] = grade(df[(df.season == s) & (df.prom == p)], f"{s} prominence {p}", rng)
        mono = vals["low"] <= vals["mid"] <= vals["high"]
        print(f"      -> {s}: low <= mid <= high ? {'YES' if mono else 'NO'}")

    # ---- 2. the intersection ----------------------------------------------
    print(f"\n{'='*100}")
    print("THE INTERSECTION — big line AND widely quoted, per season (best price)")
    print(f"  {'cell':40s} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8} {'90% CI':>17}")
    print("  " + "-" * 98)
    top = df[(df.prom == "high") & (df.att == "high")]
    grade(top[top.season.isin(a.train)], f"TRAIN {a.train} top cell", rng)
    for s in sorted(df.season.unique()):
        grade(top[top.season == s], f"  {s} top cell", rng)
    print("  " + "-" * 98)
    bot = df[(df.prom == "low") & (df.att == "low")]
    grade(bot, "bottom cell, all seasons (the control)", rng)

    print("\n  * marks an interval whose lower bound is above zero.")
    print("\nThe bar (CLAUDE.md §7): positive in EVERY season, an interval excluding zero "
          "on a season it was not chosen on, and a mechanism that is not just the price.")


if __name__ == "__main__":
    main()
