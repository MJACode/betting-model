"""
wnba_prop_sweep.py — leak-free 2026 re-sweep of ALL FIVE WNBA prop markets
(paused ones included) with the CURRENT active models, graded at real pre-tip
DraftKings prices under BOTH distribution heads.

WHY
---
Matt (2026-08-31): "you should be checking all prop bets as well, even paused
ones. We can use these models in the playoffs as well." The prior evidence per
market is a patchwork of eras (some sweeps predate the session-106 pre-tip
guard; some predate the -140 floor), and none of it ever asked whether the
POISSON HEAD is part of the problem: the points rebuild measured out-of-fold
residual variance at 3.2x the mean, and a Poisson head on an overdispersed
count overstates both tails — i.e. it manufactures edge that is not there and
buries edge that is. Every active WNBA prop model reads P(over) off a raw
Poisson. This script grades each market twice:

  poisson — exactly what production does today
  nbinom  — the same fitted means with a method-of-moments NB dispersion

If nbinom alone turns a market's grid from negative to a real plateau, the fix
is one artifact field (nb_r), not a rebuild.

DISPERSION HONESTY
------------------
The NB r is estimated from residuals on the newest season OUTSIDE the model's
train window when one exists (rebounds/assists: 2025 is genuine OOS). For the
2026-07-19 models (points/threes/pra) every pre-2026 season is in-sample, so r
comes from 2025 in-sample residuals — XGB fits its train data tightly, so the
excess variance is understated and r overshoots toward Poisson. That bias runs
AGAINST the NB head, so an NB improvement seen here is a floor, not a ceiling.

Everything else follows the pre-registered points-rebuild conventions: pre-tip
snapshot guard in Python, -140 blanket floor, plateau-not-peak reporting, and
the same STOP discipline. Requires DB access:

    python -m scripts.wnba_prop_sweep
    python -m scripts.wnba_prop_sweep --models wnba_prop_player_assists
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (  # noqa: E402
    MODEL_EDGE_THRESHOLDS,
    MODEL_MIN_ODDS,
    MODEL_PROB_THRESHOLDS,
    PROP_MODELS,
)
from data.db import get_connection  # noqa: E402
from features.wnba_prop_feature_engine import (  # noqa: E402
    build_bulk_wnba_prop_lookups,
    build_wnba_prop_training_dataset,
)
from models.scorer import american_to_implied_prob  # noqa: E402
from models.trainer import _nb_dispersion, load_model  # noqa: E402
from scripts.wnba_points_rebuild import (  # noqa: E402
    HOLDOUT_SEASON,
    MIN_CELL_BETS,
    _flat_profit,
    _nb_probs,
    _norm_name,
    fetch_pretip_lines,
    sweep,
    verdict,
)

WNBA_PROP_MODEL_IDS = [
    "wnba_prop_player_points",
    "wnba_prop_player_rebounds",
    "wnba_prop_player_assists",
    "wnba_prop_player_threes",
    "wnba_prop_player_pra",
]

ALL_SEASONS = list(range(2019, HOLDOUT_SEASON + 1))


def _poisson_probs(mu: float, line: float) -> tuple[float, float, float]:
    """Production's head: r -> infinity. Delegates so the two heads can never
    drift in push/line handling."""
    return _nb_probs(mu, line, nb_r=1e9)


def _dispersion_for(model_id: str, artifact: dict, datasets: dict) -> tuple[float, str]:
    """NB r from the newest season outside train_seasons (else 2025 in-sample)."""
    train_seasons = set(artifact.get("train_seasons") or [])
    oos = [s for s in ALL_SEASONS if s not in train_seasons and s < HOLDOUT_SEASON]
    season, basis = (max(oos), "OOS") if oos else (HOLDOUT_SEASON - 1, "in-sample")
    df = datasets[model_id]
    sl = df[df["season"] == season]
    if len(sl) < 200:
        return 500.0, f"{season} too thin — defaulting to Poisson"
    feats = [c for c in artifact["feature_cols"] if c in sl.columns]
    mu = np.clip(artifact["model"].predict(sl[feats].values.astype(float)), 1e-6, None)
    r = _nb_dispersion(sl["target"].values.astype(float), mu)
    return r, f"{season} {basis}"


def _grade(model_id: str, artifact: dict, df26: pd.DataFrame, lines: dict,
           head: str, nb_r: float) -> pd.DataFrame:
    feats = [c for c in artifact["feature_cols"] if c in df26.columns]
    floor = MODEL_MIN_ODDS.get(model_id, -140)
    mu_all = np.clip(artifact["model"].predict(df26[feats].values.astype(float)),
                     1e-6, None)
    rows = []
    for (_, r), mu in zip(df26.iterrows(), mu_all):
        dk = lines.get((r["game_id"], _norm_name(r["player_name"])))
        if dk is None:
            continue
        line = dk["line"]
        if head == "poisson":
            p_over, p_under, _p_push = _poisson_probs(mu, line)
        else:
            p_over, p_under, _p_push = _nb_probs(mu, line, nb_r)
        actual = float(r["target"])
        for side, prob, price in (("over", p_over, dk["over_price"]),
                                  ("under", p_under, dk["under_price"])):
            if price is None or float(price) < floor:
                continue
            price = float(price)
            pushed = actual == line
            won = (actual > line) if side == "over" else (actual < line)
            implied = american_to_implied_prob(price)
            rows.append({
                "game_id": r["game_id"], "player": r["player_name"],
                "game_date": r["game_date"], "month": str(r["game_date"])[:7],
                "side": side, "line": line, "price": price,
                "prob": prob, "implied": implied, "edge": prob - implied,
                "won": won, "pushed": pushed, "breakeven": implied,
                "profit": _flat_profit(won, pushed, price),
            })
    return pd.DataFrame(rows)


def _current_cut_record(model_id: str, sides: pd.DataFrame) -> str:
    """What production's own thresholds select from this side table."""
    pmin = MODEL_PROB_THRESHOLDS.get(model_id, 0.55)
    emin = MODEL_EDGE_THRESHOLDS.get(model_id, 0.05)
    sel = sides[(sides["prob"] >= pmin) & (sides["edge"] >= emin)]
    if sel.empty:
        return f"current cut {pmin}/{emin}: 0 bets"
    dec = sel[~sel["pushed"]]
    w = int(dec["won"].sum())
    roi = 100 * float(sel["profit"].sum()) / (100 * len(sel))
    return (f"current cut {pmin}/{emin}: {len(sel)} bets {w}-{len(dec) - w} "
            f"({100 * w / max(len(dec), 1):.1f}%), ROI {roi:+.2f}%")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--models", nargs="+", default=WNBA_PROP_MODEL_IDS)
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()

    conn = get_connection()
    try:
        bulk = build_bulk_wnba_prop_lookups(conn, ALL_SEASONS)
    finally:
        conn.close()

    results, dumps = {}, []
    for model_id in args.models:
        market = PROP_MODELS[model_id][1]
        logger.info(f"════ {model_id} ({market}) ════")
        try:
            artifact = load_model(model_id)
        except Exception as e:  # noqa: BLE001
            logger.error(f"{model_id}: cannot load active model ({e}) — skipped")
            continue

        # one dataset per model, all seasons, model's own feature list
        datasets = {model_id: build_wnba_prop_training_dataset(
            model_id, ALL_SEASONS, feature_cols=artifact["feature_cols"], bulk=bulk)}
        df26 = datasets[model_id][datasets[model_id]["season"] == HOLDOUT_SEASON]
        lines = fetch_pretip_lines(market=market)
        nb_r, r_basis = _dispersion_for(model_id, artifact, datasets)
        logger.info(f"{model_id}: {len(df26)} played rows, {len(lines)} pre-tip "
                    f"priced player-games, NB r={nb_r:.2f} ({r_basis})")

        for head in ("poisson", "nbinom"):
            sides = _grade(model_id, artifact, df26, lines, head, nb_r)
            if sides.empty:
                logger.warning(f"[{model_id}/{head}] no gradable sides")
                continue
            label = f"{model_id.removeprefix('wnba_prop_player_')}/{head}"
            logger.info(f"[{label}] {_current_cut_record(model_id, sides)}")
            grid = sweep(sides, label)
            results[(model_id, head)] = verdict(grid, sides, label)
            sides = sides.assign(model_id=model_id, head=head)
            dumps.append(sides)

    logger.info("════ SUMMARY ════")
    for (model_id, head), v in results.items():
        short = model_id.removeprefix("wnba_prop_player_")
        if v is None:
            logger.warning(f"{short:10s} {head:8s} STOP")
        else:
            logger.success(f"{short:10s} {head:8s} candidate: prob>={v['prob']} "
                           f"edge>={v['edge']} — {v['bets']} bets, ROI {v['roi']:+.2f}%")
    if args.csv and dumps:
        pd.concat(dumps).to_csv(args.csv, index=False)
        logger.info(f"Side rows written to {args.csv}")


if __name__ == "__main__":
    main()
