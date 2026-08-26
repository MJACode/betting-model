"""
NCAAF search — model families.

Every family exposes the same `fit_predict(X_tr, y_tr, X_te, w_tr) -> p_te`
signature so the walk-forward harness treats them identically and their
numbers are directly comparable.

Calibration + early stopping use an INTERNAL validation split taken from the
END of the training window (the most recent training season). That split is
still strictly prior to the test season, so it never touches held-out data —
the spec's "calibration fit on validation folds only" rule.

Sample sizes here are small (~800 games/season), so the tree configurations
are deliberately shallow and heavily regularised. Deep trees will happily
memorise 5,000 CFB games and tell you nothing.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
warnings.filterwarnings("ignore")

CALIB_METHODS = ("raw", "platt", "isotonic")


def _split_internal(X: pd.DataFrame, y: np.ndarray, seasons: pd.Series,
                    min_val: int = 300):
    """
    Hold out the most recent training season for calibration / early stopping.
    Falls back to a tail slice when the last season is too small to calibrate
    on. Never touches the test season.
    """
    if seasons is None or seasons.nunique() < 2:
        cut = max(int(len(X) * 0.8), len(X) - max(min_val, 1))
        return X.iloc[:cut], y[:cut], X.iloc[cut:], y[cut:]
    last = seasons.max()
    m = (seasons == last).to_numpy()
    if m.sum() < min_val:
        cut = len(X) - max(min_val, int(m.sum()))
        return X.iloc[:cut], y[:cut], X.iloc[cut:], y[cut:]
    return X[~m], y[~m], X[m], y[m]


def _apply_calibration(method: str, p_val: np.ndarray, y_val: np.ndarray,
                       p_te: np.ndarray) -> np.ndarray:
    if method == "raw" or len(np.unique(y_val)) < 2:
        return p_te
    if method == "platt":
        from sklearn.linear_model import LogisticRegression
        lr = LogisticRegression(max_iter=1000)
        lr.fit(p_val.reshape(-1, 1), y_val)
        return lr.predict_proba(p_te.reshape(-1, 1))[:, 1]
    if method == "isotonic":
        from sklearn.isotonic import IsotonicRegression
        ir = IsotonicRegression(out_of_bounds="clip", y_min=0.01, y_max=0.99)
        ir.fit(p_val, y_val)
        return ir.predict(p_te)
    raise ValueError(f"unknown calibration: {method}")


# ── Elastic-net logistic regression (mandatory baseline) ──────────────────────

def make_logreg(C: float = 0.1, l1_ratio: float = 0.5,
                calibration: str = "raw", season_col=None):
    def fit_predict(X_tr, y_tr, X_te, w_tr=None):
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.impute import SimpleImputer

        pipe = Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("sc", StandardScaler()),
            ("lr", LogisticRegression(
                penalty="elasticnet", solver="saga", C=C,
                l1_ratio=l1_ratio, max_iter=4000, tol=1e-3)),
        ])
        if calibration == "raw":
            pipe.fit(X_tr, y_tr, lr__sample_weight=w_tr)
            return pipe.predict_proba(X_te)[:, 1]

        seasons = season_col.loc[X_tr.index] if season_col is not None else None
        Xa, ya, Xv, yv = _split_internal(X_tr, y_tr, seasons)
        pipe.fit(Xa, ya)
        p_val = pipe.predict_proba(Xv)[:, 1]
        p_te = pipe.predict_proba(X_te)[:, 1]
        return _apply_calibration(calibration, p_val, yv, p_te)

    return fit_predict


# ── Gradient boosted trees ────────────────────────────────────────────────────

_XGB_DEFAULTS = dict(
    max_depth=3, learning_rate=0.03, n_estimators=400,
    min_child_weight=20, subsample=0.7, colsample_bytree=0.6,
    reg_lambda=5.0, reg_alpha=0.5, objective="binary:logistic",
    eval_metric="logloss", tree_method="hist",
)


def make_xgb(params: dict | None = None, calibration: str = "raw",
             season_col=None, early_stopping_rounds: int = 50):
    cfg = {**_XGB_DEFAULTS, **(params or {})}

    def fit_predict(X_tr, y_tr, X_te, w_tr=None):
        import xgboost as xgb
        seasons = season_col.loc[X_tr.index] if season_col is not None else None
        Xa, ya, Xv, yv = _split_internal(X_tr, y_tr, seasons)

        model = xgb.XGBClassifier(**cfg, early_stopping_rounds=early_stopping_rounds)
        wa = None
        if w_tr is not None:
            wa = pd.Series(w_tr, index=X_tr.index).loc[Xa.index].to_numpy()
        model.fit(Xa, ya, sample_weight=wa, eval_set=[(Xv, yv)], verbose=False)

        p_val = model.predict_proba(Xv)[:, 1]
        p_te = model.predict_proba(X_te)[:, 1]
        return _apply_calibration(calibration, p_val, yv, p_te)

    return fit_predict


_LGBM_DEFAULTS = dict(
    max_depth=3, num_leaves=7, learning_rate=0.03, n_estimators=400,
    min_child_samples=40, subsample=0.7, subsample_freq=1,
    colsample_bytree=0.6, reg_lambda=5.0, reg_alpha=0.5,
    objective="binary", verbose=-1,
)


def make_lgbm(params: dict | None = None, calibration: str = "raw",
              season_col=None, early_stopping_rounds: int = 50):
    cfg = {**_LGBM_DEFAULTS, **(params or {})}

    def fit_predict(X_tr, y_tr, X_te, w_tr=None):
        import lightgbm as lgb
        seasons = season_col.loc[X_tr.index] if season_col is not None else None
        Xa, ya, Xv, yv = _split_internal(X_tr, y_tr, seasons)

        model = lgb.LGBMClassifier(**cfg)
        wa = None
        if w_tr is not None:
            wa = pd.Series(w_tr, index=X_tr.index).loc[Xa.index].to_numpy()
        model.fit(Xa, ya, sample_weight=wa, eval_set=[(Xv, yv)],
                  callbacks=[lgb.early_stopping(early_stopping_rounds, verbose=False)])

        p_val = model.predict_proba(Xv)[:, 1]
        p_te = model.predict_proba(X_te)[:, 1]
        return _apply_calibration(calibration, p_val, yv, p_te)

    return fit_predict


# ── Ensembles ─────────────────────────────────────────────────────────────────

def _logit(p, eps=1e-6):
    p = np.clip(p, eps, 1 - eps)
    return np.log(p / (1 - p))


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def make_ensemble(members: list, mode: str = "logit", weights=None):
    """Average member predictions in probability or logit space."""
    def fit_predict(X_tr, y_tr, X_te, w_tr=None):
        preds = [np.asarray(f(X_tr, y_tr, X_te, w_tr), dtype=float) for f in members]
        w = np.ones(len(preds)) if weights is None else np.asarray(weights, float)
        w = w / w.sum()
        if mode == "prob":
            return np.average(np.vstack(preds), axis=0, weights=w)
        return _sigmoid(np.average(np.vstack([_logit(p) for p in preds]), axis=0, weights=w))
    return fit_predict


# ── Era handling ──────────────────────────────────────────────────────────────

def exponential_recency_weights(half_life_seasons: float = 3.0):
    """
    Spec item 4(a): full sample with exponential recency weighting. Weight is
    relative to the most recent season IN THE TRAINING WINDOW, so it is
    recomputed per fold and never references the test season.
    """
    def fn(train_df: pd.DataFrame) -> np.ndarray:
        newest = train_df["season"].max()
        age = (newest - train_df["season"]).astype(float)
        return np.power(0.5, age / half_life_seasons).to_numpy()
    return fn
