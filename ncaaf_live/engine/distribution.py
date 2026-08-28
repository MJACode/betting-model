"""
Stage 2: the joint distribution over final scores (NCAAF port).

Ported from nfl/live_model/engine/distribution.py - the architecture and its
reasons live in that file's docstring and the NFL README. CFB changes are the
CONSTANTS only:
  * MAX_REMAINING 70 -> 90. FBS blowouts really do leave one team 70+ points
    of remaining scoring early on; clipping there would pile impossible mass
    on the cap and misprice every high total.
  * MU_EDGES extended upward for the same reason - CFB Stage 1 means run well
    past the NFL's, and a top bin that mixes mu=26 with mu=45 blurs exactly
    the games where the model has the most to say.

    P(final_home = h, final_away = a | state)

This one object prices every market in the system. Game lines, team totals,
second half lines, quarter lines and the correlation between them all fall out
of it, which is the entire reason for building it rather than fitting a
separate model per market: a model per market can quote a 2H total that is
inconsistent with its own full game total, and inconsistency is precisely what
we are trying to hunt in the books.

WHY EMPIRICAL AND NOT A PARAMETRIC FAMILY
NFL scoring is lumpy. Points arrive in 3s and 7s, so remaining-point totals
have real atoms at 0, 3, 7, 10, 14 and a Poisson or normal fit smears straight
through them. The empirical residual distribution, conditioned on how much time
is left, keeps the lumps. This mirrors the decision already made in
models/ev_engine.fit_margin_pmf for the pregame spread model, and for the same
reason: the key numbers are where the money is.

CORRELATION
The two teams' remaining points are not independent. Early in a game a fast
pace lifts both. Late in a close game they move against each other, because
one team running clock is the other team not getting the ball. A single
Gaussian copula parameter per time bucket captures the sign flip without
pretending to a full joint model.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# Time buckets, in seconds remaining in regulation. Boundaries chosen at the
# points where game dynamics actually change: end of the first half, the point
# where a two-score lead becomes close to safe, and the two minute warning.
TIME_EDGES = (0, 120, 300, 600, 900, 1800, 2700, 3601)
N_BUCKETS = len(TIME_EDGES) - 1

# Remaining-points support per team. 70 is comfortably past any realistic
# remaining total and keeps the joint grid small enough to price in microseconds.
MAX_REMAINING = 90
SUPPORT = np.arange(0, MAX_REMAINING + 1)


# Predicted-mean bins. THE SHAPE OF THE REMAINING-POINTS DISTRIBUTION IS A
# FUNCTION OF ITS MEAN, not of the clock alone. With two minutes left a team
# scores exactly zero more points 77.5% of the time (measured, 2023-24); with
# a full half left that atom is 2.5%. An additive residual model cannot span
# that, which is why the first version of this file failed the coverage gate at
# 29pp in the final two minutes while passing at under 2pp in the first half.
#
# So the distribution is conditioned on the Stage 1 mean and stored as the
# empirical pmf of ACTUAL remaining points. That construction cannot place
# mass below zero, reproduces the zero atom exactly, and keeps the 3 and 7
# point lumps that a parametric family smears through.
MU_EDGES = (0.0, 0.6, 1.2, 2.0, 3.0, 4.5, 6.5, 9.0, 12.0, 15.5, 20.0,
            26.0, 33.0, 41.0, 1e9)
N_MU = len(MU_EDGES) - 1


def time_bucket(seconds_remaining) -> np.ndarray:
    """Index into TIME_EDGES for a scalar or an array of seconds."""
    s = np.asarray(seconds_remaining, dtype=float)
    idx = np.searchsorted(np.asarray(TIME_EDGES[1:-1], dtype=float), s, side="right")
    return np.clip(idx, 0, N_BUCKETS - 1).astype(int)


def mu_bucket(mu) -> np.ndarray:
    m = np.asarray(mu, dtype=float)
    idx = np.searchsorted(np.asarray(MU_EDGES[1:-1], dtype=float), m, side="right")
    return np.clip(idx, 0, N_MU - 1).astype(int)


def _mu_centres() -> np.ndarray:
    """Representative mean for each mu bin, used to interpolate between bins."""
    edges = np.array(MU_EDGES, dtype=float)
    c = (edges[:-1] + np.minimum(edges[1:], 60.0)) / 2.0
    return c


MU_CENTRES = _mu_centres()


class ScoreDistribution:
    """
    Fitted Stage 2 model.

    Holds, per (side, mu bin, time bin), the empirical pmf of ACTUAL remaining
    points, with a backoff to the mu-only pmf wherever a cell is thin. Plus a
    Gaussian copula correlation per time bin.

    Serving: look up the pmf for each team's Stage 1 mean, interpolate between
    the two neighbouring mu bins so the price moves smoothly as the mean drifts,
    couple the two marginals, add the current score.
    """

    MIN_CELL = 200          # rows needed before a (mu, time) cell beats the backoff

    def __init__(self, pmf_mu_time, pmf_mu, counts, rho, meta=None):
        self.pmf_mu_time = pmf_mu_time      # (2, N_MU, N_BUCKETS, n_support)
        self.pmf_mu = pmf_mu                # (2, N_MU, n_support) backoff
        self.counts = counts                # (2, N_MU, N_BUCKETS)
        self.rho = np.asarray(rho, dtype=float)
        self.meta = meta or {}

    # ------------------------------------------------------------------ fit
    @classmethod
    def fit(cls, y_home, y_hat_home, y_away, y_hat_away, seconds_remaining,
            laplace: float = 0.5):
        """
        Fit the conditional pmfs.

        `y_hat_*` MUST be out-of-sample Stage 1 predictions. Fitted on in-sample
        predictions the spread of actual-given-predicted is too tight, so every
        derived market looks more certain than it is, so every derivative looks
        like it has an edge. That single mistake would make the whole system
        appear profitable and be worthless.

        Laplace smoothing is not cosmetic: a zero-probability final score
        becomes an infinite edge on the alternate line that lands on it.
        """
        ys = [np.asarray(y_home, float), np.asarray(y_away, float)]
        yh = [np.asarray(y_hat_home, float), np.asarray(y_hat_away, float)]
        tb = time_bucket(seconds_remaining)
        n_sup = len(SUPPORT)

        pmf_mt = np.full((2, N_MU, N_BUCKETS, n_sup), laplace)
        pmf_m = np.full((2, N_MU, n_sup), laplace)
        counts = np.zeros((2, N_MU, N_BUCKETS), dtype=int)

        for side in (0, 1):
            mb = mu_bucket(yh[side])
            obs = np.clip(np.rint(ys[side]).astype(int), 0, MAX_REMAINING)
            np.add.at(pmf_mt[side], (mb, tb, obs), 1.0)
            np.add.at(pmf_m[side], (mb, obs), 1.0)
            np.add.at(counts[side], (mb, tb), 1)

        pmf_mt /= pmf_mt.sum(axis=-1, keepdims=True)
        pmf_m /= pmf_m.sum(axis=-1, keepdims=True)

        rho = np.zeros(N_BUCKETS)
        dh = np.asarray(y_home, float) - np.asarray(y_hat_home, float)
        da = np.asarray(y_away, float) - np.asarray(y_hat_away, float)
        for b in range(N_BUCKETS):
            m = tb == b
            if m.sum() > 200:
                rho[b] = _spearman_to_gaussian(dh[m], da[m])

        return cls(pmf_mt, pmf_m, counts, rho, meta={
            "n": int(len(tb)), "laplace": laplace, "min_cell": cls.MIN_CELL,
        })

    # -------------------------------------------------------------- predict
    def _cell(self, side: int, mu_bin: int, t_bin: int) -> np.ndarray:
        """(mu, time) cell if it has enough support, else the mu-only backoff."""
        if self.counts[side, mu_bin, t_bin] >= self.MIN_CELL:
            return self.pmf_mu_time[side, mu_bin, t_bin]
        return self.pmf_mu[side, mu_bin]

    def _marginal(self, side: int, mu: float, seconds_remaining: float) -> np.ndarray:
        """
        pmf of remaining points, interpolated between neighbouring mu bins.

        Interpolation matters: without it the price of every market would step
        discontinuously each time Stage 1's mean crossed a bin edge, and a
        market sitting on a key number would flicker in and out of an edge for
        no reason the game had anything to do with.
        """
        t = int(time_bucket(seconds_remaining))
        b = int(mu_bucket(mu))
        centre = MU_CENTRES[b]

        if mu >= centre:
            b2 = min(b + 1, N_MU - 1)
        else:
            b2 = max(b - 1, 0)
        if b2 == b:
            return self._cell(side, b, t)

        c1, c2 = MU_CENTRES[b], MU_CENTRES[b2]
        w = 0.0 if c2 == c1 else float(np.clip((mu - c1) / (c2 - c1), 0.0, 1.0))
        p = (1 - w) * self._cell(side, b, t) + w * self._cell(side, b2, t)
        s = p.sum()
        return p / s if s > 0 else p

    def remaining_pmfs(self, mu_home: float, mu_away: float,
                       seconds_remaining: float):
        return (self._marginal(0, float(mu_home), seconds_remaining),
                self._marginal(1, float(mu_away), seconds_remaining))

    def joint_remaining(self, mu_home: float, mu_away: float,
                        seconds_remaining: float) -> np.ndarray:
        ph, pa = self.remaining_pmfs(mu_home, mu_away, seconds_remaining)
        b = int(time_bucket(seconds_remaining))
        return gaussian_copula_joint(ph, pa, float(self.rho[b]))

    def final_score_pmf(self, mu_home: float, mu_away: float,
                        seconds_remaining: float,
                        home_score: int, away_score: int) -> dict:
        """
        The object everything downstream prices from.

        Returned as the joint over REMAINING points plus the current score as
        an offset rather than a shifted grid: every market is a function of
        remaining points and the offset is a constant, so shifting a 71x71 grid
        on every quote would be pure waste.
        """
        joint = self.joint_remaining(mu_home, mu_away, seconds_remaining)
        return {
            "joint_remaining": joint,
            "support": SUPPORT,
            "home_score": int(home_score),
            "away_score": int(away_score),
            "rho": float(self.rho[int(time_bucket(seconds_remaining))]),
        }

    # ----------------------------------------------------------------- I/O
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, pmf_mu_time=self.pmf_mu_time,
                            pmf_mu=self.pmf_mu, counts=self.counts, rho=self.rho)
        path.with_suffix(".meta.json").write_text(json.dumps(self.meta, indent=2))

    @classmethod
    def load(cls, path: Path) -> "ScoreDistribution":
        z = np.load(path)
        meta_path = path.with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        return cls(z["pmf_mu_time"], z["pmf_mu"], z["counts"], z["rho"], meta)


def _spearman_to_gaussian(x, y) -> float:
    """Spearman rank correlation converted to a Gaussian copula parameter."""
    from scipy.stats import rankdata
    rx, ry = rankdata(x), rankdata(y)
    if len(rx) < 2:
        return 0.0
    rx = (rx - rx.mean()) / (rx.std() + 1e-12)
    ry = (ry - ry.mean()) / (ry.std() + 1e-12)
    s = float((rx * ry).mean())
    g = 2.0 * np.sin(np.pi * np.clip(s, -1.0, 1.0) / 6.0)
    return float(np.clip(g, -0.95, 0.95))


# Gauss-Hermite nodes for the one-factor coupling below. 32 is far more than
# the accuracy the marginals need and still costs microseconds.
# Node count scales with |rho|: at high correlation the conditional cdfs are
# steep and 32 nodes leave a visible marginal error. Fitted rho here is under
# 0.1, so the cheap path is the one that runs in production; the dense path
# exists so the invariant holds across the whole parameter range rather than
# only where we happen to sit today.
def _gh(n: int):
    x, w = np.polynomial.hermite_e.hermegauss(n)
    return x, w / w.sum()


_GH_CACHE = {n: _gh(n) for n in (32, 128)}


def gaussian_copula_joint(p_a: np.ndarray, p_b: np.ndarray,
                          rho: float) -> np.ndarray:
    """
    Couple two discrete marginals with a Gaussian copula.

    Implemented as a ONE FACTOR mixture rather than a bivariate normal cdf:

        Z_a = l_a W + sqrt(1 - l_a^2) e_a
        Z_b = l_b W + sqrt(1 - l_b^2) e_b      with  l_a * l_b = rho

    Conditional on the common factor W the two are independent, so the joint is
    a Gauss-Hermite weighted average of outer products of conditional pmfs.
    That is ~1ms per state; the equivalent scipy bivariate cdf over a 71x71
    grid is ~2 orders of magnitude slower, which is the difference between a
    calibration run finishing and a calibration run timing out.

    Marginals are preserved by construction, which is the property that
    matters: the coupling must not quietly move the total or the moneyline
    away from what Stage 1 and the market anchor already agreed on.
    """
    rho = float(np.clip(rho, -0.95, 0.95))
    if abs(rho) < 1e-6:
        return np.outer(p_a, p_b)

    from scipy.stats import norm

    lam = np.sqrt(abs(rho))
    lam_a, lam_b = lam, (lam if rho > 0 else -lam)
    sa = np.sqrt(max(1.0 - lam_a ** 2, 1e-12))
    sb = np.sqrt(max(1.0 - lam_b ** 2, 1e-12))

    # Latent thresholds: the normal quantiles of each marginal cdf, with a
    # leading -inf so the first cell picks up its own mass.
    def _thresholds(p):
        c = np.clip(np.cumsum(p), 0.0, 1.0)
        c[-1] = 1.0
        z = norm.ppf(np.clip(c, 1e-12, 1 - 1e-12))
        return np.concatenate([[-np.inf], z])

    za = _thresholds(p_a)
    zb = _thresholds(p_b)

    nodes, weights = _GH_CACHE[32 if abs(rho) < 0.5 else 128]
    joint = np.zeros((len(p_a), len(p_b)), dtype=float)
    for w_node, weight in zip(nodes, weights):
        ca = norm.cdf((za - lam_a * w_node) / sa)
        cb = norm.cdf((zb - lam_b * w_node) / sb)
        joint += weight * np.outer(np.diff(ca), np.diff(cb))

    joint = np.clip(joint, 0.0, None)
    total = joint.sum()
    if total <= 0:
        return np.outer(p_a, p_b)
    joint /= total

    # The quadrature is accurate to about 1e-12 at the correlations this model
    # actually fits (|rho| under 0.1), but degrades to ~1e-4 as |rho| approaches
    # 1. Exact marginals are the invariant every downstream price depends on,
    # and the anchor blend in particular is meaningless if the coupling can
    # nudge the total off the market number. Three rounds of iterative
    # proportional fitting restore them exactly, for microseconds.
    for _ in range(8):
        ra = joint.sum(axis=1)
        joint *= np.divide(p_a, ra, out=np.ones_like(ra),
                           where=ra > 0)[:, None]
        rb = joint.sum(axis=0)
        joint *= np.divide(p_b, rb, out=np.ones_like(rb),
                           where=rb > 0)[None, :]
    # End on the row scaling so p_a, which the loop above leaves adjusted one
    # step behind p_b, is the one that lands exact.
    ra = joint.sum(axis=1)
    joint *= np.divide(p_a, ra, out=np.ones_like(ra), where=ra > 0)[:, None]
    total = joint.sum()
    return joint / total if total > 0 else np.outer(p_a, p_b)
