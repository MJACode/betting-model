"""
Is the book's live prop line still biased?

This asks the one question that needs NO model: across every quote we hold,
how far does the posted line sit from what actually happened? The 2023 and 2024
pull put DK's live pass attempt line 2.33 attempts BELOW the eventual final,
and the flow model's whole measured edge turned out to be harvesting that
rather than forecasting better than the book.

A bias that has since been corrected closes the lane. A bias that persists into
a third season is worth paper trading. Either way no model is trained here, so
the answer cannot be an artifact of one.

    python -m live_model.backtest.flow_bias --seasons 2025
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from ..engine.prop_flow import FLOW_MARKETS
from .flow_eval import load_rows
from .flow_validate import (
    attach_ids, load_snapshots, match_to_flow, resolve_snaps,
)


def bias_table(flow: pd.DataFrame, snaps: pd.DataFrame) -> pd.DataFrame:
    """
    One row per market per season: the book's line against the actual final.

    Quotes are matched to a state at or before them, exactly as the grading
    path does, so that the accrued figure and the season label come from the
    same join the ROI numbers used. Only the LINE and the FINAL are compared,
    so nothing here depends on a model.
    """
    rows = []
    for market in FLOW_MARKETS:
        d = flow[flow.market == market]
        s = snaps[snaps.market == market]
        if d.empty or s.empty:
            continue
        # match_to_flow expects an arm column; this path has no arms.
        d = d.copy()
        d["arm"] = "book"
        m = match_to_flow(s, d)
        if m.empty:
            continue
        m = m.drop_duplicates(subset=["quote_id"])
        for season, sub in m.groupby("season"):
            err = sub["line"] - sub["actual_final"]
            rows.append({
                "market": market,
                "season": int(season),
                "quotes": len(sub),
                "games": sub.game_id.nunique(),
                "bias": err.mean(),
                "mae": err.abs().mean(),
                # A bias that is real should show up in the median too, not
                # just in a mean a few blowouts can drag.
                "median_bias": err.median(),
                "over_rate": float((sub["actual_final"] > sub["line"]).mean()),
            })
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", type=int, nargs="+", default=None)
    args = ap.parse_args()

    flow = load_rows()
    if args.seasons:
        flow = flow[flow.season.isin(args.seasons)]
    snaps = load_snapshots()
    if snaps.empty:
        raise SystemExit("no prop snapshots parsed")
    snaps, unresolved = attach_ids(snaps, set(flow["player_id"].unique()))
    snaps = resolve_snaps(snaps)
    print(f"{len(snaps):,} quotes resolved, {unresolved:,} names dropped\n")

    t = bias_table(flow, snaps)
    if t.empty:
        raise SystemExit("nothing matched")

    print("book line minus actual final. NEGATIVE means the book posts LOW,")
    print("which is what an over bettor harvests.\n")
    print(f"{'market':26s} {'season':>6s} {'quotes':>7s} {'games':>6s} "
          f"{'bias':>7s} {'median':>7s} {'mae':>6s} {'went over':>10s}")
    for _, r in t.sort_values(["market", "season"]).iterrows():
        print(f"{r.market:26s} {r.season:6d} {r.quotes:7,d} {r.games:6d} "
              f"{r.bias:+7.2f} {r.median_bias:+7.2f} {r.mae:6.2f} "
              f"{100 * r.over_rate:9.1f}%")


if __name__ == "__main__":
    main()
