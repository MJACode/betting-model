"""Women's full-game totals: DraftKings only (live) against the best bettable book, decided at the same
moment (DraftKings' first posted total).

For each game DraftKings priced, every bettable book's standing total at DraftKings' first-post time
(its latest quote stamped at or before it) is priced with the live model's mean and the blend fitted
on the earlier season's DraftKings first posts, exactly as totals_b prices DraftKings. The best book is
the quote with the largest edge; the bet is graded at that book's total and price. Research only: the
local cache, nothing written.

    python -m scripts.ncaabw_research.totals_best_book
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import config  # noqa: E402
import scripts.ncaabw_research.totals_b as tb  # noqa: E402
from scripts.ncaabw_research._paths import CACHE  # noqa: E402

BOOKS = list(config.BEST_LINE_BOOKMAKERS)
CUTS = (0.03, 0.05, 0.08)

x = pd.read_parquet(CACHE / "totals_scored_input.parquet")
P = pd.read_parquet(CACHE / "pregame_quotes.parquet")
P = P[(P["market"] == "totals") & P["bookmaker"].isin(BOOKS)].dropna(subset=["total_line", "over_price", "under_price"])
P = P[(P["total_line"] >= tb.TOTAL_RANGE[0]) & (P["total_line"] <= tb.TOTAL_RANGE[1])]
P["lu_ns"] = P["last_update"].dt.as_unit("ns").astype("int64")
q = P.merge(x[["game_id", "quote_ns"]], on="game_id")
q = q[q["lu_ns"] <= q["quote_ns"]].sort_values(["game_id", "bookmaker", "lu_ns"])
standing = q.groupby(["game_id", "bookmaker"]).tail(1)
print(f"games {x['game_id'].nunique()}; books standing at DraftKings' first post, per game: "
      f"{standing.groupby('game_id').size().describe()[['mean', '50%']].round(2).to_dict()}; "
      f"by book {standing['bookmaker'].value_counts().to_dict()}")

keep = ["game_id", "season", "game_date", "pt", "total", "phase", "cons_close"]
rows = standing.rename(columns={"total_line": "line"})[["game_id", "bookmaker", "line", "over_price", "under_price"]]
rows = rows.merge(x[keep], on="game_id")
dk_rows = x[keep + ["line", "over_price", "under_price"]].assign(bookmaker="draftkings")

folds = [("2025-26, blend from 2024-25 (walk-forward)", [2025], 2026),
         ("2026-27 to date, blend from 2024-26 (walk-forward)", [2025, 2026], 2027),
         ("2024-25, blend from 2025-26 (second look)", [2026], 2025)]
for label, tr_s, te_s in folds:
    blends = tb.fit_blends(x[x["season"].isin(tr_s)])
    print(f"\n{label}")
    dk = tb.price_all(dk_rows[dk_rows["season"] == te_s], blends)
    allb = tb.price_all(rows[rows["season"] == te_s], blends)
    best = allb.sort_values("edge", ascending=False).groupby("game_id").head(1)
    for cut in CUTS:
        tb.summarise(dk[dk["edge"] > cut], f"DraftKings only, edge > {cut:.2f}")
        tb.summarise(best[best["edge"] > cut], f"best book,       edge > {cut:.2f}")
    b5 = best[best["edge"] > 0.05]
    print("  best book at 0.05, by book:", b5["bookmaker"].value_counts().to_dict())
    same = b5[b5["bookmaker"] == "draftkings"]
    other = b5[b5["bookmaker"] != "draftkings"]
    tb.summarise(same, "  of which DraftKings was best")
    tb.summarise(other, "  of which another book was best")
