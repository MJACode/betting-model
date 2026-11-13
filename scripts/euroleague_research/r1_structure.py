"""Round 1, task 4 (structural checks): do the books disagree with each other
at the same mark by a point or more, and does betting against the outlier
pay? And the off-centre "main" quotes, graded both ways.

  Disagreement: at each (game, mark), the spread of on-centre main numbers
  across books (max - min), by market, season and pair type.
  The outlier rule (thresholds fixed before reading: 1.0, 1.5, 2.0; decision
  T-10, other read T-60): a DECIDABLE book whose number differs from the
  median of every OTHER book's on-centre number at the same mark (offshore
  included, at least 2 others) by the threshold or more; bet the side the
  difference favours at that book's quoted price (its total 1+ above the
  others: under there; its home number 1+ above the others, i.e. more points
  for the home club: home there). One bet per (game, book).
  Off-centre quotes: each side bet blind at T-10, at its own price.

    python scripts/euroleague_research/r1_structure.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import r1_lib as L  # noqa: E402

pd.set_option("display.width", 250)
g = L.load_games()
QA = L.load_main_quotes(g)
Q = QA[~QA.offc]
LINE_MK = ["spreads_h1", "totals_h1", "spreads_q1", "totals_q1"]

print("==== disagreement at the same mark: share of (game, mark) with the books' numbers 1+ / 2+ points apart ====")
rows = []
for m in LINE_MK:
    x = Q[Q.market == m]
    for (season, mark), y in x.groupby(["season", "mark"]):
        if mark not in ("T-10", "T-360", "T-1440"):
            continue
        for tag, sel in [("all books", y.bookmaker.notna()), ("decidable only", y.decidable),
                         ("decidable vs offshore", None)]:
            if sel is None:
                d = y[y.decidable].groupby("game_id").line.median().rename("d").to_frame().join(
                    y[y.bookmaker.isin(L.OFFSHORE)].groupby("game_id").line.median().rename("o"), how="inner")
                gap = (d.d - d.o).abs()
            else:
                z = y[sel].groupby("game_id").line.agg(["max", "min", "size"])
                z = z[z["size"] >= 2]
                gap = z["max"] - z["min"]
            if len(gap) == 0:
                continue
            rows.append({"market": m, "season": season, "mark": mark, "compare": tag, "games": len(gap),
                         "share_ge1": round(float((gap >= 1).mean()), 3), "share_ge2": round(float((gap >= 2).mean()), 3),
                         "max_gap": float(gap.max())})
print(pd.DataFrame(rows).to_string(index=False))

print("\n==== the outlier rule: bet against a decidable book standing 1+ points off the others ====")
out = []
bets_all = []
for m in LINE_MK:
    for mark in ["T-10", "T-60"]:
        x = Q[(Q.market == m) & (Q.mark == mark)]
        recs = []
        for gid, y in x.groupby("game_id"):
            for i, r in y[y.decidable].iterrows():
                others = y[y.bookmaker != r.bookmaker]
                if len(others) < 2:
                    continue
                ref = others.line.median()
                dev = r.line - ref
                recs.append({"game_id": gid, "game_date": r.game_date, "season": r.season, "book": r.bookmaker,
                             "margin": r.margin, "total": r.total, "line": r.line, "dev": dev,
                             "pa": r.pa, "pb": r.pb, "n_others": len(others)})
        R = pd.DataFrame(recs)
        if not len(R):
            continue
        for th in [1.0, 1.5, 2.0]:
            z = R[R.dev.abs() >= th].copy()
            if m.startswith("totals"):
                z["side"] = np.where(z.dev > 0, "under", "over")
                z["price"] = np.where(z.dev > 0, z.pb, z.pa)
            else:
                z["side"] = np.where(z.dev > 0, "home", "away")
                z["price"] = np.where(z.dev > 0, z.pa, z.pb)
            gr = L.grade_rows(z, m)
            gr["market"], gr["mark"], gr["th"] = m, mark, th
            bets_all.append(gr)
            s = L.summary(gr)
            sides = gr.side.value_counts().to_dict()
            out.append({"market": m, "mark": mark, "threshold": th,
                        "seasons": ",".join(str(v) for v in sorted(gr.season.unique())),
                        "sides": sides, "books": gr.book.value_counts().to_dict(),
                        **{k: s[k] for k in ["bets", "W", "L", "P", "units", "ret%", "lo%", "hi%"]}})
print(pd.DataFrame(out).to_string(index=False))
B = pd.concat(bets_all) if bets_all else pd.DataFrame()
print("\n-- by season, threshold 1.0, T-10")
if len(B):
    t = B[(B.th == 1.0) & (B.mark == "T-10")]
    print(pd.DataFrame([{"market": m, "season": s, **{k: v for k, v in L.summary(z).items()
                                                        if k in ["bets", "W", "L", "P", "units", "ret%", "lo%", "hi%"]}}
                        for (m, s), z in t.groupby(["market", "season"])]).to_string(index=False))

print("\n==== off-centre 'main' quotes at T-10, each side bet blind at its own price ====")
oc = QA[QA.offc & (QA.mark == "T-10")]
rows = []
for (m, book, season), x in oc.groupby(["market", "bookmaker", "season"]):
    for side in (["over", "under"] if m.startswith("totals") else ["home", "away"]):
        y = x.assign(side=side, price=x.pa if side in ("over", "home") else x.pb)
        y["short"] = y.price < 0
        r = L.grade_rows(y, m)
        for tag, z in [("long-priced side", r[~r.short]), ("short-priced side", r[r.short])]:
            if len(z):
                s = L.summary(z)
                rows.append({"market": m, "book": book, "season": season, "side": side, "which": tag,
                             "median_price": float(z.price.median()),
                             **{k: s[k] for k in ["bets", "W", "L", "P", "units", "ret%", "lo%", "hi%"]}})
print(pd.DataFrame(rows).to_string(index=False))
r = []
for side in ["long", "short"]:
    pass
allq = []
for (m, book, season), x in oc.groupby(["market", "bookmaker", "season"]):
    a = x.assign(side="over" if m.startswith("totals") else "home", price=x.pa)
    b = x.assign(side="under" if m.startswith("totals") else "away", price=x.pb)
    for y in (a, b):
        gr = L.grade_rows(y, m)
        gr["long"] = gr.price > 0
        allq.append(gr)
A = pd.concat(allq)
print("\n-- pooled over every off-centre quote at T-10:")
for tag, z in [("long-priced side", A[A.long]), ("short-priced side", A[~A.long])]:
    s = L.summary(z)
    print(f"  {tag:<18}", {k: s[k] for k in ["bets", "W", "L", "P", "units", "ret%", "lo%", "hi%"]},
          "median price", float(z.price.median()))
