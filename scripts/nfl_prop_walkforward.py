"""Walk-forward the NFL prop models: train on prior seasons only, grade the next.

WHY. scripts/nfl_prop_regrade.py graded the shipped artifacts on 2025 -- their
only clean season -- and every confidence interval straddled zero: -1.18% over
564 bets excluding tackles, CI (-7.7, +5.3). The intervals are wide because it
is ONE season. This triples the sample by refitting per season so 2023 and 2024
become out-of-sample too, which the shipped artifacts can never be (2015-2024 is
their training data).

WHAT IS AND IS NOT REFIT, stated because it bounds the claim. The model WEIGHTS
are refit per season on prior seasons only -- that is the leak that matters and
it is closed. The HYPERPARAMETERS are reused from the shipped artifact's
best_params, which were tuned on 2015-2024 and therefore saw 2023 and 2024.
That is a real but second-order leak: it lets the search have known roughly how
deep a tree should be, not what any player did. Closing it too would mean 33
Optuna searches instead of 33 fits, hours instead of minutes, and the honest
trade is to run this now and say plainly what it does not control for.

Anything positive here is therefore an UPPER bound, and the interesting result
is the one this cannot flatter: if it still straddles zero with the
hyperparameters helping, it straddles zero.

Everything else follows the re-grade: real pre-game DraftKings two-way prices,
pushes returned rather than graded as losses, each model's own response
distribution, its current config cut, flat 1u, bootstrap intervals.

    python -m scripts.nfl_prop_walkforward
    python -m scripts.nfl_prop_walkforward --seasons 2024 2025
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

import numpy as np
from xgboost import XGBClassifier, XGBRegressor

import config
from data.db import get_connection
from features.nfl_prop_feature_engine import build_nfl_prop_training_dataset
from models.scorer import _nfl_prop_probs
from models.trainer import RANDOM_STATE, load_model
from scripts.nfl_prop_regrade import MARKET, implied, norm, profit

FIRST_TRAIN_SEASON = 2015


def lines_for(conn, market: str, season: int) -> dict:
    """Newest PRE-GAME DraftKings two-way quote per (player, game) for a season."""
    rows = conn.execute("""
        SELECT DISTINCT ON (o.game_id, o.player_name)
               o.game_id, o.player_name, o.line, o.over_price, o.under_price
        FROM player_prop_odds o
        JOIN nfl_team_game_stats s ON s.game_id = o.game_id
        WHERE o.game_id LIKE %s AND o.bookmaker = 'draftkings'
          AND o.market = %s AND o.line IS NOT NULL
          AND o.over_price IS NOT NULL AND o.under_price IS NOT NULL
          AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
          AND o.snapshot_at::timestamptz <= s.commence_time
        ORDER BY o.game_id, o.player_name, o.snapshot_at DESC
    """, (f"NFL_{season}%", market)).fetchall()
    return {(norm(p), g): (float(l), float(op), float(up))
            for g, p, l, op, up in rows}


def _refit(art: dict, X, y):
    """Same estimator and hyperparameters as the shipped artifact, new weights."""
    params = dict(art.get("best_params") or {})
    mt = art.get("model_type", "poisson")
    common = dict(random_state=RANDOM_STATE, n_jobs=-1, verbosity=0)
    if mt == "logistic":
        m = XGBClassifier(**params, objective="binary:logistic", **common)
    elif mt == "gamma":
        m = XGBRegressor(**params, objective="reg:squarederror", **common)
    else:
        m = XGBRegressor(**params, objective="count:poisson",
                         eval_metric="poisson-nloglik", **common)
    m.fit(X, y)
    return m


def walk(conn, mid: str, market: str, seasons: list[int]) -> list[tuple]:
    art = load_model(mid)
    if art is None:
        return []
    fc = art["feature_cols"]
    mt = art.get("model_type", "poisson")
    out = []
    for season in seasons:
        train_seasons = list(range(FIRST_TRAIN_SEASON, season))
        dtr = build_nfl_prop_training_dataset(mid, train_seasons)
        dte = build_nfl_prop_training_dataset(mid, [season])
        if dtr is None or dte is None or dtr.empty or dte.empty:
            continue
        for d in (dtr, dte):
            for c in [c for c in fc if c not in d.columns]:
                d[c] = np.nan
        model = _refit(art, dtr[fc].values.astype(float),
                       dtr["target"].values.astype(float))
        Xte = dte[fc].values.astype(float)
        preds = (model.predict_proba(Xte)[:, 1] if mt == "logistic"
                 else np.clip(model.predict(Xte), 1e-6, None))

        book = lines_for(conn, market, season)
        shim = dict(art)
        shim["model"] = model
        for i, r in enumerate(dte.itertuples(index=False)):
            key = (norm(r.player_name), r.game_id)
            if key not in book:
                continue
            line, op, up = book[key]
            actual = float(r.target)
            if actual == line:
                continue
            p_over, p_under, p_push = _nfl_prop_probs(shim, float(preds[i]), line)
            denom = max(1.0 - p_push, 1e-9)
            for side, p, price in (("over", p_over / denom, op),
                                   ("under", p_under / denom, up)):
                ip = implied(price)
                won = (actual > line) if side == "over" else (actual < line)
                out.append((season, side, p, ip, p - ip, profit(price, won)))
    return out


def _ci(rows, rng, draws: int = 20000):
    a = np.array([r[5] for r in rows])
    if len(a) < 10:
        return None
    idx = rng.integers(0, len(a), (draws, len(a)))
    roi = 100 * a[idx].mean(axis=1)
    return 100 * a.mean(), np.percentile(roi, 5), np.percentile(roi, 95)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", type=int, default=[2023, 2024, 2025])
    a = ap.parse_args()
    rng = np.random.default_rng(RANDOM_STATE)
    conn = get_connection()

    per = {}
    for mid, market in MARKET.items():
        rows = walk(conn, mid, market, a.seasons)
        mp = config.MODEL_PROB_THRESHOLDS.get(mid, 0.55)
        me = config.MODEL_EDGE_THRESHOLDS.get(mid, 0.05)
        per[mid] = [r for r in rows if r[2] >= mp and r[4] >= me]
        print(f"  {mid:26s} {len(per[mid]):>5} bets", flush=True)
    conn.close()

    print(f"\nWALK-FORWARD {a.seasons} -- weights refit per season, "
          f"hyperparameters reused (upper bound)")
    print(f"{'model':26s} {'bets':>5} {'win%':>6} {'units':>9} {'ROI':>8} "
          f"{'90% CI':>20}")
    print("-" * 80)
    for mid, rows in per.items():
        c = _ci(rows, rng)
        if c is None:
            print(f"{mid:26s} {len(rows):>5}   (thin)")
            continue
        w = sum(1 for r in rows if r[5] > 0)
        print(f"{mid:26s} {len(rows):>5} {100*w/len(rows):>5.1f}% "
              f"{sum(r[5] for r in rows):>+9.2f} {c[0]:>+7.2f}% "
              f"{'(' + format(c[1], '+.1f') + ', ' + format(c[2], '+.1f') + ')':>20}")

    allr = [r for rows in per.values() for r in rows]
    exr = [r for mid, rows in per.items()
           if mid != "nfl_prop_tackles_assists" for r in rows]
    print("-" * 80)
    for label, rows in (("ALL incl tackles", allr), ("ALL excl tackles", exr)):
        c = _ci(rows, rng)
        if c is None:
            continue
        w = sum(1 for r in rows if r[5] > 0)
        print(f"{label:26s} {len(rows):>5} {100*w/len(rows):>5.1f}% "
              f"{sum(r[5] for r in rows):>+9.2f} {c[0]:>+7.2f}% "
              f"{'(' + format(c[1], '+.1f') + ', ' + format(c[2], '+.1f') + ')':>20}")

    print(f"\nby season (excl tackles)")
    for s in a.seasons:
        rows = [r for r in exr if r[0] == s]
        c = _ci(rows, rng)
        if c is None:
            continue
        print(f"   {s}: {len(rows):>5} bets  {c[0]:>+7.2f}%  "
              f"({c[1]:+.1f}, {c[2]:+.1f})")


if __name__ == "__main__":
    main()
