"""
NCAAF search — expanding-window walk-forward validation.

Protocol (spec section "Validation protocol"):
  * train on seasons 1..N, test on season N+1; NEVER random k-fold
  * per test season AND pooled: log loss, Brier, ECE, win rate vs close at
    -110 with 95% CI, flat + fractional-Kelly ROI, bet volume, CLV
  * threshold sweep 1%-8% model edge
  * consistency flag: positive in fewer than 3 of 4 test seasons

Two rules here exist to stop us fooling ourselves:

  1. `market_only_sanity` — a model given only the closing line must score
     ~50% against that line. If it does not, the harness leaks and every other
     number in the run is meaningless. Run it FIRST.
  2. `LEAK_SUSPICION_WR` — any configuration above 55% pooled triggers a
     leakage audit rather than celebration. Beating a closing line by 3+
     points of win rate over thousands of games is not something a tabular
     model does honestly.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

BREAKEVEN = 0.5238            # -110
AMERICAN = -110
LEAK_SUSPICION_WR = 0.55
KELLY_FRACTION = 0.25         # quarter-Kelly per spec
KELLY_CAP = 0.05              # 5% of bankroll
DEFAULT_THRESHOLDS = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08]


def payout(american: int = AMERICAN) -> float:
    """Profit per 1u stake on a win."""
    return (100.0 / abs(american)) if american < 0 else (american / 100.0)


# ── metrics ───────────────────────────────────────────────────────────────────

def log_loss(y: np.ndarray, p: np.ndarray, eps: float = 1e-15) -> float:
    p = np.clip(p, eps, 1 - eps)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10,
        min_per_bin: int = 20) -> float:
    """
    Expected calibration error. Bins with < min_per_bin samples are skipped —
    the same standard-ECE guard the repo already applies elsewhere, because a
    3-sample bin reads as 0% or 100% by chance and invents miscalibration.
    """
    edges = np.linspace(0, 1, bins + 1)
    tot, err = 0, 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi)
        n = int(m.sum())
        if n < min_per_bin:
            continue
        err += n * abs(float(y[m].mean()) - float(p[m].mean()))
        tot += n
    return float(err / tot) if tot else float("nan")


def calibration_curve(y: np.ndarray, p: np.ndarray, bins: int = 10,
                      min_per_bin: int = 20) -> pd.DataFrame:
    edges = np.linspace(0, 1, bins + 1)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi)
        n = int(m.sum())
        if n < min_per_bin:
            continue
        rows.append({"bin_lo": lo, "bin_hi": hi, "n": n,
                     "predicted": float(p[m].mean()),
                     "actual": float(y[m].mean())})
    return pd.DataFrame(rows)


def wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson interval — correct near 0.5 and at small n, unlike normal approx."""
    if n == 0:
        return (float("nan"), float("nan"))
    ph = wins / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (float(c - h), float(c + h))


# ── betting simulation ────────────────────────────────────────────────────────

def kelly_stake(p: float, american: int = AMERICAN,
                frac: float = KELLY_FRACTION, cap: float = KELLY_CAP) -> float:
    b = payout(american)
    edge = p * (1 + b) - 1
    if edge <= 0:
        return 0.0
    return float(min(frac * edge / b, cap))


def simulate(y: np.ndarray, p: np.ndarray, threshold: float,
             american: int = AMERICAN) -> dict:
    """
    Bet the side the model prefers when its edge over the -110 breakeven
    exceeds `threshold`. Model prob p is P(home covers) / P(over); betting the
    under/away side means the model's probability for THAT side is 1 - p.
    """
    b = payout(american)
    side_p = np.where(p >= 0.5, p, 1 - p)          # prob of the chosen side
    side_y = np.where(p >= 0.5, y, 1 - y)          # did the chosen side win
    edge = side_p - BREAKEVEN
    m = edge >= threshold

    n = int(m.sum())
    if n == 0:
        return {"threshold": threshold, "bets": 0, "wins": 0, "win_rate": np.nan,
                "roi_flat": np.nan, "units_flat": 0.0, "roi_kelly": np.nan,
                "ci_lo": np.nan, "ci_hi": np.nan, "beats_breakeven": False}

    wins = int(side_y[m].sum())
    wr = wins / n
    units = wins * b - (n - wins)
    stakes = np.array([kelly_stake(pp, american) for pp in side_p[m]])
    k_units = float(np.sum(np.where(side_y[m] == 1, stakes * b, -stakes)))
    k_staked = float(stakes.sum())
    lo, hi = wilson_ci(wins, n)

    return {
        "threshold": threshold, "bets": n, "wins": wins, "win_rate": wr,
        "roi_flat": units / n, "units_flat": units,
        "roi_kelly": (k_units / k_staked) if k_staked > 0 else np.nan,
        "ci_lo": lo, "ci_hi": hi, "beats_breakeven": lo > BREAKEVEN,
    }


def clv_report(picked_home: np.ndarray, close_spread: np.ndarray,
               open_spread: np.ndarray) -> dict:
    """
    Did the close move toward our pick after the open?

    Home spreads: a home pick gains when the number gets SMALLER (less
    generous later), i.e. close < open. An away pick gains when it grows.
    Only meaningful under an open-time betting assumption.
    """
    ok = ~(np.isnan(close_spread) | np.isnan(open_spread))
    if ok.sum() == 0:
        return {"n": 0, "beat_close_pct": np.nan, "avg_move_captured": np.nan}
    move = open_spread[ok] - close_spread[ok]          # +ve = home side gained
    signed = np.where(picked_home[ok], move, -move)
    return {
        "n": int(ok.sum()),
        "beat_close_pct": float((signed > 0).mean()),
        "avg_move_captured": float(signed.mean()),
    }


# ── walk-forward ──────────────────────────────────────────────────────────────

@dataclass
class FoldResult:
    season: int
    train_seasons: list
    n_train: int
    n_test: int
    log_loss: float
    brier: float
    ece: float
    sweep: list = field(default_factory=list)
    clv: dict = field(default_factory=dict)


def walk_forward(matrix: pd.DataFrame, feature_cols: list[str], label: str,
                 fit_predict, test_seasons: list[int],
                 thresholds: list[float] | None = None,
                 sample_weight_fn=None) -> dict:
    """
    Expanding-window walk-forward.

    `fit_predict(X_tr, y_tr, X_te, w_tr) -> p_te` keeps this harness agnostic
    to the model family, so logreg / XGB / LGBM / ensembles all validate
    through exactly the same code path and are therefore comparable.
    """
    thresholds = thresholds or DEFAULT_THRESHOLDS
    cols = [c for c in feature_cols if c in matrix.columns]
    missing = sorted(set(feature_cols) - set(cols))

    df = matrix[matrix[label].notna()].copy()
    folds: list[FoldResult] = []
    pooled_y, pooled_p, pooled_home, pooled_close, pooled_open = [], [], [], [], []

    for season in sorted(test_seasons):
        past = sorted(s for s in df["season"].unique() if s < season)
        if not past:
            continue
        tr = df[df["season"].isin(past)]
        te = df[df["season"] == season]
        if tr.empty or te.empty:
            continue

        X_tr, y_tr = tr[cols], tr[label].astype(int).to_numpy()
        X_te, y_te = te[cols], te[label].astype(int).to_numpy()
        w_tr = sample_weight_fn(tr) if sample_weight_fn else None

        p_te = np.asarray(fit_predict(X_tr, y_tr, X_te, w_tr), dtype=float)
        p_te = np.clip(p_te, 1e-6, 1 - 1e-6)

        folds.append(FoldResult(
            season=int(season), train_seasons=past,
            n_train=len(tr), n_test=len(te),
            log_loss=log_loss(y_te, p_te), brier=brier(y_te, p_te),
            ece=ece(y_te, p_te),
            sweep=[simulate(y_te, p_te, t) for t in thresholds],
            clv=clv_report(p_te >= 0.5,
                           te.get("close_spread", pd.Series(np.nan, index=te.index)).to_numpy(float),
                           te.get("spread_open", pd.Series(np.nan, index=te.index)).to_numpy(float)),
        ))
        pooled_y.append(y_te)
        pooled_p.append(p_te)
        pooled_home.append(p_te >= 0.5)
        pooled_close.append(te.get("close_spread", pd.Series(np.nan, index=te.index)).to_numpy(float))
        pooled_open.append(te.get("spread_open", pd.Series(np.nan, index=te.index)).to_numpy(float))

    if not folds:
        return {"folds": [], "pooled": {}, "missing_features": missing}

    y = np.concatenate(pooled_y)
    p = np.concatenate(pooled_p)
    pooled_sweep = [simulate(y, p, t) for t in thresholds]

    best = None
    for row in pooled_sweep:
        if row["bets"] >= 100 and not np.isnan(row["roi_flat"]):
            if best is None or row["roi_flat"] > best["roi_flat"]:
                best = row

    seasons_positive = sum(
        1 for f in folds
        for r in f.sweep
        if r["threshold"] == (best or {}).get("threshold") and r["roi_flat"] > 0
    ) if best else 0

    pooled = {
        "log_loss": log_loss(y, p), "brier": brier(y, p), "ece": ece(y, p),
        "n": len(y), "sweep": pooled_sweep, "best": best,
        "seasons_positive": seasons_positive, "n_seasons": len(folds),
        "consistent": (best is not None and seasons_positive >= max(3, len(folds) - 1)),
        "clv": clv_report(np.concatenate(pooled_home),
                          np.concatenate(pooled_close),
                          np.concatenate(pooled_open)),
        "leak_suspect": bool(best and best["win_rate"] > LEAK_SUSPICION_WR),
    }
    return {"folds": folds, "pooled": pooled, "missing_features": missing,
            "calibration": calibration_curve(y, p)}


def market_only_sanity(matrix: pd.DataFrame, label: str,
                       test_seasons: list[int]) -> dict:
    """
    THE GATE. A model handed only the closing line must land ~50% against that
    line. Anything materially above it means the harness leaks, and no result
    produced after a failed sanity check should be believed.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer

    cols = ["close_spread", "close_total", "is_neutral_site"]

    def fp(X_tr, y_tr, X_te, w_tr):
        pipe = make_pipeline(SimpleImputer(strategy="median"),
                             StandardScaler(),
                             LogisticRegression(max_iter=2000, C=1.0))
        pipe.fit(X_tr, y_tr, logisticregression__sample_weight=w_tr)
        return pipe.predict_proba(X_te)[:, 1]

    res = walk_forward(matrix, cols, label, fp, test_seasons,
                       thresholds=[0.0, 0.01, 0.02])
    pooled = res["pooled"]
    at_zero = next((r for r in pooled["sweep"] if r["threshold"] == 0.0), None)
    wr = at_zero["win_rate"] if at_zero else float("nan")
    return {
        "win_rate_at_zero_threshold": wr,
        "n": at_zero["bets"] if at_zero else 0,
        "log_loss": pooled["log_loss"],
        "passes": bool(not np.isnan(wr) and abs(wr - 0.5) < 0.02),
        "verdict": ("market-only lands near 50% — harness looks clean"
                    if (not np.isnan(wr) and abs(wr - 0.5) < 0.02)
                    else "MARKET-ONLY IS NOT ~50%: SUSPECT LEAKAGE, STOP"),
    }
