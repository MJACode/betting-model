"""Round 4 (halftime): what the shot feed, the halftime table and the in-play quotes hold."""
import numpy as np
import pandas as pd
from pathlib import Path
C = Path(r"C:\Users\micha\euroleague_research\cache")
g = pd.read_parquet(C / "games.parquet")
s = pd.read_parquet(C / "shots.parquet")
h = pd.read_parquet(C / "halftime.parquet")
q = pd.read_parquet(C / "inplay_quotes.parquet")
s = s.merge(g[["game_id", "season"]], on="game_id", how="left")
print("shot actions:", s.action.value_counts().to_dict())
print("minute range:", s.minute.min(), s.minute.max())
print("shots games by season:", s.groupby("season").game_id.nunique().to_dict())
print("games by season (played):", g[g.played].groupby("season").game_id.nunique().to_dict())
h = h.merge(g[["game_id", "season", "home_score", "away_score", "commence_time"]], on="game_id", how="left")
print("halftime games by season:", h.groupby("season").game_id.nunique().to_dict())
print("break_minutes quantiles:", h.break_minutes.quantile([0, .01, .05, .25, .5, .75, .95, .99, 1]).round(2).to_dict())
ok = h.break_minutes.between(10, 25)
print("break 10-25:", int(ok.sum()), "of", len(h), "by season", h[ok].groupby("season").size().to_dict())
# final running score in the shot feed vs the final score
last = s.sort_values(["game_id", "shot_utc", "num_anot"]).groupby("game_id").agg(ph=("points_home", "max"), pa=("points_away", "max"))
m = last.join(g.set_index("game_id")[["home_score", "away_score"]])
print("shot feed max running score == final:", int(((m.ph == m.home_score) & (m.pa == m.away_score)).sum()), "of", len(m))
# running score at the last Q2 shot vs the half-time score
p = pd.read_parquet(C / "periods.parquet")
print("q:", q.shape, "snapshot_ts range", q.snapshot_ts.min(), q.snapshot_ts.max())
q = q.merge(g[["game_id", "season"]], on="game_id", how="left")
print("inplay rows by season x book:")
print(q.groupby(["season", "bookmaker"]).game_id.nunique().unstack(fill_value=0).to_string())
print("inplay markets:", q.market.value_counts().to_dict())
# cadence: gaps between consecutive snapshot_ts per game
ts = q[["game_id", "season", "snapshot_ts"]].drop_duplicates().sort_values(["game_id", "snapshot_ts"])
ts["gap"] = ts.groupby("game_id").snapshot_ts.diff().dt.total_seconds() / 60
print("snapshot gap minutes by season (median, share 5, share 10):")
print(ts.groupby("season").gap.agg(["median", lambda x: (x.round() == 5).mean(), lambda x: (x.round() == 10).mean(), "count"]).to_string())
print("snapshot_ts second-of-minute:", ts.snapshot_ts.dt.second.value_counts().head(5).to_dict())
