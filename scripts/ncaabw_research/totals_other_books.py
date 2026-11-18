"""Women's full-game totals at OTHER books' first posted totals, on the games
DraftKings never prices (2026-11-16, docs/sports/ncaabw.md, "Why the women's
record trails the men's").

DraftKings posts a women's total on about one game in ten, and the live model
decides only at DraftKings' first posted total. This asks whether the same model
holds where DraftKings is absent. Same pipeline as totals_b, one change: a game
DraftKings never posted a total for is priced at the earliest first posted total
among the other bettable books (config.BEST_LINE_BOOKMAKERS less DraftKings),
with the ratings as of that quote's hour. The blend (c, beta, sigma) is fitted on
DraftKings' first posts of the earlier season only, as the live model's is, and
applied unchanged to both populations:

  A  DraftKings' first posted total (the live model's population; reproduces
     totals_b to the bet)
  B  games with no DraftKings total: the earliest other bettable book's first post

Prints only; reads the local cache (README). Stake: one unit to win, risk capped
at 3. 95% interval resampled by date.

    python -m scripts.ncaabw_research.totals_other_books
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config  # noqa: E402
import models.ncaab_total_blend as nb  # noqa: E402
import scripts.ncaab_total_blend_build as mb  # noqa: E402
import scripts.ncaabw_research.totals_b as tb  # noqa: E402
from scripts.ncaabw_research._paths import CACHE  # noqa: E402
from scripts.ncaabw_research.totals_a import load  # noqa: E402

OTHER = [b for b in config.BEST_LINE_BOOKMAKERS if b != "draftkings"]
CUTS = (0.03, 0.04, 0.05, 0.06, 0.08)


def first_posts(books, exclude_games=()):
    P = pd.read_parquet(CACHE / "pregame_quotes.parquet")
    t = P[(P["market"] == "totals") & (P["bookmaker"].isin(books))].copy()
    t = t.dropna(subset=["total_line", "over_price", "under_price"])
    t = t[(t["total_line"] >= tb.TOTAL_RANGE[0]) & (t["total_line"] <= tb.TOTAL_RANGE[1])]
    t = t[~t["game_id"].isin(set(exclude_games))]
    t = t.sort_values(["game_id", "last_update", "snapshot_ts"])
    first = t.groupby("game_id").head(1).copy()
    # when that same book next changed its total
    same = t.merge(first[["game_id", "bookmaker", "last_update"]].rename(columns={"last_update": "first_lu"}),
                   on=["game_id", "bookmaker"])
    nxt = (same[same["last_update"] > same["first_lu"]].groupby("game_id")["last_update"].min()
           .rename("next_change"))
    first = first.merge(nxt, on="game_id", how="left")
    first["quote_ns"] = first["last_update"].dt.as_unit("ns").astype("int64")
    first = first.rename(columns={"total_line": "line"})
    return first[["game_id", "bookmaker", "line", "over_price", "under_price", "quote_ns", "last_update",
                  "snapshot_ts", "next_change"]]


def main():
    t0 = time.time()
    A = tb.dk_first_totals()
    A["bookmaker"] = "draftkings"
    A["pop"] = "A"
    B = first_posts(OTHER, exclude_games=A["game_id"])
    B["pop"] = "B"
    g, box = load()
    g, b = mb.prepare(g, box)
    keep = set(g["game_id"])
    A = A[A["game_id"].isin(keep)]
    B = B[B["game_id"].isin(keep)]
    AB = pd.concat([A[B.columns.tolist()], B], ignore_index=True)
    print(f"A (DraftKings first post) {len(A):,} games; B (no DraftKings total, other book's first post) "
          f"{len(B):,} games; B by first book {B['bookmaker'].value_counts().to_dict()}")
    cut = dict(zip(AB["game_id"], AB["quote_ns"]))
    params = nb.Params.from_dict(mb.SETTINGS)
    preds, _ = mb.ratings_chain(g, cut, params, log=lambda *_: None)
    feats, _ = mb.features_all(g, b, AB)
    d = preds.merge(g[["game_id", "home_score", "away_score"]], on="game_id")
    d["total"] = d["home_score"] + d["away_score"]
    d = d.merge(feats, on="game_id", how="left")
    d = d[d["pt_s1"].notna() & d["total"].notna()].copy()
    rh = pd.Series(np.nan, index=d.index)
    for S in range(2017, int(d["season"].max()) + 1):
        coef = nb.fit_stage2(d[(d["season"] >= 2016) & (d["season"] < S)])
        te = d[d["season"] == S]
        rh.loc[te.index] = nb.residual(te, coef)
    d["pt"] = d["pt_s1"] + rh.fillna(0.0)
    x = d.merge(AB, on="game_id").merge(tb.consensus_close(), on="game_id", how="left")
    x["phase"] = [nb.phase_of(v) for v in x["game_date"]]
    print(f"scored with a model total: {len(x):,} ({x.groupby(['pop', 'season']).size().to_dict()}) "
          f"({time.time() - t0:.0f}s)")
    for (pop, s), xs in x.groupby(["pop", "season"]):
        print(f"  {pop} {s}: n {len(xs)}  line MAE {(xs['total'] - xs['line']).abs().mean():.2f}  "
              f"model MAE {(xs['total'] - xs['pt']).abs().mean():.2f}")
    folds = [("2025-26, blend from 2024-25 DraftKings first posts (walk-forward)", [2025], 2026),
             ("2026-27 to date, blend from 2024-26 (walk-forward)", [2025, 2026], 2027),
             ("2024-25, blend from 2025-26 (second look, not walk-forward)", [2026], 2025)]
    for label, tr_s, te_s in folds:
        blends = tb.fit_blends(x[(x["pop"] == "A") & x["season"].isin(tr_s)])
        if blends["all"] is None:
            continue
        print(f"\n{label}")
        for k, v in blends.items():
            if v:
                print(f"  blend {k}: c {v['c']:+.3f} beta {v['beta']:.3f} sigma {v['sigma']:.2f} n {v['n']}")
        for pop in ("A", "B"):
            te = x[(x["pop"] == pop) & (x["season"] == te_s)]
            if not len(te):
                print(f"  {pop}: no games")
                continue
            sc = tb.price_all(te, blends)
            print(f"  population {pop} ({len(te)} games)")
            for cutv in CUTS:
                tb.summarise(sc[sc["edge"] > cutv], f"{pop} edge > {cutv:.2f}")
            if pop == "B":
                bets = sc[sc["edge"] > 0.05]
                for book, z in bets.groupby("bookmaker"):
                    tb.summarise(z, f"B > 0.05 at {book}")
                tb.summarise(bets[bets["phase"] == "Nov"], "B > 0.05, November")
                tb.summarise(bets[bets["phase"] != "Nov"], "B > 0.05, December on")
                tb.summarise(bets[bets["side"] == "over"], "B > 0.05, overs")
                tb.summarise(bets[bets["side"] == "under"], "B > 0.05, unders")
                base = sc.copy(); base["side"] = "over"; base["price"] = base["over_price"]
                tb.summarise(base, "B every over, blind")
                base = sc.copy(); base["side"] = "under"; base["price"] = base["under_price"]
                tb.summarise(base, "B every under, blind")
    print(f"\ndone ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
