"""The spread rule with the side tilt taken out, and a table-free version.

The first replay's bets were 99% away sides: the fitted table says the home side covers the
consensus a little under half the time at most lines (walk-forward offset -0.27 to -0.39 points,
plus the kernel's own noise on 7,500-9,200 games), and a 0.03 cut then admits one side only.
Every-game controls show no away edge on 2023-2025 (away at the consensus -110: -4.4%).

  SYM   the same table, but each side's chance at the CONSENSUS line is set equal (the push left
        out); a quote's value is then only the margin mass between its line and the consensus,
        and its price.
  PTS   no table: bet the deciding-book quote that is the most points better than the consensus
        for either side, when it is at least `pts` better and its price is -115 or longer.
"""
import numpy as np
import pandas as pd

import lab
from lab import BETTABLE, MIN_OTHER, dec, grade, by_season, halves, best, md, D

g, q = lab.load()
tabs = lab.tables(g, [2023, 2024, 2025])
SLOTS = ["D0_AM", "D1_AM", "D2_AM", "D3_AM", "D4_AM", "D5_AM", "D0_PM", "D1_PM"]


def line(tag, b):
    r = grade(b)
    if r["bets"] == 0:
        print(f"{tag:<40} 0 bets")
        return None
    bb = r["_b"]
    home = int((bb.side == 1).sum())
    print(f"{tag:<40} {r['bets']:>4} (home {home:>3}) {r['rec']:>11} {r['units']:>+7.1f}u {r['roi']:>+6.1f}% [{r['lo']:>5.1f},{r['hi']:>5.1f}] "
          f"cv{r['ev_close']:>+5.1f} clv{r['clv_pts']:>+5.2f} ex10 {r['ex10']:>+6.1f} | {by_season(bb)} | {halves(bb)}")
    return bb


def clean(x):
    z = x[x.spread_home.notna() & x.sp_home.notna() & x.sp_away.notna()].copy()
    z = z[(z.spread_home.abs() <= 70) & lab._sanity(dec(z.sp_home), dec(z.sp_away))]
    med_all = z.groupby("game_id").spread_home.transform("median")
    cnt = z.groupby("game_id").spread_home.transform("size")
    z = z[~((np.sign(z.spread_home) * np.sign(med_all) < 0) & (cnt >= 3))].copy()
    z["cons"] = z.groupby("game_id").spread_home.transform("median")
    z["n_ok"] = z.groupby("game_id").spread_home.transform("size")
    return z


def price_sym(x, tabs):
    z = clean(x)
    out = []
    for s, zz in z.groupby("season"):
        t = tabs[s]
        zz = zz.copy()
        mu = (-zz.cons).to_numpy(float)
        gC, pC, lC = md.probs(mu, (-zz.cons).to_numpy(float), t["Tm"])
        gL, pL, lL = md.probs(mu, (-zz.spread_home).to_numpy(float), t["Tm"])
        tilt = (gC - lC) / 2
        w, l = np.clip(gL - tilt, 1e-6, 1), np.clip(lL + tilt, 1e-6, 1)
        ph = w / (w + l)
        zz["ph"] = ph
        e1 = ph - 1 / dec(zz.sp_home)
        e2 = (1 - ph) - 1 / dec(zz.sp_away)
        zz["side"] = np.where(e1 >= e2, 1, 2)
        zz["edge"] = np.maximum(e1, e2)
        zz["price"] = np.where(zz.side == 1, zz.sp_home, zz.sp_away)
        zz["prob"] = np.where(zz.side == 1, ph, 1 - ph)
        zz["line_side"] = np.where(zz.side == 1, zz.spread_home, -zz.spread_home)
        zz["off_pts"] = zz.line_side - np.where(zz.side == 1, zz.cons, -zz.cons)
        res = np.where(zz.side == 1, zz.margin + zz.spread_home, -(zz.margin + zz.spread_home))
        zz["res"] = np.sign(res)
        # value at the CFBD close, same symmetric construction
        muc = (-zz.close_spread).to_numpy(float)
        gC, pC, lC = md.probs(muc, muc, t["Tm"])
        gL, pL, lL = md.probs(muc, (-zz.spread_home).to_numpy(float), t["Tm"])
        tilt = (gC - lC) / 2
        w, l = np.clip(gL - tilt, 1e-6, 1), np.clip(lL + tilt, 1e-6, 1)
        phc = w / (w + l)
        pc = np.where(zz.side == 1, phc, 1 - phc)
        d = dec(zz.price)
        zz["ev_close"] = pc * (d - 1) - (1 - pc)
        zz["clv_pts"] = zz.line_side - np.where(zz.side == 1, zz.close_spread, -zz.close_spread)
        out.append(zz)
    z = pd.concat(out)
    return z[z.bookmaker.isin(BETTABLE)]


def price_pts(x):
    """Both sides of every deciding-book quote, with points better than the consensus."""
    z = clean(x)
    z = z[z.bookmaker.isin(BETTABLE)]
    h = z.assign(side=1, price=z.sp_home, line_side=z.spread_home, off_pts=z.spread_home - z.cons,
                 res=np.sign(z.margin + z.spread_home), clv_pts=z.spread_home - z.close_spread)
    a = z.assign(side=2, price=z.sp_away, line_side=-z.spread_home, off_pts=z.cons - z.spread_home,
                 res=np.sign(-(z.margin + z.spread_home)), clv_pts=z.close_spread - z.spread_home)
    y = pd.concat([h, a])
    y["ev_close"] = np.nan
    y["edge"] = y.off_pts + (dec(y.price) - 1.9) * 0.5     # points first, price breaks ties
    return y


print("\n== SYM: tilt removed ==")
keep = {}
for s in SLOTS:
    pr = price_sym(q[q.slot == s], tabs)
    c = best(pr)
    c = c[c.n_ok - 1 >= MIN_OTHER]
    keep[s] = c
    for cut in (0.015, 0.02, 0.025, 0.03, 0.04):
        line(f"SYM {s} cut {cut}", c[c.edge > cut])
pd.to_pickle(keep, D / "sym_cand.pkl")

b = keep["D0_AM"][keep["D0_AM"].edge > 0.02]
r = grade(b)["_b"]
print("\nSYM D0_AM cut 0.02 detail:")
r = r.assign(off=pd.cut(r.off_pts, [-9, 0.01, 0.75, 1.25, 9], labels=["<=0 (price only)", "0.5", "1.0", "1.5+"]),
             size=pd.cut(r.spread_home.abs(), [-1, 3, 7, 14, 24.5, 99], labels=["0-3", "3.5-7", "7.5-14", "14.5-24.5", "25+"]),
             sd=np.where(r.side == 1, "home", "away"), fav=np.where(r.line_side < 0, "favourite", "dog"))
for col in ("off", "size", "sd", "fav", "bookmaker"):
    t = r.groupby(col, observed=True).agg(bets=("pnl", "size"), units=("pnl", "sum"), risked=("risked", "sum"),
                                          cv=("ev_close", "mean"), clv=("clv_pts", "mean"))
    t["roi%"] = 100 * t.units / t.risked
    print(t.round(2).to_string(), "\n")
print("price min/median/max:", r.price.min(), r.price.median(), r.price.max())

print("\n== PTS: table-free, price -115 or longer ==")
for s in SLOTS:
    y = price_pts(q[q.slot == s])
    y = y[(y.n_ok - 1 >= MIN_OTHER) & (dec(y.price) >= dec(-115))]
    c = y.sort_values(["game_id", "edge"], ascending=[True, False]).drop_duplicates("game_id")
    for pts in (0.5, 1.0, 1.5):
        line(f"PTS {s} >= {pts} pts", c[c.off_pts >= pts])
# how common is an off-market number at all
y = price_pts(q[q.slot == "D0_AM"])
y = y[(y.n_ok - 1 >= MIN_OTHER)]
c = y.sort_values(["game_id", "off_pts"], ascending=[True, False]).drop_duplicates("game_id")
print("\nD0_AM: games", c.game_id.nunique(), "| best deciding-book quote vs consensus, share of games:",
      {k: round(float((c.off_pts >= k).mean()), 3) for k in (0.5, 1.0, 1.5, 2.0)})
