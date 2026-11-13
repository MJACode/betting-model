"""Round 1, task 2: blind baselines on the six first-half / first-quarter
markets. Per market, season and decision (T-10 close; each game's earliest
stored mark): home / away / favourite / underdog (spreads, moneylines) and
over / under (totals), at each book's own quoted number and price, and at the
best decidable price on the modal decidable number (the repo's same-line rule).

Offshore books (betus, gtbets, mybookieag) are REFERENCE ONLY: never a book a
pick may name. Off-centre "mains" are set aside (r1_lib header).

    python scripts/euroleague_research/r1_baselines.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import r1_lib as L  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 2000)

g = L.load_games()
Q = L.load_main_quotes(g)
Q = Q[~Q.offc]


def sides_for(market):
    if market.startswith("totals"):
        return ["over", "under"]
    return ["home", "away", "fav", "dog"]


def assign(x: pd.DataFrame, market: str, side: str, fav_home=None) -> pd.DataFrame:
    """Rows with side and price set; fav/dog rows drop a pick'em."""
    x = x.copy()
    if side in ("home", "over"):
        x["side"], x["price"] = side, x.pa
    elif side in ("away", "under"):
        x["side"], x["price"] = side, x.pb
    else:
        fh = fav_home if fav_home is not None else (
            x.line < 0 if market.startswith("spreads") else x.pa_fair > 0.5)
        pk = (x.line == 0) if market.startswith("spreads") else np.isclose(x.pa_fair, 0.5)
        if fav_home is not None:
            pk = x["pk"]
        home = fh if side == "fav" else ~fh
        x["side"] = np.where(home, "home", "away")
        x["price"] = np.where(home, x.pa, x.pb)
        x = x[~pk]
    return x


def at_decision(x: pd.DataFrame, decision: str) -> pd.DataFrame:
    """x for one book: the T-10 row, or each game's earliest stored mark."""
    if decision == "T-10":
        return x[x.mark == "T-10"]
    return x.sort_values("mark_min", ascending=False).drop_duplicates("game_id")


def best_decidable(x: pd.DataFrame, market: str, decision: str) -> pd.DataFrame:
    """One row per game with the best decidable price per side on the modal
    decidable number at the decision mark (earliest: the earliest mark any
    decidable book quoted). Columns pa / pb are the best prices; line the
    modal number; fav_home / pk the consensus favourite."""
    x = x[x.decidable]
    if decision == "T-10":
        x = x[x.mark == "T-10"]
    else:
        first = x.groupby("game_id").mark_min.max().rename("first")
        x = x.join(first, on="game_id")
        x = x[x.mark_min == x["first"]]
    rows = []
    for gid, y in x.groupby("game_id"):
        base = y.iloc[0]
        if market.startswith("h2h"):
            line = np.nan
            yy = y
            fair = y.pa_fair.mean()
            fav_home, pk = fair > 0.5, np.isclose(fair, 0.5)
        else:
            vc = y.line.value_counts()
            top = vc[vc == vc.max()].index.to_numpy(float)
            med = y.line.median()
            line = sorted(top, key=lambda v: (abs(v - med), v))[0]
            yy = y[y.line == line]
            fav_home, pk = (line < 0, line == 0) if market.startswith("spreads") else (False, False)
        ia, ib = yy.pa.idxmax(), yy.pb.idxmax()   # higher American price = better for the bettor
        rows.append({"game_id": gid, "game_date": base.game_date, "season": base.season,
                     "margin": base.margin, "total": base.total, "line": line,
                     "pa": yy.pa.max(), "pb": yy.pb.max(), "book_a": yy.loc[ia, "bookmaker"],
                     "book_b": yy.loc[ib, "bookmaker"], "nbooks": yy.bookmaker.nunique(),
                     "fav_home": fav_home, "pk": pk, "pa_fair": np.nan})
    return pd.DataFrame(rows)


out = []
bands = []
for m in L.MARKETS:
    xm = Q[Q.market == m]
    for season in sorted(xm.season.unique()):
        xs = xm[xm.season == season]
        for decision in ["T-10", "earliest"]:
            books = [b for b in L.DECIDABLE + L.OFFSHORE if b in set(xs.bookmaker)]
            for b in books:
                xb = at_decision(xs[xs.bookmaker == b], decision)
                for side in sides_for(m):
                    r = L.grade_rows(assign(xb, m, side), m)
                    s = L.summary(r)
                    out.append({"market": m, "season": season, "decision": decision,
                                "book": b + ("" if b in L.DECIDABLE else " (ref)"), "side": side, **s})
            if xs.decidable.any():
                bd = best_decidable(xs, m, decision)
                for side in sides_for(m):
                    a = bd.copy()
                    if side in ("fav", "dog"):
                        a = assign(a, m, side, fav_home=a.fav_home.astype(bool))
                    else:
                        a = assign(a, m, side)
                    r = L.grade_rows(a, m)
                    s = L.summary(r)
                    out.append({"market": m, "season": season, "decision": decision,
                                "book": "BEST decidable", "side": side, **s})
                    if m.startswith("h2h") and decision == "T-10" and side in ("fav", "dog"):
                        r["band"] = pd.cut(r.price, [-5000, -300, -200, -150, -100, 100, 150, 200, 300, 5000])
                        for bnd, rb in r.groupby("band", observed=True):
                            bands.append({"market": m, "season": season, "side": side, "band": str(bnd),
                                          **L.summary(rb)})

res = pd.DataFrame(out)
res = res[res.bets > 0]
res["bh10"] = False
pos = (res["ret%"] > 0) & (res.bets >= 25)      # the repo's 25-settled-pick floor for a cell
res.loc[pos, "bh10"] = L.bh(res.loc[pos, "p_le0"].to_numpy(), 0.10)
cols = ["market", "season", "decision", "book", "side", "bets", "W", "L", "P", "units", "ret%", "lo%", "hi%", "u/bet"]
print(f"cells printed: {len(res)}; with 25+ bets: {int((res.bets >= 25).sum())}; positive with 25+ bets: "
      f"{int(pos.sum())}; surviving Benjamini-Hochberg at FDR 10% (one-sided bootstrap p): {int(res.bh10.sum())}")
print(res[res.bh10][cols].to_string(index=False))
print("positive cells with 25+ bets whose 90% interval is above zero:")
print(res[pos & (res['lo%'] > 0)][cols].to_string(index=False))
for m in L.MARKETS:
    print(f"\n==== {m} ====")
    print(res[res.market == m][cols].to_string(index=False))

print("\n==== pooled over seasons: BEST decidable (2025-26 + 2026-27) and offshore reference (every season) ====")
pool = []
for m in L.MARKETS:
    xm = Q[Q.market == m]
    for decision in ["T-10", "earliest"]:
        if xm.decidable.any():
            bd = pd.concat([best_decidable(xm[xm.season == s], m, decision) for s in sorted(xm[xm.decidable].season.unique())])
            for side in sides_for(m):
                a = assign(bd, m, side, fav_home=bd.fav_home.astype(bool)) if side in ("fav", "dog") else assign(bd, m, side)
                pool.append({"market": m, "decision": decision, "book": "BEST decidable", "side": side,
                             **L.summary(L.grade_rows(a, m))})
        for b in L.OFFSHORE:
            xb = xm[xm.bookmaker == b]
            if not len(xb):
                continue
            xb = pd.concat([at_decision(xb[xb.season == s], decision) for s in sorted(xb.season.unique())])
            for side in sides_for(m):
                pool.append({"market": m, "decision": decision, "book": b + " (ref)", "side": side,
                             **L.summary(L.grade_rows(assign(xb, m, side), m))})
pool = pd.DataFrame(pool)
print(pool[["market", "decision", "book", "side", "bets", "W", "L", "P", "units", "ret%", "lo%", "hi%"]].to_string(index=False))

print("\n==== moneyline favourite / underdog at the best decidable price, T-10, by price band ====")
bd = pd.DataFrame(bands)
print(bd[["market", "season", "side", "band", "bets", "W", "L", "P", "units", "ret%", "lo%", "hi%"]].to_string(index=False))

top = res[res.bets >= 100].sort_values("ret%")
print("\n==== the five best and five worst cells with 100+ bets ====")
print(pd.concat([top.tail(5), top.head(5)])[cols + ["bh10"]].to_string(index=False))
