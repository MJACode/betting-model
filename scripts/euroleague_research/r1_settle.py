"""Round 1, step 3: how the first-half and first-quarter moneylines settle, and
the shape of the main-market quotes (one row per game, market, book, mark?).

Reads only the local parquet cache. No database, no API.

    python scripts/euroleague_research/r1_settle.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

C = Path(r"C:\Users\micha\euroleague_research\cache")
g = pd.read_parquet(C / "games.parquet")
p = pd.read_parquet(C / "periods.parquet")
q = pd.read_parquet(C / "period_quotes.parquet")

q = q.merge(g[["game_id", "season", "commence_time"]], on="game_id", how="left")

print("== quotes by season and market (rows) ==")
mk = ["h2h_h1", "spreads_h1", "totals_h1", "h2h_q1", "spreads_q1", "totals_q1",
      "h2h_3_way_h1", "h2h_3_way_q1"]
print(q[q.market.isin(mk)].pivot_table(index="market", columns="season", values="game_id",
                                       aggfunc="count", fill_value=0))

print("\n== draw_price presence, by market and book ==")
for m in ["h2h_h1", "h2h_q1", "h2h_3_way_h1", "h2h_3_way_q1", "h2h_h2", "h2h_q2"]:
    x = q[q.market == m]
    t = x.groupby("bookmaker").agg(rows=("game_id", "size"),
                                   with_draw=("draw_price", lambda s: int(s.notna().sum())),
                                   home_na=("home_price", lambda s: int(s.isna().sum())))
    print(f"-- {m}")
    print(t)

# implied overround of the two-way h2h_h1 / h2h_q1 (home+away only) by book
def imp(a):
    a = np.asarray(a, float)
    return np.where(a > 0, 100 / (a + 100), -a / (-a + 100))

print("\n== two-way overround (home + away implied) by market and book, median ==")
for m in ["h2h_h1", "h2h_q1", "h2h_3_way_h1", "h2h_3_way_q1"]:
    x = q[q.market == m].copy()
    x["ovr"] = imp(x.home_price) + imp(x.away_price)
    x["ovr3"] = x["ovr"] + np.where(x.draw_price.notna(), imp(x.draw_price.fillna(100)), 0)
    print(f"-- {m}")
    print(x.groupby("bookmaker")[["ovr", "ovr3"]].median().round(4))

print("\n== ties in the stored period scores ==")
pv = p.pivot_table(index="game_id", columns="period", values=["home_points", "away_points"],
                   aggfunc="sum")
h1 = pv[("home_points", 1)] + pv[("home_points", 2)]
a1 = pv[("away_points", 1)] + pv[("away_points", 2)]
d = pd.DataFrame({"q1m": pv[("home_points", 1)] - pv[("away_points", 1)],
                  "h1m": h1 - a1}).reset_index()
d = d.merge(g[["game_id", "season", "played"]], on="game_id")
d = d[d.played]
t = d.groupby("season").agg(games=("game_id", "size"),
                            q1_tie=("q1m", lambda s: int((s == 0).sum())),
                            h1_tie=("h1m", lambda s: int((s == 0).sum())))
t["q1_tie_pct"] = (100 * t.q1_tie / t.games).round(2)
t["h1_tie_pct"] = (100 * t.h1_tie / t.games).round(2)
print(t)
print("pooled", int(t.games.sum()), "q1 ties", int(t.q1_tie.sum()),
      round(100 * t.q1_tie.sum() / t.games.sum(), 2), "% | h1 ties", int(t.h1_tie.sum()),
      round(100 * t.h1_tie.sum() / t.games.sum(), 2), "%")

print("\n== main-market shape: rows per (game, market, book, mark) ==")
for m in ["spreads_h1", "totals_h1", "h2h_h1", "spreads_q1", "totals_q1", "h2h_q1"]:
    x = q[q.market == m]
    c = x.groupby(["game_id", "bookmaker", "mark"]).size()
    print(m, "groups", len(c), "rows/group dist", c.value_counts().sort_index().to_dict(),
          "| no mark", int(x.mark.isna().sum()))

print("\n== quotes per (game, market, book): distinct marks / distinct numbers ==")
for m in ["spreads_h1", "totals_h1"]:
    x = q[q.market == m]
    col = "spread_home" if "spreads" in m else "total_line"
    c = x.groupby(["game_id", "bookmaker"]).agg(marks=("mark", "nunique"), nums=(col, "nunique"))
    print(m, "marks per game-book", c.marks.value_counts().sort_index().to_dict())
    print(m, "numbers per game-book", c.nums.value_counts().sort_index().to_dict())

print("\n== snapshot_at vs commence_time: minutes before tip (main markets) ==")
x = q[q.market.isin(["spreads_h1", "totals_h1", "h2h_h1"])].copy()
x["snap"] = pd.to_datetime(x.snapshot_at, utc=True)
x["tip"] = pd.to_datetime(x.commence_time, utc=True)
x["lead"] = (x.tip - x.snap).dt.total_seconds() / 60
x["ask_lead"] = (x.tip - x.asked_at).dt.total_seconds() / 60
print(x.groupby("mark")[["lead", "ask_lead"]].describe(percentiles=[.05, .5, .95]).round(1).T)
print("snap after tip:", int((x.lead < 0).sum()), "| snap after ask:", int((x.snap > x.asked_at).sum()))
