"""Due diligence on the spread rule (best deciding-book quote vs the consensus line), 2023-2025.

  1. per-season / halves at each morning slot
  2. where the profit sits: points off the consensus, line size, key numbers, side, book
  3. the reference: 10-book median vs deciding books only vs Pinnacle alone
  4. is the off-market number still there at the next pull, and where did the consensus go
  5. first-cross across morning slots (the live shape: decided once a game)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import lab
from lab import D, BETTABLE, CONS_BOOKS, MIN_OTHER, dec, grade, by_season, halves, best, price_spread

g, q = lab.load()
tabs = lab.tables(g, [2023, 2024, 2025])
AM = ["D5_AM", "D4_AM", "D3_AM", "D2_AM", "D1_AM", "D0_AM"]


def line(tag, b):
    r = grade(b)
    if r["bets"] == 0:
        print(f"{tag:<34} 0 bets")
        return
    bb = r["_b"]
    print(f"{tag:<34} {r['bets']:>4} {r['rec']:>11} {r['units']:>+7.1f}u {r['roi']:>+6.1f}% [{r['lo']:>5.1f},{r['hi']:>5.1f}] "
          f"cv{r['ev_close']:>+5.1f} clv{r['clv_pts']:>+5.2f} ex10 {r['ex10']:>+6.1f} | {by_season(bb)} | {halves(bb)}")


priced = {s: price_spread(q[q.slot == s], tabs) for s in AM + ["D1_PM", "D0_PM"]}
cand = {s: best(p)[lambda z: z.n_ok - 1 >= MIN_OTHER] for s, p in priced.items()}

print("\n== 1. per slot, cut 0.03 and 0.04 ==")
for s in AM + ["D1_PM", "D0_PM"]:
    for c in (0.03, 0.04):
        line(f"{s} cut {c}", cand[s][cand[s].edge > c])

b0 = cand["D0_AM"][cand["D0_AM"].edge > 0.03]
r0 = grade(b0)["_b"]
print("\n== 2. D0_AM cut 0.03: where the profit sits ==")
r0 = r0.assign(off=pd.cut(r0.off_pts, [-9, 0.01, 0.75, 1.25, 9], labels=["<=0 (price only)", "0.5", "1.0", "1.5+"]),
               size=pd.cut(r0.spread_home.abs(), [-1, 3, 7, 14, 24.5, 99], labels=["0-3", "3.5-7", "7.5-14", "14.5-24.5", "25+"]),
               sd=np.where(r0.side == 1, "home", "away"),
               fav=np.where(r0.line_side < 0, "favourite", "dog"))
for col in ("off", "size", "sd", "fav", "bookmaker", "season"):
    t = r0.groupby(col, observed=True).agg(bets=("pnl", "size"), units=("pnl", "sum"), risked=("risked", "sum"),
                                           cv=("ev_close", "mean"), clv=("clv_pts", "mean"))
    t["roi%"] = 100 * t.units / t.risked
    print(t.round(2).to_string(), "\n")
print("price range: min", r0.price.min(), "median", r0.price.median(), "max", r0.price.max(),
      "| share shorter than -120:", round((r0.price < -120).mean(), 3))
print("edge quantiles:", r0.edge.quantile([0, .25, .5, .75, 1]).round(4).to_dict())

print("\n== 3. the reference line (D0_AM) ==")


def reprice(x, ref):
    """Same rule with another reference: 'bettable' median, or 'pinnacle' (needs a Pinnacle quote)."""
    x = x.copy()
    if ref == "bettable":
        x = x[x.bookmaker.isin(BETTABLE)]
        return price_spread(x, tabs)
    z = price_spread(x, tabs)             # for hygiene + columns
    pin = x[(x.bookmaker == "pinnacle") & x.spread_home.notna()].drop_duplicates("game_id").set_index("game_id").spread_home
    z = z[z.game_id.isin(pin.index)].copy()
    out = []
    for s, zz in z.groupby("season"):
        t = tabs[s]
        zz = zz.copy()
        zz["cons"] = zz.game_id.map(pin)
        mu = (-zz.cons + t["c"]).to_numpy(float)
        ph, _ = lab.md.home_cover(mu, zz.spread_home.to_numpy(float), t["Tm"])
        e1 = ph - 1 / dec(zz.sp_home)
        e2 = (1 - ph) - 1 / dec(zz.sp_away)
        zz["side"] = np.where(e1 >= e2, 1, 2)
        zz["edge"] = np.maximum(e1, e2)
        zz["price"] = np.where(zz.side == 1, zz.sp_home, zz.sp_away)
        zz["line_side"] = np.where(zz.side == 1, zz.spread_home, -zz.spread_home)
        res = np.where(zz.side == 1, zz.margin + zz.spread_home, -(zz.margin + zz.spread_home))
        zz["res"] = np.sign(res)
        out.append(zz)
    return pd.concat(out)


x0 = q[q.slot == "D0_AM"]
for ref in ("bettable", "pinnacle"):
    z = best(reprice(x0, ref))
    z = z[z.n_ok - 1 >= MIN_OTHER]
    for c in (0.02, 0.03, 0.04):
        line(f"ref={ref} cut {c}", z[z.edge > c])

print("\n== 4. D0_AM cut 0.03: the same book at the next pull, and the consensus at the next pull ==")
allq = q[q.spread_home.notna()].sort_values("pull_ts")
nxt_rows = []
for r in b0.itertuples():
    later = allq[(allq.game_id == r.game_id) & (allq.pull_ts > r.pull_ts)]
    if not len(later):
        nxt_rows.append((r.game_id, np.nan, np.nan, np.nan))
        continue
    t1 = later.pull_ts.min()
    l1 = later[later.pull_ts == t1]
    same = l1[l1.bookmaker == r.bookmaker]
    nxt_rows.append((r.game_id, (t1 - r.pull_ts).total_seconds() / 3600,
                     same.spread_home.iloc[0] if len(same) else np.nan, l1.spread_home.median()))
nx = pd.DataFrame(nxt_rows, columns=["game_id", "hrs_next", "book_next", "cons_next"]).set_index("game_id")
j = b0.set_index("game_id").join(nx)
have = j[j.hrs_next.notna()]
print("bets with a later pre-kick pull:", len(have), "of", len(j), "| median hours to it:", round(have.hrs_next.median(), 1))
if len(have):
    moved_to_cons = (have.book_next - have.cons).abs() < (have.spread_home - have.cons).abs()
    print("  bet book moved toward the old consensus:", round(moved_to_cons.mean(), 3),
          "| bet book unchanged:", round((have.book_next == have.spread_home).mean(), 3),
          "| bet book gone:", round(have.book_next.isna().mean(), 3))
    toward_us = np.where(have.side == 1, have.cons_next - have.cons, have.cons - have.cons_next)  # +: consensus moved AGAINST the bet side's number... see note
    print("  consensus move in the bet's favour (points, + = the market came to our side):", round(float(np.nanmean(-toward_us)), 3))
print("clv points by season (bet line vs CFBD close, + = better than close):")
print(r0.groupby("season").clv_pts.agg(["mean", "median", lambda v: (v > 0).mean(), lambda v: (v < 0).mean()]).round(3).to_string())

print("\n== 5. first cross across morning slots, decided once a game ==")
for start in (4, 3, 2, 1, 0):
    for c in (0.03, 0.04):
        seen = set()
        parts = []
        for k in range(start, -1, -1):
            cc = cand[f"D{k}_AM"]
            cc = cc[(cc.edge > c) & ~cc.game_id.isin(seen)]
            seen |= set(cc.game_id)
            parts.append(cc)
        line(f"first cross from D{start} cut {c}", pd.concat(parts))
pd.to_pickle(dict(cand=cand), D / "spread_cand.pkl")


print()
print("== 6. controls ==")
# (a) no home/away tilt: offset 0
tabs0 = {s: dict(t, c=0.0) for s, t in tabs.items()}
for s_ in ("D0_AM", "D1_AM", "D2_AM", "D3_AM", "D4_AM", "D1_PM"):
    z = best(price_spread(q[q.slot == s_], tabs0))
    z = z[z.n_ok - 1 >= MIN_OTHER]
    for c in (0.02, 0.03, 0.04):
        zz = z[z.edge > c]
        line(f"offset 0 {s_} cut {c} (home {int((zz.side==1).sum())})", zz)
# (b) every game, the away side: at the consensus line at -110, and at the best away quote among deciding books
x = q[(q.slot == "D0_AM") & q.spread_home.notna() & q.sp_away.notna() & q.sp_home.notna()].copy()
x["cons"] = x.groupby("game_id").spread_home.transform("median")
x["n_ok"] = x.groupby("game_id").spread_home.transform("size")
xb = x[x.bookmaker.isin(BETTABLE) & (x.n_ok >= 4)]
one = xb.drop_duplicates("game_id")
for nm, side in (("away", 2), ("home", 1)):
    res = np.where(side == 1, one.margin + one.cons, -(one.margin + one.cons))
    b = one.assign(side=side, price=-110.0, res=np.sign(res), ev_close=np.nan, clv_pts=np.nan)
    line(f"every game {nm} at consensus -110", b)
# best away line then price
xa = xb.assign(_d=dec(xb.sp_away)).sort_values(["game_id", "spread_home", "_d"], ascending=[True, True, False]).drop_duplicates("game_id")
res = -(xa.margin + xa.spread_home)
line("every game away at its best quote", xa.assign(side=2, price=xa.sp_away, res=np.sign(res), ev_close=np.nan, clv_pts=np.nan))
xh = xb.assign(_d=dec(xb.sp_home)).sort_values(["game_id", "spread_home", "_d"], ascending=[True, False, False]).drop_duplicates("game_id")
res = (xh.margin + xh.spread_home)
line("every game home at its best quote", xh.assign(side=1, price=xh.sp_home, res=np.sign(res), ev_close=np.nan, clv_pts=np.nan))
# (c) the rule's own bets, re-bet on the same side at the consensus line at -110
res = np.where(b0.side == 1, b0.margin + b0.cons, -(b0.margin + b0.cons))
line("rule bets re-bet at consensus -110", b0.assign(price=-110.0, res=np.sign(res)))
# (d) dogs vs favourites base rate at the consensus, every game
dogside = np.where(one.cons > 0, 1, 2)
res = np.where(dogside == 1, one.margin + one.cons, -(one.margin + one.cons))
line("every game the dog at consensus -110", one.assign(side=dogside, price=-110.0, res=np.sign(res), ev_close=np.nan, clv_pts=np.nan)[one.cons != 0])
