"""2026 forward read of the two best full-game candidates from the 2023-2025 archive, unchanged.

  S  spread: best deciding-book quote vs the 10-book consensus line (fitted offset), edge > cut
  C  moneyline: best deciding-book moneyline vs the consensus spread, edge > cut, never shorter than -200
Game-day morning: each book's newest stored pre-game quote at or before 13:55 UTC on the game's ET date,
no older than 24 hours. Tables fitted on every season through 2025. Graded on 2026 finals.
Also: what the road-underdog spread sizes did with no model at all (every game, away side).
"""
from pathlib import Path

import numpy as np
import pandas as pd

import lab
from lab import D, BETTABLE, CONS_BOOKS, MIN_OTHER, dec, grade, by_season, best, price_spread, price_ml, md

pd.set_option("display.width", 230)
g = pd.read_parquet(D / "g.parquet")
tabs = lab.tables(g, [2026])

L = pd.read_parquet(D / "q_2026_long.parquet")
L = L[L.bookmaker.isin(CONS_BOOKS)]
gg = g[(g.season == 2026) & g.margin.notna()][["game_id", "kick", "et_date", "season", "margin", "total", "week", "home_team", "away_team"]]
L = L.merge(gg, on="game_id", how="inner")
slot = (pd.to_datetime(L.et_date) + pd.Timedelta(hours=13, minutes=55)).dt.tz_localize("UTC")
L = L[(L.pull_ts <= slot) & (L.pull_ts >= slot - pd.Timedelta(hours=24)) & (slot < L.kick - pd.Timedelta(minutes=5))]
L = L.sort_values("pull_ts").drop_duplicates(["game_id", "bookmaker", "market"], keep="last")
age = (slot.loc[L.index] - L.pull_ts).dt.total_seconds() / 3600
print("2026 game-day-morning quotes:", len(L), "games", L.game_id.nunique(), "| quote age hours: median", round(age.median(), 2), "90th pct", round(age.quantile(.9), 2))
key = ["game_id", "bookmaker"]
s = L[L.market == "spreads"][key + ["spread_home", "home_price", "away_price"]].rename(columns={"home_price": "sp_home", "away_price": "sp_away"})
t = L[L.market == "totals"][key + ["total_line", "over_price", "under_price"]]
m = L[L.market == "h2h"][key + ["home_price", "away_price"]].rename(columns={"home_price": "ml_home", "away_price": "ml_away"})
x = s.merge(t, on=key, how="outer").merge(m, on=key, how="outer").merge(gg, on="game_id")
# a 2026 game can sit under two ids (ET and UTC dated): keep the id with more books
n = x.groupby("game_id").bookmaker.nunique()
x["pair"] = x.apply(lambda r: "|".join(sorted((r.home_team, r.away_team))) + "|" + str(r.week), axis=1)
keep = x.assign(nb=x.game_id.map(n)).sort_values("nb", ascending=False).drop_duplicates(["pair", "bookmaker"]).game_id.unique()
x = x[x.game_id.isin(keep)]
# closes for the close-value columns: each book's last pre-kick row, median
allq = pd.read_parquet(D / "q_2026_long.parquet")
allq = allq[allq.bookmaker.isin(CONS_BOOKS) & (allq.market == "spreads")].merge(gg[["game_id", "kick"]], on="game_id")
allq = allq[allq.pull_ts < allq.kick].sort_values("pull_ts").drop_duplicates(["game_id", "bookmaker"], keep="last")
x["close_spread"] = x.game_id.map(allq.groupby("game_id").spread_home.median())
x["close_total"] = np.nan
print("games priced:", x.game_id.nunique(), "| books per game (median):", x.groupby("game_id").bookmaker.nunique().median())


def line(tag, b):
    r = grade(b)
    if r["bets"] == 0:
        print(f"{tag:<40} 0 bets")
        return
    bb = r["_b"]
    print(f"{tag:<40} {r['bets']:>4} (home {int((bb.side==1).sum()):>2}) {r['rec']:>10} {r['units']:>+7.2f}u {r['roi']:>+6.1f}% [{r['lo']:>5.1f},{r['hi']:>5.1f}] "
          f"cv{r['ev_close']:>+5.1f} clv{r['clv_pts']:>+5.2f} | price {int(bb.price.min())}/{int(bb.price.median())}/{int(bb.price.max())}")


print("\n== S spread, 2026 forward ==")
c = best(price_spread(x, tabs))
c = c[c.n_ok - 1 >= MIN_OTHER]
for cut in (0.02, 0.03, 0.04, 0.05):
    line(f"S cut {cut}", c[c.edge > cut])
b = c[c.edge > 0.03]
if len(b):
    bb = grade(b)["_b"]
    print("  by month:", {k: f"{len(v)}/{v.pnl.sum():+.1f}u" for k, v in bb.groupby(bb.et_date.str.slice(0, 7))})
    res = np.where(b.side == 1, b.margin + b.cons, -(b.margin + b.cons))
    line("  same sides at the consensus -110", b.assign(price=-110.0, res=np.sign(res)))
print("\n== C moneyline vs consensus spread, 2026 forward ==")
c2 = best(price_ml(x, tabs, "cons"))
c2 = c2[c2.n_ok - 1 >= MIN_OTHER]
for cut in (0.01, 0.02, 0.03, 0.04):
    line(f"C cut {cut}", c2[c2.edge > cut])
print("\n== M moneyline vs own spread, 2026 forward ==")
c3 = best(price_ml(x, tabs, "own"))
for cut in (0.005, 0.01, 0.015, 0.02):
    line(f"M cut {cut}", c3[c3.edge > cut])

print("\n== no model: every game, the away side, by the size of the consensus spread ==")
one = x[x.spread_home.notna() & x.sp_away.notna() & x.sp_home.notna()].copy()
one["cons"] = one.groupby("game_id").spread_home.transform("median")
one["n_ok"] = one.groupby("game_id").spread_home.transform("size")
ob = one[one.bookmaker.isin(BETTABLE) & (one.n_ok >= 4)]
aw = ob.assign(_d=dec(ob.sp_away)).sort_values(["game_id", "spread_home", "_d"], ascending=[True, True, False]).drop_duplicates("game_id")
aw = aw.assign(side=2, price=aw.sp_away, res=np.sign(-(aw.margin + aw.spread_home)), ev_close=np.nan, clv_pts=np.nan)
for lo, hi in ((-99, -24.5), (-24.5, -14.5), (-14, -7.5), (-7, -3.5), (-3, 0), (0.5, 99)):
    line(f"2026 away, home line {lo}..{hi}", aw[(aw.cons >= lo) & (aw.cons <= hi)])
