"""Round 2 (full game): the quote clock and structure checks."""
import pandas as pd, numpy as np
from pathlib import Path
C = Path(r"C:\Users\micha\euroleague_research\cache")
q = pd.read_parquet(C / "fullgame_quotes.parquet")
g = pd.read_parquet(C / "games.parquet")
g["tip"] = pd.to_datetime(g.commence_time, utc=True)
q = q.merge(g[["game_id", "season", "tip", "played"]], on="game_id", how="left")
print("quotes with no games row:", q.season.isna().sum())
q["lead_min"] = (q.tip - q.snapshot_at).dt.total_seconds() / 60
print("lead minutes describe:\n", q.lead_min.describe().to_string())
print("rows with snapshot_at > tip:", (q.lead_min < 0).sum())
print("rows by season:\n", q.groupby("season").size().to_string())
# snapshot clock: seconds within 5-minute grid
s = q.snapshot_at
print("second-of-minute distribution (top):", s.dt.second.value_counts().head(5).to_dict())
print("minute mod 5 distribution:", (s.dt.minute % 5).value_counts().sort_index().to_dict())
# duplicates per (game, market, book, snapshot_at)
d = q.groupby(["game_id", "market", "bookmaker", "snapshot_at"]).size()
print("dup (game,market,book,snapshot) >1:", (d > 1).sum(), "of", len(d))
# example duplicate
if (d > 1).any():
    k = d[d > 1].index[0]
    print(q[(q.game_id == k[0]) & (q.market == k[1]) & (q.bookmaker == k[2]) & (q.snapshot_at == k[3])].to_string())
# change-only check: consecutive identical rows
q = q.sort_values(["game_id", "market", "bookmaker", "snapshot_at"])
cols = ["home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"]
prev = q.groupby(["game_id", "market", "bookmaker"])[cols].shift()
same = (q[cols].fillna(-9999) == prev.fillna(-9999)).all(axis=1) & prev.notna().any(axis=1)
print("rows identical to the previous row of the same key:", int(same.sum()))
# distinct snapshot_at values per game per market-book: how much spread of created_at
print("created_at range:", q.created_at.min(), q.created_at.max())
# per season unique games quoted
print(q.groupby("season").game_id.nunique().to_string())
# check the gaps between consecutive snapshot_at of the same key, in minutes
q["gap"] = q.groupby(["game_id", "market", "bookmaker"]).snapshot_at.diff().dt.total_seconds() / 60
print("gap minutes quantiles:", q.gap.quantile([.05, .25, .5, .75, .95]).round(2).to_dict())
# fractional-minute: are snapshot_at on the 5-min clock exactly?
off = (s.dt.minute % 5) * 60 + s.dt.second
print("seconds past a 5-minute mark quantiles:", off.quantile([.05, .25, .5, .75, .95]).to_dict())
