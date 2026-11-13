"""Full-game round 1, step 3: methods (a), (b), (d), run unchanged. Prints markdown.

All settings are frozen in r2_lib's docstring. In brief:

(a) LINE SHOPPING against the books' own median (spreads; totals with the same
    kernel). At the read, every book's standing line; a line on the other side
    of zero from the median of the other books is a sign error and is dropped
    (2+ others; with one other it is ambiguous and dropped too); consensus =
    median of the remaining lines; mean = -consensus + c (spreads) or
    consensus + c (totals); each DECIDABLE quote priced through the margin
    table at its own line; a quote's side is the one with the larger edge;
    bet the game's single best quote when its edge > cut and >= 3 other books
    are in the consensus. Variants: consensus over all ten books (main) and
    over the decidable books only (the catalogued one; can bet only from
    2025-26).
(b) A BOOK'S MONEYLINE AGAINST ITS OWN SPREAD. Each decidable book's
    moneyline and its own spread at the read; the spread power de-vigged to
    P(home covers | no push), the margin table inverted to the mean that gives
    it, P(home win) at that mean; flagged moneylines out (implied sum outside
    1.00-1.15; a favourite no other book shares, 2+ others among the decidable
    books, Pinnacle and Bovada; the own spread of 1.5+ naming the other team);
    sides shorter than -200 removed before the pick; bet the game's largest
    edge (P - implied incl. vig) above the cut. Ties: the longer price, then
    the book's name.
(d) SHARP AGAINST SOFT AT ONE SNAPSHOT. At the read, Pinnacle's standing
    quote and each decidable book's standing quote at the SAME line (or the
    moneyline); edge = Pinnacle no-vig P(side) - implied of the soft price;
    the game's largest edge per market above the cut; moneyline sides shorter
    than -200 removed first.

Walk-forward: the margin tables and c are fitted on every season before the
one priced (first priced season 2022-23 on a one-season table, flagged; the
headline pools 2023-24 on). CLV column: P(side) from Pinnacle's no-vig close
at the bet's own line (spreads / totals through the margin table) minus the
bet price's implied probability; beat% = share of bets where that is > 0.
"""
import numpy as np
import pandas as pd
import r2_lib as L
from models import ncaab_margin_dist as md

TOT0 = 160
READS = ["15utc", "6h", "60m", "close"]
A_CUTS = [0.00, 0.01, 0.02, 0.03, 0.04, 0.05]
B_CUTS = [0.000, 0.005, 0.010, 0.015, 0.020, 0.025, 0.030]
D_CUTS = [0.00, 0.01, 0.02, 0.03, 0.04]
SEASONS = [2023, 2024, 2025, 2026, 2027]

g = L.load_games()
g = g[g.played].copy()
q = L.load_quotes(games=g)
q = q[q.played].copy()
dt = L.decision_times(g)
boards = {r: L.board_at(q, dt[r].dropna()) for r in READS}


def sign_flag(b):
    """b: one market's board (spreads). Adds flag ok / artefact / ambiguous."""
    b = b.copy()
    flag = np.array(["ok"] * len(b), dtype=object)
    lines = b.line.to_numpy(float)
    for _, idx in b.groupby("game_id", sort=False).indices.items():
        v = lines[idx]
        for j, k in enumerate(idx):
            o = np.delete(v, j)
            if len(o):
                m = np.median(o)
                if v[j] * m < 0:
                    flag[k] = "artefact" if len(o) >= 2 else "ambiguous"
    b["flag"] = flag
    return b


def consensus(b, books):
    """Median of the ok lines of `books` per game, and their count."""
    x = b[(b.flag == "ok") & b.bookmaker.isin(books)]
    return x.groupby("game_id").line.median().rename("cons"), x.groupby("game_id").line.size().rename("n_ok")


# ── the training pieces, per priced season ───────────────────────────────────
cb = boards["close"]
sp_c = sign_flag(cb[cb.market == "spreads"])
to_c = cb[cb.market == "totals"].assign(flag="ok")
cons_sp_close = consensus(sp_c, L.ALLBOOKS)[0]
cons_to_close = consensus(to_c, L.ALLBOOKS)[0]
b15 = boards["15utc"]
cons_sp_15 = consensus(sign_flag(b15[b15.market == "spreads"]), L.ALLBOOKS)[0]
cons_to_15 = consensus(b15[b15.market == "totals"].assign(flag="ok"), L.ALLBOOKS)[0]
gg = g.set_index("game_id").sort_values(["game_date"]).copy()
gg["cons_sp_close"] = cons_sp_close
gg["cons_to_close"] = cons_to_close
gg["cons_sp_15"] = cons_sp_15
gg["cons_to_15"] = cons_to_15
gg = gg.reset_index().sort_values(["game_date", "game_id"], kind="mergesort")

TABLES = {}
fit_rows = []
for s in SEASONS:
    tr = gg[(gg.season < s)]
    a = tr.dropna(subset=["cons_sp_close"])
    Tsp = md.fit(a.margin.astype(int).values, -a.cons_sp_close.values)
    b = tr.dropna(subset=["cons_to_close"])
    Tto = md.fit((b.total - TOT0).astype(int).values, (b.cons_to_close - TOT0).values)
    c1 = tr.dropna(subset=["cons_sp_15"])
    c_sp = float((c1.margin + c1.cons_sp_15).mean())
    c2 = tr.dropna(subset=["cons_to_15"])
    c_to = float((c2.total - c2.cons_to_15).mean())
    TABLES[s] = {"sp": Tsp, "to": Tto, "c_sp": c_sp, "c_to": c_to}
    # bandwidth at the central grid rows
    ctr = [np.argmin(np.abs(md.GRID - v)) for v in (-10, -5, 0, 5, 10)]
    fit_rows.append({"priced season": s, "train games (spread)": len(a), "train games (total)": len(b),
                     "c_sp (pts)": round(c_sp, 3), "c_to (pts)": round(c_to, 3),
                     "spread h at mean -10/-5/0/+5/+10": "/".join(f"{Tsp['h'][i]:.2f}" for i in ctr),
                     "total h at 150/155/160/165/170": "/".join(f"{Tto['h'][i]:.2f}" for i in ctr),
                     "spread neff at 0": round(float(Tsp["neff"][ctr[2]]), 0)})


def season_of(gid):
    return gseason[gid]


gseason = g.set_index("game_id").season.to_dict()


def p_cover(mu, line, T, kind):
    """P(side a wins | no push) at the quote's line: home covers (spreads) or over (totals)."""
    if kind == "sp":
        pw, pp, pl = md.probs(mu, -np.asarray(line, float), T)
    else:
        pw, pp, pl = md.probs(np.asarray(mu, float) - TOT0, np.asarray(line, float) - TOT0, T)
    with np.errstate(invalid="ignore", divide="ignore"):
        return pw / (pw + pl)


# ── Pinnacle's close as a mean, for CLV ──────────────────────────────────────
pin_c = cb[cb.bookmaker == "pinnacle"].set_index(["game_id", "market"])


def clv(bets):
    """P(side) at the bet's line from Pinnacle's no-vig close, minus the bet's implied."""
    out = np.full(len(bets), np.nan)
    for i, r in enumerate(bets.itertuples()):
        key = (r.game_id, r.market)
        if key not in pin_c.index:
            continue
        p = pin_c.loc[key]
        s = gseason[r.game_id]
        if r.market == "h2h":
            pa = p.pa_pow
        else:
            T = TABLES[s]["sp" if r.market == "spreads" else "to"]
            kind = "sp" if r.market == "spreads" else "to"
            pc = p.pa_mult
            if p.line == r.line:
                pa = pc
            else:
                if kind == "sp":
                    mu = md.mean_for_cover(np.array([pc]), np.array([-p.line]), T)[0]
                    pa = p_cover(mu, r.line, T, "sp")
                else:
                    mu = md.mean_for_cover(np.array([pc]), np.array([p.line - TOT0]), T)[0] + TOT0
                    pa = p_cover(mu, r.line, T, "to")
                pa = float(np.asarray(pa).ravel()[0])
        ps = pa if r.side in ("home", "over") else 1 - pa
        out[i] = ps - float(L.imp(r.price))
    return out


def summarize(bets, label):
    r = L.row(label, bets)
    if len(bets):
        c = bets["clv"]
        r["clv_mean"] = round(float(np.nanmean(c)), 4) if np.isfinite(c).any() else np.nan
        r["beat%"] = round(100 * float(np.nanmean(c > 0)), 1) if np.isfinite(c).any() else np.nan
    return r


# ── (a) line shopping ────────────────────────────────────────────────────────

def method_a(read, market, cons_books):
    b = boards[read]
    b = b[b.market == market]
    b = sign_flag(b) if market == "spreads" else b.assign(flag="ok")
    cons, n_ok = consensus(b, cons_books)
    z = b[(b.flag == "ok") & b.bookmaker.isin(L.DECIDABLE)].copy()
    z["cons"] = z.game_id.map(cons)
    z["n_ok"] = z.game_id.map(n_ok).fillna(0)
    z["in_cons"] = z.bookmaker.isin(cons_books)
    z["others"] = z.n_ok - z.in_cons.astype(int)
    z = z[z.cons.notna() & (z.season >= SEASONS[0])]
    out = []
    for s, x in z.groupby("season"):
        T = TABLES[s]
        if market == "spreads":
            mu = -x.cons + T["c_sp"]
            pa = p_cover(mu, x.line, T["sp"], "sp")
        else:
            mu = x.cons + T["c_to"]
            pa = p_cover(mu, x.line, T["to"], "to")
        x = x.assign(pa_model=np.asarray(pa, float))
        out.append(x)
    z = pd.concat(out)
    ea = z.pa_model - L.imp(z.pa)
    eb = (1 - z.pa_model) - L.imp(z.pb)
    a_side = "home" if market == "spreads" else "over"
    b_side = "away" if market == "spreads" else "under"
    z["side"] = np.where(ea >= eb, a_side, b_side)
    z["price"] = np.where(ea >= eb, z.pa, z.pb)
    z["edge"] = np.maximum(ea, eb)
    # tie-breaks: edge, better line for the side, better price, name
    z["line_good"] = np.where(z.side.isin(["home", "under"]), z.line, -z.line)
    z["dz"] = L.dec(z.price)
    z = z[z.others >= 3]
    z = z.sort_values(["game_id", "edge", "line_good", "dz", "bookmaker"],
                      ascending=[True, False, False, False, True])
    return z.drop_duplicates("game_id", keep="first")


# ── (b) moneyline against the same book's own spread ─────────────────────────

def method_b(read, floor=-200):
    b = boards[read]
    ml = b[(b.market == "h2h") & b.bookmaker.isin(L.DECIDABLE + ["pinnacle", "bovada"])].copy()
    sp = sign_flag(b[(b.market == "spreads") & b.bookmaker.isin(L.DECIDABLE)])
    ml["fav"] = np.sign(ml.pa_pow - 0.5)
    # favourite alone: 2+ other books, every one with the other favourite
    fa = np.zeros(len(ml), bool)
    favs = ml.fav.to_numpy()
    for _, idx in ml.groupby("game_id", sort=False).indices.items():
        for j, k in enumerate(idx):
            o = np.delete(favs[idx], j)
            if len(o) >= 2 and favs[k] != 0 and np.all(o == -favs[k]):
                fa[k] = True
    ml["fav_alone"] = fa
    own = sp[sp.flag == "ok"][["game_id", "bookmaker", "line", "pa", "pb"]].rename(
        columns={"line": "own_line", "pa": "spa", "pb": "spb"})
    h = ml[ml.bookmaker.isin(L.DECIDABLE)].merge(own, on=["game_id", "bookmaker"], how="inner")
    h["disagree"] = (h.own_line.abs() >= 1.5) & (-np.sign(h.own_line) != h.fav) & (h.fav != 0)
    h = h[~h.fav_alone & ~h.disagree & (h.season >= SEASONS[0])]
    out = []
    for s, x in h.groupby("season"):
        T = TABLES[s]["sp"]
        pcov = L.power_fair(L.imp(x.spa), L.imp(x.spb))[0]
        mu = md.mean_for_cover(pcov, -x.own_line.to_numpy(float), T)
        pw, pp, pl = md.probs(mu, np.zeros(len(x)), T)
        out.append(x.assign(ph=pw / (pw + pl)))
    h = pd.concat(out)
    sides = []
    for side, pc in (("home", "pa"), ("away", "pb")):
        z = h.copy()
        z["side"] = side
        z["price"] = z[pc]
        z["prob"] = z.ph if side == "home" else 1 - z.ph
        z["edge"] = z.prob - L.imp(z.price)
        sides.append(z)
    z = pd.concat(sides)
    if floor is not None:
        z = z[z.price >= floor]
    z["dz"] = L.dec(z.price)
    z = z.sort_values(["game_id", "edge", "dz", "bookmaker"], ascending=[True, False, False, True])
    z = z.drop_duplicates("game_id", keep="first")
    z["line"] = np.nan
    return z


# ── (d) sharp against soft at one snapshot ───────────────────────────────────

def method_d(read, market, floor=-200):
    b = boards[read]
    b = b[b.market == market]
    pin = b[b.bookmaker == "pinnacle"][["game_id", "line", "pa_pow", "pa_mult"]].rename(
        columns={"line": "pline", "pa_pow": "ppow", "pa_mult": "pmult"})
    z = b[b.bookmaker.isin(L.DECIDABLE) & (b.season >= SEASONS[0])].merge(pin, on="game_id", how="inner")
    if market != "h2h":
        z = z[z.line == z.pline]
    fair = z.ppow if market == "h2h" else z.pmult
    a_side, b_side = {"h2h": ("home", "away"), "spreads": ("home", "away"), "totals": ("over", "under")}[market]
    za = z.assign(side=a_side, price=z.pa, edge=fair - L.imp(z.pa))
    zb = z.assign(side=b_side, price=z.pb, edge=(1 - fair) - L.imp(z.pb))
    z = pd.concat([za, zb])
    if market == "h2h" and floor is not None:
        z = z[z.price >= floor]
    z["dz"] = L.dec(z.price)
    z = z.sort_values(["game_id", "edge", "dz", "bookmaker"], ascending=[True, False, False, True])
    return z.drop_duplicates("game_id", keep="first")


def run(cands, cuts, labels, main_cut):
    """cands: dict read -> candidate frame (one row a game). Grid by read x cut,
    pooled 2023-24 on (and 2022-23 flagged), then the main cut by season."""
    rows, srows = [], []
    for read, z in cands.items():
        z = L.grade(z)
        z["clv"] = clv(z)
        for cut in cuts:
            x = z[z.edge > cut]
            rows.append(summarize(x[x.season >= 2024], dict(labels, read=read, cut=cut, seasons="2023-24 on")))
            rows.append(summarize(x[x.season == 2023], dict(labels, read=read, cut=cut, seasons="2022-23 (1-season table)")))
            if cut == main_cut:
                for s, xs in x.groupby("season"):
                    srows.append(summarize(xs, dict(labels, read=read, cut=cut, seasons=int(s))))
    return pd.DataFrame(rows), pd.DataFrame(srows)


def main():
    print("## r2_methods.py\n")
    print("### The walk-forward tables\n")
    print(L.md_table(pd.DataFrame(fit_rows)))

    for market in ("spreads", "totals"):
        for variant, books in (("all ten books", L.ALLBOOKS), ("decidable only (catalogued)", L.DECIDABLE)):
            c = {r: method_a(r, market, books) for r in READS}
            t, s = run(c, A_CUTS, {"method": "(a) line shopping", "market": market, "consensus": variant}, 0.03)
            print(f"\n### (a) line shopping, {market}, consensus over {variant}: read x cut\n")
            print(L.md_table(t))
            print(f"\n### (a) line shopping, {market}, consensus over {variant}: cut 0.03 by season\n")
            print(L.md_table(s))

    for floor in (-200, None):
        c = {r: method_b(r, floor=floor) for r in READS}
        lab = "-200 floor" if floor else "no floor"
        t, s = run(c, B_CUTS, {"method": "(b) moneyline vs own spread", "floor": lab}, 0.01)
        print(f"\n### (b) moneyline against the same book's spread, {lab}: read x cut\n")
        print(L.md_table(t))
        print(f"\n### (b) {lab}: cut 0.01 by season\n")
        print(L.md_table(s))
        if floor is None:
            z = L.grade(c["15utc"])
            z = z[(z.edge > 0.01) & (z.season >= 2024)].copy()
            z["band"] = L.ml_band(z.price)
            z["clv"] = clv(z)
            bt = pd.DataFrame([summarize(z[z.band == bd], {"band": bd}) for bd in L.BANDS])
            print("\n### (b) no floor, 15utc, cut 0.01, 2023-24 on: by price band\n")
            print(L.md_table(bt))

    for market in ("h2h", "spreads", "totals"):
        c = {r: method_d(r, market) for r in READS}
        t, s = run(c, D_CUTS, {"method": "(d) sharp vs soft", "market": market}, 0.01)
        print(f"\n### (d) sharp vs soft, {market}: read x cut\n")
        print(L.md_table(t))
        print(f"\n### (d) {market}: cut 0.01 by season\n")
        print(L.md_table(s))


if __name__ == "__main__":
    main()
