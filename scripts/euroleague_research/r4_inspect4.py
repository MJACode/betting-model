"""Round 4 (halftime): the shot feed's clock near the end of the half, one game, and the clock-order census."""
import numpy as np
import pandas as pd
from pathlib import Path
C = Path(r"C:\Users\micha\euroleague_research\cache")
s = pd.read_parquet(C / "shots.parquet")
h = pd.read_parquet(C / "halftime.parquet")
cs = s.console.str.split(":", expand=True).astype(float)
s["clock_s"] = cs[0] * 60 + cs[1]
for gid in ["EUROLEAGUE_E2021_10", "EUROLEAGUE_E2025_100"]:
    x = s[(s.game_id == gid) & s.minute.between(17, 22)].sort_values("num_anot")
    print(gid); print(x[["num_anot", "minute", "console", "points_home", "points_away", "shot_utc"]].to_string(index=False))
    print(h[h.game_id == gid].to_string())
# minute 20 consoles distribution
print("minute==20 console seconds quantiles:", s[s.minute == 20].clock_s.quantile([0, .1, .5, .9, 1]).to_dict())
print("minute==11 console seconds quantiles:", s[s.minute == 11].clock_s.quantile([0, .1, .5, .9, 1]).to_dict())
print("minute==1 console:", s[s.minute == 1].clock_s.quantile([0, .1, .5, .9, 1]).to_dict())
