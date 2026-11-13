"""Run the baseline and rules R1-R3 of deriv_lab.py and print the tables (also to CACHE/deriv_rules.txt).

    python deriv_rules.py            every table
    python deriv_rules.py base       the baseline only   (base | r1 | r2 | r3)
"""
import io
import sys
from contextlib import redirect_stdout

import numpy as np
import pandas as pd

import deriv_lab as lab
from deriv_lab import BETTABLE, D, LINE_MARKETS, MIN_PRICE, summ

H1 = ["h2h_h1", "spreads_h1", "totals_h1"]
TT = ["team_totals_home", "team_totals_away"]


def tag_sides(L):
    """Who each row backs: the favourite or the underdog of the full-game middle, home or away."""
    L = L.copy()
    team = np.where(L.market == "team_totals_home", "home", np.where(L.market == "team_totals_away", "away", L.side))
    L["team"] = np.where(L.market == "totals_h1", "", team)
    fav_side = np.where(L.fg_spread < 0, "home", np.where(L.fg_spread > 0, "away", ""))
    L["role"] = np.where(L.team == "", "", np.where(fav_side == "", "pick", np.where(L.team == fav_side, "fav", "dog")))
    return L


def show(rows, title):
    print(f"\n== {title}")
    t = pd.DataFrame(rows)
    if t.empty:
        print("(nothing)")
        return t
    print(t.to_string(index=False))
    return t


# ── baseline ─────────────────────────────────────────────────────────────────

def baseline(L):
    b = L[L.bookmaker.isin(BETTABLE) & L.main & L.res.notna()]
    print("\n== the books' margin on these markets (median of both sides' implied chances, minus 1), main lines")
    print(L[L.main].groupby(["market", "bookmaker"]).over_round.median().unstack().round(4).to_string())
    rows = []
    for mk in H1 + TT:
        for slot in ("am", "pm"):
            x = b[(b.market == mk) & (b.slot == slot)]
            rows.append(dict(market=mk, read=slot, **summ(x, "every quote, both sides")))
    show(rows, "BASELINE: every deciding-book main-line quote, both sides")
    rows = []
    for mk in H1 + TT:
        x = b[(b.market == mk) & (b.slot == "am")]
        keys = (["side"] if mk == "totals_h1" else ["side", "role"] if mk in TT else ["role", "team"])
        for k, xx in x.groupby(keys):
            k = k if isinstance(k, tuple) else (k,)
            rows.append(dict(market=mk, split=" ".join(map(str, k)), **summ(xx, "")))
    show(rows, "BASELINE by side, game-day read (who the bet backs)")
    # is the no-vig price calibrated? (moneyline, ties out)
    m = b[(b.market == "h2h_h1") & (b.slot == "am") & (b.res != 0)].copy()
    if len(m):
        m["bin"] = pd.cut(m.p_nv, [0, .2, .35, .45, .55, .65, .8, 1])
        print("\n== first-half moneyline: no-vig chance against how often it won (ties out), game-day read")
        print(m.groupby("bin", observed=True).agg(quotes=("res", "size"), no_vig=("p_nv", "mean"),
                                                  won=("res", lambda s: (s > 0).mean())).round(4).to_string())


# ── R1: same line, better price ──────────────────────────────────────────────

def r1_frame(L):
    key = ["game_id", "slot", "market", "side", "linekey"]
    L = L.copy()
    L["linekey"] = L.line.round(2).fillna(-999.0)
    grp = L.groupby(key).p_nv
    n = grp.transform("size")
    L = L[n >= 3].copy()                     # self plus two others at least
    fair = np.full(len(L), np.nan)
    n_oth = np.zeros(len(L), int)
    pos = {k: v for k, v in L.groupby(key).indices.items()}
    p = L.p_nv.to_numpy()
    for idx in pos.values():
        v = p[idx]
        for j, i in enumerate(idx):
            o = np.delete(v, j)
            fair[i] = np.median(o)
            n_oth[i] = len(o)
    L["fair"], L["n_oth"] = fair, n_oth
    L["edge"] = L.fair - 1 / L.dec
    return L[L.bookmaker.isin(BETTABLE)]


def r1(L):
    F = r1_frame(L)
    rows = []
    for mk in H1 + TT:
        need = 3 if mk == "h2h_h1" else 2
        for slot in ("am", "pm"):
            x = F[(F.market == mk) & (F.slot == slot) & (F.n_oth >= need) & (F.price >= -200)]
            for cut in (0.0, 0.01, 0.02, 0.03, 0.04):
                b = lab.one_per_game(x[x.edge > cut])
                rows.append(dict(market=mk, read=slot, cut=cut, **summ(b, "R1")))
    show(rows, "R1 same line, better price: best quote a game, edge above the cut (no price shorter than -200)")
    rows = []
    for mk in H1 + TT:
        x = F[(F.market == mk) & (F.slot == "am") & (F.n_oth >= (3 if mk == "h2h_h1" else 2)) & (F.price >= -200)]
        b = lab.one_per_game(x[x.edge > 0.02])
        keys = (["side"] if mk == "totals_h1" else ["side", "role"] if mk in TT else ["role", "team"])
        for k, xx in b.groupby(keys):
            k = k if isinstance(k, tuple) else (k,)
            rows.append(dict(market=mk, split=" ".join(map(str, k)), **summ(xx, "")))
        for bk, xx in b.groupby("bookmaker"):
            rows.append(dict(market=mk, split="book " + bk, **summ(xx, "")))
    show(rows, "R1 at the 0.02 cut, game-day read: who it backs and where")
    return F


# ── R1p: the same rule with Pinnacle alone as the fair price ─────────────────

def r1p(L):
    """A deciding book's price against Pinnacle's no-vig chance on the SAME line (the sharp-book form of
    R1). Added 2026-11-11 after R1 found almost no quotes above its cut; same cuts, same price floor."""
    L = L.copy()
    L["linekey"] = L.line.round(2).fillna(-999.0)
    key = ["game_id", "slot", "market", "side", "linekey"]
    pin = L[L.bookmaker == "pinnacle"].drop_duplicates(key)[key + ["p_nv"]].rename(columns={"p_nv": "fair"})
    F = L[L.bookmaker.isin(BETTABLE)].merge(pin, on=key, how="inner")
    F["edge"] = F.fair - 1 / F.dec
    rows = []
    for mk in H1 + TT:
        for slot in ("am", "pm"):
            x = F[(F.market == mk) & (F.slot == slot) & (F.price >= -200)]
            for cut in (0.0, 0.01, 0.02, 0.03):
                rows.append(dict(market=mk, read=slot, cut=cut, **summ(lab.one_per_game(x[x.edge > cut]), "R1p")))
    show(rows, "R1p a deciding book's price against Pinnacle's no-vig chance on the same line")
    rows = []
    for mk in H1 + TT:
        x = F[(F.market == mk) & (F.slot == "am") & (F.price >= -200)]
        b = lab.one_per_game(x[x.edge > 0.01])
        keys = (["side"] if mk == "totals_h1" else ["side", "role"] if mk in TT else ["role", "team"])
        for k, xx in b.groupby(keys):
            k = k if isinstance(k, tuple) else (k,)
            rows.append(dict(market=mk, split=" ".join(map(str, k)), **summ(xx, "")))
    show(rows, "R1p at the 0.01 cut, game-day read: who it backs")
    return F


# ── R2: better line ──────────────────────────────────────────────────────────

def r2_frame(L):
    M = L[L.main & L.market.isin(LINE_MARKETS)].copy()
    # a number that is better for the bettor when higher
    M["adv_line"] = np.where(M.side == "over", -M.line, M.line)
    key = ["game_id", "slot", "market", "side"]
    med = np.full(len(M), np.nan)
    n_oth = np.zeros(len(M), int)
    a = M.adv_line.to_numpy()
    for idx in M.groupby(key).indices.values():
        if len(idx) < 4:
            continue
        v = a[idx]
        for j, i in enumerate(idx):
            o = np.delete(v, j)
            med[i] = np.median(o)
            n_oth[i] = len(o)
    M["others"], M["n_oth"] = med, n_oth
    M["edge"] = M.adv_line - M.others          # points better than the other books' middle
    return M[M.bookmaker.isin(BETTABLE) & M.others.notna()]


def r2(L):
    F = r2_frame(L)
    rows = []
    for mk in LINE_MARKETS:
        for slot in ("am", "pm"):
            x = F[(F.market == mk) & (F.slot == slot) & (F.price >= MIN_PRICE)]
            for k in (0.5, 1.0, 1.5, 2.0):
                b = lab.one_per_game(x[x.edge >= k].assign(edge=lambda z: z.edge + z.dec / 1000))
                rows.append(dict(market=mk, read=slot, pts=k, **summ(b, "R2")))
    show(rows, f"R2 better line: a main line at least k points better than the other books' middle, price {MIN_PRICE} or longer")
    rows = []
    for mk in LINE_MARKETS:
        x = F[(F.market == mk) & (F.slot == "am") & (F.price >= MIN_PRICE)]
        b = lab.one_per_game(x[x.edge >= 1.0].assign(edge=lambda z: z.edge + z.dec / 1000))
        keys = (["side"] if mk == "totals_h1" else ["side", "role"] if mk in TT else ["role", "team"])
        for k, xx in b.groupby(keys):
            k = k if isinstance(k, tuple) else (k,)
            rows.append(dict(market=mk, split=" ".join(map(str, k)), **summ(xx, "")))
        for bk, xx in b.groupby("bookmaker"):
            rows.append(dict(market=mk, split="book " + bk, **summ(xx, "")))
    show(rows, "R2 at 1 point, game-day read: who it backs and where")
    return F


# ── R3: team total against the full game ─────────────────────────────────────

def r3_frame(L):
    T = L[L.market.isin(TT) & L.fg_spread.notna() & L.fg_total.notna() & (L.fg_n >= 4)].copy()
    T["implied"] = np.where(T.market == "team_totals_home", (T.fg_total - T.fg_spread) / 2, (T.fg_total + T.fg_spread) / 2)
    T["dev"] = T.line - T.implied
    T["pts"] = np.where(T.market == "team_totals_home", T.home_score, T.away_score)
    return T


def r3(L):
    T = r3_frame(L)
    m = T[T.main & (T.side == "over") & (T.slot == "am")]
    print("\n== team totals against the full game, game-day read, main lines (points)")
    print(m.groupby("role").agg(quotes=("dev", "size"), line_minus_implied=("dev", "mean"),
                                scored_minus_implied=("pts", lambda s: np.nan),
                                ).drop(columns="scored_minus_implied").round(3).to_string())
    one = m.drop_duplicates(["canon", "market"])
    print(one.assign(a=one.pts - one.implied, b=one.pts - one.line).groupby("role").agg(
        teams=("a", "size"), scored_minus_implied=("a", "mean"), scored_minus_line=("b", "mean"),
        went_over=("b", lambda s: (s > 0).sum() / max((s != 0).sum(), 1))).round(3).to_string())
    B = T[T.bookmaker.isin(BETTABLE) & (T.price >= MIN_PRICE)]
    rows = []
    for slot in ("am", "pm"):
        for k in (0.5, 1.0, 1.5, 2.0, 2.5):
            for side, sel in (("over", (B.side == "over") & (B.dev <= -k)), ("under", (B.side == "under") & (B.dev >= k))):
                x = B[sel & (B.slot == slot)].assign(edge=lambda z: z.dev.abs() + z.dec / 1000)
                b = lab.one_per_game(x)
                rows.append(dict(read=slot, pts=k, side=side, **summ(b, "R3")))
    show(rows, f"R3 team total at least k points off (total -/+ spread)/2, price {MIN_PRICE} or longer")
    rows = []
    x = B[(B.slot == "am")]
    for side, sel in (("over", (x.side == "over") & (x.dev <= -1.0)), ("under", (x.side == "under") & (x.dev >= 1.0))):
        b = lab.one_per_game(x[sel].assign(edge=lambda z: z.dev.abs() + z.dec / 1000))
        for k, xx in b.groupby(["role", "team"]):
            rows.append(dict(side=side, split=" ".join(k), **summ(xx, "")))
        for bk, xx in b.groupby("bookmaker"):
            rows.append(dict(side=side, split="book " + bk, **summ(xx, "")))
    show(rows, "R3 at 1 point, game-day read: who it backs and where")
    return T


def main():
    which = sys.argv[1:] or ["base", "r1", "r2", "r3"]
    buf = io.StringIO()

    class Tee:
        def write(self, s):
            sys.__stdout__.write(s)
            buf.write(s)

        def flush(self):
            sys.__stdout__.flush()

    with redirect_stdout(Tee()):
        L = tag_sides(lab.load())
        if "base" in which:
            baseline(L)
        if "r1" in which:
            r1(L)
        if "r1p" in which:
            r1p(L)
        if "r2" in which:
            r2(L)
        if "r3" in which:
            r3(L)
    (D / f"deriv_rules_{'_'.join(which)}.txt").write_text(buf.getvalue(), encoding="utf-8")


if __name__ == "__main__":
    main()
