"""Grade nfl_prop_anytime_td — the one model both prior backtests skipped.

WHY IT WAS SKIPPED, and why that is not a small omission. scripts/nfl_prop_regrade
and scripts/nfl_prop_walkforward both require a two-way DraftKings quote so the
price can be de-vigged proportionally. Anytime TD is ONE-SIDED: docs §5d measured
141,116 rows, 88.7% with no under price. So the market map in those scripts
simply omits it, and anytime_td has been LIVE and ungraded — the only one of the
twelve never measured either way.

WHAT CHANGES FOR A ONE-WAY MARKET. There is no second side to de-vig against, so
the book's implied probability cannot be separated from its margin. That does not
block grading — the bet is still "yes at this price, did he score" — but it does
mean the edge is measured against a VIG-INCLUSIVE number, which makes the bar
strictly harder than for the two-way markets. Stated rather than hidden: a
positive result here is conservative, a negative one is not necessarily damning.

The juice is the story. §5d: anytime TD's base rate is ~27% and the book's
summed implied probability across a field runs far over 100%.

Walk-forward like nfl_prop_walkforward: weights refit per season on prior seasons
only, hyperparameters reused from the shipped artifact (a second-order leak that
runs in the model's favour, so a positive number is an upper bound).

    python -m scripts.nfl_anytime_td_grade
    python -m scripts.nfl_anytime_td_grade --seasons 2024 2025
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

import numpy as np

import config
from data.db import get_connection
from features.nfl_prop_feature_engine import build_nfl_prop_training_dataset
from models.trainer import RANDOM_STATE, load_model
from scripts.nfl_prop_regrade import implied, norm, profit
from scripts.nfl_prop_walkforward import FIRST_TRAIN_SEASON, _ci, _refit

MODEL_ID = "nfl_prop_anytime_td"
MARKET = "player_anytime_td"


def yes_prices(conn, season: int) -> dict:
    """{(norm player, game_id): over_price} — newest PRE-GAME DraftKings quote.

    over_price only: the under is absent on ~89% of rows, and requiring it would
    reduce the sample to the unrepresentative sliver that happens to have one.
    """
    rows = conn.execute("""
        SELECT DISTINCT ON (o.game_id, o.player_name)
               o.game_id, o.player_name, o.over_price
        FROM player_prop_odds o
        JOIN nfl_team_game_stats s ON s.game_id = o.game_id
        WHERE o.game_id LIKE %s AND o.bookmaker = 'draftkings'
          AND o.market = %s AND o.over_price IS NOT NULL
          AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
          AND o.snapshot_at::timestamptz <= s.commence_time
        ORDER BY o.game_id, o.player_name, o.snapshot_at DESC
    """, (f"NFL_{season}%", MARKET)).fetchall()
    return {(norm(p), g): float(op) for g, p, op in rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", type=int, default=[2023, 2024, 2025])
    a = ap.parse_args()
    rng = np.random.default_rng(RANDOM_STATE)
    conn = get_connection()

    art = load_model(MODEL_ID)
    if art is None:
        print(f"no artifact for {MODEL_ID}")
        return
    fc = art["feature_cols"]
    mp = config.MODEL_PROB_THRESHOLDS.get(MODEL_ID, 0.3)
    me = config.MODEL_EDGE_THRESHOLDS.get(MODEL_ID, 0.05)

    rows, quoted = [], 0
    for season in a.seasons:
        dtr = build_nfl_prop_training_dataset(MODEL_ID,
                                              list(range(FIRST_TRAIN_SEASON, season)))
        dte = build_nfl_prop_training_dataset(MODEL_ID, [season])
        if dtr is None or dte is None or dtr.empty or dte.empty:
            continue
        for d in (dtr, dte):
            for c in [c for c in fc if c not in d.columns]:
                d[c] = np.nan
        model = _refit(art, dtr[fc].values.astype(float),
                       dtr["target"].values.astype(float))
        preds = model.predict_proba(dte[fc].values.astype(float))[:, 1]

        book = yes_prices(conn, season)
        for i, r in enumerate(dte.itertuples(index=False)):
            key = (norm(r.player_name), r.game_id)
            if key not in book:
                continue
            quoted += 1
            price = book[key]
            p = float(preds[i])
            ip = implied(price)
            scored = float(r.target) > 0
            rows.append((season, p, ip, price, scored))
    conn.close()

    print(f"\nnfl_prop_anytime_td — walk-forward {a.seasons}, ONE-SIDED market")
    print(f"quoted player-games with a pre-game DK price and an actual: {quoted}")
    if not quoted:
        return

    base = 100 * np.mean([r[4] for r in rows])
    ours = 100 * np.mean([r[1] for r in rows])
    dk = 100 * np.mean([r[2] for r in rows])
    print(f"\nactual TD rate {base:.1f}%   our mean P {ours:.1f}%   "
          f"DK implied (vig included) {dk:.1f}%")
    print(f"the book's margin on this market is the {dk - base:+.1f}pp gap "
          f"between its price and reality")

    print(f"\ncurrent cut is p>={mp:.2f}, edge>={me:.2f}")
    print(f"{'min_edge':>9} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8} "
          f"{'90% CI':>18}")
    print("-" * 62)
    for e in (0.02, 0.05, 0.08, 0.10, 0.12, me, 0.20):
        sel = [r for r in rows if r[1] >= mp and r[1] - r[2] >= e]
        if len(sel) < 10:
            print(f"{e:>8.0%} {len(sel):>6}   (thin)")
            continue
        prof = [profit(r[3], r[4]) for r in sel]
        c = _ci([(0, 0, 0, 0, 0, p) for p in prof], rng)
        w = sum(1 for p in prof if p > 0)
        tag = "  <- current cut" if abs(e - me) < 1e-9 else ""
        print(f"{e:>8.0%} {len(sel):>6} {100*w/len(sel):>5.1f}% "
              f"{sum(prof):>+9.2f} {c[0]:>+7.2f}% "
              f"{'(' + format(c[1], '+.1f') + ', ' + format(c[2], '+.1f') + ')':>18}"
              f"{tag}")

    print(f"\nby season at the current cut")
    for s in a.seasons:
        sel = [r for r in rows if r[0] == s and r[1] >= mp and r[1] - r[2] >= me]
        if len(sel) < 10:
            print(f"   {s}: {len(sel):>4} bets  (thin)")
            continue
        prof = [profit(r[3], r[4]) for r in sel]
        print(f"   {s}: {len(sel):>4} bets  {100*np.mean(prof):>+7.2f}%")


if __name__ == "__main__":
    main()
