"""Rebuild the EV breakpoints in models/nba_prop_rank.py from the two NBA prop models' graded bets.

The NBA prop door (scripts/nba_props_card.py) gives a game's one bet to the candidate with the
highest EV PERCENTILE WITHIN ITS OWN MODEL. The two models' EVs are on different scales (median
EV 0.020 for nba_prop_market, 0.083 for nba_prop_projection), so raw EV would hand nearly every
game to the projection model. This script reads the bets each model would have made at its LIVE
rule over 2023-24..2025-26 and prints each model's EV at the 0th, 1st, ... 100th percentile,
rounded to 4 decimals, ready to paste over BREAKPOINTS in models/nba_prop_rank.py.

The two bet lists are the ones the 2026-10-20 cap grade used (the same filters as its
grade_cap.load), each reproducing docs/thresholds.md to the unit:
  nba_prop_market     props_market_bets_sharp_ALL_under_prop_0.00.parquet, price >= -200, no
                      double- or triple-doubles: 24,572 bets, +781.3 units
  nba_prop_projection bets_card_arriving5.parquet (the 5 books the live feed returns), assists
                      overs removed, graded rows only: 66,588 bets, +2,392.8 units

    python -m scripts.nba_prop_rank_table
    python -m scripts.nba_prop_rank_table --market <parquet> --projection <parquet>
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

MARKET = "C:/Users/micha/AppData/Local/Temp/nba_rebuild/results/props_market_bets_sharp_ALL_under_prop_0.00.parquet"
PROJECTION = "C:/Users/micha/AppData/Local/Temp/nba_rebuild/proj/bets_card_arriving5.parquet"
N_BREAKS = 101


def market_ev(path: str) -> np.ndarray:
    m = pd.read_parquet(path)
    m = m[~m.market.isin(["player_double_double", "player_triple_double"]) & (m.price >= -200)]
    return m.ev.to_numpy(float)


def projection_ev(path: str) -> np.ndarray:
    p = pd.read_parquet(path)
    p = p[~((p.market == "player_assists") & (p.side == "over"))]
    p = p[p.result.isin(["W", "L", "P"])]
    return p.ev.to_numpy(float)


def breakpoints(ev: np.ndarray, n: int = N_BREAKS) -> list[float]:
    return [round(float(x), 4) for x in np.quantile(ev, np.linspace(0, 1, n))]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--market", default=MARKET)
    ap.add_argument("--projection", default=PROJECTION)
    a = ap.parse_args()
    for model_id, ev in (("nba_prop_market", market_ev(a.market)),
                         ("nba_prop_projection", projection_ev(a.projection))):
        q = breakpoints(ev)
        print(f"# {model_id}: {len(ev):,} bets, median EV {np.median(ev):.4f}, "
              f"{len(q) - len(set(q))} repeated breakpoint(s)")
        print(f'    "{model_id}": (')
        for i in range(0, len(q), 10):
            print("        " + ", ".join(f"{x:.4f}" for x in q[i:i + 10]) + ",")
        print("    ),")


if __name__ == "__main__":
    main()
