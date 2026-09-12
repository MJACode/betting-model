"""The one region of the replay grid that looked positive, tested the way the
bar was written: positive in BOTH halves of the season, CI clear of zero.

ncaaf_live_win_prob showed a cluster at LOW prob x HIGH EV -- prob 0.55-0.62,
EV >= 0.26/0.30 -- reading +5% to +17%. That is live underdogs at long prices.
Four adjacent cells positive is the shape of a plateau, so it deserves the
split rather than a dismissal.
"""
import pickle
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
from scripts.ncaaf_inplay_history_backtest import (  # noqa: E402
    first_signals, split_halves, summarise)

cands = pickle.loads((Path(tempfile.gettempdir()) /
                      "ncaaf_inplay_candidates_2025.pkl").read_bytes())
ml = [c for c in cands if c["model_id"] == "ncaaf_live_win_prob"]
tot = [c for c in cands if c["model_id"] == "ncaaf_live_total"]
floors = {"ncaaf_live_total": 0.12, "ncaaf_live_win_prob": 0.10}
CAP = 0.18


def row(label, bets):
    h1, h2 = split_halves(bets, 2025)
    a, b, c = summarise(bets), summarise(h1), summarise(h2)
    def f(s):
        if not s["n"]:
            return "      no bets      "
        return (f"{s['n']:4d} {s['units']:+7.1f}u {s['roi_pct']:+6.1f}% "
                f"[{s['ci_low'] or 0:.0f},{s['ci_high'] or 0:.0f}]")
    verdict = "PASS" if (b["n"] and c["n"] and (b["roi_pct"] or 0) > 0
                         and (c["roi_pct"] or 0) > 0
                         and (a["ci_low"] or 0) > 52.4) else "fail"
    print(f"  {label:<22} all {f(a)} | H1 {f(b)} | H2 {f(c)}  -> {verdict}")


print("ncaaf_live_win_prob, FRESH quotes, the candidate region:")
for p in (0.55, 0.58, 0.60, 0.62):
    for ev in (0.26, 0.30, 0.34):
        row(f"prob>={p} ev>={ev}",
            first_signals(ml, p, floors, ev, CAP, fresh_only=True))

print("\nncaaf_live_total, FRESH quotes, its least-bad cells:")
for p, ev in ((0.68, 0.22), (0.72, 0.22), (0.68, 0.0)):
    row(f"prob>={p} ev>={ev}",
        first_signals(tot, p, floors, ev, CAP, fresh_only=True))

print("\nBar: positive in BOTH halves AND the all-sample CI low above the ~52.4%")
print("breakeven at -110. A cell passing on one half is a cell that has not")
print("been tested (CLAUDE.md: require a plateau, not a peak).")
