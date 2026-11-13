"""Round 1, step 6 (continued): three checks on the method.

 (1) The kernel table's floor: for each fit, the bandwidth the repo's widening
     loop (start 0.75, x1.25 until the weights reach 500 games or the
     bandwidth passes 20) reaches at the fit's 5th, 50th and 95th percentile
     key.
 (2) P2 (V2 first-quarter total, T-10, cut 0.02): how many bets sit at the
     decidable book with the HIGHEST first-quarter total at that mark (ties
     count as highest), and how many at the lowest.
 (3) The market-alone control row for P2: the same table, cut, books and
     seasons, but mu = the median decidable first-quarter total at the mark
     (the market's own number) instead of the full-game anchor. If it matches
     P2, the anchor adds nothing.

    python scripts/euroleague_research/r1_kill2.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import r1_lib as L  # noqa: E402
import r1_method as M  # noqa: E402

pd.set_option("display.width", 250)
g, Q = M.g, M.Q
COLS = ["bets", "W", "L", "P", "units", "ret%", "lo%", "hi%"]


def h_reached(key, m, h0=0.75, nmin=500):
    h = h0
    while True:
        w = np.exp(-0.5 * ((key - m) / h) ** 2)
        if w.sum() >= nmin or h > 20:
            return h, float(w.sum())
        h *= 1.25


s26 = g[(g.season == 2026) & g.played].sort_values("tip")
split = s26.tip.iloc[len(s26) // 2]
fit26 = s26[s26.tip < split].game_id.to_numpy()

print("==== (1) bandwidth the kernel table reaches (start 0.75, x1.25 to 500 games or past 20) ====")
rows = []
for m in ["totals_h1", "spreads_h1", "totals_q1", "spreads_q1"]:
    fits = [("V1", "2025-26 first half", fit26)]
    for S in [2025, 2026, 2027]:
        fits.append(("V2", f"seasons before {S}", g[(g.season < S) & (g.season >= 2024) & g.played].game_id.to_numpy()))
    for ver, tag, ids in fits:
        a = M.anchor_values(ver, m, "T-10", ids)
        y = M.G.loc[ids, M.outcome_of(m)]
        ok = a.notna() & y.notna()
        b1, b0 = np.polyfit(a[ok], y[ok], 1)
        key = (b0 + b1 * a[ok]).to_numpy()
        rec = {"market": m, "version": ver, "fit": tag, "games": int(ok.sum()),
               "key_sd": round(float(key.std()), 2)}
        for q in [5, 50, 95]:
            h, w = h_reached(key, float(np.percentile(key, q)))
            rec[f"h_at_p{q}"] = round(h, 2) if h <= 20 else f">20 ({w:.0f})"
        rows.append(rec)
print("h_at_pX = bandwidth reached at the key's X-th percentile; '>20 (n)' = the floor was never met, n = weight reached")
print(pd.DataFrame(rows).to_string(index=False))

print("\n==== (2) and (3): V2 first-quarter total, decidable books, T-10 ====")
mk = "totals_q1"
ctrl_parts, real_parts = [], []
for S in [2026, 2027]:
    fit_ids = g[(g.season < S) & (g.season >= 2024) & g.played].game_id.to_numpy()
    ids = g[(g.season == S) & g.played].game_id.to_numpy()
    model = M.fit("V2", mk, fit_ids)
    d = M.decide("V2", mk, "T-10", model, ids, L.DECIDABLE)
    x = Q[(Q.market == mk) & (Q.mark == "T-10") & Q.game_id.isin(ids) & Q.bookmaker.isin(L.DECIDABLE)].copy()
    hi = x.groupby("game_id").line.max().rename("hi_line")
    lo = x.groupby("game_id").line.min().rename("lo_line")
    nb = x.groupby("game_id").bookmaker.nunique().rename("n_dec")
    d = d.join(hi, on="game_id").join(lo, on="game_id").join(nb, on="game_id")
    real_parts.append(d)
    # control: mu = the market's own number (median decidable first-quarter total at the mark)
    x["mu"] = x.game_id.map(x.groupby("game_id").line.median())
    side, edge, qq = M.price(mk, x.mu.to_numpy(), x, model["T"])
    x["side"], x["edge"], x["q"] = side, edge, qq
    x["price"] = np.where(np.isin(side, ["home", "over"]), x.pa, x.pb)
    x = x.sort_values(["game_id", "edge", "bookmaker"], ascending=[True, False, True]).drop_duplicates("game_id")
    ctrl_parts.append(L.grade_rows(x, mk).assign(S=S))
R = pd.concat(real_parts)
C = pd.concat(ctrl_parts)
y = R[R.edge > 0.02]
multi = y[y.n_dec >= 2]
print(f"(2) P2 bets at cut 0.02: {len(y)}; on games with 2+ decidable books quoting: {len(multi)}; "
      f"of those at the highest decidable number: {int((multi.line == multi.hi_line).sum())} "
      f"(strictly above the lowest: {int(((multi.line == multi.hi_line) & (multi.hi_line > multi.lo_line)).sum())}); "
      f"at the lowest: {int((multi.line == multi.lo_line).sum())}; one decidable book only: {int((y.n_dec == 1).sum())}")
print("    P2 bets by under/over and whether at the highest number:",
      y.assign(at_hi=(y.line == y.hi_line)).groupby(["side", "at_hi"]).size().to_dict())
print("\n(3) control row (mu = the market's own median number) against P2 (mu from the full-game anchor):")
out = []
for cut in L.CUTS:
    for tag, D in [("P2: full-game anchor", R), ("control: market's own number", C)]:
        z = D[D.edge > cut]
        s = L.summary(z)
        out.append({"cut": cut, "rule": tag, **{k: s[k] for k in COLS},
                    "unders": int((z.side == "under").sum()) if len(z) else 0})
print(pd.DataFrame(out).to_string(index=False))
for S, z in C.groupby("S"):
    s = L.summary(z[z.edge > 0.02])
    print(f"   control, season {S}, cut 0.02:", {k: s[k] for k in COLS})
