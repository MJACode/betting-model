"""
NCAAB final-margin distribution ("emp3"): the chance a full-game spread wins,
pushes or loses, given the market's expected home margin.

Shared by the NCAAB spread model (models/ncaab_spread_market.py) and the
moneyline and first-half models planned on the same pieces. A straight port of
the research's kernel (scratch round3/spreads/dist_kern.py, "emp3"), checked
table for table against the research's fitted tables by
scripts/ncaab_spread_market_build.py (largest difference 0.0).

WHAT IT IS. For an expected home margin m, the distribution of FINAL margins
(home minus away, overtime included) among earlier games whose closing line
implied a mean near m. Kernel-weighted in the mean: Gaussian, bandwidth 0.75
points, widened by x1.25 until the weights sum to at least 500 games. Margins
are not smoothed, so the key numbers (the trough at 1, the peak at 3,
overtime's small margins) are whatever history shows for games like this one,
and a 0 margin cannot happen except in widened tails. Where the kernel had to
widen, each game's margin is first moved by the whole-point difference of
means, or the tail's mean is dragged toward the centre. Tabulated on a grid of
means from -45 to +45 in steps of 0.25 and interpolated linearly between grid
points. Margins are clipped to -90..+90.

    T = fit(margins, means)              # fit once, freeze with to_json()
    pw, pp, pl = probs(mu, -home_line, T)  # P(home covers), P(push), P(home fails)

`thresh` is the margin the home side must beat: a home line L covers when
margin + L > 0, i.e. margin > -L. A half-point line cannot push.
"""
from __future__ import annotations

import numpy as np

KLO, KHI = -90, 90
KK = np.arange(KLO, KHI + 1)
GRID = np.arange(-45.0, 45.0001, 0.25)
H0 = 0.75          # starting bandwidth, points of mean
NMIN = 500         # the kernel widens until its weights sum to this
WIDEN = 1.25
H_MAX = 20.0


def fit(margin, mu, h0: float = H0, nmin: int = NMIN) -> dict:
    """Fit the table on final margins and the means their lines implied.

    The input ORDER is part of the result: the weighted sums are added in it,
    so the same games in another order can differ in the last bit. The build
    sorts by game date, then game id, as the research did."""
    margin = np.asarray(margin, int)
    mu = np.asarray(mu, float)
    mclip = np.clip(margin, KLO, KHI)
    onehot_idx = mclip - KLO
    pmf = np.zeros((len(GRID), len(KK)))
    hs = np.zeros(len(GRID))
    neff = np.zeros(len(GRID))
    for i, m in enumerate(GRID):
        h = h0
        while True:
            w = np.exp(-0.5 * ((mu - m) / h) ** 2)
            if w.sum() >= nmin or h > H_MAX:
                break
            h *= WIDEN
        if h > h0:
            idx = np.clip(margin + np.round(m - mu).astype(int), KLO, KHI) - KLO
        else:
            idx = onehot_idx
        p = np.bincount(idx, weights=w, minlength=len(KK))
        pmf[i] = p / p.sum()
        hs[i] = h
        neff[i] = w.sum() ** 2 / (w ** 2).sum()
    return {"pmf": pmf, "ge": _ge(pmf), "h": hs, "neff": neff}


def _ge(pmf: np.ndarray) -> np.ndarray:
    """P(X >= k) per grid row, the same operation the fit uses."""
    return np.cumsum(pmf[:, ::-1], axis=1)[:, ::-1]


def _interp(T: dict, key: str, mu, col) -> np.ndarray:
    """Linear interpolation over the mean grid of T[key] at integer column col."""
    mu = np.asarray(mu, float)
    bad = ~np.isfinite(mu)
    x = np.clip((np.where(bad, 0.0, mu) - GRID[0]) / 0.25, 0, len(GRID) - 1 - 1e-9)
    i0 = np.floor(x).astype(int)
    f = x - i0
    tab = T[key]
    out = tab[i0, col] * (1 - f) + tab[i0 + 1, col] * f
    return np.where(bad, np.nan, out)


def probs(mu, thresh, T: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(P(margin > thresh), P(margin == thresh), P(margin < thresh)) for an
    expected home margin mu. Vectorised; a non-finite mu gives NaN."""
    mu = np.asarray(mu, float)
    thresh = np.asarray(thresh, float)
    integer = np.isclose(thresh, np.round(thresh))
    m = np.where(integer, np.round(thresh) + 1, np.ceil(thresh)).astype(int)
    col = np.clip(m - KLO, 0, len(KK) - 1)
    pw = _interp(T, "ge", mu, col)
    pw = np.where(m > KHI, 0.0, np.where(m < KLO, 1.0, pw))
    t = np.round(thresh).astype(int)
    pp = np.where(integer & (t >= KLO) & (t <= KHI),
                  _interp(T, "pmf", mu, np.clip(t - KLO, 0, len(KK) - 1)), 0.0)
    return pw, pp, 1 - pw - pp


def home_cover(mu, home_line, T: dict) -> tuple[np.ndarray, np.ndarray]:
    """(P(home covers | no push), P(push)) at a HOME line (CLAUDE.md section 4:
    the home number; home covers when margin + line > 0)."""
    pw, pp, pl = probs(mu, -np.asarray(home_line, float), T)
    with np.errstate(invalid="ignore", divide="ignore"):    # a certain push: NaN
        return pw / (pw + pl), pp


def mean_for_cover(target, thresh, T: dict, lo: float = -45.0, hi: float = 45.0,
                   it: int = 50) -> np.ndarray:
    """The mean whose P(margin > thresh | no push) is `target` (bisection)."""
    target = np.asarray(target, float)
    lo = np.full(target.shape, lo)
    hi = np.full(target.shape, hi)
    for _ in range(it):
        mid = (lo + hi) / 2
        pw, pp, pl = probs(mid, thresh, T)
        f = pw / np.maximum(pw + pl, 1e-12)
        lo = np.where(f < target, mid, lo)
        hi = np.where(f < target, hi, mid)
    return (lo + hi) / 2


# ── freezing ──────────────────────────────────────────────────────────────────

def to_json(T: dict) -> dict:
    """The table as JSON: each grid row's non-zero span of the pmf, every float
    at full precision (json's repr round-trips exactly), so from_json gives back
    the identical table. `ge` is not stored: it is the pmf's running sum."""
    rows = []
    for r in T["pmf"]:
        nz = np.flatnonzero(r)
        if not len(nz):
            rows.append([0, []])
            continue
        a, b = int(nz[0]), int(nz[-1])
        rows.append([a, [float(v) for v in r[a:b + 1]]])
    return {"kind": "emp3", "grid": [float(GRID[0]), float(GRID[-1]), 0.25],
            "margins": [KLO, KHI], "h0": H0, "nmin": NMIN,
            "pmf_rows": rows,
            "h": [float(v) for v in T["h"]], "neff": [float(v) for v in T["neff"]]}


def from_json(d: dict) -> dict:
    if d.get("kind") != "emp3":
        raise ValueError("not an emp3 margin table")
    if d["grid"] != [float(GRID[0]), float(GRID[-1]), 0.25] or d["margins"] != [KLO, KHI]:
        raise ValueError("emp3 table built on another grid")
    pmf = np.zeros((len(GRID), len(KK)))
    for i, (a, vals) in enumerate(d["pmf_rows"]):
        if vals:
            pmf[i, a:a + len(vals)] = np.asarray(vals, float)
    return {"pmf": pmf, "ge": _ge(pmf), "h": np.asarray(d["h"], float),
            "neff": np.asarray(d["neff"], float)}
