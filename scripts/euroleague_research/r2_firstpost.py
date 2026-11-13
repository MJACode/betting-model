"""Full-game round 1, step 3c: the first post. Prints markdown.

(c) As briefed: the moment a DECIDABLE book first posts a market on a game
    (the ledger snapshot that captured its first row), with Pinnacle's
    standing coherent quote at that moment as the reference (de-vigged: power
    for h2h, multiplicative at the SAME line for spreads and totals) and at
    least 3 other books (any of the other nine, Pinnacle included) standing.
    Bet the posting book's side when Pinnacle's no-vig P(side) minus the
    side's implied (vig included) is above the cut; moneyline sides shorter
    than -200 removed first. Posts are taken in time order per game and
    market; the first post that bets closes that game's market (one bet a
    game a market). Cuts 0.000-0.030 step 0.005, catalogued 0.015.
(c2) The catalogued first-post card: the posting book's new MONEYLINE priced
    off its OWN spread standing at that moment (r2_methods.method_b's pricing,
    the same walk-forward margin table), >= 3 OTHER DECIDABLE books with a
    moneyline standing (possible only from 2025-26), cut 0.015; and a variant
    counting any of the other nine books.

First the condition counts, per season and book: how many first posts have
Pinnacle standing, at the same line, and >= 3 other books up.
"""
import numpy as np
import pandas as pd
import r2_lib as L
import r2_methods as M
from models import ncaab_margin_dist as md

q = M.q.copy()
q["seen"] = L.seen_at(q.snapshot_at)
fp = L.first_posts(q)
fpd = fp[fp.bookmaker.isin(L.DECIDABLE) & (fp.season >= 2023)].copy()
CUTS = [0.000, 0.005, 0.010, 0.015, 0.020, 0.025, 0.030]


def standing_at(q, keys):
    """keys: game_id, market, Tf, post_id. Every other book's standing row at Tf."""
    z = q.merge(keys, on=["game_id", "market"], how="inner")
    z = z[z.snapshot_at <= z.Tf]
    return z.drop_duplicates(["post_id", "bookmaker"], keep="last")


fpd = fpd.reset_index(drop=True)
fpd["post_id"] = np.arange(len(fpd))
fpd["Tf"] = fpd.seen
keys = fpd[["game_id", "market", "Tf", "post_id", "bookmaker"]].rename(columns={"bookmaker": "poster"})
st = standing_at(q, keys)
st = st[st.bookmaker != st.poster]
n_other = st.groupby("post_id").size()
n_other_dec = st[st.bookmaker.isin(L.DECIDABLE)].groupby("post_id").size()
pin = st[st.bookmaker == "pinnacle"].set_index("post_id")
fpd["n_other"] = fpd.post_id.map(n_other).fillna(0).astype(int)
fpd["n_other_dec"] = fpd.post_id.map(n_other_dec).fillna(0).astype(int)
fpd["pin_up"] = fpd.post_id.isin(pin.index)
fpd["pin_line"] = fpd.post_id.map(pin.line)
fpd["pin_pow"] = fpd.post_id.map(pin.pa_pow)
fpd["pin_mult"] = fpd.post_id.map(pin.pa_mult)
fpd["same_line"] = np.where(fpd.market == "h2h", fpd.pin_up, fpd.pin_up & (fpd.line == fpd.pin_line))
fpd["cond"] = fpd.same_line & (fpd.n_other >= 3)

print("## r2_firstpost.py\n")
print("### The condition: decidable first posts, 2022-23 on, with Pinnacle standing at that moment\n")
t = fpd.groupby(["season", "market", "bookmaker"]).agg(
    first_posts=("post_id", "size"), pinnacle_up=("pin_up", "sum"), same_line=("same_line", "sum"),
    with_3_others=("cond", "sum"), median_others=("n_other", "median")).reset_index()
print(L.md_table(t))

# (c) the bet
fair = np.where(fpd.market == "h2h", fpd.pin_pow, fpd.pin_mult)
a_side = np.where(fpd.market == "totals", "over", "home")
b_side = np.where(fpd.market == "totals", "under", "away")
ea = fair - L.imp(fpd.pa)
eb = (1 - fair) - L.imp(fpd.pb)
sa = fpd.assign(side=a_side, price=fpd.pa, edge=ea)
sb = fpd.assign(side=b_side, price=fpd.pb, edge=eb)
s = pd.concat([sa, sb])
s = s[s.cond]
s = s[~((s.market == "h2h") & (s.price < -200))]
s["dz"] = L.dec(s.price)
s = s.sort_values(["post_id", "edge", "dz"], ascending=[True, False, False]).drop_duplicates("post_id")


def first_bet(s, cut):
    x = s[s.edge > cut].sort_values(["game_id", "market", "Tf", "edge", "bookmaker"],
                                    ascending=[True, True, True, False, True])
    return x.drop_duplicates(["game_id", "market"], keep="first")


rows, srows = [], []
for market in L.MARKETS:
    for cut in CUTS:
        x = L.grade(first_bet(s[s.market == market], cut))
        x["clv"] = M.clv(x) if len(x) else []
        rows.append(M.summarize(x, {"method": "(c) first post, Pinnacle reference", "market": market, "cut": cut}))
        if cut == 0.015:
            for season, xs in x.groupby("season"):
                srows.append(M.summarize(xs, {"market": market, "cut": cut, "season": int(season)}))
            if len(x):
                print(f"\n(c) {market} cut 0.015: bets by book {x.bookmaker.value_counts().to_dict()}, "
                      f"by side {x.side.value_counts().to_dict()}, median hours before tip "
                      f"{round(float(((x.tip - x.Tf).dt.total_seconds() / 3600).median()), 1)}")
print("\n### (c) first post against Pinnacle: cut grid, 2022-23 on\n")
print(L.md_table(pd.DataFrame(rows)))
print("\n### (c) cut 0.015 by season\n")
print(L.md_table(pd.DataFrame(srows)))

# (c2) own spread at the first moneyline post
ml = fpd[fpd.market == "h2h"].copy()
sp = q[q.market == "spreads"]
k2 = ml[["game_id", "post_id", "bookmaker", "Tf"]].assign(market="spreads")
own = sp.merge(k2, on=["game_id", "market", "bookmaker"], how="inner")
own = own[own.snapshot_at <= own.Tf].drop_duplicates("post_id", keep="last").set_index("post_id")
ml["own_line"] = ml.post_id.map(own.line)
ml["spa"] = ml.post_id.map(own.pa)
ml["spb"] = ml.post_id.map(own.pb)
# other books' moneyline favourites at the moment, for the favourite-alone flag
st_ml = st[(st.market == "h2h") & st.bookmaker.isin(L.DECIDABLE + ["pinnacle", "bovada"])]
ml = ml[ml.own_line.notna()].copy()
ml["fav"] = np.sign(ml.pa_pow - 0.5)
of = st_ml.assign(ofav=np.sign(st_ml.pa_pow - 0.5)).groupby("post_id").ofav.agg(list)
ml["fav_alone"] = [len(of.get(p, [])) >= 2 and f != 0 and all(o == -f for o in of.get(p, []))
                   for p, f in zip(ml.post_id, ml.fav)]
ml["disagree"] = (ml.own_line.abs() >= 1.5) & (-np.sign(ml.own_line) != ml.fav) & (ml.fav != 0)
n_ml_dec = st[(st.market == "h2h") & st.bookmaker.isin(L.DECIDABLE)].groupby("post_id").size()
n_ml_any = st[(st.market == "h2h")].groupby("post_id").size()
ml["n_ml_dec"] = ml.post_id.map(n_ml_dec).fillna(0).astype(int)
ml["n_ml_any"] = ml.post_id.map(n_ml_any).fillna(0).astype(int)
ml = ml[~ml.fav_alone & ~ml.disagree]
parts = []
for season, x in ml.groupby("season"):
    T = M.TABLES[season]["sp"]
    pcov = L.power_fair(L.imp(x.spa), L.imp(x.spb))[0]
    mu = md.mean_for_cover(pcov, -x.own_line.to_numpy(float), T)
    pw, pp, pl = md.probs(mu, np.zeros(len(x)), T)
    parts.append(x.assign(ph=pw / (pw + pl)))
ml = pd.concat(parts)
sd = []
for side, pc in (("home", "pa"), ("away", "pb")):
    z = ml.assign(side=side, price=ml[pc])
    z["edge"] = (z.ph if side == "home" else 1 - z.ph) - L.imp(z.price)
    sd.append(z)
s2 = pd.concat(sd)
s2 = s2[s2.price >= -200]
s2["dz"] = L.dec(s2.price)
s2 = s2.sort_values(["post_id", "edge", "dz"], ascending=[True, False, False]).drop_duplicates("post_id")
rows = []
print("\n### (c2) the catalogued first-post card (moneyline off its own spread): condition counts\n")
print(L.md_table(ml.groupby("season").agg(posts=("post_id", "size"), three_other_decidable=("n_ml_dec", lambda v: int((v >= 3).sum())),
                                          three_other_any=("n_ml_any", lambda v: int((v >= 3).sum()))).reset_index()))
for variant, col in (("3 other decidable books", "n_ml_dec"), ("3 other books of any kind", "n_ml_any")):
    for cut in CUTS:
        x = s2[s2[col] >= 3]
        x = L.grade(first_bet(x, cut))
        x["clv"] = M.clv(x) if len(x) else []
        rows.append(M.summarize(x, {"method": "(c2) first post, own spread", "others": variant, "cut": cut}))
        if cut == 0.015:
            for season, xs in x.groupby("season"):
                rows.append(M.summarize(xs, {"method": "(c2) by season", "others": variant, "cut": cut, "season": int(season)}))
print("\n### (c2) results\n")
print(L.md_table(pd.DataFrame(rows)))
