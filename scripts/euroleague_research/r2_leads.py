"""Full-game round 1, step 4: the scout's three cheapest leads. Prints markdown.

FROZEN BEFORE READING (2026-11-13):
  Residual   home margin + the closing home spread (overtime included), at
             Pinnacle's close (the board at the last ledger snapshot <= tip-10);
             also at DraftKings' close. Positive = the home team did better
             than the line. Neutral-site games are excluded everywhere.
  (i)  Relocated "home" games: the groups R1 / R2 of r2_lib's docstring;
       low attendance = audience 1..999 at a non-relocated game; audience 0
       is "missing" (it is not an empty arena). Compared with every other
       home game, and with the same clubs' own-country home games. Blind
       bets on R1: away against the spread and away on the moneyline at the
       DraftKings close and at the best decidable close.
  (ii) Home edge by club, out of sample: for each priced season s (2022-23
       on), the club's mean residual over every earlier season (from
       2021-22), shrunk by n / (n + 30) toward the league's earlier mean;
       relocated and neutral games out of both sides. Read: the regression
       slope of each game's residual on the club's shrunk deviation; a rule
       (fixed now): home against the spread at the DraftKings close when the
       league prior mean plus the club's shrunk deviation is > +1.0 point,
       away when < -1.0. Attendance: the club's previous-season mean
       attendance (audience > 0) in terciles within the priced season,
       against the residual (known before the game); and the game's own
       attendance terciles (descriptive: measured at the game, not before).
       The scout's lead 3 in its cheapest form: the residual by the closing
       home spread's size, per season.
  (iii) Favourite-longshot on moneylines at the DraftKings and Pinnacle
       closes: buckets of the side's power-de-vigged probability; the win
       rate and the return at that book's own price.
"""
import numpy as np
import pandas as pd
import r2_lib as L

R1 = {("TEL", "ALEKSANDAR NIKOLIC HALL"), ("TEL", "BELGRADE ARENA"), ("TEL", "SPYROS KYPRIANOU ATHLETIC CENTER"),
      ("HTA", "ARENA 8888 SOFIA"), ("HTA", "ARENA BOTEVGRAD"),
      ("DUB", "ZETRA ARENA"), ("DUB", "ARENA HUSEJIN SMAJLOVIC ZENICA")}
R2 = {("IST", "MORACA"), ("IST", "ARENA RIGA"), ("ULK", "SAP GARDEN"), ("ULK", "KALNAPILIO ARENA"),
      ("ULK", "ZALGIRIO ARENA"), ("PAR", "BMW PARK")}
EXCL = {("IST", "XIAOMI ARENA")}
K = 30

g = L.load_games()
g = g[g.played].copy()
q = L.load_quotes(games=g)
q = q[q.played]
dt = L.decision_times(g)
cb = L.board_at(q, dt["close"])
key = list(zip(g.home_code, g.venue_name.str.strip()))
g["grp"] = np.select([[k in R1 for k in key], [k in R2 for k in key], [k in EXCL for k in key]],
                     ["R1 relocated (scout's list)", "R2 other one-off venue abroad", "excluded (location unknown)"],
                     "own country")
g.loc[g.neutral_site, "grp"] = "neutral"
lowatt = (g.grp == "own country") & (g.audience > 0) & (g.audience < 1000)
g.loc[lowatt, "grp"] = "own country, attendance 1-999"
g.loc[(g.grp == "own country") & (g.audience == 0), "grp"] = "own country, attendance missing (0)"
sp = cb[cb.market == "spreads"]
g = g.merge(sp[sp.bookmaker == "pinnacle"][["game_id", "line"]].rename(columns={"line": "pin_line"}), on="game_id", how="left")
g = g.merge(sp[sp.bookmaker == "draftkings"][["game_id", "line"]].rename(columns={"line": "dk_line"}), on="game_id", how="left")
ml = cb[(cb.market == "h2h") & (cb.bookmaker == "pinnacle")][["game_id", "pa_pow"]].rename(columns={"pa_pow": "pin_ph"})
g = g.merge(ml, on="game_id", how="left")
g["res_pin"] = g.margin + g.pin_line
g["res_dk"] = g.margin + g.dk_line
g["res"] = g.res_pin.fillna(g.res_dk)


def rsum(x, col="res", n_boot=1000, seed=7):
    x = x[np.isfinite(x[col])]
    if not len(x):
        return {"n": 0}
    by = x.groupby("game_date")[col].agg(["sum", "size"])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(by), size=(n_boot, len(by)))
    m = by["sum"].to_numpy()[idx].sum(1) / by["size"].to_numpy()[idx].sum(1)
    lo, hi = np.percentile(m, [5, 95])
    return {"n": len(x), "mean_resid_pts": round(float(x[col].mean()), 2), "lo": round(float(lo), 2),
            "hi": round(float(hi), 2), "home_cover%": round(100 * float((x[col] > 0).sum() / max((x[col] != 0).sum(), 1)), 1)}


print("## r2_leads.py\n")
# (i)
rows = []
for grp, x in g[g.season >= 2022].groupby("grp"):
    for col in ("res_pin", "res_dk"):
        d = {"group": grp, "line": col.replace("res_", "")}
        d.update(rsum(x, col))
        if col == "res_pin":
            y = x[x.pin_ph.notna()]
            d["home_win%"] = round(100 * float((y.margin > 0).mean()), 1) if len(y) else np.nan
            d["pin_fair_home%"] = round(100 * float(y.pin_ph.mean()), 1) if len(y) else np.nan
        rows.append(d)
print("### (i) The close's spread residual (home margin + closing home spread), 2021-22 on, by venue group\n")
print(L.md_table(pd.DataFrame(rows)))
rows = []
for (club, grp), x in g[(g.season >= 2022) & g.home_code.isin(["TEL", "HTA", "DUB"])].groupby(["home_code", "grp"]):
    d = {"club": club, "group": grp, "seasons": ",".join(str(s) for s in sorted(x.season.unique()))}
    d.update(rsum(x, "res_pin"))
    d["mean_att"] = round(float(x.audience[x.audience > 0].mean()), 0) if (x.audience > 0).any() else np.nan
    rows.append(d)
print("\n### (i) The three relocated clubs, home games by venue group (Pinnacle close)\n")
print(L.md_table(pd.DataFrame(rows)))
rows = []
for s, x in g[g.grp == "R1 relocated (scout's list)"].groupby("season"):
    d = {"season": s}
    d.update(rsum(x, "res_pin"))
    rows.append(d)
print("\n### (i) R1 by season (Pinnacle close)\n")
print(L.md_table(pd.DataFrame(rows)))
# blind bets on R1
r1 = set(g.game_id[g.grp == "R1 relocated (scout's list)"])
rows = []
for market, side in (("spreads", "away"), ("h2h", "away"), ("spreads", "home"), ("h2h", "home")):
    for book in ("draftkings", "best decidable"):
        b = cb[(cb.market == market) & cb.game_id.isin(r1)]
        if book == "draftkings":
            z = L.sides_long(b[b.bookmaker == "draftkings"])
        else:
            d = b[b.bookmaker.isin(L.DECIDABLE)]
            if market == "spreads":
                # the modal decidable number, ties nearest the median then the lower
                ml_ = {}
                for gid, x in d.groupby("game_id"):
                    vc = x.line.value_counts()
                    top = sorted(vc[vc == vc.max()].index, key=lambda v: (abs(v - x.line.median()), v))
                    ml_[gid] = top[0]
                d = d[d.line == d.game_id.map(ml_)]
            z = L.sides_long(d)
            z["dz"] = L.dec(z.price)
            z = z.sort_values(["game_id", "side", "dz"], ascending=[True, True, False]).drop_duplicates(["game_id", "side"])
        z = L.grade(z[z.side == side])
        rows.append(L.row({"market": market, "side": side, "book": book}, z))
print("\n### (i) Blind bets on the R1 games at the close\n")
print(L.md_table(pd.DataFrame(rows)))

# (ii) home edge by club, out of sample
h = g[(g.grp.isin(["own country", "own country, attendance 1-999", "own country, attendance missing (0)"]))
      & np.isfinite(g.res)].copy()
preds = []
for s in range(2023, 2028):
    tr = h[h.season < s]
    te = h[h.season == s].copy()
    lm = tr.res.mean()
    cs = tr.groupby("home_code").res.agg(["mean", "size"])
    dev = (cs["mean"] - lm) * cs["size"] / (cs["size"] + K)
    te["league_prior"] = lm
    te["club_dev"] = te.home_code.map(dev).fillna(0.0)
    te["pred"] = te.league_prior + te.club_dev
    preds.append(te)
P = pd.concat(preds)


def slope(x, y):
    X = np.column_stack([np.ones(len(x)), x])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b
    s2 = (r ** 2).sum() / (len(y) - 2)
    cov = s2 * np.linalg.inv(X.T @ X)
    return b[1], np.sqrt(cov[1, 1])


rows = []
for s, x in list(P.groupby("season")) + [("pooled", P)]:
    b1, se = slope(x.club_dev.to_numpy(), x.res.to_numpy())
    rows.append({"season": s, "games": len(x), "league prior mean (pts)": round(float(x.league_prior.mean()), 2),
                 "actual mean (pts)": round(float(x.res.mean()), 2), "slope on club deviation": round(float(b1), 3),
                 "slope se": round(float(se), 3), "sd of club deviation": round(float(x.club_dev.std()), 3)})
print("\n### (ii) Home edge by club, out of sample: each game's residual on its club's shrunk earlier deviation\n")
print(L.md_table(pd.DataFrame(rows)))
# the rule at the DraftKings close
dk = cb[(cb.market == "spreads") & (cb.bookmaker == "draftkings")]
z = L.sides_long(dk).merge(P[["game_id", "pred"]], on="game_id", how="inner")
home = z[(z.side == "home") & (z.pred > 1.0)]
away = z[(z.side == "away") & (z.pred < -1.0)]
rows = []
for lab, x in (("home when predicted > +1.0", home), ("away when predicted < -1.0", away), ("both", pd.concat([home, away]))):
    x = L.grade(x)
    rows.append(L.row({"rule": lab, "season": "all"}, x))
    for s, xs in x.groupby("season"):
        rows.append(L.row({"rule": lab, "season": int(s)}, xs))
print("\n### (ii) The club home-edge rule at the DraftKings close\n")
print(L.md_table(pd.DataFrame(rows)))
print(f"\nShare of priced home games whose prediction is > +1.0: {100 * float((P.pred > 1.0).mean()):.1f}%; < -1.0: {100 * float((P.pred < -1.0).mean()):.1f}%")

# attendance
att = g[(g.audience > 0) & ~g.neutral_site].groupby(["home_code", "season"]).audience.mean()
P["prev_att"] = [att.get((c, s - 1), np.nan) for c, s in zip(P.home_code, P.season)]
rows = []
for s, x in P[P.prev_att.notna()].groupby("season"):
    x = x.copy()
    x["t"] = pd.qcut(x.prev_att, 3, labels=["low", "mid", "high"])
    for t, y in x.groupby("t", observed=True):
        d = {"season": s, "club's previous-season attendance tercile": str(t), "mean att": round(float(y.prev_att.mean()), 0)}
        d.update(rsum(y))
        rows.append(d)
x = P[P.prev_att.notna()].copy()
x["t"] = x.groupby("season").prev_att.transform(lambda v: pd.qcut(v, 3, labels=False))
for t, y in x.groupby("t"):
    d = {"season": "pooled", "club's previous-season attendance tercile": ["low", "mid", "high"][int(t)],
         "mean att": round(float(y.prev_att.mean()), 0)}
    d.update(rsum(y))
    rows.append(d)
print("\n### (ii) Residual by the club's previous-season attendance (known before the game)\n")
print(L.md_table(pd.DataFrame(rows)))
rows = []
y = h[(h.audience > 0) & (h.season >= 2022)].copy()
y["t"] = y.groupby("season").audience.transform(lambda v: pd.qcut(v, 3, labels=False))
for t, z_ in y.groupby("t"):
    d = {"game's own attendance tercile (descriptive)": ["low", "mid", "high"][int(t)], "mean att": round(float(z_.audience.mean()), 0)}
    d.update(rsum(z_))
    rows.append(d)
print("\n### (ii) Residual by the game's own attendance (measured at the game; descriptive only)\n")
print(L.md_table(pd.DataFrame(rows)))

# the scout's lead 3, cheapest form: residual by the closing home spread
bins = [-99, -10, -5, -1.5, 1.5, 5, 99]
labs = ["home -10 or more", "-10..-5", "-5..-1.5", "-1.5..+1.5", "+1.5..+5", "home +5 or more"]
h2 = h[h.season >= 2022].copy()
h2["line_used"] = h2.pin_line.fillna(h2.dk_line)
h2["bucket"] = pd.cut(h2.line_used, bins, labels=labs, right=False)
rows = []
for bk, x in h2.groupby("bucket", observed=True):
    d = {"closing home spread": bk, "season": "all"}
    d.update(rsum(x))
    rows.append(d)
    for s, xs in x.groupby("season"):
        d = {"closing home spread": bk, "season": int(s)}
        d.update(rsum(xs))
        rows.append(d)
print("\n### (ii) Residual by the size of the closing home spread (the 'weaker teams lean on home court' lead), by season\n")
print(L.md_table(pd.DataFrame(rows)))

# (iii) favourite-longshot
fb = [0, .10, .20, .35, .50, .65, .80, .90, 1.0001]
fl = ["<10%", "10-20%", "20-35%", "35-50%", "50-65%", "65-80%", "80-90%", ">=90%"]
rows = []
for book in ("draftkings", "pinnacle"):
    z = L.sides_long(cb[(cb.market == "h2h") & (cb.bookmaker == book)])
    z["fair_pow"] = np.where(z.side == "home", z.pa_pow, 1 - z.pa_pow)
    z = L.grade(z)
    z["bucket"] = pd.cut(z.fair_pow, fb, labels=fl, right=False)
    for bk, x in z.groupby("bucket", observed=True):
        d = L.row({"book": book, "no-vig P(side)": bk}, x)
        d["mean fair%"] = round(100 * float(x.fair_pow.mean()), 2)
        d["won%"] = round(100 * float((x.res > 0).mean()), 2)
        d["home share%"] = round(100 * float((x.side == "home").mean()), 1)
        rows.append(d)
print("\n### (iii) Favourite-longshot: moneyline sides at the close by their power-de-vigged probability\n")
print(L.md_table(pd.DataFrame(rows)))
rows = []
for book in ("draftkings", "pinnacle"):
    z = L.sides_long(cb[(cb.market == "h2h") & (cb.bookmaker == book)])
    z["fair_pow"] = np.where(z.side == "home", z.pa_pow, 1 - z.pa_pow)
    z = L.grade(z)
    for side in ("home", "away"):
        for lo, hi, lab in ((0.80, 1.01, "favourite 80%+"), (0.65, 0.80, "favourite 65-80%"), (0.0, 0.20, "underdog <20%")):
            x = z[(z.side == side) & (z.fair_pow >= lo) & (z.fair_pow < hi)]
            d = L.row({"book": book, "side": side, "bucket": lab}, x)
            d["mean fair%"] = round(100 * float(x.fair_pow.mean()), 2) if len(x) else np.nan
            d["won%"] = round(100 * float((x.res > 0).mean()), 2) if len(x) else np.nan
            rows.append(d)
print("\n### (iii) The tails split by home and away\n")
print(L.md_table(pd.DataFrame(rows)))
