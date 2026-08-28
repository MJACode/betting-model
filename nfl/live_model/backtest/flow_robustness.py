"""
Stress the flow result against a SMARTER book.

    python -m live_model.backtest.flow_robustness

The main evaluation assumes a book prorates its opening line by raw CLOCK time.
If real books instead prorate by expected remaining OPPORTUNITIES, then part of
any measured edge is just "we account for pace and they do not", which a
competent book already does. This re-runs the same graded bets against three
progressively smarter anchors and reports how much of the edge survives each:

  time      accrued + baseline * (seconds remaining / 3600)
  plays     accrued + baseline * (expected remaining team plays / 62.6)
  script    the plays anchor, further adjusted for the run-pass split that the
            current score implies, which is the single most obvious adjustment
            a live trader would make by hand

An edge that survives the SCRIPT anchor is an edge over a book doing the
sensible manual thing. An edge that only exists against the TIME anchor is an
edge over a book doing the lazy thing, which is a real but much more fragile
claim and should be sized accordingly.

Nothing here refits a model. The model's predictions are held fixed and only
the number it is betting against changes, so any difference is attributable to
the anchor and not to a different fit.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from ..engine.prop_flow import FLOW_MARKETS
from .flow_eval import BREAKEVEN, GATES, MIN_BETS, load_rows, walk_forward

LEAGUE_PLAYS = 62.6
PASS_MARKETS = ("player_pass_yds", "player_pass_attempts",
                "player_pass_completions", "player_reception_yds",
                "player_receptions")


def anchors(d: pd.DataFrame, market: str) -> pd.DataFrame:
    """Three reconstructions of what the book's live number might be."""
    out = d.copy()
    frac = out["frac_remaining"].astype(float)
    base = out["baseline_per_game"].astype(float)
    acc = out["accrued"].astype(float)

    out["anchor_time"] = acc + base * frac

    # A trailing team runs more plays per remaining minute, a leading one
    # fewer. Measured on 2023-2024 the remaining rate is ~1.14 plays per
    # minute per team against a 1.04 full game rate.
    margin = out["team_margin"].astype(float)
    pace_adj = 1.0 + np.clip(-margin / 7.0, -1.5, 1.5) * 0.045
    exp_remaining_plays = LEAGUE_PLAYS * frac * pace_adj
    out["anchor_plays"] = acc + base * (exp_remaining_plays / LEAGUE_PLAYS)

    # Script: a trailing team throws more, so pass-family production is worth
    # more than the play count alone implies and rushing is worth less.
    lean = np.clip(-margin * 0.012 * (1.0 + (1.0 - frac)), -0.35, 0.35)
    mult = (1.0 + lean) if market in PASS_MARKETS else (1.0 - lean)
    out["anchor_script"] = acc + base * (exp_remaining_plays / LEAGUE_PLAYS) * mult
    return out


def grade_against(d: pd.DataFrame, anchor_col: str) -> pd.DataFrame:
    g = d.copy()
    g["line"] = g[anchor_col]
    g["deviation"] = g["model_final"] - g["line"]
    g["dev_frac"] = g["deviation"] / g["line"].clip(lower=0.5)
    g["side"] = np.where(g["deviation"] > 0, "over", "under")
    over_hit = g["actual_final"] > g["line"]
    g["won"] = np.where(g["side"] == "over", over_hit, ~over_hit).astype(float)
    g.loc[g["actual_final"] == g["line"], "won"] = np.nan
    return g


def best_gate(graded: pd.DataFrame) -> dict | None:
    best = None
    for gate in GATES:
        d = graded[graded["dev_frac"].abs() >= gate].dropna(subset=["won"])
        if len(d) < MIN_BETS:
            continue
        hit = float(d["won"].mean())
        if best is None or hit > best["hit"]:
            best = {"gate": gate, "n": int(len(d)), "hit": hit,
                    "edge_pp": (hit - BREAKEVEN) * 100,
                    "over_share": float((d["side"] == "over").mean())}
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=500)
    ap.add_argument("--markets", nargs="+", default=None)
    args = ap.parse_args()

    rows = load_rows()
    markets = args.markets or list(FLOW_MARKETS)

    print("\n=== how much edge survives a smarter book ===")
    print(f"breakeven {BREAKEVEN:.4f}; the model is held FIXED and only the "
          f"number it bets against changes\n")
    for market in markets:
        oos = walk_forward(rows, market, rounds=args.rounds)
        if oos.empty:
            print(f"{market:26s} skipped")
            continue
        a = anchors(oos, market)
        print(f"{market}")
        for label, col in (("time  (lazy book)", "anchor_time"),
                           ("plays (pace aware)", "anchor_plays"),
                           ("script(trader-like)", "anchor_script")):
            b = best_gate(grade_against(a, col))
            if b is None:
                print(f"  {label:20s} no gate reaches {MIN_BETS} bets")
                continue
            verdict = "clears" if b["hit"] > BREAKEVEN else "DEAD"
            print(f"  {label:20s} gate {b['gate']:.2f}  n={b['n']:6d}  "
                  f"hit {100*b['hit']:5.2f}%  edge {b['edge_pp']:+5.2f}pp  "
                  f"over {100*b['over_share']:3.0f}%   {verdict}")
        print()


if __name__ == "__main__":
    main()
