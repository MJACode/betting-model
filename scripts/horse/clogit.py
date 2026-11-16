"""Conditional logit: one softmax per race. Shared by the racing studies.

Rows must be sorted so that each race's runners are contiguous; `starts_of`
gives the first row of each race."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def fit_clogit(X: np.ndarray, won: np.ndarray, starts: np.ndarray, l2: float = 1.0) -> np.ndarray:
    """Maximise sum over races of log softmax(X b)[winner] - l2/2 |b|^2."""
    def nll(b):
        z = X @ b
        mx = np.maximum.reduceat(z, starts)
        e = np.exp(z - np.repeat(mx, np.diff(np.append(starts, len(z)))))
        s = np.add.reduceat(e, starts)
        p = e / np.repeat(s, np.diff(np.append(starts, len(z))))
        ll = (z[won == 1] - (mx + np.log(s))).sum()
        grad = X[won == 1].sum(0) - np.add.reduceat(p[:, None] * X, starts).sum(0)
        return -ll + 0.5 * l2 * b @ b, -grad + l2 * b
    res = minimize(nll, np.zeros(X.shape[1]), jac=True, method="L-BFGS-B")
    return res.x


def softmax_by_race(z: np.ndarray, starts: np.ndarray) -> np.ndarray:
    sizes = np.diff(np.append(starts, len(z)))
    mx = np.repeat(np.maximum.reduceat(z, starts), sizes)
    e = np.exp(z - mx)
    return e / np.repeat(np.add.reduceat(e, starts), sizes)


def starts_of(df: pd.DataFrame, key: str = "race_id") -> np.ndarray:
    rid = df[key].to_numpy()
    return np.flatnonzero(np.r_[True, rid[1:] != rid[:-1]])


