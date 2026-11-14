"""Round 1: data facts that fix the baseline definitions before any grading.

    python scripts/euroleague_research/r1_facts.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

C = Path(r"C:\Users\micha\euroleague_research\cache")
g = pd.read_parquet(C / "games.parquet")
q = pd.read_parquet(C / "period_quotes.parquet")
q = q.merge(g[["game_id", "season", "played"]], on="game_id", how="left")

print("== Pinnacle: markets it holds ==")
print(q[q.bookmaker == "pinnacle"].groupby(["market", "season"]).size().unstack(fill_value=0))

MK = ["spreads_h1", "totals_h1", "h2h_h1", "spreads_q1", "totals_q1", "h2h_q1"]
print("\n== main-line prices by market and book: quantiles of each side's price ==")
for m in MK:
    x = q[q.market == m]
    a, b = ("home_price", "away_price") if not m.startswith("totals") else ("over_price", "under_price")
    pr = pd.concat([x[[ "bookmaker", a]].rename(columns={a: "p"}), x[["bookmaker", b]].rename(columns={b: "p"})])
    print(f"-- {m}")
    print(pr.groupby("bookmaker")["p"].describe(percentiles=[.05, .25, .5, .75, .95]).round(0))

print("\n== main numbers: half-point vs whole number share, by market ==")
for m in MK[:2] + MK[3:5]:
    x = q[q.market == m]
    col = "spread_home" if m.startswith("spreads") else "total_line"
    whole = np.isclose(x[col], np.round(x[col]))
    print(m, "rows", len(x), "whole-number share", round(float(whole.mean()), 3),
          "| range", x[col].min(), x[col].max())

print("\n== quotes on games not played / without scores ==")
print(q.groupby(["season", "played"]).game_id.nunique())
