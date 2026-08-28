"""
Would finer-grained data actually buy us anything?

THE QUESTION THIS SETTLES BEFORE ANY PURCHASE. The archive we train on is a
five minute grid. Vendors exist who sell tick level in-play prop history, at
enterprise pricing. Paying for resolution is only worth it if the line
actually MOVES faster than we can see it: a pass attempt line that sits
unchanged for twenty minutes is fully described by a five minute grid, and a
tick feed of it is the same numbers at a higher bill.

We cannot observe sub-five-minute movement in a five minute archive. What we
CAN observe is how often the line changes across ONE interval. If it rarely
changes at five minutes, there is little movement to miss and finer data is
low value. If it changes at nearly every interval, the line is moving faster
than we sample and we are certainly missing some of it.

This is a bound, not a measurement, and it is stated that way in the output.
The real answer arrives once the live worker has collected a season at sixty
seconds and the five minute grid can be simulated against it directly.

    python -m live_model.backtest.line_churn --market player_pass_attempts
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from .flow_validate import load_snapshots, resolve_snaps

KEY = ["game_id", "player_id", "market", "book"]


def churn_table(snaps: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for market, d in snaps.groupby("market"):
        d = d.sort_values("ts_dt")
        gaps, line_moves, price_moves, sizes = [], [], [], []
        for _, grp in d.groupby([c for c in KEY if c in d.columns],
                                sort=False, dropna=False):
            if len(grp) < 2:
                continue
            g = grp.sort_values("ts_dt")
            dt = g["ts_dt"].diff().dt.total_seconds().to_numpy()[1:]
            dl = g["line"].diff().to_numpy()[1:]
            keep = ~np.isnan(dt) & ~np.isnan(dl)
            dt, dl = dt[keep], dl[keep]
            if not len(dt):
                continue
            gaps.append(dt)
            line_moves.append(dl != 0)
            sizes.append(np.abs(dl[dl != 0]))
            if "over_price" in g:
                dp = g["over_price"].diff().to_numpy()[1:][keep]
                price_moves.append(~np.isnan(dp) & (dp != 0))
        if not gaps:
            continue
        gaps = np.concatenate(gaps)
        lm = np.concatenate(line_moves)
        sz = np.concatenate(sizes) if any(len(s) for s in sizes) else np.array([])
        rows.append({
            "market": market,
            "intervals": int(len(gaps)),
            "median_gap_min": float(np.median(gaps) / 60.0),
            "line_moved_pct": float(100.0 * lm.mean()),
            "median_move": float(np.median(sz)) if len(sz) else float("nan"),
            "price_moved_pct": (
                float(100.0 * np.concatenate(price_moves).mean())
                if price_moves else float("nan")),
        })
    return pd.DataFrame(rows)


def verdict(t: pd.DataFrame, market: str) -> list[str]:
    out = []
    row = t[t.market == market]
    if row.empty:
        return [f"no intervals for {market}"]
    r = row.iloc[0]
    moved = r.line_moved_pct
    out.append(f"{market}: the LINE changed across {moved:.1f}% of "
               f"{r.intervals:,} consecutive snapshots "
               f"(median gap {r.median_gap_min:.1f} min).")
    if not np.isnan(r.price_moved_pct):
        out.append(f"the PRICE changed across {r.price_moved_pct:.1f}% of them, "
                   "which moves far more freely than the line and is the part "
                   "a tick feed would really add.")
    if moved < 15:
        out.append("BUYING FINER DATA IS LOW VALUE for the line itself. It sits "
                   "still across most five minute intervals, so a tick feed "
                   "would mostly resell numbers we already hold. Spend on "
                   "DENSITY across more games instead of resolution within "
                   "one.")
    elif moved < 40:
        out.append("MIXED. The line moves often enough that some intra-interval "
                   "movement is certainly being missed, but not so often that "
                   "the grid is misrepresenting it. Worth a free trial of a "
                   "tick vendor before any spend.")
    else:
        out.append("FINER DATA MATTERS. The line changes across most intervals, "
                   "so five minutes is under-sampling a moving number and the "
                   "quotes we grade against are stale by construction.")
    out.append("BOUND, NOT MEASUREMENT: a five minute archive cannot show "
               "sub-five-minute movement. This says how much movement is "
               "visible AT five minutes, which is a floor on what exists. The "
               "direct answer needs the live worker's 60s collection.")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="player_pass_attempts")
    args = ap.parse_args()

    snaps = load_snapshots()
    if snaps.empty:
        raise SystemExit("no prop snapshots parsed")
    snaps = resolve_snaps(snaps)
    if snaps.empty:
        raise SystemExit("no snapshots resolved to games")

    t = churn_table(snaps)
    hdr = (f"{'market':26s} {'intervals':>10s} {'gap min':>8s} "
           f"{'line moved':>11s} {'med move':>9s} {'price moved':>12s}")
    print(hdr)
    print("-" * len(hdr))
    for _, r in t.iterrows():
        print(f"{r.market:26s} {r.intervals:10d} {r.median_gap_min:8.1f} "
              f"{r.line_moved_pct:10.1f}% {r.median_move:9.2f} "
              f"{r.price_moved_pct:11.1f}%")
    print()
    print("VERDICT")
    for line in verdict(t, args.market):
        print(" ", line)


if __name__ == "__main__":
    main()
