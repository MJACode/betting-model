"""The eleven's distributions against DraftKings' OWN alternate ladders.

DraftKings prices its standard line flat, but its alternate ladder is where
its prices vary: over 40.5 at -250, over 60.5 at +120, over 80.5 at +400.
Every one of those is a claim about the tail, and a distributional model
makes exactly that claim. This grades each model's fitted survival function
(the mean it projected plus the Gamma / negative-binomial tail the backtest
fitted for that season, carried in the dump's `art` column) against every
DK alternate strike quoted at or before the row's own snapshot.

The ladder is OVER-ONLY (no under price on 2025 rows; 2024 carries an under
on 21% of rows), so this is a test of the over tail, and the eleven project
low, so it is the side they are least likely to take. That is the point: a
model that is right about the tail wins here regardless of its bias at the
median.

Bets: one per (proposition, strike) where P_model(actual > strike) minus the
implied price clears the cut; graded at the DK alternate price, per season,
with the usual interval. Also reported: the model's calibration across the
ladder -- mean P_model vs realised frequency by strike bucket -- because a
tail that is wrong on average cannot be trusted where it disagrees most.

    python -m scripts.nfl_prop_dk_alt_ladder --rows <dump dir>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import config
from data import local_store
from data.ingestors.nfl_props_data_ingestor import norm_player_name
from models.market_relative import implied
from models.scorer import _nfl_prop_probs
from scripts.nfl_prop_information_test import grade, profit


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--cuts", nargs="+", type=float, default=[0.03, 0.05, 0.08, 0.12])
    a = ap.parse_args()
    rng = np.random.default_rng(42)
    local_store.activate()
    odds = local_store.read_table("nfl_prop_odds")
    alt = odds[(odds.bookmaker == "draftkings") & odds.market.str.endswith("_alternate")].copy()
    alt["norm"] = alt.player_name.map(norm_player_name)
    alt["ts"] = pd.to_datetime(alt.snapshot_at, utc=True, format="mixed")
    alt["base"] = alt.market.str.replace("_alternate", "", regex=False)
    groups = {k: g for k, g in alt.groupby(["game_id", "norm", "base"], sort=False)}
    print(f"DK alternate rows: {len(alt):,} over {len(groups):,} propositions")

    for f in sorted(Path(a.rows).glob("nfl_prop_*.csv")):
        mid = f.stem
        market = config.PROP_MODELS[mid][1]
        rows = pd.read_csv(f)
        if "art" not in rows.columns:
            print(f"{mid}: dump has no `art` column -- re-dump first"); continue
        rows["norm"] = rows.player.map(norm_player_name)
        rows["ts"] = pd.to_datetime(rows.snapshot_at, utc=True, format="mixed")
        cands = []                       # (season, strike-line ratio, p_model, price, went_over)
        for r in rows.itertuples(index=False):
            g = groups.get((r.game_id, r.norm, market))
            if g is None:
                continue
            g = g[g.ts <= r.ts].sort_values("ts").drop_duplicates("line", keep="last")
            art = json.loads(r.art)
            for q in g.itertuples(index=False):
                if q.over_price is None or not np.isfinite(float(q.over_price)):
                    continue
                strike = float(q.line)
                if r.actual == strike:
                    continue
                p_over, _pu, _pp = _nfl_prop_probs(art, float(r.pred), strike)
                cands.append((r.season, strike / max(r.line, 0.5), float(p_over),
                              float(q.over_price), float(r.actual) > strike))
        if not cands:
            print(f"\n{mid}: no DK alternate quotes for these rows"); continue
        c = pd.DataFrame(cands, columns=["season", "rel", "p", "price", "over"])
        c["imp"] = c.price.map(implied)
        c["edge"] = c.p - c.imp
        print(f"\n=== {mid}: {len(c):,} (row, strike) pairs, {c.season.value_counts().to_dict()} ===")
        print("  calibration by strike position (strike / main line):")
        for lo, hi in ((0, 0.6), (0.6, 0.85), (0.85, 1.15), (1.15, 1.5), (1.5, 9)):
            b = c[(c.rel >= lo) & (c.rel < hi)]
            if len(b) >= 50:
                print(f"    {lo:.2f}-{hi:.2f}: n={len(b):5d}  model P(over) {100*b.p.mean():5.1f}%  "
                      f"realised {100*b.over.mean():5.1f}%  DK implied {100*b.imp.mean():5.1f}%")
        print(f"  {'cut':>5} {'seas':>4} {'bets':>5} {'win%':>6} {'units':>9} {'ROI':>8}  90% CI")
        for cut in a.cuts:
            for season, g in c.groupby("season"):
                sel = g[g.edge >= cut]
                prof = np.array([profit(p, w) for p, w in zip(sel.price, sel.over)])
                print(f"  {cut:>5.0%} {season:>4} {grade(prof, rng) if len(prof) else '    0'}")


if __name__ == "__main__":
    main()
