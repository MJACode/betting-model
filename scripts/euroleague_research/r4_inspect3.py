"""Round 4 (halftime): structural checks before the pre-registration (no results read)."""
import numpy as np
import pandas as pd
from pathlib import Path
C = Path(r"C:\Users\micha\euroleague_research\cache")
g = pd.read_parquet(C / "games.parquet"); g["tip"] = pd.to_datetime(g.commence_time, utc=True)
s = pd.read_parquet(C / "shots.parquet")
h = pd.read_parquet(C / "halftime.parquet")
q = pd.read_parquet(C / "inplay_quotes.parquet")
f = pd.read_parquet(C / "fullgame_quotes.parquet")
print("inplay dup (snapshot,game,book,market):", int(q.duplicated(["snapshot_ts", "game_id", "bookmaker", "market"]).sum()))
print("last_update > snapshot_ts:", int((q.last_update > q.snapshot_ts).sum()), "null last_update:", int(q.last_update.isna().sum()))
print("console examples:", s.console.head(5).tolist(), "minute 10 consoles:", s[s.minute == 10].console.head(5).tolist())
cs = s.console.str.split(":", expand=True).astype(float)
s["clock_s"] = cs[0] * 60 + cs[1]
s["q"] = np.where(s.minute <= 40, (s.minute - 1) // 10 + 1, 4 + (s.minute - 41) // 5 + 1)
s["gs_calc"] = np.where(s.q <= 4, (s.q - 1) * 600 + 600 - s.clock_s, 2400 + (s.q - 5) * 300 + 300 - s.clock_s)
s["min_calc"] = np.floor(np.where(s.q <= 4, s.gs_calc, s.gs_calc) / 60) + 1
print("minute vs floor(gs/60)+1 agree:", float(((s.min_calc == s.minute) | (s.clock_s % 60 == 0)).mean()))
print("clock > 600 rows:", int((s.clock_s > 600).sum()), "OT clock > 300:", int(((s.q > 4) & (s.clock_s > 300)).sum()))
s = s.sort_values(["game_id", "num_anot"])
s["wall_back"] = s.groupby("game_id").shot_utc.diff().dt.total_seconds() < 0
s["gs_back"] = s.groupby("game_id").gs_calc.diff() < 0
print("shot_utc runs backwards in num_anot order:", int(s.wall_back.sum()), "game clock backwards:", int(s.gs_back.sum()), "of", len(s))
fs = s.groupby("game_id").shot_utc.min().rename("first_shot")
x = g.set_index("game_id").join(fs, how="inner")
d = (x.first_shot - x.tip).dt.total_seconds() / 60
print("first shot minus listed tip, minutes:", d.quantile([0, .01, .05, .25, .5, .75, .95, .99, 1]).round(2).to_dict())
# score at the last Q2 shot vs the half-time score
h2 = s[s.minute <= 20].groupby("game_id").agg(ph=("points_home", "max"), pa=("points_away", "max"), last=("shot_utc", "max"))
hh = h.set_index("game_id").join(h2)
print("running max at Q2 end == ht score:", int(((hh.ph == hh.ht_home) & (hh.pa == hh.ht_away)).sum()), "of", len(hh),
      "; last_q2_shot == max shot_utc in min<=20:", int((hh["last"] == hh.last_q2_shot).sum()))
# clock at the last Q2 shot
lastq2 = s[s.minute <= 20].sort_values("num_anot").groupby("game_id").tail(1)
print("game clock left in Q2 at last Q2 shot (s):", (1200 - lastq2.gs_calc).quantile([.1, .25, .5, .75, .9]).to_dict())
# reads inside the halftime window
h = h[h.break_minutes.between(10, 25)]
qq = q.merge(h[["game_id", "last_q2_shot", "first_q3_shot"]], on="game_id")
win = (qq.snapshot_ts > qq.last_q2_shot + pd.Timedelta(minutes=1)) & (qq.snapshot_ts < qq.first_q3_shot - pd.Timedelta(minutes=1))
r = qq[win][["game_id", "snapshot_ts"]].drop_duplicates()
print("games with >=1 read in window:", r.game_id.nunique(), "reads per game:", r.groupby("game_id").size().value_counts().sort_index().to_dict())
# full-game quotes after the listed tip
f = f.merge(g[["game_id", "tip"]], on="game_id")
print("fullgame rows with snapshot_at > tip:", int((f.snapshot_at > f.tip).sum()), "of", len(f))
print("fullgame books:", f.bookmaker.value_counts().to_dict())
