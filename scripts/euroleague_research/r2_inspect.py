"""Round 2 (full game): first look at the cache. Prints shapes, dtypes, heads."""
import pandas as pd
from pathlib import Path
C = Path(r"C:\Users\micha\euroleague_research\cache")
for f in ["games", "periods", "fullgame_quotes"]:
    d = pd.read_parquet(C / f"{f}.parquet")
    print("=====", f, d.shape)
    print(d.dtypes.to_string())
    print(d.head(5).to_string())
q = pd.read_parquet(C / "fullgame_quotes.parquet")
print(q.groupby(["market", "bookmaker"]).size().unstack(0).to_string())
g = pd.read_parquet(C / "games.parquet")
print(g.groupby(["season", "phase"]).size().unstack().to_string())
print(g.status.value_counts().to_string()); print(g.played.value_counts().to_string())
