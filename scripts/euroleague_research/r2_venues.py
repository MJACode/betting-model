"""Full-game round 1: tip hours (UTC) and each club's home venues with counts, attendance."""
import pandas as pd, numpy as np
import r2_lib as L
g = L.load_games(); g = g[g.played]
print("tip hour UTC counts:", g.tip.dt.hour.value_counts().sort_index().to_dict())
print("tips before 15:05 UTC:", int(((g.tip.dt.hour * 60 + g.tip.dt.minute) < 15 * 60 + 5).sum()), "of", len(g))
t = g.groupby(["home_code", "venue_name", "neutral_site"]).agg(n=("game_id", "size"), seasons=("season", lambda s: ",".join(map(str, sorted(set(s))))),
    att_mean=("audience", lambda a: round(float(a[a > 0].mean()), 0) if (a > 0).any() else np.nan), att0=("audience", lambda a: int((a == 0).sum()))).reset_index()
pd.set_option("display.width", 250)
print(t.sort_values(["home_code", "n"], ascending=[True, False]).to_string(index=False))
