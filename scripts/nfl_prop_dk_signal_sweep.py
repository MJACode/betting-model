"""Every one-feature signal a DraftKings-decided prop model could use, graded.

DraftKings prices its standard prop lines FLAT -- -115 both sides on most
yardage rows -- so at DK the market's information is entirely in the LINE.
A DK-decided model can only win by knowing the true median sits away from
DK's number. This sweeps every candidate for that knowledge we hold, one at a
time, on the market features `scripts/nfl_prop_market_stack` builds:

  sharp-line    a sharp book's main line sits k+ points above/below DK's
  cons-line     the median retail line sits k+ points above/below DK's
  movement      DK's own line moved k+ points from t72 to the row priced
  adjust        DK's line sits k+ points above/below the player's rolling-8
  model         the model projection sits k+ sd above/below DK's line
  blind-under   take every under (the empirical over-rate runs below 50%)

Each is graded as a bet at the DK price, per season, with a 90% interval,
across a fixed grid. Nothing is tuned; every cell is printed. A signal has to
be positive in both test seasons with an interval excluding zero to be more
than noise, and there are six signals times eleven markets times a grid, so
one such cell is expected by chance.

    python -m scripts.nfl_prop_dk_signal_sweep --feats <cache dir>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from models.market_relative import implied
from scripts.nfl_prop_information_test import profit


def _grade(prof: list[float], rng) -> str:
    if len(prof) < 30:
        return f"{len(prof):>5}  (thin)"
    p = np.array(prof)
    idx = rng.integers(0, len(p), (10000, len(p)))
    roi = 100 * p[idx].mean(axis=1)
    lo, hi = np.percentile(roi, 5), np.percentile(roi, 95)
    flag = " *" if lo > 0 else ""
    return f"{len(p):>5} {100*(p>0).mean():>5.1f}% {p.sum():>+8.2f}u {100*p.mean():>+7.2f}%  ({lo:+.1f}, {hi:+.1f}){flag}"


def _bet(df: pd.DataFrame, side: pd.Series) -> list[float]:
    """side: +1 over, -1 under, 0 pass."""
    prof = []
    for s, r in zip(side.values, df.itertuples(index=False)):
        if s == 0:
            continue
        price = r.over_price if s > 0 else r.under_price
        if price is None or not np.isfinite(float(price)):
            continue
        won = (r.actual > r.line) if s > 0 else (r.actual < r.line)
        prof.append(profit(price, won))
    return prof


def signals(df: pd.DataFrame) -> dict[str, dict[str, pd.Series]]:
    """name -> {grid label -> side series}."""
    out: dict = {}
    sd_line = float(df.line.std() or 1.0)

    def threshold(diff: pd.Series, grid, scale=1.0, name=""):
        d = {}
        for k in grid:
            s = pd.Series(0, index=df.index)
            s[diff >= k * scale] = 1
            s[diff <= -k * scale] = -1
            d[f"{name} k>={k}"] = s
        return d

    for b in ("pinnacle", "betonlineag"):
        if f"{b}_line" in df:
            out[f"sharp-line {b}"] = threshold(df[f"{b}_line"] - df.line, (0.5, 1.5, 2.5, 4.5), name=b[:4])
    if "cons_line" in df:
        out["cons-line"] = threshold(df.cons_line - df.line, (0.5, 1.5, 2.5, 4.5), name="cons")
    if "dk_line_t72" in df:
        out["movement t72"] = threshold(df.line - df.dk_line_t72, (0.5, 1.5, 2.5, 4.5), name="mv")
        # Fade the move as well as follow it.
        out["fade movement t72"] = {k: -v for k, v in
                                    threshold(df.line - df.dk_line_t72, (0.5, 1.5, 2.5, 4.5), name="fade").items()}
    out["adjust (line-r8)"] = threshold(df.line - df.roll8, (0.1, 0.25, 0.5, 1.0), scale=sd_line, name="adj")
    out["fade adjust"] = {k: -v for k, v in
                          threshold(df.line - df.roll8, (0.1, 0.25, 0.5, 1.0), scale=sd_line, name="fadeadj").items()}
    sd_pred = float((df.pred - df.line).std() or 1.0)
    out["model z"] = threshold(df.pred - df.line, (0.25, 0.5, 1.0, 1.5), scale=sd_pred, name="z")
    out["blind-under"] = {"all": pd.Series(-1, index=df.index)}
    out["blind-over"] = {"all": pd.Series(1, index=df.index)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feats", required=True)
    ap.add_argument("--only-flagged", action="store_true",
                    help="print only cells whose interval excludes zero")
    a = ap.parse_args()
    rng = np.random.default_rng(42)
    for f in sorted(Path(a.feats).glob("nfl_prop_*.parquet")):
        if "_" in f.stem.replace("nfl_prop_", "").replace("_", "", 0) and f.stem.count("_") > 3:
            pass
        df = pd.read_parquet(f)
        df = df.dropna(subset=["line", "actual", "pred"]).copy()
        df = df[df.actual != df.line]
        print(f"\n=== {f.stem}  rows {len(df)} ===")
        print(f"{'signal':26s} {'cell':16s} {'seas':>4} {'bets':>5} {'win%':>6} {'units':>9} {'ROI':>8}  90% CI")
        for name, grid in signals(df).items():
            for cell, side in grid.items():
                lines = []
                flagged = False
                for season, g in df.groupby("season"):
                    prof = _bet(g, side.loc[g.index])
                    s = _grade(prof, rng)
                    flagged |= s.endswith("*")
                    lines.append(f"{name:26s} {cell:16s} {season:>4} {s}")
                if a.only_flagged and not flagged:
                    continue
                print("\n".join(lines))


if __name__ == "__main__":
    main()
