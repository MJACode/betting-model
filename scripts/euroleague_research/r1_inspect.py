"""Round 1 orientation: the cache files' shape (columns, row counts, markets,
books, marks, games by season and phase).

    python scripts/euroleague_research/r1_inspect.py
"""
from pathlib import Path

import pandas as pd

C = Path(r"C:\Users\micha\euroleague_research\cache")
for f in ["games", "periods", "period_quotes", "period_fetches"]:
    d = pd.read_parquet(C / f"{f}.parquet")
    print("=====", f, d.shape)
    print(d.dtypes)
    print(d.head(3).T)
q = pd.read_parquet(C / "period_quotes.parquet")
print(q.market.value_counts())
print(q.bookmaker.value_counts())
print(q.mark.value_counts())
g = pd.read_parquet(C / "games.parquet")
print(g.groupby(["season", "phase"]).size())
print(g.groupby("season")[["played"]].sum())
