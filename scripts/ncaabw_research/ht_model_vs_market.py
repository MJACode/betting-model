"""The halftime total's betting share by season and model fit: is this season's
fall the books or the model file? (2026-11-16, docs/sports/ncaabw.md, "Why the
women's record trails the men's")

The build's own replay (scripts/build_ncaabw_live_ht_artifact.py, the production
reading of the play list) with every model fit on every season: 2024-25 only,
2025-26 only, and both (the file the loop loads). For each, the share of decided
games whose deciding quote clears the cut, the November share, the share with EV
under 0.02, and the bets. If every fit bets about the same share of a season,
that season's books are what moved, not the model.

Prints only; reads the local research cache.

    python -m scripts.ncaabw_research.ht_model_vs_market
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import scripts.build_ncaabw_live_ht_artifact as B  # noqa: E402
from models import ncaabw_live_ht as M  # noqa: E402
from scripts.ncaabw_research._paths import CACHE  # noqa: E402


def share(dec, label):
    if not len(dec):
        print(f"  {label:44s} no decisions")
        return
    nov = dec[dec["game_date"].str[5:7] == "11"]
    bets = dec[dec["ev"] >= B.CUT]
    nov_share = (nov["ev"] >= B.CUT).mean() if len(nov) else float("nan")
    print(f"  {label:44s} decided {len(dec):5d}  bet share {(dec['ev'] >= B.CUT).mean():6.1%}  "
          f"November {len(nov):4d} games, bet share {nov_share:6.1%}  EV<0.02 {(dec['ev'] < 0.02).mean():6.1%}  "
          f"bets {len(bets)} {bets['units'].sum():+.2f}u")


def main():
    g = B.load_games()
    pri = B.priors()
    Q = pd.read_parquet(CACHE / "inplay_quotes.parquet")
    Q = Q[Q["market"] == "totals"].rename(columns={"bookmaker": "book", "last_update": "stamp"})
    Q = Q[["snapshot_ts", "game_id", "book", "stamp", "total_line", "over_price", "under_price"]]
    all_states, _ = B.load_states(g, set(pri.index) | set(Q["game_id"]))
    states = all_states["production"]
    for tr_s in ((2025, 2026), (2025,), (2026,)):
        model = M.fit(B.training(states, g, pri, tr_s))
        print(f"\nmodel fitted on seasons {tr_s}: mean {np.round(model.b, 4)}")
        for te_s in (2025, 2026, 2027):
            dec, _ = B.replay(Q, states, g, pri, model, te_s)
            tag = "in sample" if te_s in tr_s else "out of sample"
            share(dec, f"replayed on season {te_s} ({tag})")


if __name__ == "__main__":
    main()
