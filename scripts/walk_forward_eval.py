"""Walk-forward evaluation: many out-of-sample reads instead of one.

mike, 2026-09-03: *"why holdout an entire season? why not hold out various
intervals of all seasons?"*

THE SEASON HOLDOUT IS RIGHT; ONE OF THEM IS NOT ENOUGH. Random intervals would
be worse, not better: every feature here is a rolling window
(`d_runs_last_5`, `d_runs_last_10`, `d_starter_era_last3`), so a held-out June
game is described by May games that would sit in the training set. The score
comes back flattering and nothing warns you. Holding out a whole season avoids
that by construction, and it matches the deployment condition — train on the
past, predict the future.

What a single season cannot tell you is whether the number is REAL. One season
is one draw: one ball, one rule set, one round of roster churn, and for
`mlb_f5_moneyline` about a thousand rows. A model that scores 0.60 once and a
model that scores 0.60 every year are the same number and completely different
propositions.

So this walks the seasons instead:

    train <= 2021  ->  test 2022
    train <= 2022  ->  test 2023
    ...
    train <= 2025  ->  test 2026

Every fold is honest in the same way the single holdout was, and there are five
or six of them. What you are looking for is not the best fold — it is whether
the folds AGREE. A model whose AUC swings 0.52 / 0.61 / 0.54 has no stable
edge however good its average looks, which is the same lesson §7 already
records for thresholds ("require a plateau, not a peak") applied to the model
itself.

Reads the same feature engine the trainer reads, so a result here is a result
about the model that would actually ship.

    python -m scripts.walk_forward_eval --model mlb_f5_moneyline
    python -m scripts.walk_forward_eval --model mlb_over_under --first-test 2023
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
from loguru import logger
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from xgboost import XGBClassifier

sys.path.insert(0, ".")

import config
from features.feature_engine import build_training_dataset

# Deliberately fixed rather than tuned per fold. The question here is whether
# the SIGNAL is stable across seasons; re-running Optuna inside every fold would
# add a second moving part and turn a clean comparison into a noisy one.
BASELINE_PARAMS = dict(
    n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8,
    colsample_bytree=0.8, min_child_weight=5, eval_metric="logloss",
    random_state=42, n_jobs=-1, verbosity=0,
)


def _frame(model_id: str, seasons: list[int]):
    out = build_training_dataset(model_id, seasons=seasons)
    return out[0] if isinstance(out, tuple) else out


def walk_forward(model_id: str, seasons: list[int], first_test: int,
                 features: list[str] | None = None) -> list[dict]:
    """One row per fold. Empty when no fold has enough data to be worth reading."""
    rows: list[dict] = []
    for test_season in [s for s in seasons if s >= first_test]:
        train_seasons = [s for s in seasons if s < test_season]
        if len(train_seasons) < 2:
            continue
        df_tr = _frame(model_id, train_seasons)
        df_te = _frame(model_id, [test_season])
        if df_tr.empty or df_te.empty:
            continue

        cols = features or [c for c in df_tr.columns
                            if c not in ("target", "game_id", "game_date",
                                         "sport", "home_team", "away_team")]
        cols = [c for c in cols if c in df_te.columns]
        X_tr = df_tr[cols].values.astype(float)
        y_tr = df_tr["target"].values.astype(int)
        X_te = df_te[cols].values.astype(float)
        y_te = df_te["target"].values.astype(int)
        if len(np.unique(y_te)) < 2:
            continue

        model = XGBClassifier(**BASELINE_PARAMS)
        model.fit(X_tr, y_tr, verbose=False)
        p = model.predict_proba(X_te)[:, 1]
        rows.append({
            "test_season": test_season,
            "train_rows": len(X_tr),
            "test_rows": len(X_te),
            "accuracy": round(accuracy_score(y_te, (p >= 0.5).astype(int)), 4),
            "auc": round(roc_auc_score(y_te, p), 4),
            "brier": round(brier_score_loss(y_te, p), 4),
            "base_rate": round(float(y_te.mean()), 4),
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--seasons", default="",
                    help="comma-separated; defaults to the sport's train_seasons")
    ap.add_argument("--first-test", type=int, default=0,
                    help="first season to TEST on (default: third available)")
    args = ap.parse_args()

    if args.model not in config.MODELS:
        raise SystemExit(f"unknown model {args.model!r}")
    sport = config.MODELS[args.model][0]
    seasons = ([int(s) for s in args.seasons.split(",") if s.strip()]
               or list(config.SPORTS[sport]["train_seasons"]))
    seasons = sorted(set(seasons))
    first_test = args.first_test or seasons[2]

    logger.info(f"walk-forward {args.model}: seasons {seasons}, "
                f"first test {first_test}")
    rows = walk_forward(args.model, seasons, first_test)
    if not rows:
        print("no fold had enough data to evaluate")
        return

    print(f"\n{args.model}")
    print(f"{'test':>6}{'train n':>9}{'test n':>8}{'base':>7}"
          f"{'acc':>8}{'AUC':>8}{'Brier':>8}")
    for r in rows:
        print(f"{r['test_season']:>6}{r['train_rows']:>9}{r['test_rows']:>8}"
              f"{r['base_rate']:>7.3f}{r['accuracy']:>8.4f}{r['auc']:>8.4f}"
              f"{r['brier']:>8.4f}")

    aucs = [r["auc"] for r in rows]
    # The spread is the point. A mean AUC hides a model that only worked once,
    # and "worked once" is what most of this repo's false positives looked like.
    print(f"\n{'':>6}{'':>9}{'':>8}{'':>7}{'mean AUC':>16}{np.mean(aucs):.4f}")
    print(f"{'':>6}{'':>9}{'':>8}{'':>7}{'min / max':>16}"
          f"{min(aucs):.4f} / {max(aucs):.4f}")
    print(f"{'':>6}{'':>9}{'':>8}{'':>7}{'folds > 0.55':>16}"
          f"{sum(1 for a in aucs if a > 0.55)} of {len(aucs)}")


if __name__ == "__main__":
    main()
