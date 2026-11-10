"""Games with in-play quotes and no pre-game ones: is ESPN's stored tip early?

    python -m scripts.ncaabw_research.check_tips
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.ncaabw_research._paths import CACHE as C  # noqa: E402
P = pd.read_parquet(C / "pregame_quotes.parquet", columns=["game_id"])
L = pd.read_parquet(C / "inplay_quotes.parquet", columns=["game_id", "snapshot_ts", "last_update"])
g = pd.read_parquet(C / "games.parquet")[["game_id", "season", "commence_time", "game_date", "espn_event_id"]]
only = sorted(set(L["game_id"]) - set(P["game_id"]))
print("games with in-play quotes", L["game_id"].nunique(), "| pre-game quotes", P["game_id"].nunique(),
      "| in-play only", len(only))
x = L[L["game_id"].isin(only)].groupby("game_id").agg(first_quote=("last_update", "min"),
                                                      last_quote=("last_update", "max")).reset_index()
x = x.merge(g, on="game_id")
x["tip"] = pd.to_datetime(x["commence_time"], utc=True, errors="coerce")
x["first_quote"] = pd.to_datetime(x["first_quote"], utc=True)
x["lead_h"] = (x["first_quote"] - x["tip"]).dt.total_seconds() / 3600
print("by season:", x.groupby("season").size().to_dict())
print("stored tip missing:", int(x["tip"].isna().sum()))
print("hours from the stored tip to the first 'in-play' quote:", x["lead_h"].describe().round(2).to_dict())
print("stored tip's UTC hour:", x["tip"].dt.hour.value_counts().head(6).to_dict())
pb = {}
for s in (2025, 2026):
    df = pd.read_parquet(C / f"pbp_{s}.parquet", columns=["game_id", "wallclock"])
    df = df[df["game_id"].isin(x["espn_event_id"])]
    pb.update(pd.to_datetime(df["wallclock"], utc=True, errors="coerce").groupby(df["game_id"]).min().to_dict())
x["first_play"] = x["espn_event_id"].map(pb)
y = x.dropna(subset=["first_play", "tip"])
y = y.assign(tip_to_first_play_h=(y["first_play"] - y["tip"]).dt.total_seconds() / 3600)
print("with a play-by-play:", len(y), "| hours from the stored tip to the first play:",
      y["tip_to_first_play_h"].describe().round(2).to_dict())
print(y[["game_id", "commence_time", "first_quote", "first_play"]].head(4).to_string())
