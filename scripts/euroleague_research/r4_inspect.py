"""Round 4 (halftime): print the schema and a few rows of each cache file used."""
import pandas as pd
from pathlib import Path
C = Path(r"C:\Users\micha\euroleague_research\cache")
for f in ["games", "periods", "halftime", "shots", "inplay_quotes", "fullgame_quotes"]:
    d = pd.read_parquet(C / f"{f}.parquet")
    print("=====", f, d.shape)
    print(d.dtypes.to_string())
    print(d.head(3).to_string())
