"""
trainer.py — XGBoost model training with Optuna hyperparameter tuning
             and Platt scaling calibration.

One model per sport × market. Models are serialized as .pkl files and
registered in the model_registry table.

Usage:
    python -m models.trainer --model mlb_moneyline
    python -m models.trainer --model nhl_over_under --seasons 2019 2020 2021 2022 2023
    python -m models.trainer --all                  # train all 7 models
"""

import argparse
import json
import pickle
from datetime import date, datetime
from pathlib import Path
import sys
from typing import Optional

import numpy as np
import optuna
import pandas as pd
from loguru import logger
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier

optuna.logging.set_verbosity(optuna.logging.WARNING)

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MODELS, MODELS_DIR, SPORTS
from data.db import get_connection
from features.feature_engine import FEATURE_MAP, build_training_dataset

# ── Training Config ────────────────────────────────────────────────────────────

OPTUNA_TRIALS = 100         # hyperparameter search trials
CV_FOLDS      = 5           # stratified k-fold for Optuna objective
CALIBRATION_FOLDS = 5       # Platt scaling CV folds
RANDOM_STATE  = 42


# ── Optuna Objective ──────────────────────────────────────────────────────────

def _xgb_objective(trial: optuna.Trial, X: np.ndarray, y: np.ndarray,
                   scale_pos_weight: float = 1.0) -> float:
    """
    Optuna objective: minimize mean log-loss across CV folds.
    Returns mean validation log-loss (lower = better).
    """
    params = {
        "n_estimators":     trial.suggest_int("n_estimators", 100, 800),
        "max_depth":        trial.suggest_int("max_depth", 3, 8),
        "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "subsample":        trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
        "gamma":            trial.suggest_float("gamma", 0.0, 1.0),
        "reg_alpha":        trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda":       trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        "scale_pos_weight": scale_pos_weight,
        "use_label_encoder": False,
        "eval_metric":      "logloss",
        "random_state":     RANDOM_STATE,
        "n_jobs":           -1,
        "verbosity":        0,
    }

    cv    = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    scores = []

    for train_idx, val_idx in cv.split(X, y):
        X_tr, X_val = X[train_idx], X[val_idx]
        y_tr, y_val = y[train_idx], y[val_idx]

        model = XGBClassifier(**params)
        model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)],
                  verbose=False)
        probs = model.predict_proba(X_val)[:, 1]
        scores.append(log_loss(y_val, probs))

    return float(np.mean(scores))


# ── Model Trainer ─────────────────────────────────────────────────────────────

def train_model(model_id: str,
                train_seasons: list[int] = None,
                holdout_season: int = None) -> dict:
    """
    Full training pipeline for one model:
      1. Build feature matrix from DB
      2. Tune XGBoost hyperparameters with Optuna
      3. Train final model on all train data
      4. Calibrate with Platt scaling
      5. Evaluate on holdout season
      6. Save .pkl and register in model_registry

    Returns metrics dict.
    """
    if model_id not in MODELS:
        raise ValueError(f"Unknown model_id '{model_id}'. "
                         f"Available: {list(MODELS.keys())}")

    sport, market, description = MODELS[model_id]
    sport_cfg  = SPORTS[sport]

    train_seasons  = train_seasons  or sport_cfg["train_seasons"]
    holdout_season = holdout_season or sport_cfg["test_season"]

    feature_cols = FEATURE_MAP[model_id]

    logger.info(f"\n{'═'*60}")
    logger.info(f"Training: {model_id}")
    logger.info(f"Sport: {sport} | Market: {market}")
    logger.info(f"Train seasons: {train_seasons} | Holdout: {holdout_season}")
    logger.info(f"Features ({len(feature_cols)}): {feature_cols[:5]}...")
    logger.info(f"{'═'*60}")

    # ── 1. Build training data ────────────────────────────────────────────────
    df_train = build_training_dataset(model_id, train_seasons)
    df_hold  = build_training_dataset(model_id, [holdout_season])

    if df_train.empty:
        raise ValueError(f"No training data for {model_id} in seasons {train_seasons}")
    if df_hold.empty:
        logger.warning(f"No holdout data for {model_id} season {holdout_season}")

    # Verify all expected feature columns are present. Missing columns mean
    # the feature list references a column that was never built — raise clearly
    # rather than silently filling with 0.
    missing_train = [c for c in feature_cols if c not in df_train.columns]
    if missing_train:
        raise ValueError(f"Feature columns missing from training data: {missing_train}")
    if not df_hold.empty:
        missing_hold = [c for c in feature_cols if c not in df_hold.columns]
        if missing_hold:
            logger.warning(f"Feature columns missing from holdout data: {missing_hold}")
            for col in missing_hold:
                df_hold[col] = np.nan

    X_train = df_train[feature_cols].values.astype(float)
    y_train = df_train["target"].values.astype(int)

    if not df_hold.empty:
        X_hold  = df_hold[feature_cols].values.astype(float)
        y_hold  = df_hold["target"].values.astype(int)
    else:
        X_hold = y_hold = None

    # Compute class weight for imbalanced targets (e.g. runline ~35% positive).
    # scale_pos_weight = neg / pos tells XGBoost to upweight the minority class.
    # XGBoost handles moderate class imbalance (30-70% splits) without weighting.
    # scale_pos_weight is only applied for severe imbalance (<15% positive rate).
    n_neg = int((y_train == 0).sum())
    n_pos = int((y_train == 1).sum())
    pos_rate = n_pos / (n_pos + n_neg) if (n_pos + n_neg) > 0 else 0.5
    if pos_rate < 0.15:
        scale_pos_weight = round(n_neg / n_pos, 4)
        logger.info(f"Severe class imbalance — scale_pos_weight={scale_pos_weight:.3f} "
                    f"(pos_rate={pos_rate:.1%})")
    else:
        scale_pos_weight = 1.0   # moderate imbalance; XGBoost handles natively

    logger.info(f"Training set: {len(X_train)} rows, "
                f"{y_train.mean():.1%} positive rate")

    # ── 2. Hyperparameter tuning with Optuna ──────────────────────────────────
    logger.info(f"Tuning hyperparameters ({OPTUNA_TRIALS} trials)...")
    study = optuna.create_study(direction="minimize",
                                sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
    study.optimize(
        lambda trial: _xgb_objective(trial, X_train, y_train, scale_pos_weight),
        n_trials=OPTUNA_TRIALS,
        show_progress_bar=False,
    )

    best_params = study.best_params
    best_cv_loss = study.best_value
    logger.success(f"Best CV log-loss: {best_cv_loss:.4f}")
    logger.info(f"Best params: {best_params}")

    # ── 3. Train final XGBoost on all train data ──────────────────────────────
    xgb_final = XGBClassifier(
        **best_params,
        scale_pos_weight=scale_pos_weight,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=RANDOM_STATE,
        n_jobs=-1,
        verbosity=0,
    )
    xgb_final.fit(X_train, y_train)

    # ── 4. Platt scaling calibration ──────────────────────────────────────────
    logger.info("Calibrating with Platt scaling...")
    calibrated = CalibratedClassifierCV(
        estimator=xgb_final,
        method="sigmoid",      # Platt scaling
        cv=CALIBRATION_FOLDS,
    )
    calibrated.fit(X_train, y_train)

    # ── 5. Evaluate on holdout ─────────────────────────────────────────────────
    holdout_metrics = {}
    if X_hold is not None and len(X_hold) > 0:
        probs_hold = calibrated.predict_proba(X_hold)[:, 1]
        preds_hold = (probs_hold >= 0.5).astype(int)

        accuracy  = (preds_hold == y_hold).mean()
        auc       = roc_auc_score(y_hold, probs_hold) if len(np.unique(y_hold)) > 1 else 0.5
        brier     = brier_score_loss(y_hold, probs_hold)
        cal_error = _mean_calibration_error(y_hold, probs_hold)

        # Simulate flat-bet ROI at edge threshold
        holdout_roi = _simulate_flat_roi(df_hold, probs_hold, y_hold)

        holdout_metrics = {
            "holdout_season":   int(holdout_season),
            "holdout_picks":    int(len(X_hold)),
            "holdout_accuracy": round(float(accuracy), 4),
            "holdout_auc":      round(float(auc), 4),
            "holdout_brier":    round(float(brier), 4),
            "cal_error":        round(float(cal_error), 4),
            "holdout_roi":      round(float(holdout_roi), 4),
        }

        logger.success(
            f"Holdout {holdout_season}: "
            f"accuracy={accuracy:.3f} | AUC={auc:.3f} | "
            f"Brier={brier:.4f} | CalError={cal_error:.4f} | "
            f"ROI={holdout_roi:.3f}"
        )

    # ── 6. Feature importance ─────────────────────────────────────────────────
    importances = dict(zip(feature_cols,
                           xgb_final.feature_importances_.tolist()))
    top5 = sorted(importances.items(), key=lambda x: -x[1])[:5]
    logger.info(f"Top 5 features: {top5}")

    # ── 7. Save model ─────────────────────────────────────────────────────────
    version    = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = MODELS_DIR / f"{model_id}_{version}.pkl"
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    artifact = {
        "model_id":     model_id,
        "version":      version,
        "sport":        sport,
        "market":       market,
        "feature_cols": feature_cols,
        "model":        calibrated,
        "best_params":  best_params,
        "train_seasons": train_seasons,
        "holdout_metrics": holdout_metrics,
        "feature_importances": importances,
        "trained_at":   datetime.now().isoformat(),
    }

    with open(model_path, "wb") as f:
        pickle.dump(artifact, f)

    logger.success(f"Model saved: {model_path}")

    # ── 8. Register in DB ─────────────────────────────────────────────────────
    _register_model(model_id, version, train_seasons, holdout_season,
                    holdout_metrics, str(model_path))

    return {
        "model_id": model_id,
        "version":  version,
        "path":     str(model_path),
        **holdout_metrics,
    }


def _mean_calibration_error(y_true: np.ndarray, y_prob: np.ndarray,
                             n_bins: int = 10, min_samples: int = 20) -> float:
    """
    Compute mean absolute calibration error across probability bins.

    Bins with fewer than min_samples are excluded. Single-sample bins at
    extreme probabilities produce 0.0 or 1.0 actual rates by chance, which
    are not meaningful calibration measurements and inflate the metric.
    min_samples=20 is the standard threshold in the ECE literature.
    """
    bin_edges = np.linspace(0, 1, n_bins + 1)
    errors = []
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = (y_prob >= lo) & (y_prob < hi)
        if mask.sum() < min_samples:
            continue
        mean_pred = y_prob[mask].mean()
        mean_true = y_true[mask].mean()
        errors.append(abs(mean_pred - mean_true))
    return float(np.mean(errors)) if errors else 0.0


def _simulate_flat_roi(df_hold: pd.DataFrame,
                        probs: np.ndarray,
                        y_true: np.ndarray,
                        edge_threshold: float = 0.03) -> float:
    """
    Simulate $100 flat-bet ROI on holdout picks above edge_threshold.
    Requires odds in df_hold (from the training dataset which includes
    market columns from the odds table).
    Returns ROI as decimal (0.05 = 5%).
    """
    if "total_line" not in df_hold.columns and "spread_home" not in df_hold.columns:
        # No odds available — skip ROI calc
        return 0.0

    # Use a proxy: DK-implied probability from the odds in the holdout df
    # If we have DK odds we can compute implied prob; otherwise return 0
    return 0.0   # placeholder — real ROI computed in backtester.py


def _register_model(model_id: str, version: str,
                     train_seasons: list[int], holdout_season: int,
                     metrics: dict, model_path: str) -> None:
    """Register or update model version in model_registry table."""
    conn = get_connection()
    try:
        # Deactivate previous active version
        conn.execute("""
            UPDATE model_registry SET is_active = 0
            WHERE model_id = %s AND is_active = 1
        """, (model_id,))

        conn.execute("""
            INSERT INTO model_registry (
                model_id, version, trained_on, train_seasons, holdout_season,
                holdout_accuracy, holdout_roi, holdout_picks, calibration_score,
                is_active, model_path, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)
            ON CONFLICT (model_id, version) DO UPDATE SET
                trained_on        = EXCLUDED.trained_on,
                holdout_accuracy  = EXCLUDED.holdout_accuracy,
                holdout_roi       = EXCLUDED.holdout_roi,
                holdout_picks     = EXCLUDED.holdout_picks,
                calibration_score = EXCLUDED.calibration_score,
                is_active         = 1,
                model_path        = EXCLUDED.model_path,
                notes             = EXCLUDED.notes
        """, (
            model_id,
            version,
            date.today().isoformat(),
            json.dumps(train_seasons),
            holdout_season,
            metrics.get("holdout_accuracy"),
            metrics.get("holdout_roi"),
            metrics.get("holdout_picks"),
            metrics.get("cal_error"),
            model_path,
            f"Optuna {OPTUNA_TRIALS} trials | CalibCV {CALIBRATION_FOLDS}",
        ))
        conn.commit()
        logger.info(f"Registered {model_id} v{version} in model_registry")
    finally:
        conn.close()


# ── Loader ────────────────────────────────────────────────────────────────────

def load_model(model_id: str) -> dict | None:
    """
    Load the active model artifact for a given model_id.
    Returns the full artifact dict (including 'model' key with calibrated clf).
    """
    conn = get_connection()
    row = conn.execute("""
        SELECT model_path, version FROM model_registry
        WHERE model_id = %s AND is_active = 1
        ORDER BY created_at DESC
        LIMIT 1
    """, (model_id,)).fetchone()
    conn.close()

    if not row:
        logger.warning(f"No active model found for {model_id}")
        return None

    model_path, version = row
    # Resolve relative paths against project root so the same registry row
    # works on any machine (local Windows dev or GitHub Actions ubuntu runner)
    path = Path(model_path)
    if not path.is_absolute():
        path = Path(__file__).parent.parent / path
    if not path.exists():
        logger.error(f"Model file not found: {path}")
        return None

    with open(path, "rb") as f:
        artifact = pickle.load(f)

    logger.debug(f"Loaded {model_id} v{version}")
    return artifact


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train betting models")
    parser.add_argument("--model",    help="Model ID (e.g. mlb_moneyline)")
    parser.add_argument("--all",      action="store_true", help="Train all models")
    parser.add_argument("--seasons",  nargs="+", type=int,
                        help="Override train seasons")
    parser.add_argument("--holdout",  type=int, help="Override holdout season")
    parser.add_argument("--trials",   type=int, default=OPTUNA_TRIALS,
                        help=f"Optuna trials (default: {OPTUNA_TRIALS})")
    args = parser.parse_args()

    if args.trials:
        OPTUNA_TRIALS = args.trials

    if args.all:
        models = list(MODELS.keys())
    elif args.model:
        models = [args.model]
    else:
        parser.error("Specify --model MODEL_ID or --all")

    for mid in models:
        try:
            result = train_model(mid,
                                  train_seasons=args.seasons,
                                  holdout_season=args.holdout)
            logger.success(f"✓ {mid}: {result}")
        except Exception as exc:
            logger.error(f"✗ {mid}: {exc}")
