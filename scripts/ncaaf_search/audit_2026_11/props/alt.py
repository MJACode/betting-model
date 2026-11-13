"""Alternate ladders: is a soft book's ladder rung mispriced against a reference's MAIN line at the same number?

Run only after the main test was finished and written up (REPORT.md sections 1-7).

DEFINITIONS -- written before any alternate-ladder result was produced.
===========================================================================
SEASON    2026 only: alternate rows exist only in 2026 (alt_inspect.py).
SOFT SIDE pre-game `*_alternate` rows from the bettable books (draftkings,
          fanduel, betmgm, williamhill_us, fanatics, betrivers, hardrockbet).
          Measured in alt_inspect.py: all 306,971 pre-game rows are OVER-only
          and every line ends in .5, so every bet here is an OVER and there
          are no pushes.
PROPOSITION (game, player, base market) -- base market = the market key with
          `_alternate` removed.
REFERENCE the reference's MAIN two-way quote for the same player and base
          market, in the SAME pull, at EXACTLY the rung's line.
            named:   pinnacle | bovada | consensus (median de-vigged over
                     probability of >= 2 books' main two-way quotes at that
                     line in that pull, excluding the book being bet)
            placebo: fanduel, hardrockbet, williamhill_us, betmgm, espnbet,
                     fliff (main two-way quotes); a bettable book used as the
                     reference is removed from the bettable set.
EDGE      reference de-vigged OVER probability (multiplicative) minus the
          implied probability of the rung's over price (vig included).
CUTS      0.02, 0.03, 0.04, 0.05, 0.06, 0.08. No cap.
LOCK      one bet per proposition: the first pull in which any bettable
          book's rung crosses the cut; largest edge if several; ties by
          bettable-book order.
GRADING, STAKE, INTERVAL, HALVES, CLOSE VALUE, CLEARS: exactly as main.py.
VARIANTS  one. Cells: 1 season x (3 named + 6 placebo) x 6 cuts = 54.
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402

import sys

import numpy as np
import pandas as pd

OUT = str(WORK / "props")
sys.path.insert(0, OUT)
import main as M      # noqa: E402

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 80)
pd.set_option("display.max_rows", 600)

ALT_NAMED = ["pinnacle", "bovada", "consensus"]
ALT_PLACEBO = ["fanduel", "hardrockbet", "williamhill_us", "betmgm", "espnbet", "fliff"]


def alt_quotes(p, q):
    a = p[p.pre & p.market.str.endswith("_alternate") & p.line.notna() & p.over_price.notna()
          & p.bookmaker.isin(M.BETTABLE)].copy()
    a["market"] = a.market.str.replace("_alternate", "", regex=False)
    a = a[a.market.isin(M.MARKET_STAT)]
    a["nn"] = a.player_name.map(M.norm)
    a = a.rename(columns={"bookmaker": "book", "over_price": "price"})
    # the same window ids as the main board: a pull is one stamp, so join on (game_id, stamp)
    wmap = q[["game_id", "win", "win_ts"]].drop_duplicates()
    n0 = len(a)
    a = a.merge(wmap.rename(columns={"win_ts": "ts"}), on=["game_id", "ts"], how="inner")
    a["win_ts"] = a.ts
    a = a.sort_values("ts").drop_duplicates(["game_id", "nn", "market", "book", "win", "line"], keep="last")
    a["side"] = "over"
    a["imp"] = M.imp(a.price)
    return a[["season", "game_date", "game_id", "nn", "market", "win", "line", "book", "win_ts", "price",
              "side", "imp"]].reset_index(drop=True), n0


def alt_candidates(a, q, ref):
    two = q[q.two]
    soft = a[a.book != ref]
    diag = {"ref": ref, "soft_rungs": len(soft)}
    if ref == "consensus":
        oth = two[M.KEY5 + ["book", "fo_m", "fu_m"]].rename(columns={"book": "obook", "fo_m": "fo", "fu_m": "fu"})
        sq = soft[M.KEY5 + ["book"]].drop_duplicates()
        mm = sq.merge(oth, on=M.KEY5)
        mm = mm[mm.obook != mm.book]
        agg = mm.groupby(M.KEY5 + ["book"]).agg(fo=("fo", "median"), fu=("fu", "median"), n_oth=("fo", "size")).reset_index()
        agg = agg[agg.n_oth >= 2]
        c = soft.merge(agg, on=M.KEY5 + ["book"])
    else:
        r = two[two.book == ref][M.KEY5 + ["fo_m", "fu_m"]].rename(columns={"fo_m": "fo", "fu_m": "fu"})
        c = soft.merge(r, on=M.KEY5)
        k4 = ["game_id", "nn", "market", "win"]
        diag["rungs_where_ref_quotes_player"] = int(len(soft.merge(r[k4].drop_duplicates(), on=k4)))
    c["fair"] = c.fo
    c["edge"] = c.fair - c.imp
    c["edge_vs_price"] = c.edge
    diag.update(rungs_at_ref_line=len(c), propositions=int(c.drop_duplicates(M.KEY3).shape[0]),
                games=int(c.game_id.nunique()))
    return c, diag


def main():
    np.seterr(divide="ignore")
    p, g, lt = M.load()
    q = M.build_quotes(p, list(M.MARKET_STAT))
    actuals, _ = M.build_actuals(q, g, lt)
    q26 = q[q.season == 2026]
    dates = np.sort(q26.game_date.unique())
    mid = {2026: dates[(len(dates) - 1) // 2]}
    a, n0 = alt_quotes(p[p.season == 2026], q26)
    print(f"bettable over-only alternate rungs, pre-game, 2026: {n0}; in a pull that also has a main-board quote: {len(a)}")
    print(a.groupby("book").size().to_string())

    rows, brk, diags, allb = [], [], [], []
    for ref in ALT_NAMED + ALT_PLACEBO:
        c, d = alt_candidates(a, q26, ref)
        diags.append(d)
        d2 = c.groupby("book").size().to_dict()
        print(f"ref {ref}: {d}  by book {d2}")
        for cut in M.CUTS:
            b = M.lock(c, cut)
            b = M.grade(b, actuals)
            b = M.close_value(b, q26, ref)
            r = M.summarise(b, mid)
            r.update(variant="ALT", season="2026", ref=ref, cut=cut)
            rows.append(r)
            for col in ("market", "book"):
                for x in M.breakdown(b, col):
                    x.update(variant="ALT", season="2026", ref=ref, cut=cut, by=col)
                    brk.append(x)
            allb.append(b.assign(ref=ref, cut=cut))
    res = pd.DataFrame(rows)
    front = ["variant", "season", "ref", "cut"]
    res = res[front + [c for c in res.columns if c not in front]]
    res.to_csv(OUT + r"\alt_grid.csv", index=False)
    pd.DataFrame(brk).to_csv(OUT + r"\alt_breakdowns.csv", index=False)
    pd.DataFrame(diags).to_csv(OUT + r"\alt_diagnostics.csv", index=False)
    ab = pd.concat(allb, ignore_index=True)
    keep = ["ref", "cut", "season", "game_date", "game_id", "nn", "market", "book", "side", "line", "price", "fair",
            "edge", "win", "win_ts", "status", "gstatus", "actual", "nan0", "result", "risk", "units", "later",
            "close_edge"]
    ab[keep].to_parquet(OUT + r"\alt_bets.parquet", index=False)
    # edge distribution of every comparable rung (context for how often a rung beats the reference)
    ed = []
    for ref in ALT_NAMED:
        c, _ = alt_candidates(a, q26, ref)
        qs = c.groupby("book").edge.describe(percentiles=[.5, .9, .99]).round(4)
        qs["n_ge_0"] = c.groupby("book").edge.apply(lambda s: int((s >= 0).sum()))
        qs["n_ge_002"] = c.groupby("book").edge.apply(lambda s: int((s >= 0.02 - 1e-12).sum()))
        qs.insert(0, "ref", ref)
        ed.append(qs.reset_index())
    ed = pd.concat(ed)
    ed.to_csv(OUT + r"\alt_edge_dist.csv", index=False)
    print("\nedge of every rung at the reference's line, by soft book:\n", ed.to_string(index=False))
    show = ["ref", "cut", "bets", "W", "L", "P", "units", "risked", "roi", "ci_lo", "ci_hi", "h1_bets", "h1_roi",
            "h2_bets", "h2_roi", "clv_n", "clv_mean", "price_min", "price_med", "price_max", "share_shorter_200"]
    for c_ in show:
        if c_ not in res.columns:
            res[c_] = np.nan
    print("\nALT GRID\n", res[show].round(4).to_string(index=False))
    print("\ncells run:", len(res), " with a bet:", int((res.bets > 0).sum()))


if __name__ == "__main__":
    main()
