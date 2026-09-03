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

try:  # psycopg2 only for the BYTEA adapter; absent under sqlite tests
    import psycopg2
except Exception:  # noqa: BLE001
    psycopg2 = None
from pathlib import Path
import sys
from typing import Optional

import numpy as np
import optuna
import pandas as pd
from loguru import logger
from scipy import stats as scipy_stats
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import KFold
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score, mean_absolute_error
from sklearn.model_selection import KFold, StratifiedKFold, TimeSeriesSplit
from xgboost import XGBClassifier, XGBRegressor

optuna.logging.set_verbosity(optuna.logging.WARNING)

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (LIVE_MODELS, MODEL_PROB_THRESHOLDS, MODELS, MODELS_DIR,
                    PROP_MODELS, SPORTS, calibration_method)
from data.db import get_connection
from features.feature_engine import FEATURE_MAP, build_training_dataset
from features.prop_feature_engine import PROP_FEATURE_MAP, build_prop_training_dataset

# ── Training Config ────────────────────────────────────────────────────────────

OPTUNA_TRIALS = 100         # hyperparameter search trials
CV_FOLDS      = 5           # stratified k-fold for Optuna objective
CALIBRATION_FOLDS = 5       # Platt scaling CV folds
RANDOM_STATE  = 42

# NFL prop response-distribution bounds. The clips are guard rails, not tuning:
# a market whose moment estimate lands outside them has a pathological residual
# distribution and should be caught, not silently modelled.
_NB_R_MIN, _NB_R_MAX = 0.5, 500.0       # NB dispersion (r → ∞ is Poisson)
_GAMMA_K_MIN, _GAMMA_K_MAX = 0.15, 50.0  # Gamma shape (k = 1/relative variance)
_DISPERSION_FOLDS = 5


# ── Optuna Objective ──────────────────────────────────────────────────────────


def _time_ordered_cv(n_rows: int) -> TimeSeriesSplit:
    """Expanding-window folds: every validation set is LATER than its training set.

    THIS WAS StratifiedKFold(shuffle=True) UNTIL 2026-09-03, and the mismatch is
    the point. The final holdout has always been a whole season -- train on the
    past, predict the future, which is the job. But the hyperparameters were
    chosen on RANDOMLY SHUFFLED folds, so the tuner was scoring a different task:
    interpolating between games it had already seen.

    That is not a subtle distinction here. Every feature is a rolling window --
    d_runs_last_5, d_runs_last_10, d_starter_era_last3 -- so a shuffled fold puts
    a game's own neighbourhood on both sides of the split. The validation score
    comes back flattering, and 100 Optuna trials optimise toward it. The reported
    "best CV log-loss" was measuring leakage, not skill.

    mike, 2026-09-03, asking why the holdout is a whole season rather than
    intervals: the season holdout was never the weak part.

    Requires the rows to be in DATE ORDER -- train_model sorts the frame before
    building the arrays, and test_training_rows_are_date_ordered pins it. Without
    that sort this split is just an arbitrary partition wearing a better name.
    """
    return TimeSeriesSplit(n_splits=CV_FOLDS)


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

    cv    = _time_ordered_cv(len(y))
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


def _xgb_multiclass_objective(trial: optuna.Trial, X: np.ndarray, y: np.ndarray,
                              n_classes: int) -> float:
    """
    Optuna objective for multiclass models (UFC method of victory):
    minimize mean multiclass log-loss across stratified CV folds.
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
        "objective":        "multi:softprob",
        "num_class":        n_classes,
        "eval_metric":      "mlogloss",
        "random_state":     RANDOM_STATE,
        "n_jobs":           -1,
        "verbosity":        0,
    }

    cv = _time_ordered_cv(len(y))
    scores = []
    for train_idx, val_idx in cv.split(X, y):
        model = XGBClassifier(**params)
        model.fit(X[train_idx], y[train_idx],
                  eval_set=[(X[val_idx], y[val_idx])], verbose=False)
        probs = model.predict_proba(X[val_idx])
        scores.append(log_loss(y[val_idx], probs, labels=list(range(n_classes))))

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

    # 3-class problems: 'method' (UFC method of victory: 0=decision, 1=ko_tko,
    # 2=submission) and 'h2h_3way' (NHL regulation result: 0=away reg win,
    # 1=draw/OT, 2=home reg win). Everything else is binary.
    is_multiclass = market in ("method", "h2h_3way")
    n_classes = 3 if is_multiclass else 2

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

    # DATE ORDER IS LOAD-BEARING, not tidiness: _time_ordered_cv splits on
    # positional index, so an unsorted frame turns "train on the past, validate
    # on the future" into an arbitrary partition that merely looks principled.
    # The feature engine does not promise an order, so the sort happens here,
    # once, right before the arrays are built.
    if "game_date" in df_train.columns:
        df_train = df_train.sort_values("game_date", kind="mergesort")

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
    if is_multiclass:
        scale_pos_weight = 1.0   # not applicable to multi:softprob
        class_counts = {int(c): int((y_train == c).sum()) for c in np.unique(y_train)}
        logger.info(f"Training set: {len(X_train)} rows, class counts {class_counts}")
    else:
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
    if is_multiclass:
        study.optimize(
            lambda trial: _xgb_multiclass_objective(trial, X_train, y_train, n_classes),
            n_trials=OPTUNA_TRIALS,
            show_progress_bar=False,
        )
    else:
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
    if is_multiclass:
        xgb_final = XGBClassifier(
            **best_params,
            objective="multi:softprob",
            num_class=n_classes,
            eval_metric="mlogloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
            verbosity=0,
        )
    else:
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

    # ── 4. Probability calibration ────────────────────────────────────────────
    # Platt/sigmoid by default; config can override per model (see
    # config.MODEL_CALIBRATION_METHOD). Isotonic is the escape hatch for a model
    # that is systematically overconfident rather than uniformly shifted.
    cal_method = calibration_method(model_id)
    logger.info(f"Calibrating ({cal_method})...")
    calibrated = CalibratedClassifierCV(
        estimator=xgb_final,
        method=cal_method,
        cv=CALIBRATION_FOLDS,
    )
    calibrated.fit(X_train, y_train)

    # ── 5. Evaluate on holdout ─────────────────────────────────────────────────
    holdout_metrics = {}
    if X_hold is not None and len(X_hold) > 0 and is_multiclass:
        probs_hold = calibrated.predict_proba(X_hold)
        preds_hold = probs_hold.argmax(axis=1)

        accuracy = (preds_hold == y_hold).mean()
        try:
            auc = roc_auc_score(y_hold, probs_hold, multi_class="ovr",
                                average="macro", labels=list(range(n_classes)))
        except ValueError:
            auc = 0.5
        mlogloss = log_loss(y_hold, probs_hold, labels=list(range(n_classes)))
        # Per-class one-vs-rest calibration error, averaged
        cls_errors = [
            _mean_calibration_error((y_hold == c).astype(int), probs_hold[:, c])
            for c in range(n_classes)
        ]
        cal_error = float(np.mean(cls_errors))

        holdout_metrics = {
            "holdout_season":   int(holdout_season),
            "holdout_picks":    int(len(X_hold)),
            "holdout_accuracy": round(float(accuracy), 4),
            "holdout_auc":      round(float(auc), 4),
            "holdout_mlogloss": round(float(mlogloss), 4),
            "cal_error":        round(cal_error, 4),
            "holdout_roi":      0.0,   # prob-only market — ROI from backtester
        }

        logger.success(
            f"Holdout {holdout_season}: "
            f"accuracy={accuracy:.3f} | AUC(ovr)={auc:.3f} | "
            f"mlogloss={mlogloss:.4f} | CalError={cal_error:.4f}"
        )

    elif X_hold is not None and len(X_hold) > 0:
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
    model_path = _output_dir() / f"{model_id}_{version}.pkl"
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
                    holdout_metrics, model_path.relative_to(MODELS_DIR.parent.parent).as_posix())

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



def _calibration_error_weighted(y_true: np.ndarray, y_prob: np.ndarray,
                                n_bins: int = 10, min_samples: int = 20,
                                min_prob: float | None = None) -> float:
    """Sample-weighted ECE, optionally restricted to the ACTIONABLE range.

    `_mean_calibration_error` above is kept unchanged because every historical
    `model_registry.calibration_score` was measured with it, and redefining it
    in place would silently change what every past row means. But it is wrong
    for a go-live gate in two ways, and both matter:

    1. **It averages bins unweighted.** A bin holding 20 predictions counts as
       much as one holding 5,000. Standard ECE weights by bin population.
    2. **It averages over the whole probability range.** Most of a model's mass
       sits near 0.5, where these models are well calibrated; the bins that get
       BET are a small minority and their error is diluted away.

    Measured 2026-08-30, that is not theoretical. Thirteen live models are
    6-16pp overconfident at the probabilities actually bet, and every one of
    them passed the <=5% gate on the old metric. `mlb_live_total_runs` was
    already 9-10pp over on its OWN 2025 holdout the day it shipped.

    Pass `min_prob` to measure only where money is placed -- normally the
    model's own `MODEL_PROB_THRESHOLDS` entry.
    """
    if min_prob is not None:
        keep = y_prob >= min_prob
        y_true, y_prob = y_true[keep], y_prob[keep]
    if len(y_prob) == 0:
        return 0.0
    edges = np.linspace(0, 1, n_bins + 1)
    total_err = 0.0
    total_n = 0
    for i in range(n_bins):
        mask = (y_prob >= edges[i]) & (y_prob < edges[i + 1])
        n = int(mask.sum())
        if n < min_samples:
            continue
        total_err += n * abs(y_prob[mask].mean() - y_true[mask].mean())
        total_n += n
    return float(total_err / total_n) if total_n else 0.0


def calibration_metrics(model_id: str, y_true: np.ndarray,
                        y_prob: np.ndarray) -> dict:
    """The three numbers a go-live decision needs, not just the legacy one."""
    floor = MODEL_PROB_THRESHOLDS.get(model_id)
    return {
        # legacy, unchanged, so historical registry rows keep their meaning
        "cal_error": _mean_calibration_error(y_true, y_prob),
        "cal_error_weighted": _calibration_error_weighted(y_true, y_prob),
        # the one that decides: calibration where the model actually bets
        "cal_error_actionable": _calibration_error_weighted(
            y_true, y_prob, min_prob=floor),
        "cal_floor": floor,
    }

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


# When False, a training run writes its artifact to models/saved/_baseline/ and
# does NOT touch model_registry. That combination is the point: every training
# run otherwise deactivates the live version and activates the new one, so a
# throwaway comparison run (a matched baseline before a feature change, say)
# silently swaps production to a model whose .pkl is not committed -- which is
# the "uncommitted artifact is a silent outage" failure, arrived at by someone
# who thought they were only measuring. Set via --no-register.
REGISTER_TRAINED_MODELS = True


def _output_dir():
    """Where this run's .pkl goes. Baselines are kept out of models/saved/ so
    they cannot be mistaken for a real artifact -- by a person, by `git add`,
    or by tests/test_feature_artifact_agreement.py, which reads the newest
    file per model id."""
    d = MODELS_DIR if REGISTER_TRAINED_MODELS else MODELS_DIR / "_baseline"
    d.mkdir(parents=True, exist_ok=True)
    return d


ARTIFACT_DDL = """
CREATE TABLE IF NOT EXISTS model_artifacts (
    model_path  TEXT PRIMARY KEY,
    model_id    TEXT NOT NULL,
    version     TEXT NOT NULL,
    stored_at   TEXT NOT NULL,
    size_bytes  INTEGER NOT NULL,
    payload     BYTEA NOT NULL
)
"""

# The table holds the .pkl PAYLOADS the scorer loads when the file is missing
# from disk (see load_model), so a row here IS a model. Supabase's default
# privileges hand anon and authenticated the full arwdDxtm on anything created
# in `public`, and REVOKE ... FROM PUBLIC does not touch a named role -- so
# without this the app's own anon key could UPDATE a payload and change what
# every model predicts, or DELETE one and take the model offline.
#
# It has to live beside the CREATE rather than in a migration, because
# _store_artifact creates the table on demand: a one-off revoke is undone by
# the next retrain that runs against a database where the table does not yet
# exist. Found 2026-09-03 -- the table reappeared with the full grant between
# one sweep of the schema and the next.
#
# Nothing in mobile/src references model_artifacts, so there is no app surface
# to preserve.
ARTIFACT_REVOKE = "REVOKE ALL ON model_artifacts FROM anon, authenticated"


def _store_artifact(conn, model_id: str, version: str, path) -> None:
    """Copy a trained .pkl into Supabase, keyed by its registry path.

    WHY. A retrain that runs on the Railway worker writes its artifact to
    CONTAINER DISK, and the registry row then points at a path that the next
    deploy destroys. That is the "an uncommitted .pkl is a silent outage"
    failure with a new cause: not a person forgetting to `git add`, but a
    filesystem that does not survive. Training in the cloud is only safe once
    the artifact outlives the container, and CLAUDE.md 1b already says where
    extracted data belongs -- Supabase, not a disk nobody backs up.

    Best-effort: a failed upload must not lose a model that trained correctly.
    It is logged loudly, because the failure mode it guards against is exactly
    the silent one.
    """
    try:
        data = Path(path).read_bytes()
        rel = Path(path).relative_to(MODELS_DIR.parent.parent).as_posix()
        conn.execute(ARTIFACT_DDL)
        conn.execute(ARTIFACT_REVOKE)
        conn.execute("""
            INSERT INTO model_artifacts
                (model_path, model_id, version, stored_at, size_bytes, payload)
            VALUES (%(p)s, %(m)s, %(v)s, %(t)s, %(n)s, %(b)s)
            ON CONFLICT (model_path) DO UPDATE SET
                model_id = EXCLUDED.model_id, version = EXCLUDED.version,
                stored_at = EXCLUDED.stored_at, size_bytes = EXCLUDED.size_bytes,
                payload = EXCLUDED.payload
        """, {"p": rel, "m": model_id, "v": version,
              "t": datetime.now().isoformat(), "n": len(data),
              "b": psycopg2.Binary(data) if psycopg2 else data})
        conn.commit()
        logger.success(f"Artifact stored in Supabase: {rel} ({len(data):,} bytes)")
    except Exception as exc:  # noqa: BLE001 — see docstring
        logger.error(f"Could not store artifact for {model_id} in Supabase: {exc}. "
                     "If this trained on the worker, the .pkl will NOT survive the "
                     "next deploy — commit it from models/saved/ before then.")
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass


def _restore_artifact(conn, model_path: str):
    """Write a stored artifact back to disk. Returns the path, or None.

    The other half of the contract: `load_model` calls this when the registry
    names a file the container does not have, which is precisely what happens
    on the first deploy after a cloud retrain.
    """
    try:
        row = conn.execute(
            "SELECT payload FROM model_artifacts WHERE model_path = %s",
            (model_path,)).fetchone()
    except Exception as exc:  # noqa: BLE001 — a missing table is not an error here
        logger.warning(f"model_artifacts unavailable: {exc}")
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None
    if not row or row[0] is None:
        return None
    dest = MODELS_DIR.parent.parent / model_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(bytes(row[0]))
    logger.success(f"Restored {model_path} from Supabase ({dest.stat().st_size:,} bytes)")
    return dest


def _register_model(model_id: str, version: str,
                     train_seasons: list[int], holdout_season: int,
                     metrics: dict, model_path: str) -> None:
    """Register or update model version in model_registry table."""
    if not REGISTER_TRAINED_MODELS:
        logger.warning(
            f"--no-register: {model_id} {version} was NOT registered and the "
            f"live version is untouched. Artifact: {model_path}"
        )
        return
    conn = get_connection()
    # Store the bytes BEFORE the registry row points at them. Registering first
    # and uploading second leaves a window where the active model is a path
    # nothing can produce -- which is the outage this is here to prevent.
    _store_artifact(conn, model_id, version, MODELS_DIR.parent.parent / model_path)
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


# ── Poisson Prop Trainer ──────────────────────────────────────────────────────

def _poisson_objective(trial: optuna.Trial, X: np.ndarray, y: np.ndarray) -> float:
    """
    Optuna objective for Poisson regression: minimize mean Poisson NLL across CV folds.
    Uses KFold (not stratified — target is a count, not a class).
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
        "objective":        "count:poisson",
        "eval_metric":      "poisson-nloglik",
        "random_state":     RANDOM_STATE,
        "n_jobs":           -1,
        "verbosity":        0,
    }

    kf = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    scores = []

    for train_idx, val_idx in kf.split(X):
        X_tr, X_val = X[train_idx], X[val_idx]
        y_tr, y_val = y[train_idx], y[val_idx]

        model = XGBRegressor(**params)
        model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
        mu = np.clip(model.predict(X_val), 1e-6, None)
        nll = -float(np.mean(scipy_stats.poisson.logpmf(y_val.astype(int), mu)))
        scores.append(nll)

    return float(np.mean(scores))


def _squared_objective(trial: optuna.Trial, X: np.ndarray, y: np.ndarray) -> float:
    """CV RMSE objective for the continuous (yardage) mean model."""
    params = {
        "n_estimators":     trial.suggest_int("n_estimators", 150, 700),
        "max_depth":        trial.suggest_int("max_depth", 3, 7),
        "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
        "subsample":        trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 30),
        "reg_lambda":       trial.suggest_float("reg_lambda", 0.5, 10.0, log=True),
    }
    kf = KFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)
    scores = []
    for tr, te in kf.split(X):
        m = XGBRegressor(**params, objective="reg:squarederror",
                         random_state=RANDOM_STATE, n_jobs=-1, verbosity=0)
        m.fit(X[tr], y[tr])
        scores.append(float(np.sqrt(np.mean((y[te] - m.predict(X[te])) ** 2))))
    return float(np.mean(scores))


def _poisson_calibration_error(y_true: np.ndarray, mu: np.ndarray,
                                 n_bins: int = 10, min_samples: int = 20) -> float:
    """
    Mean absolute calibration error for a Poisson model.
    Bins rows by predicted lambda; in each bin, compares actual mean count to
    predicted mean lambda. Bins with < min_samples are excluded.
    """
    bin_edges = np.percentile(mu, np.linspace(0, 100, n_bins + 1))
    errors = []
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = (mu >= lo) & (mu <= hi) if i == n_bins - 1 else (mu >= lo) & (mu < hi)
        if mask.sum() < min_samples:
            continue
        errors.append(abs(mu[mask].mean() - y_true[mask].mean()))
    return float(np.mean(errors)) if errors else 0.0



def poisson_probability_metrics(model_id: str, y_true: np.ndarray,
                                mu: np.ndarray) -> dict:
    """Calibration of the probability a Poisson model actually BETS.

    `_poisson_calibration_error` checks the COUNT fit — bin by predicted lambda,
    compare mean lambda to mean actual. `mlb_live_total_runs` is excellent by
    that measure (bias -0.072 runs on 2026) and shipped on it.

    But nothing bets lambda. The scorer bets P(over) = the Poisson tail at the
    live line, a transformation applied at SERVE time that training never
    evaluated — so the model went live with an unmeasured probability layer, and
    that layer is where the error was: measured 2026-08-30 on its own 2025
    holdout, 287,334 priced states, the derived probability is 9-10pp
    overconfident and fails the 5% gate on every probability-scale metric.

    Prices each state across a spread of candidate lines around its own
    expectation, so a natural range of claimed probabilities appears rather than
    the ~50% a fair line alone would give.
    """
    from scipy.stats import poisson as _poisson

    ps, ws = [], []
    for off in (-3.5, -2.5, -1.5, 1.5, 2.5, 3.5):
        line = np.maximum(0.5, np.round((mu + off) * 2) / 2)
        p_over = 1.0 - _poisson.cdf(np.floor(line), mu)
        won_over = y_true > line
        prefer_over = p_over >= 0.5
        ps.append(np.where(prefer_over, p_over, 1 - p_over))
        ws.append(np.where(prefer_over, won_over, ~won_over))
    p = np.concatenate(ps)
    y = np.concatenate(ws).astype(float)
    return {f"prob_{k}": v for k, v in calibration_metrics(model_id, y, p).items()}

def _over_under_accuracy(y_true: np.ndarray, mu: np.ndarray,
                          lines: np.ndarray | None = None) -> float:
    """
    For each row, evaluate P(actual > line) vs the actual outcome.
    When lines is None, uses the median K count in the test set as a uniform line
    (simulates a typical DK prop line when real lines aren't available).
    Returns fraction of correct over/under decisions.
    """
    if lines is None:
        # Synthetic line: median actual count minus 0.5 (standard half-point DK line).
        # Clamped to 0.5 minimum — rare-event props (HR, SB) have median=0, which would
        # produce a negative line where both predict_over and actually_over are trivially True.
        line = max(float(np.median(y_true)) - 0.5, 0.5)
        lines = np.full(len(y_true), line)

    correct = 0
    for actual, lam, line in zip(y_true.astype(int), mu, lines):
        # P(actual > line) = P(actual >= ceil(line)) = 1 - CDF(floor(line))
        threshold = int(np.floor(line))
        p_over = 1.0 - scipy_stats.poisson.cdf(threshold, lam)
        predict_over = p_over >= 0.5
        actually_over = actual > line
        correct += int(predict_over == actually_over)

    return round(correct / len(y_true), 4)


# ── Response-distribution helpers (NFL props) ─────────────────────────────────
#
# The platform's other prop models are Poisson-mean-only: fit E[X], then read
# P(over) off a Poisson CDF. That is wrong for most NFL markets — NFL yardage
# has a variance-to-mean ratio of 27-36 and even the count markets are
# overdispersed — so the NFL heads fit a mean AND a dispersion, and the scorer
# reads P(over) off the distribution the model was validated under.
#
# Dispersion is estimated from OUT-OF-FOLD predictions, never from in-sample
# residuals: a fitted model's own residuals are too small, which would make
# every predictive distribution too tight and every P(over) overconfident —
# the exact failure the dispersion is there to prevent.

def _oof_predictions(params: dict, X: np.ndarray, y: np.ndarray,
                     objective: str, folds: int = 5) -> np.ndarray:
    """Out-of-fold predicted means, for honest dispersion estimation."""
    oof = np.zeros(len(y), dtype=float)
    kf = KFold(n_splits=folds, shuffle=True, random_state=RANDOM_STATE)
    for tr, te in kf.split(X):
        m = XGBRegressor(**params, objective=objective, random_state=RANDOM_STATE,
                         n_jobs=-1, verbosity=0)
        m.fit(X[tr], y[tr])
        oof[te] = m.predict(X[te])
    return oof


def _nb_dispersion(y: np.ndarray, mu: np.ndarray) -> float:
    """
    Negative-binomial `r` by method of moments: Var = mu + mu^2 / r.

    Returned large (≈ Poisson) when the excess variance is non-positive, so an
    equidispersed market degrades to Poisson rather than to nonsense.
    """
    mu = np.clip(mu, 1e-6, None)
    excess = float(np.mean((y - mu) ** 2 - mu))
    if excess <= 0:
        return _NB_R_MAX
    return float(np.clip(np.mean(mu ** 2) / excess, _NB_R_MIN, _NB_R_MAX))


def _gamma_shape(y: np.ndarray, m: np.ndarray) -> float:
    """Gamma shape k = 1/phi from the relative-residual dispersion Var = phi*m^2."""
    m = np.clip(m, 1e-6, None)
    phi = float(np.mean(((y - m) / m) ** 2))
    if phi <= 0:
        return _GAMMA_K_MAX
    return float(np.clip(1.0 / phi, _GAMMA_K_MIN, _GAMMA_K_MAX))


def _pit_calibration_error(u: np.ndarray, bins: int = 10) -> float:
    """
    How far the probability integral transform is from uniform.

    If the predictive distribution is right, F_i(y_i) is uniform on [0,1]. This
    is the line-free way to score a whole distribution — it needs no betting
    line, so it cannot be gamed by choosing where to put one. 0 is perfect;
    values are on the same scale as the calibration errors elsewhere in this
    file (mean absolute gap per decile).
    """
    u = np.clip(np.asarray(u, dtype=float), 0.0, 1.0)
    edges = np.linspace(0, 1, bins + 1)
    observed = np.histogram(u, bins=edges)[0] / max(len(u), 1)
    return float(np.mean(np.abs(observed - 1.0 / bins)) * bins / 2)


def _nb_pit(y: np.ndarray, mu: np.ndarray, r: float,
            rng: np.random.Generator) -> np.ndarray:
    """Randomised PIT for a discrete NB — without randomisation a count PIT is
    lumpy by construction and would read as miscalibration."""
    from scipy import stats
    p = r / (r + np.clip(mu, 1e-6, None))
    lo = stats.nbinom.cdf(y - 1, r, p)
    hi = stats.nbinom.cdf(y, r, p)
    return lo + rng.random(len(y)) * (hi - lo)


def _zig_pit(y: np.ndarray, mu: np.ndarray, k: float, p0: float,
             rng: np.random.Generator) -> np.ndarray:
    """PIT for the zero-inflated Gamma; the point mass at 0 is randomised."""
    from scipy import stats
    m = np.clip(mu, 1e-6, None) / max(1.0 - p0, 1e-6)
    pos = stats.gamma.cdf(np.clip(y, 1e-9, None), a=k, scale=m / k)
    u = p0 + (1.0 - p0) * pos
    zero = y <= 0
    u[zero] = rng.random(int(zero.sum())) * p0
    return u


def train_prop_model(model_id: str,
                     train_seasons: list[int] = None,
                     holdout_season: int = None,
                     n_trials: int = None) -> dict:
    """
    Prop model training pipeline — Poisson (count stats) or logistic (rare binary events).

    model_type is read from PROP_MODELS config:
      "poisson"  → XGBRegressor (count:poisson); scorer uses Poisson CDF
      "logistic" → XGBClassifier + Platt scaling; scorer uses predict_proba directly

    Steps:
      1. Build feature matrix from player_game_log + Savant + context tables
      2. Tune hyperparameters with Optuna
      3. Train final model on all train data
      4. Evaluate on holdout season
      5. Save .pkl and register in model_registry

    Returns metrics dict.
    """
    from config import PROP_MODELS, SPORTS
    from data import local_store

    # Training is offline: read the pulled cache when one exists. Scoring never
    # activates it, so the live path always sees the database.
    local_store.activate()

    if model_id not in PROP_MODELS:
        raise ValueError(f"Unknown prop model_id '{model_id}'. "
                         f"Available: {list(PROP_MODELS.keys())}")

    sport, market, model_type, note = PROP_MODELS[model_id]
    sport_cfg = SPORTS[sport]

    # WNBA/NBA props use their own feature map + dataset builder; MLB uses the
    # pitcher/batter engine. Select per sport so the trainer stays generic.
    if sport == "WNBA":
        from features.wnba_prop_feature_engine import (
            WNBA_PROP_FEATURE_MAP, build_wnba_prop_training_dataset,
        )
        feature_cols     = WNBA_PROP_FEATURE_MAP[model_id]
        _build_prop_data = build_wnba_prop_training_dataset
    elif sport == "NBA":
        from features.nba_prop_feature_engine import (
            NBA_PROP_FEATURE_MAP, build_nba_prop_training_dataset,
        )
        feature_cols     = NBA_PROP_FEATURE_MAP[model_id]
        _build_prop_data = build_nba_prop_training_dataset
    elif sport == "NFL":
        from features.nfl_prop_feature_engine import (
            NFL_PROP_FEATURE_MAP, build_nfl_prop_training_dataset,
        )
        feature_cols     = NFL_PROP_FEATURE_MAP[model_id]
        _build_prop_data = build_nfl_prop_training_dataset
    else:
        feature_cols     = PROP_FEATURE_MAP[model_id]
        _build_prop_data = build_prop_training_dataset

    train_seasons  = train_seasons  or sport_cfg["train_seasons"]
    holdout_season = holdout_season or sport_cfg["test_season"]
    trials         = n_trials or OPTUNA_TRIALS

    logger.info(f"\n{'═'*60}")
    logger.info(f"Training prop model: {model_id}  [{model_type}]")
    logger.info(f"Market: {market} | Sport: {sport}")
    logger.info(f"Train seasons: {train_seasons} | Holdout: {holdout_season}")
    logger.info(f"Features ({len(feature_cols)}): {feature_cols[:5]}...")
    logger.info(f"{'═'*60}")

    # ── 1. Build feature matrices ─────────────────────────────────────────────
    df_train = _build_prop_data(model_id, train_seasons)
    df_hold  = _build_prop_data(model_id, [holdout_season])

    if df_train.empty:
        raise ValueError(f"No training data for {model_id} in seasons {train_seasons}")
    if df_hold.empty:
        logger.warning(f"No holdout data for {model_id} season {holdout_season}")

    missing = [c for c in feature_cols if c not in df_train.columns]
    if missing:
        raise ValueError(f"Feature columns missing from training data: {missing}")

    X_train = df_train[feature_cols].values.astype(float)

    if not df_hold.empty:
        X_hold = df_hold[feature_cols].values.astype(float)
    else:
        X_hold = None

    # ── Logistic branch (binary rare events: HR, SB) ─────────────────────────
    if model_type == "logistic":
        # Binarize target: any count ≥ 1 is a "hit" (player achieves the outcome)
        y_train = (df_train["target"].values >= 1).astype(int)
        y_hold  = (df_hold["target"].values  >= 1).astype(int) if X_hold is not None else None

        pos_rate = y_train.mean()
        logger.info(f"Training set: {len(X_train)} rows | "
                    f"positive rate={pos_rate:.1%} (binarized ≥ 1)")

        n_neg = int((y_train == 0).sum())
        n_pos = int((y_train == 1).sum())
        scale_pos_weight = round(n_neg / n_pos, 4) if n_pos > 0 and pos_rate < 0.15 else 1.0
        if scale_pos_weight != 1.0:
            logger.info(f"Severe class imbalance — scale_pos_weight={scale_pos_weight:.3f}")

        logger.info(f"Tuning hyperparameters ({trials} trials, logistic)...")
        study = optuna.create_study(direction="minimize",
                                    sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
        study.optimize(
            lambda trial: _xgb_objective(trial, X_train, y_train, scale_pos_weight),
            n_trials=trials,
            show_progress_bar=False,
        )
        best_params = study.best_params
        logger.success(f"Best CV log-loss: {study.best_value:.4f}")
        logger.info(f"Best params: {best_params}")

        xgb_clf = XGBClassifier(
            **best_params,
            scale_pos_weight=scale_pos_weight,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
            verbosity=0,
        )
        xgb_clf.fit(X_train, y_train)

        final_model = CalibratedClassifierCV(estimator=xgb_clf, method="sigmoid",
                                             cv=CALIBRATION_FOLDS)
        final_model.fit(X_train, y_train)

        holdout_metrics = {}
        if X_hold is not None and len(X_hold) > 0:
            probs_hold = final_model.predict_proba(X_hold)[:, 1]
            auc     = roc_auc_score(y_hold, probs_hold) if len(np.unique(y_hold)) > 1 else 0.5
            cal = calibration_metrics(model_id, y_hold, probs_hold)
            cal_err = cal["cal_error"]
            accuracy = ((probs_hold >= 0.5).astype(int) == y_hold).mean()

            holdout_metrics = {
                "holdout_season":   int(holdout_season),
                "holdout_picks":    int(len(X_hold)),
                "holdout_auc":      round(float(auc), 4),
                "holdout_accuracy": round(float(accuracy), 4),
                "cal_error":        round(float(cal_err), 4),
                # The gate's real question: is it calibrated WHERE IT BETS.
                "cal_error_weighted":   round(float(cal["cal_error_weighted"]), 4),
                "cal_error_actionable": round(float(cal["cal_error_actionable"]), 4),
            }
            logger.success(
                f"Holdout {holdout_season}: "
                f"AUC={auc:.3f} | accuracy={accuracy:.3f} | CalErr={cal_err:.4f}"
            )

        importances = dict(zip(feature_cols, xgb_clf.feature_importances_.tolist()))
        top5 = sorted(importances.items(), key=lambda x: -x[1])[:5]
        logger.info(f"Top 5 features: {top5}")

        version    = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = _output_dir() / f"{model_id}_{version}.pkl"
        MODELS_DIR.mkdir(parents=True, exist_ok=True)

        artifact = {
            "model_id":            model_id,
            "version":             version,
            "sport":               sport,
            "market":              market,
            "model_type":          model_type,
            "feature_cols":        feature_cols,
            "model":               final_model,    # CalibratedClassifierCV → predict_proba
            "best_params":         best_params,
            "train_seasons":       train_seasons,
            "holdout_metrics":     holdout_metrics,
            "feature_importances": importances,
            "trained_at":          datetime.now().isoformat(),
        }
        with open(model_path, "wb") as f:
            pickle.dump(artifact, f)
        logger.success(f"Model saved: {model_path}")

        _register_model(
            model_id, version, train_seasons, holdout_season,
            {
                "holdout_accuracy": holdout_metrics.get("holdout_accuracy"),
                "holdout_roi":      0.0,
                "holdout_picks":    holdout_metrics.get("holdout_picks"),
                "cal_error":        holdout_metrics.get("cal_error"),
            },
            model_path.relative_to(MODELS_DIR.parent.parent).as_posix(),
        )

        return {"model_id": model_id, "version": version, "path": str(model_path),
                **holdout_metrics}

    # ── Zero-inflated Gamma branch (NFL yardage) ─────────────────────────────
    # Yards are continuous, right-skewed, can be negative (a stuffed run), and
    # carry a real point mass at zero (a targeted receiver who catches nothing).
    # So: fit the unconditional mean with squared error, then represent the
    # response as (point mass at 0) + (Gamma on the positive part), with the
    # Gamma re-scaled so the MIXTURE mean equals the fitted mean.
    if model_type == "gamma":
        y_train = df_train["target"].values.astype(float)
        y_hold  = df_hold["target"].values.astype(float) if X_hold is not None else None
        p0 = float((y_train <= 0).mean())
        logger.info(f"Training set: {len(X_train)} rows | target mean={y_train.mean():.2f} "
                    f"sd={y_train.std():.2f} | zero mass p0={p0:.4f} | "
                    f"var/mean={y_train.var()/max(y_train.mean(), 1e-6):.1f}")

        logger.info(f"Tuning hyperparameters ({trials} trials, gamma-mean)...")
        study = optuna.create_study(direction="minimize",
                                    sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
        study.optimize(lambda t: _squared_objective(t, X_train, y_train),
                       n_trials=trials, show_progress_bar=False)
        best_params = study.best_params
        logger.success(f"Best CV RMSE: {study.best_value:.4f}")

        oof = np.clip(_oof_predictions(best_params, X_train, y_train,
                                       "reg:squarederror", _DISPERSION_FOLDS), 1e-6, None)
        pos = y_train > 0
        gamma_k = _gamma_shape(y_train[pos], oof[pos] / max(1.0 - p0, 1e-6))
        logger.info(f"Zero-inflated Gamma: p0={p0:.4f}, shape k={gamma_k:.3f} "
                    f"(from {int(pos.sum())} out-of-fold positive rows)")

        final_model = XGBRegressor(**best_params, objective="reg:squarederror",
                                   random_state=RANDOM_STATE, n_jobs=-1, verbosity=0)
        final_model.fit(X_train, y_train)

        holdout_metrics = {}
        if X_hold is not None and len(X_hold) > 0:
            mu_hold = np.clip(final_model.predict(X_hold), 1e-6, None)
            rng = np.random.default_rng(RANDOM_STATE)
            pit = _zig_pit(y_hold, mu_hold, gamma_k, p0, rng)
            holdout_metrics = {
                "holdout_season":  int(holdout_season),
                "holdout_picks":   int(len(X_hold)),
                "holdout_mae":     round(float(mean_absolute_error(y_hold, mu_hold)), 4),
                "holdout_rmse":    round(float(np.sqrt(np.mean((y_hold - mu_hold) ** 2))), 4),
                "cal_error":       round(_pit_calibration_error(pit), 4),
                "zero_inflation":  round(p0, 4),
                "gamma_shape":     round(gamma_k, 4),
            }
            logger.success(f"Holdout {holdout_season}: MAE={holdout_metrics['holdout_mae']:.3f} "
                           f"| RMSE={holdout_metrics['holdout_rmse']:.3f} "
                           f"| PIT CalErr={holdout_metrics['cal_error']:.4f}")

        importances = dict(zip(feature_cols, final_model.feature_importances_.tolist()))
        logger.info(f"Top 5 features: {sorted(importances.items(), key=lambda x: -x[1])[:5]}")

        version    = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = _output_dir() / f"{model_id}_{version}.pkl"
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        artifact = {
            "model_id": model_id, "version": version, "sport": sport, "market": market,
            "model_type": model_type, "feature_cols": feature_cols, "model": final_model,
            "best_params": best_params, "train_seasons": train_seasons,
            "holdout_metrics": holdout_metrics, "feature_importances": importances,
            # read by the scorer to rebuild the predictive distribution
            "zero_inflation": p0, "gamma_shape": gamma_k,
            "trained_at": datetime.now().isoformat(),
        }
        with open(model_path, "wb") as f:
            pickle.dump(artifact, f)
        logger.success(f"Model saved: {model_path}")
        _register_model(model_id, version, train_seasons, holdout_season,
                        {"holdout_accuracy": None, "holdout_roi": 0.0,
                         "holdout_picks": holdout_metrics.get("holdout_picks"),
                         "cal_error": holdout_metrics.get("cal_error")},
                        model_path.relative_to(MODELS_DIR.parent.parent).as_posix())
        return {"model_id": model_id, "version": version, "path": str(model_path),
                **holdout_metrics}

    # ── Poisson branch (count stats: Ks, hits, TB, etc.) ─────────────────────
    y_train = df_train["target"].values.astype(float)
    y_hold  = df_hold["target"].values.astype(float) if X_hold is not None else None

    logger.info(f"Training set: {len(X_train)} rows | "
                f"target mean={y_train.mean():.2f}, std={y_train.std():.2f}, "
                f"range=[{y_train.min():.0f}, {y_train.max():.0f}]")

    # ── 2. Hyperparameter tuning ──────────────────────────────────────────────
    logger.info(f"Tuning hyperparameters ({trials} trials)...")
    study = optuna.create_study(direction="minimize",
                                sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
    study.optimize(
        lambda trial: _poisson_objective(trial, X_train, y_train),
        n_trials=trials,
        show_progress_bar=False,
    )

    best_params = study.best_params
    best_nll    = study.best_value
    logger.success(f"Best CV Poisson NLL: {best_nll:.4f}")
    logger.info(f"Best params: {best_params}")

    # ── 3. Train final model ──────────────────────────────────────────────────
    final_model = XGBRegressor(
        **best_params,
        objective="count:poisson",
        eval_metric="poisson-nloglik",
        random_state=RANDOM_STATE,
        n_jobs=-1,
        verbosity=0,
    )
    final_model.fit(X_train, y_train)

    train_mu  = np.clip(final_model.predict(X_train), 1e-6, None)
    train_mae = mean_absolute_error(y_train, train_mu)
    logger.info(f"Train MAE: {train_mae:.3f}")

    # Negative-binomial head: same fitted mean, but the scorer reads P(over) off
    # an NB rather than a Poisson. Every overdispersed NFL count market needs
    # this — under a Poisson head pass attempts miscalibrates by 8.3 points.
    nb_r = None
    if model_type == "nbinom":
        oof = np.clip(_oof_predictions(best_params, X_train, y_train,
                                       "count:poisson", _DISPERSION_FOLDS), 1e-6, None)
        nb_r = _nb_dispersion(y_train, oof)
        vm = float(np.mean((y_train - oof) ** 2) / max(np.mean(oof), 1e-6))
        logger.info(f"Negative binomial: r={nb_r:.2f} "
                    f"(out-of-fold residual var/mean={vm:.2f}; r→∞ would be Poisson)")

    # ── 4. Holdout evaluation ─────────────────────────────────────────────────
    holdout_metrics = {}
    if X_hold is not None and len(X_hold) > 0:
        mu_hold  = np.clip(final_model.predict(X_hold), 1e-6, None)
        mae      = mean_absolute_error(y_hold, mu_hold)
        rmse     = float(np.sqrt(np.mean((y_hold - mu_hold) ** 2)))
        ou_acc   = _over_under_accuracy(y_hold.astype(int), mu_hold)
        cal_err  = _poisson_calibration_error(y_hold, mu_hold)

        holdout_metrics = {
            "holdout_season":   int(holdout_season),
            "holdout_picks":    int(len(X_hold)),
            "holdout_mae":      round(mae, 4),
            "holdout_rmse":     round(rmse, 4),
            "holdout_ou_acc":   round(ou_acc, 4),
            "cal_error":        round(cal_err, 4),
            "train_mae":        round(train_mae, 4),
        }
        if nb_r is not None:
            rng = np.random.default_rng(RANDOM_STATE)
            pit = _nb_pit(y_hold.astype(int), mu_hold, nb_r, rng)
            holdout_metrics["nb_r"] = round(nb_r, 4)
            # PIT calibration is the honest read for a distribution: it needs no
            # betting line, so it cannot be flattered by where one is placed.
            holdout_metrics["pit_cal_error"] = round(_pit_calibration_error(pit), 4)
            holdout_metrics["cal_error"] = holdout_metrics["pit_cal_error"]

        logger.success(
            f"Holdout {holdout_season}: "
            f"MAE={mae:.3f} | RMSE={rmse:.3f} | "
            f"O/U acc={ou_acc:.3f} | CalErr={cal_err:.4f}"
        )

    # ── 5. Feature importance ─────────────────────────────────────────────────
    importances = dict(zip(feature_cols, final_model.feature_importances_.tolist()))
    top5 = sorted(importances.items(), key=lambda x: -x[1])[:5]
    logger.info(f"Top 5 features: {top5}")

    # ── 6. Save model ─────────────────────────────────────────────────────────
    version    = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = _output_dir() / f"{model_id}_{version}.pkl"
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    artifact = {
        "model_id":            model_id,
        "version":             version,
        "sport":               sport,
        "market":              market,
        "model_type":          model_type,      # "poisson" or "logistic"
        "feature_cols":        feature_cols,
        "model":               final_model,     # XGBRegressor (predict → lambda)
        "nb_r":                nb_r,            # None for Poisson; the scorer branches on it
        "best_params":         best_params,
        "train_seasons":       train_seasons,
        "holdout_metrics":     holdout_metrics,
        "feature_importances": importances,
        "trained_at":          datetime.now().isoformat(),
    }

    with open(model_path, "wb") as f:
        pickle.dump(artifact, f)

    logger.success(f"Model saved: {model_path}")

    # ── 7. Register in DB ─────────────────────────────────────────────────────
    _register_model(
        model_id, version, train_seasons, holdout_season,
        {
            "holdout_accuracy": holdout_metrics.get("holdout_ou_acc"),
            "holdout_roi":      0.0,   # populated later by backtester with real lines
            "holdout_picks":    holdout_metrics.get("holdout_picks"),
            "cal_error":        holdout_metrics.get("cal_error"),
        },
        model_path.relative_to(MODELS_DIR.parent.parent).as_posix(),
    )

    return {
        "model_id": model_id,
        "version":  version,
        "path":     str(model_path),
        **holdout_metrics,
    }


# ── Live (In-Play) Win-Probability Trainer ────────────────────────────────────

# Live training matrices are play-level (~75 rows per game ≈ 1M+ rows across
# 6 seasons), so the Optuna search runs on a random subsample and with fewer
# trials than the pre-game models. The FINAL model still fits on all rows.
LIVE_OPTUNA_TRIALS   = 25
LIVE_OPTUNA_MAX_ROWS = 200_000
LIVE_CALIBRATION_FOLDS = 3


def _per_inning_auc(df_hold: pd.DataFrame, probs: np.ndarray,
                    y_true: np.ndarray) -> dict:
    """AUC bucketed by inning — shows where in the game the model has signal."""
    out = {}
    innings = df_hold["inning"].values
    for lo, hi, label in [(1, 3, "inn_1_3"), (4, 6, "inn_4_6"), (7, 20, "inn_7_plus")]:
        mask = (innings >= lo) & (innings <= hi)
        if mask.sum() < 100 or len(np.unique(y_true[mask])) < 2:
            continue
        out[label] = round(float(roc_auc_score(y_true[mask], probs[mask])), 4)
    return out


def train_live_model(model_id: str,
                     train_seasons: list[int] = None,
                     holdout_season: int = None,
                     n_trials: int = None,
                     sample_frac: float = 1.0) -> dict:
    """
    Train one live (in-play) model on the play-by-play state corpus.

    Requires the `plays` table to be populated first:
        python -m data.ingestors.mlb_pbp_ingestor --backfill 2019 2025

    Binary models (win_prob, runline): XGBClassifier + Platt scaling.
    Poisson model (total_runs): XGBRegressor count:poisson on runs REMAINING.
    """
    from features.live_game_features import (
        LIVE_FEATURE_MAP, build_live_training_dataset,
    )

    if model_id not in LIVE_MODELS:
        raise ValueError(f"Unknown live model_id '{model_id}'. "
                         f"Available: {list(LIVE_MODELS.keys())}")

    sport, market, model_type, description = LIVE_MODELS[model_id]
    sport_cfg = SPORTS[sport]

    train_seasons  = train_seasons  or sport_cfg["train_seasons"]
    holdout_season = holdout_season or sport_cfg["test_season"]
    trials         = n_trials or LIVE_OPTUNA_TRIALS
    feature_cols   = LIVE_FEATURE_MAP[model_id]

    logger.info(f"\n{'═'*60}")
    logger.info(f"Training LIVE model: {model_id}  [{model_type}]")
    logger.info(f"Market: {market} | Train: {train_seasons} | Holdout: {holdout_season}")
    logger.info(f"Features ({len(feature_cols)}): {feature_cols[:6]}...")
    logger.info(f"{'═'*60}")

    df_train = build_live_training_dataset(model_id, train_seasons,
                                           sample_frac=sample_frac)
    df_hold  = build_live_training_dataset(model_id, [holdout_season])

    if df_train.empty:
        raise ValueError(
            f"No live training data for {model_id} in seasons {train_seasons}. "
            f"Has the plays backfill been run?")
    if df_hold.empty:
        logger.warning(f"No holdout data for {model_id} season {holdout_season}")

    missing = [c for c in feature_cols if c not in df_train.columns]
    if missing:
        raise ValueError(f"Feature columns missing from live training data: {missing}")

    X_train = df_train[feature_cols].values.astype(float)
    X_hold  = df_hold[feature_cols].values.astype(float) if not df_hold.empty else None

    # Subsample for the hyperparameter search only.
    if len(X_train) > LIVE_OPTUNA_MAX_ROWS:
        rng = np.random.RandomState(RANDOM_STATE)
        idx = rng.choice(len(X_train), LIVE_OPTUNA_MAX_ROWS, replace=False)
        logger.info(f"Optuna search on {LIVE_OPTUNA_MAX_ROWS:,} of "
                    f"{len(X_train):,} rows (final fit uses all rows)")
    else:
        idx = np.arange(len(X_train))

    holdout_metrics: dict = {}
    version = datetime.now().strftime("%Y%m%d_%H%M%S")

    if model_type == "binary":
        y_train = df_train["target"].values.astype(int)
        logger.info(f"Training set: {len(X_train):,} play-rows, "
                    f"{y_train.mean():.1%} positive rate")

        logger.info(f"Tuning hyperparameters ({trials} trials)...")
        study = optuna.create_study(direction="minimize",
                                    sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
        study.optimize(
            lambda t: _xgb_objective(t, X_train[idx], y_train[idx], 1.0),
            n_trials=trials, show_progress_bar=False)
        best_params = study.best_params
        logger.success(f"Best CV log-loss: {study.best_value:.4f}")

        xgb_final = XGBClassifier(
            **best_params, use_label_encoder=False, eval_metric="logloss",
            random_state=RANDOM_STATE, n_jobs=-1, verbosity=0)
        xgb_final.fit(X_train, y_train)

        logger.info("Calibrating with Platt scaling...")
        final_model = CalibratedClassifierCV(estimator=xgb_final, method="sigmoid",
                                             cv=LIVE_CALIBRATION_FOLDS)
        final_model.fit(X_train, y_train)

        if X_hold is not None and len(X_hold) > 0:
            y_hold = df_hold["target"].values.astype(int)
            probs  = final_model.predict_proba(X_hold)[:, 1]
            auc      = roc_auc_score(y_hold, probs) if len(np.unique(y_hold)) > 1 else 0.5
            brier    = brier_score_loss(y_hold, probs)
            cal_err  = _mean_calibration_error(y_hold, probs)
            accuracy = ((probs >= 0.5).astype(int) == y_hold).mean()
            by_inning = _per_inning_auc(df_hold, probs, y_hold)

            holdout_metrics = {
                "holdout_season":   int(holdout_season),
                "holdout_picks":    int(len(X_hold)),
                "holdout_accuracy": round(float(accuracy), 4),
                "holdout_auc":      round(float(auc), 4),
                "holdout_brier":    round(float(brier), 4),
                "cal_error":        round(float(cal_err), 4),
                "auc_by_inning":    by_inning,
            }
            logger.success(
                f"Holdout {holdout_season}: AUC={auc:.3f} | acc={accuracy:.3f} | "
                f"Brier={brier:.4f} | CalErr={cal_err:.4f} | by inning: {by_inning}")

        importances = dict(zip(feature_cols, xgb_final.feature_importances_.tolist()))

    elif model_type == "poisson":
        y_train = df_train["target"].values.astype(float)
        logger.info(f"Training set: {len(X_train):,} play-rows | "
                    f"runs-remaining mean={y_train.mean():.2f}, std={y_train.std():.2f}")

        logger.info(f"Tuning hyperparameters ({trials} trials, Poisson)...")
        study = optuna.create_study(direction="minimize",
                                    sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
        study.optimize(
            lambda t: _poisson_objective(t, X_train[idx], y_train[idx]),
            n_trials=trials, show_progress_bar=False)
        best_params = study.best_params
        logger.success(f"Best CV Poisson NLL: {study.best_value:.4f}")

        final_model = XGBRegressor(
            **best_params, objective="count:poisson",
            eval_metric="poisson-nloglik",
            random_state=RANDOM_STATE, n_jobs=-1, verbosity=0)
        final_model.fit(X_train, y_train)

        if X_hold is not None and len(X_hold) > 0:
            y_hold  = df_hold["target"].values.astype(float)
            mu_hold = np.clip(final_model.predict(X_hold), 1e-6, None)
            mae     = mean_absolute_error(y_hold, mu_hold)
            rmse    = float(np.sqrt(np.mean((y_hold - mu_hold) ** 2)))
            cal_err = _poisson_calibration_error(y_hold, mu_hold)
            # The count fit is not what gets bet. Also measure the DERIVED
            # probability -- the Poisson tail the scorer prices against the live
            # line -- because that layer was never evaluated at training time and
            # is where this model's 9-10pp overconfidence lived (2026-08-30).
            prob_cal = poisson_probability_metrics(model_id, y_hold, mu_hold)

            holdout_metrics = {
                "holdout_season": int(holdout_season),
                "holdout_picks":  int(len(X_hold)),
                "holdout_mae":    round(float(mae), 4),
                "holdout_rmse":   round(rmse, 4),
                "cal_error":      round(float(cal_err), 4),
                **{k: (round(float(v), 4) if isinstance(v, float) else v)
                   for k, v in prob_cal.items()},
            }
            actionable = prob_cal.get("prob_cal_error_actionable")
            logger.success(
                f"Holdout {holdout_season}: MAE={mae:.3f} | RMSE={rmse:.3f} | "
                f"count CalErr={cal_err:.4f} | "
                f"PROBABILITY CalErr(actionable)={actionable:.4f}")
            if actionable is not None and actionable > 0.05:
                logger.error(
                    f"  {model_id} FAILS the 5% calibration gate on the probability "
                    f"it actually bets ({actionable:.1%}). The count fit passing is "
                    f"not the same question -- do not ship on it.")

        importances = dict(zip(feature_cols, final_model.feature_importances_.tolist()))

    else:
        raise ValueError(f"Unknown live model_type: {model_type}")

    top5 = sorted(importances.items(), key=lambda x: -x[1])[:5]
    logger.info(f"Top 5 features: {top5}")

    model_path = _output_dir() / f"{model_id}_{version}.pkl"
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "model_id":            model_id,
        "version":             version,
        "sport":               sport,
        "market":              market,
        "model_type":          model_type,
        "is_live":             True,
        "feature_cols":        feature_cols,
        "model":               final_model,
        "best_params":         best_params,
        "train_seasons":       train_seasons,
        "holdout_metrics":     holdout_metrics,
        "feature_importances": importances,
        "trained_at":          datetime.now().isoformat(),
    }
    with open(model_path, "wb") as f:
        pickle.dump(artifact, f)
    logger.success(f"Model saved: {model_path}")

    _register_model(
        model_id, version, train_seasons, holdout_season,
        {
            "holdout_accuracy": holdout_metrics.get("holdout_accuracy"),
            "holdout_roi":      0.0,
            "holdout_picks":    holdout_metrics.get("holdout_picks"),
            "cal_error":        holdout_metrics.get("cal_error"),
        },
        model_path.relative_to(MODELS_DIR.parent.parent).as_posix(),
    )

    return {"model_id": model_id, "version": version, "path": str(model_path),
            **holdout_metrics}


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
        # A cloud retrain wrote this file to a container that no longer exists.
        # The bytes are in Supabase; put them back rather than failing scoring.
        conn2 = get_connection()
        try:
            restored = _restore_artifact(conn2, model_path)
        finally:
            conn2.close()
        if restored is None:
            logger.error(f"Model file not found and not in model_artifacts: {path}")
            return None
        path = restored

    with open(path, "rb") as f:
        artifact = pickle.load(f)

    logger.debug(f"Loaded {model_id} v{version}")
    return artifact


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train betting models")
    parser.add_argument("--model",    help="Model ID (e.g. mlb_moneyline, mlb_prop_pitcher_k, mlb_live_total_runs)")
    parser.add_argument("--all",      action="store_true", help="Train all game models")
    parser.add_argument("--all-props", action="store_true", help="Train all prop models")
    parser.add_argument("--all-live", action="store_true", help="Train all live (in-play) models")
    parser.add_argument("--seasons",  nargs="+", type=int,
                        help="Override train seasons")
    parser.add_argument("--holdout",  type=int, help="Override holdout season")
    parser.add_argument("--trials",   type=int, default=None,
                        help=f"Optuna trials (default: {OPTUNA_TRIALS}, "
                             f"live models: {LIVE_OPTUNA_TRIALS})")
    parser.add_argument("--sample-frac", type=float, default=1.0,
                        help="Live models only: subsample plays for training (0-1]")
    parser.add_argument("--no-register", action="store_true",
                        help="Write the artifact to models/saved/_baseline/ and "
                             "leave model_registry alone. Use for comparison runs "
                             "-- a normal run ACTIVATES what it trains.")
    args = parser.parse_args()

    if args.no_register:
        REGISTER_TRAINED_MODELS = False
        logger.warning("--no-register: artifacts go to models/saved/_baseline/, "
                       "the live models stay as they are")

    if args.trials:
        OPTUNA_TRIALS = args.trials

    if args.all:
        models = list(MODELS.keys())
    elif args.all_props:
        models = list(PROP_MODELS.keys())
    elif args.all_live:
        models = list(LIVE_MODELS.keys())
    elif args.model:
        models = [args.model]
    else:
        parser.error("Specify --model MODEL_ID, --all, --all-props, or --all-live")

    for mid in models:
        try:
            if mid in LIVE_MODELS:
                result = train_live_model(mid,
                                          train_seasons=args.seasons,
                                          holdout_season=args.holdout,
                                          n_trials=args.trials,
                                          sample_frac=args.sample_frac)
            elif mid in PROP_MODELS:
                result = train_prop_model(mid,
                                          train_seasons=args.seasons,
                                          holdout_season=args.holdout,
                                          n_trials=args.trials)
            else:
                result = train_model(mid,
                                     train_seasons=args.seasons,
                                     holdout_season=args.holdout)
            logger.success(f"✓ {mid}: {result}")
        except Exception as exc:
            logger.error(f"✗ {mid}: {exc}")
