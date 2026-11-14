"""Census of UFC rows in the local mirror of public.odds (no database load)."""
import glob, time
import pyarrow.dataset as ds
import pyarrow.compute as pc
import pandas as pd

pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
from _paths import MIRROR
M = MIRROR + r"\public.odds"
t0 = time.time()
d = ds.dataset(glob.glob(M + r"\*.parquet"), format="parquet")
print(d.schema.names)
cols = [c for c in d.schema.names]
tbl = d.to_table(filter=pc.field("sport") == "UFC")
df = tbl.to_pandas()
print("rows", len(df), "secs", round(time.time() - t0, 1))
df.to_parquet("ufc_odds.parquet")
df["snap"] = pd.to_datetime(df.get("snapshot_at", df.get("created_at")), utc=True, errors="coerce")
df["yr"] = df["snap"].dt.year
print(df.groupby(["yr", "market"]).size().unstack(fill_value=0))
print(df.groupby(["market", "bookmaker"]).size().unstack(fill_value=0).T)
if "source" in df:
    print(df.groupby(["source", "yr"]).size())
print(df.groupby("snapshot_type").size())
print("games", df.game_id.nunique(), df.groupby("yr").game_id.nunique())
