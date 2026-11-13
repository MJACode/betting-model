"""Round 1: two checks on the best-price definition and the off-number mains.

 (1) At T-10, per market and season: how many decidable books sit on the
     modal decidable number (1, 2, 3+), i.e. how often "best price" is a real
     shop and not one book.
 (2) Per book and season, the on-centre main quotes' distance from the median
     of the OTHER books' numbers at the same (game, mark): share 1+ and 2+
     points away. A book whose "main" is a ladder rung shows here even when
     its price passed the off-centre filter.

    python scripts/euroleague_research/r1_nbooks.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import r1_lib as L  # noqa: E402

pd.set_option("display.width", 250)
g = L.load_games()
Q = L.load_main_quotes(g)
Q = Q[~Q.offc]

print("==== (1) decidable books on the modal decidable number at T-10 (games) ====")
rows = []
for m in ["spreads_h1", "totals_h1", "spreads_q1", "totals_q1", "h2h_h1", "h2h_q1"]:
    x = Q[(Q.market == m) & (Q.mark == "T-10") & Q.decidable]
    for season, y in x.groupby("season"):
        n = []
        for gid, z in y.groupby("game_id"):
            if m.startswith("h2h"):
                n.append(z.bookmaker.nunique())
                continue
            vc = z.line.value_counts()
            top = vc[vc == vc.max()].index.to_numpy(float)
            med = z.line.median()
            ln = sorted(top, key=lambda v: (abs(v - med), v))[0]
            n.append(int((z.line == ln).sum()))
        n = np.array(n)
        rows.append({"market": m, "season": season, "games": len(n), "one_book": int((n == 1).sum()),
                     "two_books": int((n == 2).sum()), "three_plus": int((n >= 3).sum())})
print(pd.DataFrame(rows).to_string(index=False))

print("\n==== (2) on-centre main quotes: distance from the other books' median number, same (game, mark) ====")
rows = []
for m in ["spreads_h1", "totals_h1", "spreads_q1", "totals_q1"]:
    x = Q[Q.market == m]
    tot = x.groupby(["game_id", "mark"]).line.agg(["sum", "size"])
    for (season, book), y in x.groupby(["season", "bookmaker"]):
        devs = []
        for (gid, mk), z in y.groupby(["game_id", "mark"]):
            others = x[(x.game_id == gid) & (x.mark == mk) & (x.bookmaker != book)]
            if len(others) < 1:
                continue
            devs.append(float(z.line.iloc[0] - others.line.median()))
        if not devs:
            continue
        d = np.abs(np.array(devs))
        rows.append({"market": m, "season": season, "book": book, "quotes": len(d),
                     "share_ge1": round(float((d >= 1).mean()), 3), "share_ge2": round(float((d >= 2).mean()), 3),
                     "median_abs": float(np.median(d))})
print(pd.DataFrame(rows).to_string(index=False))
