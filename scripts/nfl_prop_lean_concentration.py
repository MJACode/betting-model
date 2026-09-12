#!/usr/bin/env python3
"""Where does the NFL prop over-lean concentrate, and does the concentration hold?

    python -m scripts.nfl_prop_lean_concentration --rows data/local/over_lean.csv

WHY. `scripts/nfl_prop_over_lean.py` measures the lean market by market and finds
it real in aggregate but unstable per market: on the best bettable price, blind
unders return -1.29% in 2025 against blind overs at -7.91%, so the under side is
worth ~3.3pp more than the over side, but the cost of the bet at the best price
is ~4.6pp and no market's lean is stable enough to select on.

The gap is about ONE POINT of ROI. This asks whether the lean concentrates
anywhere that would close it. Every candidate below is a RECREATIONAL-MONEY
mechanism -- the documented reason prop lines get shaded over -- and each is
knowable before kickoff, so it could actually be traded:

  prominence   a bigger line means a bigger name and more public money
  attention    more books quoting means a more heavily-traded proposition
  shading      the book pricing the OVER as the favourite has already leaned
  slot         primetime games draw casual money; 1pm windows draw less

THE DISCIPLINE (CLAUDE.md §7). Every split is measured on TRAIN seasons, the
best cell is chosen there, and the SAME cell is then applied to a TEST season it
never saw. A cell that only works in the season it was chosen on is noise, and
this project has shipped that mistake twice. Tercile boundaries are computed on
TRAIN and carried to TEST unchanged.

Reads the CSV that over_lean.py dumps. Zero credits.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from data import local_store


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


def under_profit(df: pd.DataFrame):
    d = df[df.actual != df.under_line]
    prof = np.array([profit(p, a < l) for p, a, l
                     in zip(d.under_price, d.actual, d.under_line)])
    return prof, d.game_id.values


def report(df: pd.DataFrame, label: str, rng, thin: int = 100) -> float:
    prof, games = under_profit(df)
    if len(prof) < thin:
        print(f"  {label:38s} {len(prof):>6}   (thin)")
        return float("nan")
    lo, hi = boot(prof, games, rng)
    print(f"  {label:38s} {len(prof):>6} {100*(prof > 0).mean():>6.1f}% "
          f"{prof.sum():>+9.2f} {100*prof.mean():>+7.2f}% "
          f"{'('+format(lo,'+.1f')+', '+format(hi,'+.1f')+')':>17}")
    return float(prof.mean() * 100)


def add_context(df: pd.DataFrame) -> pd.DataFrame:
    """Kickoff slot, known pre-game."""
    local_store.activate()
    g = local_store.read_table("nfl_team_game_stats",
                               columns=["game_id", "commence_time"]).drop_duplicates("game_id")
    g["kick"] = pd.to_datetime(g.commence_time, utc=True)
    g["et_hour"] = g.kick.dt.tz_convert("America/New_York").dt.hour
    g["slot"] = np.where(g.et_hour >= 19, "primetime",
                         np.where(g.et_hour >= 16, "late afternoon", "early afternoon"))
    return df.merge(g[["game_id", "slot"]], on="game_id", how="left")


def tercile_split(train: pd.DataFrame, test: pd.DataFrame, col: str, label: str,
                  rng, per_market: bool = True) -> None:
    """Terciles fitted on TRAIN, applied unchanged to TEST."""
    print(f"\n{label}")
    print(f"  {'cell':38s} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8} {'90% CI':>17}")
    print("  " + "-" * 96)
    if per_market:
        edges = train.groupby("market")[col].quantile([1 / 3, 2 / 3]).unstack()

        def bucket(d):
            lo = d.market.map(edges[1 / 3])
            hi = d.market.map(edges[2 / 3])
            return np.where(d[col] <= lo, "low", np.where(d[col] <= hi, "mid", "high"))
    else:
        lo_v, hi_v = train[col].quantile([1 / 3, 2 / 3])

        def bucket(d):
            return np.where(d[col] <= lo_v, "low", np.where(d[col] <= hi_v, "mid", "high"))

    train = train.assign(cell=bucket(train))
    test = test.assign(cell=bucket(test))
    for c in ("low", "mid", "high"):
        report(train[train.cell == c], f"TRAIN {c}", rng)
    print("  " + "-" * 96)
    for c in ("low", "mid", "high"):
        report(test[test.cell == c], f"TEST  {c}", rng)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", default="data/local/over_lean.csv")
    ap.add_argument("--train", nargs="+", type=int, default=[2023, 2024])
    ap.add_argument("--test", nargs="+", type=int, default=[2025])
    a = ap.parse_args()
    rng = np.random.default_rng(20260912)

    df = pd.read_csv(a.rows)
    df = add_context(df)
    df["line_pct"] = df.groupby("market").line.rank(pct=True)
    train = df[df.season.isin(a.train)]
    test = df[df.season.isin(a.test)]
    print(f"{len(df):,} propositions; train {len(train):,} test {len(test):,}")

    print(f"\n{'='*98}\nBASELINE — blind unders at the best price, everything")
    print(f"  {'cell':38s} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8} {'90% CI':>17}")
    print("  " + "-" * 96)
    report(train, "TRAIN all", rng)
    report(test, "TEST  all", rng)

    tercile_split(train, test, "line_pct",
                  "PROMINENCE — line size within its own market (public money follows names)",
                  rng, per_market=False)
    tercile_split(train, test, "n_books",
                  "ATTENTION — how many bettable books quote the proposition",
                  rng, per_market=False)
    tercile_split(train, test, "cons_over",
                  "SHADING — consensus de-vigged P(over); high = the book already leans over",
                  rng, per_market=True)

    print(f"\nSLOT — primetime draws casual money, early-afternoon windows draw less")
    print(f"  {'cell':38s} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8} {'90% CI':>17}")
    print("  " + "-" * 96)
    for s in ("early afternoon", "late afternoon", "primetime"):
        report(train[train.slot == s], f"TRAIN {s}", rng)
    print("  " + "-" * 96)
    for s in ("early afternoon", "late afternoon", "primetime"):
        report(test[test.slot == s], f"TEST  {s}", rng)

    print("\nRead TRAIN and TEST as a pair. A cell strong on TRAIN and flat on TEST is "
          "noise; only a cell strong on BOTH is a candidate, and it still has to clear "
          "zero with an interval that excludes it.")


if __name__ == "__main__":
    main()
