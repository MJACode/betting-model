"""
Expected-value engine for NFL spreads.

The core correction over the CLV-in-points approach:

    CLV measured in points cannot tell you whether a bet is profitable,
    because the value of a point depends entirely on WHERE it sits.
    Moving 3.5 -> 3.0 is worth roughly 9 points of win probability.
    Moving 8.5 -> 8.0 is worth roughly 2. And the vig hurdle depends on
    the price, which varies from -105 to -115 across books.

So we work in probability space:

  1. Estimate the true spread mu for each game (best available estimate).
  2. Convert mu into a full discrete distribution over integer margins,
     using an empirical margin-relative-to-close distribution estimated on
     TRAINING seasons only. This preserves the lumpiness at 3, 7, 10, 14.
  3. For every book, every side, compute P(cover), P(push) and the exact EV
     at that book's actual price.
  4. Take the best EV available across the whole book universe, bet if it
     clears a threshold, and stake fractional Kelly.

Output is units won, not points of CLV.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SUPPORT = np.arange(-60, 61)          # integer margins
SUP_IDX = {int(k): i for i, k in enumerate(SUPPORT)}


# ------------------------------------------------------------------ pricing
def american_to_decimal(odds):
    odds = np.asarray(odds, dtype=float)
    return np.where(odds > 0, 1 + odds / 100.0, 1 + 100.0 / np.abs(odds))


# ------------------------------------------- empirical margin distribution
def fit_margin_pmf(margins: np.ndarray, closes: np.ndarray,
                   laplace: float = 2.0) -> np.ndarray:
    """
    pmf of (margin - closing spread) over integer support.

    Estimated only on games with an integer closing spread, so the residual
    is integer-valued and the key-number atoms (0, +/-3, +/-7) survive.
    Laplace smoothing keeps the tails from producing zero-probability
    outcomes that would blow up an EV calculation.
    """
    mask = np.isfinite(margins) & np.isfinite(closes) & (np.mod(closes, 1) == 0)
    d = (margins[mask] - closes[mask]).astype(int)
    counts = np.full(len(SUPPORT), laplace, dtype=float)
    for v in d:
        i = SUP_IDX.get(int(v))
        if i is not None:
            counts[i] += 1.0
    return counts / counts.sum()


def margin_pmf_for(mu: np.ndarray, base_pmf: np.ndarray) -> np.ndarray:
    """
    Shift the base residual pmf by a continuous mu via linear interpolation
    between the two adjacent integer shifts. Returns (n_games, n_support).
    """
    mu = np.asarray(mu, dtype=float)
    lo = np.floor(mu).astype(int)
    frac = mu - lo
    n, m = len(mu), len(SUPPORT)
    out = np.zeros((n, m))
    for w, shift in ((1.0 - frac, lo), (frac, lo + 1)):
        for j in range(m):
            tgt = j + shift                      # index in output for support[j]
            ok = (tgt >= 0) & (tgt < m)
            idx = np.where(ok)[0]
            if len(idx):
                out[idx, tgt[idx]] += w[idx] * base_pmf[j]
    s = out.sum(axis=1, keepdims=True)
    return out / np.where(s > 0, s, 1.0)


def cover_probs(pmf: np.ndarray, lines: np.ndarray):
    """
    For each row's pmf and its line L (home handicap, home covers if
    margin > L), return (p_home, p_push, p_away).
    """
    cum = np.cumsum(pmf, axis=1)                       # P(margin <= support[j])
    Lf = np.floor(lines).astype(int)
    j = np.clip(Lf - SUPPORT[0], 0, len(SUPPORT) - 1)
    rows = np.arange(len(lines))
    cdf_at_floor = cum[rows, j]                        # P(margin <= floor(L))
    is_int = np.mod(lines, 1) == 0
    p_push = np.where(is_int, pmf[rows, j], 0.0)
    p_home = 1.0 - cdf_at_floor                        # P(margin > floor(L))
    p_away = np.where(is_int, cdf_at_floor - p_push, cdf_at_floor)
    return p_home, p_push, p_away


def ev_per_unit(p_win, p_push, dec):
    """Push refunds the stake, so it contributes zero to EV."""
    p_lose = 1.0 - p_win - p_push
    return p_win * (dec - 1.0) - p_lose


def kelly_fraction(p_win, p_push, dec, frac=0.25, cap=0.03):
    b = dec - 1.0
    p_lose = 1.0 - p_win - p_push
    denom = np.where(p_lose > 0, p_lose, np.nan)
    # conditional-on-no-push Kelly
    tot = p_win + p_lose
    pw = np.where(tot > 0, p_win / tot, 0.0)
    f = (b * pw - (1 - pw)) / b
    f = np.clip(f, 0, None) * frac
    return np.minimum(f, cap)
