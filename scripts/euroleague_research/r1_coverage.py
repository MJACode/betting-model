"""Round 1, task 1: coverage. Per season and market, the played games with a
main quote at each mark, by book; then any decidable book; then any book.
Off-centre "mains" are counted separately (r1_lib header).

    python scripts/euroleague_research/r1_coverage.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd  # noqa: E402

import r1_lib as L  # noqa: E402

pd.set_option("display.width", 250)
g = L.load_games()
q = L.load_main_quotes(g)
played = g[g.played].groupby("season").size()
print("played games by season:", played.to_dict())
print("seasons with any main period quote:", q.groupby("season").game_id.nunique().to_dict())

for m in L.MARKETS:
    x = q[(q.market == m) & ~q.offc]
    print(f"\n==== {m}: games with an on-centre main quote, by season, book and mark ====")
    t = x.groupby(["season", "bookmaker", "mark"]).game_id.nunique().unstack("mark").reindex(columns=L.MARKS)
    d = x[x.decidable].groupby(["season", "mark"]).game_id.nunique().unstack("mark").reindex(columns=L.MARKS)
    d.index = pd.MultiIndex.from_tuples([(s, "ANY DECIDABLE") for s in d.index])
    a = x.groupby(["season", "mark"]).game_id.nunique().unstack("mark").reindex(columns=L.MARKS)
    a.index = pd.MultiIndex.from_tuples([(s, "ANY BOOK") for s in a.index])
    out = pd.concat([t, d, a]).sort_index().fillna(0).astype(int)
    out["played"] = [played.get(s, 0) for s in out.index.get_level_values(0)]
    print(out.to_string())
    oc = q[(q.market == m) & q.offc]
    if len(oc):
        print(f"-- off-centre main quotes set aside ({m}): rows, games, by season and book")
        print(oc.groupby(["season", "bookmaker"]).agg(rows=("game_id", "size"),
                                                        games=("game_id", "nunique")).to_string())

print("\n==== stored snapshot time before tip, by mark (minutes; main markets) ====")
q["lead"] = (q.tip - q.snap).dt.total_seconds() / 60
print(q.groupby("mark").lead.describe(percentiles=[.05, .5, .95]).round(1).reindex(L.MARKS).to_string())
