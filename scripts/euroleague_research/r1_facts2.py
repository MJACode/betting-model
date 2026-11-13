"""Round 1: are BetMGM's / Fanatics' long-priced main first-half lines real
off-centre numbers? Compare each with the other books' number at the same
(game, mark).

    python scripts/euroleague_research/r1_facts2.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

C = Path(r"C:\Users\micha\euroleague_research\cache")
g = pd.read_parquet(C / "games.parquet")
q = pd.read_parquet(C / "period_quotes.parquet")
q = q.merge(g[["game_id", "season"]], on="game_id", how="left")

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 30)


def imp(a):
    a = np.asarray(a, float)
    return np.where(a > 0, 100 / (a + 100), -a / (-a + 100))


for m, col, a, b in [("spreads_h1", "spread_home", "home_price", "away_price"),
                     ("totals_h1", "total_line", "over_price", "under_price"),
                     ("totals_q1", "total_line", "over_price", "under_price")]:
    x = q[q.market == m].copy()
    x["s"] = imp(x[a]) + imp(x[b])
    x["pa"] = imp(x[a]) / x["s"]
    x["offc"] = (x["pa"] - 0.5).abs() > 0.15        # one side shorter than about -186 no-vig
    print(f"== {m}: share of main quotes with a side's no-vig prob beyond 0.35/0.65, by book and season")
    print(x.pivot_table(index="bookmaker", columns="season", values="offc", aggfunc="mean").round(3))
    # median of other books' numbers at the same (game, mark)
    med = x.groupby(["game_id", "mark"])[col].median().rename("med")
    x = x.join(med, on=["game_id", "mark"])
    x["dev"] = x[col] - x["med"]
    y = x[x.offc]
    print(f"-- off-centre quotes: their number minus the (game, mark) median number, by book")
    print(y.groupby("bookmaker")["dev"].describe().round(2))
    print(y[["game_id", "mark", "bookmaker", col, a, b, "med"]].head(8).to_string())
    print()
