"""POST-HOC data check on the alternate ladders, prompted by one bet (a DraftKings +429 rung at a number Pinnacle
priced as a coin flip). An over ladder must get longer as the line rises. A ladder whose implied probability RISES
at a higher line is two products stored under one market key.

1. Measure, per book, how many (player, market, pull) ladders break that order (tolerance 0.01 of implied probability).
2. Re-run the alternate-ladder grid on ladders that keep the order only (variant ALT_M, POST-HOC, everything else as alt.py).
"""
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402
import sys

import numpy as np
import pandas as pd

OUT = str(WORK / "props")
sys.path.insert(0, OUT)
import main as M     # noqa: E402
import alt as A      # noqa: E402

pd.set_option("display.width", 260); pd.set_option("display.max_columns", 80); pd.set_option("display.max_rows", 600)
TOL = 0.01


def main():
    np.seterr(divide="ignore")
    p, g, lt = M.load()
    q = M.build_quotes(p, list(M.MARKET_STAT))
    actuals, _ = M.build_actuals(q, g, lt)
    q26 = q[q.season == 2026]
    dates = np.sort(q26.game_date.unique())
    mid = {2026: dates[(len(dates) - 1) // 2]}
    a, _ = A.alt_quotes(p[p.season == 2026], q26)
    lk = ["game_id", "nn", "market", "book", "win"]
    a = a.sort_values(lk + ["line"])
    a["rise"] = a.groupby(lk).imp.diff()
    lad = a.groupby(lk).agg(rungs=("line", "size"), max_rise=("rise", "max")).reset_index()
    lad["broken"] = lad.max_rise > TOL
    t = lad.groupby("book").agg(ladders=("broken", "size"), broken=("broken", "sum"),
                                multi_rung=("rungs", lambda s: int((s > 1).sum()))).reset_index()
    t["broken_share"] = t.broken / t.ladders
    rb = a.merge(lad[lk + ["broken"]], on=lk)
    t2 = rb.groupby("book").agg(rungs=("broken", "size"), rungs_in_broken=("broken", "sum")).reset_index()
    t = t.merge(t2, on="book")
    t.to_csv(OUT + r"\alt_monotone_inventory.csv", index=False)
    print("ladders whose over price gets SHORTER at a higher line (two products under one key):\n", t.round(4).to_string(index=False))
    by_m = lad.merge(a[lk].drop_duplicates(), on=lk).groupby(["book", "market"]).broken.agg(["size", "sum"]).reset_index()
    print("\nby book x market:\n", by_m.to_string(index=False))
    by_m.to_csv(OUT + r"\alt_monotone_by_market.csv", index=False)

    good = rb[~rb.broken].drop(columns=["rise", "broken"])
    rows = []
    for ref in A.ALT_NAMED + A.ALT_PLACEBO:
        c, d = A.alt_candidates(good, q26, ref)
        for cut in M.CUTS:
            b = M.lock(c, cut)
            b = M.grade(b, actuals)
            b = M.close_value(b, q26, ref)
            r = M.summarise(b, mid)
            r.update(variant="ALT_M_POSTHOC_ordered_ladders_only", season="2026", ref=ref, cut=cut,
                     rungs_at_ref_line=len(c))
            rows.append(r)
    res = pd.DataFrame(rows)
    front = ["variant", "season", "ref", "cut"]
    res = res[front + [c for c in res.columns if c not in front]]
    res.to_csv(OUT + r"\alt_m_grid.csv", index=False)
    show = ["ref", "cut", "bets", "W", "L", "P", "units", "risked", "roi", "ci_lo", "ci_hi", "h1_bets", "h1_roi",
            "h2_bets", "h2_roi", "clv_n", "clv_mean", "price_min", "price_med", "price_max"]
    for c_ in show:
        if c_ not in res.columns:
            res[c_] = np.nan
    print("\nALT_M GRID (ordered ladders only)\n", res[show].round(4).to_string(index=False))
    print("cells:", len(res), "with a bet:", int((res.bets > 0).sum()))


if __name__ == "__main__":
    main()
