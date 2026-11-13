"""Round 1: do Pinnacle's full-game alternate ladders (bought with the period
lines, same fetch) bracket even money, so the rung nearest 50/50 gives a
same-moment sharp full-game number on every season?

    python scripts/euroleague_research/r1_pinnacle_ladder.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

C = Path(r"C:\Users\micha\euroleague_research\cache")
g = pd.read_parquet(C / "games.parquet")
q = pd.read_parquet(C / "period_quotes.parquet")
q = q.merge(g[["game_id", "season"]], on="game_id", how="left")


def imp(a):
    a = np.asarray(a, float)
    return np.where(a > 0, 100 / (a + 100), -a / (-a + 100))


for m, col, a, b in [("alternate_totals", "total_line", "over_price", "under_price"),
                     ("alternate_spreads", "spread_home", "home_price", "away_price")]:
    x = q[(q.market == m) & (q.bookmaker == "pinnacle")].copy()
    x["pa"] = imp(x[a]) / (imp(x[a]) + imp(x[b]))
    grp = x.groupby(["game_id", "mark"])
    s = grp.agg(season=("season", "first"), rungs=(col, "size"), lo=("pa", "min"), hi=("pa", "max"))
    s["brackets"] = (s.lo <= 0.5) & (s.hi >= 0.5)
    print(f"== Pinnacle {m}: (game, mark) ladders")
    print(s.groupby("season").agg(ladders=("rungs", "size"), games=("rungs", lambda v: v.index.get_level_values(0).nunique()),
                                  med_rungs=("rungs", "median"), brackets=("brackets", "mean")).round(3))
    print(s.groupby("mark").agg(ladders=("rungs", "size"), brackets=("brackets", "mean")).round(3).T)
    # nearest-even rung's distance from 0.5
    x["d"] = (x.pa - 0.5).abs()
    near = x.sort_values("d").drop_duplicates(["game_id", "mark"])
    print("nearest rung |p-0.5| quantiles", near.d.quantile([.5, .9, .99]).round(4).to_dict())
    # rung spacing
    sp = x.sort_values(col).groupby(["game_id", "mark"])[col].diff().dropna()
    print("rung spacing value counts", sp.round(2).value_counts().head(5).to_dict())
    print()

# other books' full-game alternates and team totals, by season (coverage only)
for m in ["alternate_totals", "alternate_spreads", "team_totals_home", "team_totals_away"]:
    x = q[q.market == m]
    print(m, x.groupby(["bookmaker", "season"]).game_id.nunique().unstack(fill_value=0).to_string())
