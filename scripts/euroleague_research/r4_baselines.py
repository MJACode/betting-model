"""Round 4, experiment 2: blind baselines at halftime.

(a) At each book's first read in the break holding a FRESH quote from it:
    totals over / under; spreads home / away / favourite / underdog (the side
    giving points at the half); moneyline home / away / favourite / underdog
    (by price). All ten books; reference books are marked not bettable.
(b) At the best decidable price at the first read holding any fresh
    decidable quote: best number first, then best price.
No price band. Every cell is registered for Benjamini-Hochberg."""
from __future__ import annotations

import numpy as np
import pandas as pd

import r4_lib as L
import r1_lib as L1


def long_sides(x: pd.DataFrame) -> pd.DataFrame:
    a = x.assign(side=np.where(x.market == "totals", "over", "home"), price=x.pa, other_price=x.pb)
    b = x.assign(side=np.where(x.market == "totals", "under", "away"), price=x.pb, other_price=x.pa)
    z = pd.concat([a, b], ignore_index=True)
    z["fav"] = L.fav_flag(z)
    # pick'em spreads and level moneylines have no favourite
    level = ((z.market == "spreads") & (z.line == 0)) | ((z.market == "h2h") & (z.price == z.other_price))
    z["favdog"] = np.where(z.market == "totals", "", np.where(level, "", np.where(z.fav, "favourite", "underdog")))
    return z


def cells(z: pd.DataFrame, exp: str, who: str, rows: list, by_season: bool = False):
    for mkt in ["totals", "spreads", "h2h"]:
        zm = z[z.market == mkt]
        groups = [("side", s) for s in (["over", "under"] if mkt == "totals" else ["home", "away"])]
        if mkt != "totals":
            groups += [("favdog", "favourite"), ("favdog", "underdog")]
        for col, v in groups:
            x = L.grade(zm[zm[col] == v])
            r = L.reg(exp, f"{who} {mkt} {v}", x)
            r.update({"book": who, "market": mkt, "side": v})
            rows.append(r)
            if by_season:
                for s, xs in x.groupby("season"):
                    rr = L.row({"experiment": exp, "cell": f"{who} {mkt} {v} season {s}"}, xs)
                    rr.update({"book": who, "market": mkt, "side": v, "season": L.SEASON_NAME[s]})
                    rows.append(rr)


def run() -> str:
    q = L.ht_quotes()
    fr = q[q.fresh & q.priced]
    out = []

    # (a) per book, its first fresh read
    first = fr.sort_values("snapshot_ts").drop_duplicates(["game_id", "market", "bookmaker"], keep="first")
    z = long_sides(first)
    rows = []
    for b in L.BOOKS:
        zb = z[z.bookmaker == b]
        if not len(zb):
            continue
        cells(zb, "2a blind, first fresh quote per book", b + ("" if b in L.DECIDABLE else " (reference)"), rows)
    t = pd.DataFrame(rows)[["book", "market", "side", "bets", "W", "L", "P", "units", "ret%", "lo%", "hi%"]]
    out.append("### (a) Blind bets at each book's first fresh halftime quote, all seasons\n\n"
               "Reference books are not bettable; their rows say only what their prices would have paid.\n\n"
               + L.md(t.to_dict("records")))

    # (b) best decidable price at the first read holding any fresh decidable quote
    dz = fr[fr.decidable]
    ts = dz.groupby(["game_id", "market"]).snapshot_ts.transform("min")
    dz = long_sides(dz[dz.snapshot_ts == ts])
    dz["_d"] = L1.dec(dz.price)
    # best number first: over lowest total, under highest; home highest home spread, away lowest
    key = np.where(dz.market == "h2h", 0.0,
                   np.where(dz.side.isin(["over", "away"]), dz.line, -dz.line))
    dz["_k"] = key
    best = dz.sort_values(["game_id", "market", "side", "_k", "_d"], ascending=[True, True, True, True, False]) \
             .drop_duplicates(["game_id", "market", "side"], keep="first")
    best["fav"] = L.fav_flag(best)
    rows = []
    cells(best, "2b blind, best decidable price", "best decidable", rows, by_season=True)
    t = pd.DataFrame(rows)
    t["season"] = t.get("season", pd.Series(dtype=str)).fillna("all")
    t = t[["market", "side", "season", "bets", "W", "L", "P", "units", "ret%", "lo%", "hi%"]]
    out.append("### (b) Blind bets at the best decidable price, first read holding a fresh decidable quote\n\n"
               + L.md(t.to_dict("records")))

    # moneyline by price band at the best decidable price
    ml = L.grade(best[best.market == "h2h"])
    ml["band"] = L2band(ml.price)
    rb = []
    for (fd, band), x in ml.groupby(["favdog", "band"]):
        if fd == "":
            continue
        r = L.row({"side": fd, "price band": band}, x)
        rb.append(r)
    out.append("### (b2) Moneyline at the best decidable price, by price band (not registered: sub-rows)\n\n"
               + L.md(rb))

    # early/late, without the 10 best dates and price band for each best-decidable cell (sub-rows, not registered)
    import r3_lib as L3
    kr = []
    for mkt in ["totals", "spreads", "h2h"]:
        zm = best[best.market == mkt]
        groups = [("side", s) for s in (["over", "under"] if mkt == "totals" else ["home", "away"])]
        if mkt != "totals":
            groups += [("favdog", "favourite"), ("favdog", "underdog")]
        for col, v in groups:
            x = L.grade(zm[zm[col] == v])
            for r in L3.kill_rows(f"{mkt} {v}", x, side_cols=(), fav_col=None):
                if r["subset"].startswith("season") or r["subset"] == "all":
                    continue
                r.pop("p_one", None)
                kr.append(r)
    out.append("### (b3) The same blind bets: early/late half of each season, without the 10 best dates, and by "
               "price band (not registered: sub-rows)\n\n" + L.md(kr))

    # what the sample resolves: half-width of the blind interval
    res = []
    for mkt, side in [("totals", "over"), ("spreads", "home"), ("h2h", "favourite")]:
        x = best[(best.market == mkt) & ((best.side == side) | (best.favdog == side))]
        s = L.row({}, L.grade(x))
        res.append({"market": mkt, "side": side, "bets": s["bets"], "half-width of the 90% interval":
                    round((s["hi%"] - s["lo%"]) / 2, 2)})
    out.append("### What the sample resolves (blind bet at the best decidable price, all seasons)\n\n" + L.md(res))
    return "\n\n".join(out)


def L2band(p):
    import r2_lib
    return r2_lib.ml_band(p)


if __name__ == "__main__":
    print(run())
