"""Section 8 of REPORT.md: the alternate-ladder test. Reads only what alt.py wrote."""
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402
import numpy as np
import pandas as pd

import verdict as V

OUT = str(WORK / "props")
ALT_NAMED = ["pinnacle", "bovada", "consensus"]


def section(w, md, pct, num, grid_table, pivot_table):
    g = pd.read_csv(OUT + r"\alt_grid.csv", dtype={"season": str})
    brk = pd.read_csv(OUT + r"\alt_breakdowns.csv", dtype={"season": str})
    dg = pd.read_csv(OUT + r"\alt_diagnostics.csv")
    ed = pd.read_csv(OUT + r"\alt_edge_dist.csv")
    ver = V.verdict(OUT + r"\alt_grid.csv")
    ver.to_csv(OUT + r"\alt_verdict.csv", index=False)
    w("## 8. Separate section: alternate ladders against a reference's main line (2026 only)")
    w()
    w("Run after sections 1 to 7 were written. Definitions are at the top of `alt.py`, fixed before its first run; one "
      f"variant, {len(g)} cells, {int((g.bets > 0).sum())} with a bet. This is the only test DraftKings can take part in, "
      "because its college props reach the feed only as ladders.")
    w()
    w("- **Soft side**: a bettable book's ladder rung. Every rung is over-only and every line ends in .5, so every bet is an over.")
    w("- **Reference**: the reference's main two-way quote for the same player and market, in the same pull, at exactly the rung's number.")
    w("- **Edge**: reference de-vigged over probability minus the implied probability of the rung's price. Same cuts, lock, grading, stake and tests as the main run.")
    w()
    w("### 8.1 How many rungs sit on a reference's main line, and how they are priced")
    w()
    d = dg[dg.ref.isin(ALT_NAMED)][["ref", "soft_rungs", "rungs_where_ref_quotes_player", "rungs_at_ref_line", "propositions", "games"]].copy()
    d["rungs_where_ref_quotes_player"] = d.rungs_where_ref_quotes_player.map(lambda x: "" if pd.isna(x) else int(x))
    d.columns = ["reference", "bettable rungs", "rungs where the reference quotes that player/market/pull",
                 "rungs at the reference's line", "propositions", "games"]
    md(d)
    e = ed.copy()
    for c in ("mean", "50%", "90%", "99%", "max", "min"):
        e[c] = e[c].map(lambda x: f"{x:+.4f}")
    e["count"] = e["count"].astype(int)
    e = e[["ref", "book", "count", "mean", "50%", "90%", "99%", "max", "n_ge_0", "n_ge_002"]]
    e.columns = ["reference", "soft book", "rungs at the reference's line", "mean edge", "median", "90th pct", "99th pct", "max",
                 "rungs at or better than fair", "rungs at 0.02+"]
    w("Edge of every such rung (before any cut):")
    w()
    md(e)
    dk = ed[(ed.book == "draftkings") & (ed.ref == "pinnacle")].iloc[0]
    w(f"A DraftKings rung at Pinnacle's number is priced a median {abs(dk['50%']) * 100:.1f} points worse than Pinnacle's fair "
      f"value: of {int(dk['count']):,} such rungs, {int(dk['n_ge_0'])} are at or better than fair and {int(dk['n_ge_002'])} reach the 0.02 cut.")
    w()
    w("### 8.2 Full grid, named references")
    w()
    x = g[g.ref.isin(ALT_NAMED)].copy()
    x["o"] = x.ref.map({r: i for i, r in enumerate(ALT_NAMED)})
    grid_table(x)
    w("### 8.3 The placebo (bets / ROI)")
    w()
    pivot_table(g)
    w("### 8.4 By soft book and by market, named references (bets / units / ROI)")
    w()
    for by in ("book", "market"):
        bx = brk[(brk.by == by) & brk.ref.isin(ALT_NAMED)].copy()
        bx["cell"] = [f"{int(n)} / {num(u)}u / {pct(r_)}" for n, u, r_ in zip(bx.bets, bx.units, bx.roi)]
        pv = bx.pivot_table(index=["ref", "level"], columns="cut", values="cell", aggfunc="first").reset_index()
        pv.columns = [c_ if isinstance(c_, str) else f"{c_:.2f}" for c_ in pv.columns]
        md(pv.rename(columns={"ref": "reference", "level": by}).fillna(""))
    w("### 8.5 Verdict for the ladders")
    w()
    mx = g[g.ref.isin(ALT_NAMED)].sort_values("bets", ascending=False).iloc[0]
    p2 = g[(g.ref == "pinnacle") & np.isclose(g.cut, 0.02)].iloc[0]
    b2 = g[(g.ref == "bovada") & np.isclose(g.cut, 0.02)].iloc[0]
    c2 = g[(g.ref == "consensus") & np.isclose(g.cut, 0.02)].iloc[0]
    w(f"**Nothing clears** ({int(ver.CLEARS.sum())} of {len(ver)} named cells; {int(ver.c1_150_bets.sum())} reach 150 bets). "
      f"The largest named cell has {int(mx.bets)} bets ({mx.ref}, cut {mx.cut:.2f}). At the 0.02 cut: "
      f"Pinnacle {int(p2.bets)} bets, {num(p2.units)} units, {pct(p2.roi)} ({pct(p2.ci_lo)}, {pct(p2.ci_hi)}); "
      f"Bovada {int(b2.bets)} bets, {num(b2.units)} units, {pct(b2.roi)} ({pct(b2.ci_lo)}, {pct(b2.ci_hi)}); "
      f"consensus {int(c2.bets)} bets, {num(c2.units)} units, {pct(c2.roi)} ({pct(c2.ci_lo)}, {pct(c2.ci_hi)}).")
    w()
    dkb = brk[(brk.by == "book") & (brk.level == "draftkings") & brk.ref.isin(ALT_NAMED) & np.isclose(brk.cut, 0.02)]
    if len(dkb):
        w("DraftKings alone at the 0.02 cut: " + "; ".join(
            f"{r.ref}: {int(r.bets)} bets, {num(r.units)} units, {pct(r.roi)}" for r in dkb.itertuples()) + ".")
        w()
    import os
    if os.path.exists(OUT + r"\alt_m_grid.csv"):
        inv = pd.read_csv(OUT + r"\alt_monotone_inventory.csv")
        gm = pd.read_csv(OUT + r"\alt_m_grid.csv", dtype={"season": str})
        w("### 8.6 A data fault in the stored ladders (found after the ladder grid, POST-HOC)")
        w()
        w("One winning bet above was a DraftKings rung at +429 on a number Pinnacle priced as a coin flip (Bo Jackson rushing "
          "yards 69.5, 2026-10-03). In that pull DraftKings' stored ladder for him runs 39.5 at -101, 49.5 at +169, 69.5 at +429, "
          "then 70.5 at -119 and 99.5 at +235: the price gets shorter at a higher line, which a single over ladder cannot do. "
          "So that stored ladder is not one product; what the second one is was not established. Counted across every ladder (a ladder = one book, "
          "player, market and pull; broken = implied probability rises by more than 0.01 at a higher line):")
        w()
        t = inv[["book", "ladders", "broken", "broken_share", "rungs", "rungs_in_broken"]].copy()
        t["broken_share"] = t.broken_share.map(lambda x: f"{100 * x:.2f}%")
        t.columns = ["book", "ladders", "broken ladders", "broken share", "rungs", "rungs in broken ladders"]
        md(t)
        w("The same grid on ordered ladders only (named references; everything else unchanged):")
        w()
        x = gm[gm.ref.isin(ALT_NAMED)].copy()
        x["o"] = x.ref.map({r: i for i, r in enumerate(ALT_NAMED)})
        grid_table(x)
        vm = V.verdict(OUT + r"\alt_m_grid.csv")
        w(f"Still nothing clears ({int(vm.CLEARS.sum())} of {len(vm)} named cells; largest {int(gm[gm.ref.isin(ALT_NAMED)].bets.max())} bets). "
          "A rung taken from one of these ladders cannot be assumed to be the full-game stat at that number.")
        w()
