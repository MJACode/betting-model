"""
Derive every game-line market from the one score distribution (NCAAF port).

Verbatim port of nfl/live_model/engine/pricing.py - every function here is
football-generic given the joint pmf. One semantic note for CFB: a FINAL
regulation tie goes to overtime rather than standing, so price_moneyline's
"push" mass reads as "regulation ends level" - the full-game ML then hinges
on OT, which the engine declines to model. The executor must treat that mass
as uncertainty, never fold it into a side.

Everything in here is a function of the SAME joint pmf over remaining points.
That is the point. A book that prices its 2H total off one model and its full
game total off another can quote two numbers that cannot both be right, and
that inconsistency is exactly what lane b hunts. We can only see it if our own
numbers are guaranteed consistent, which they are by construction here.

WHAT IS EXACT AND WHAT IS NOT
  Full game ML / spread / total / team totals: exact given the pmf.
  Second half markets: exact when priced AT HALFTIME, where second half points
    and remaining points are the same thing. Priced mid third quarter they need
    the halftime score, which the caller supplies.
  Quarter markets: NOT exact. The engine models points remaining to the end of
    the game, not points inside one quarter, so a quarter price requires
    allocating remaining points across the periods still to play. That
    allocation is a documented approximation and quarter markets are flagged
    `approx=True` and excluded from the default betting lanes until someone
    validates them. Betting an approximation because it was easy to compute is
    how a model loses money politely.
"""

from __future__ import annotations

import numpy as np

from .distribution import MAX_REMAINING, SUPPORT

PUSH = "push"


# ------------------------------------------------------------------ pricing
def american_to_prob(odds: float) -> float:
    o = float(odds)
    return 100.0 / (o + 100.0) if o > 0 else (-o) / (-o + 100.0)


def american_to_decimal(odds: float) -> float:
    o = float(odds)
    return 1.0 + o / 100.0 if o > 0 else 1.0 + 100.0 / abs(o)


def devig_power(px_a: float, px_b: float) -> tuple[float, float]:
    """
    Power de-vig of a two-way market: solve p_a^k + p_b^k = 1.

    Power rather than multiplicative because the hold is not spread
    proportionally wherever the favourite-longshot bias bites, and on an
    in-play moneyline at -600 it bites hard. This matches the method already
    used in scripts/screen_books.py so the whole repo devigs one way.
    """
    a, b = american_to_prob(px_a), american_to_prob(px_b)
    if not (0 < a < 1 and 0 < b < 1):
        return float("nan"), float("nan")
    lo, hi = 0.2, 5.0
    for _ in range(80):
        k = (lo + hi) / 2
        if a ** k + b ** k > 1:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    pa = a ** k
    return float(pa), float(1.0 - pa)


# ------------------------------------------------------- marginals from joint
def margin_pmf(joint: np.ndarray, score_diff: int) -> tuple[np.ndarray, np.ndarray]:
    """
    pmf of the FINAL margin (home minus away).

    Returned as (values, probs) over the integer support that the grid can
    actually produce, offset by the current score differential.
    """
    n = joint.shape[0]
    idx = (SUPPORT[:, None] - SUPPORT[None, :]) + (n - 1)      # 0 .. 2n-2
    probs = np.bincount(idx.ravel(), weights=joint.ravel(), minlength=2 * n - 1)
    values = np.arange(-(n - 1), n) + int(score_diff)
    return values, probs


def total_pmf(joint: np.ndarray, points_so_far: int) -> tuple[np.ndarray, np.ndarray]:
    """pmf of the FINAL combined total."""
    n = joint.shape[0]
    idx = SUPPORT[:, None] + SUPPORT[None, :]
    probs = np.bincount(idx.ravel(), weights=joint.ravel(), minlength=2 * n - 1)
    values = np.arange(0, 2 * n - 1) + int(points_so_far)
    return values, probs


def team_total_pmf(joint: np.ndarray, side: str,
                   score_now: int) -> tuple[np.ndarray, np.ndarray]:
    probs = joint.sum(axis=1) if side == "home" else joint.sum(axis=0)
    values = SUPPORT + int(score_now)
    return values, probs


# ------------------------------------------------------------------ markets
def _over_under(values: np.ndarray, probs: np.ndarray, line: float) -> dict:
    """P(over), P(under), P(push) for a total-style market at `line`."""
    over = float(probs[values > line].sum())
    under = float(probs[values < line].sum())
    push = float(probs[values == line].sum()) if float(line).is_integer() else 0.0
    return {"over": over, "under": under, PUSH: push}


def price_moneyline(dist_out: dict) -> dict:
    """
    P(home win), P(away win), P(tie).

    An NFL tie is a moneyline push at every book that matters, so it is
    reported separately rather than folded into either side. Folding it in
    would overstate both sides by roughly the tie probability, which is small
    but is exactly the size of the edges we are hunting.
    """
    values, probs = margin_pmf(dist_out["joint_remaining"],
                               dist_out["home_score"] - dist_out["away_score"])
    return {
        "home": float(probs[values > 0].sum()),
        "away": float(probs[values < 0].sum()),
        PUSH: float(probs[values == 0].sum()),
    }


def price_spread(dist_out: dict, spread_home: float) -> dict:
    """
    P(home covers `spread_home`), standard form: negative means home is laying.

    Home covers when margin + spread_home > 0.
    """
    values, probs = margin_pmf(dist_out["joint_remaining"],
                               dist_out["home_score"] - dist_out["away_score"])
    adj = values + float(spread_home)
    push = float(probs[adj == 0].sum()) if float(spread_home).is_integer() else 0.0
    return {
        "home": float(probs[adj > 0].sum()),
        "away": float(probs[adj < 0].sum()),
        PUSH: push,
    }


def price_total(dist_out: dict, line: float) -> dict:
    values, probs = total_pmf(dist_out["joint_remaining"],
                              dist_out["home_score"] + dist_out["away_score"])
    return _over_under(values, probs, line)


def price_team_total(dist_out: dict, side: str, line: float) -> dict:
    score_now = dist_out["home_score"] if side == "home" else dist_out["away_score"]
    values, probs = team_total_pmf(dist_out["joint_remaining"], side, score_now)
    return _over_under(values, probs, line)


def price_second_half(dist_out: dict, market: str, line: float,
                      half_home_score: int, half_away_score: int) -> dict:
    """
    Second half markets.

    Second half points = final minus the score at halftime. At halftime that is
    exactly the remaining-points distribution, which is why this lane is the
    cleanest in the system: no approximation, and a 13 minute window with the
    market open and no plays being run.
    """
    joint = dist_out["joint_remaining"]
    # Points already scored in the second half, if we are past halftime.
    h_done = int(dist_out["home_score"]) - int(half_home_score)
    a_done = int(dist_out["away_score"]) - int(half_away_score)

    if market == "totals_h2":
        values, probs = total_pmf(joint, h_done + a_done)
        return _over_under(values, probs, line)
    if market == "spreads_h2":
        values, probs = margin_pmf(joint, h_done - a_done)
        adj = values + float(line)
        push = float(probs[adj == 0].sum()) if float(line).is_integer() else 0.0
        return {"home": float(probs[adj > 0].sum()),
                "away": float(probs[adj < 0].sum()), PUSH: push}
    if market == "h2h_h2":
        values, probs = margin_pmf(joint, h_done - a_done)
        return {"home": float(probs[values > 0].sum()),
                "away": float(probs[values < 0].sum()),
                PUSH: float(probs[values == 0].sum())}
    raise ValueError(f"not a second half market: {market}")


def price_quarter(dist_out: dict, market: str, line: float,
                  seconds_left_in_quarter: float,
                  seconds_remaining: float) -> dict:
    """
    Quarter markets, APPROXIMATE. Flagged, and off by default.

    The engine gives points remaining to the end of the GAME. Splitting that
    across the remaining periods by clock share assumes scoring is uniform in
    time, which it is not: the two minute drill and end of half clock
    management both concentrate scoring. The approximation is here so the
    market can be priced and studied, not so it can be bet.
    """
    share = 0.0
    if seconds_remaining > 0:
        share = float(np.clip(seconds_left_in_quarter / seconds_remaining, 0.0, 1.0))

    joint = dist_out["joint_remaining"]
    ph = joint.sum(axis=1)
    pa = joint.sum(axis=0)
    mu_h = float((ph * SUPPORT).sum() * share)
    mu_a = float((pa * SUPPORT).sum() * share)

    # Poisson-ish scaling of the marginals down to the quarter. Deliberately
    # crude; a real quarter model would need its own residual fit.
    from scipy.stats import poisson
    k = np.arange(0, MAX_REMAINING + 1)
    qh = poisson.pmf(k, max(mu_h, 1e-6))
    qa = poisson.pmf(k, max(mu_a, 1e-6))
    qh /= qh.sum()
    qa /= qa.sum()
    qjoint = np.outer(qh, qa)

    out_stub = {"joint_remaining": qjoint, "support": SUPPORT,
                "home_score": 0, "away_score": 0}
    if market.startswith("totals"):
        res = price_total(out_stub, line)
    elif market.startswith("spreads"):
        res = price_spread(out_stub, line)
    elif market.startswith("h2h"):
        res = price_moneyline(out_stub)
    else:
        raise ValueError(f"not a quarter market: {market}")
    res["approx"] = True
    return res


# ------------------------------------------------------------- anchor blend
def anchor_to_market(dist_out: dict, *, market_home_wp: float | None = None,
                     market_total: float | None = None,
                     max_iter: int = 40) -> dict:
    """
    Recalibrate the distribution so its implied main line matches the market's.

    The live main line is truth (build spec constraint 4). Our job is the SHAPE
    of the distribution and the CONSISTENCY of the derivatives, not disagreeing
    with the number the whole market is repricing off a 1 second official feed.
    So we shift the marginals until our implied moneyline and total agree with
    the devigged market, and only then price the derivatives.

    Without this step every derivative edge would be contaminated by our
    disagreement with the main line, and we would systematically bet the side
    of a 2H total that our full game total already disagreed with. That is not
    a lag edge, it is just a wrong model with extra steps.
    """
    joint = dist_out["joint_remaining"].copy()
    ph = joint.sum(axis=1)
    pa = joint.sum(axis=0)

    if market_total is not None:
        pts_now = dist_out["home_score"] + dist_out["away_score"]
        target_remaining = float(market_total) - pts_now
        cur = float((ph * SUPPORT).sum() + (pa * SUPPORT).sum())
        if cur > 1e-6 and target_remaining > 0:
            # Exponential tilt on the remaining-points marginals: preserves
            # shape and support while moving the mean onto the market number.
            scale = target_remaining / cur
            ph = _tilt_to_mean(ph, (ph * SUPPORT).sum() * scale, max_iter)
            pa = _tilt_to_mean(pa, (pa * SUPPORT).sum() * scale, max_iter)

    if market_home_wp is not None and np.isfinite(market_home_wp):
        ph, pa = _shift_to_wp(ph, pa, dist_out, float(market_home_wp), max_iter)

    from .distribution import gaussian_copula_joint
    rho = dist_out.get("rho", 0.0)
    out = dict(dist_out)
    out["joint_remaining"] = gaussian_copula_joint(ph, pa, float(rho))
    out["anchored"] = True
    return out


def _tilt_to_mean(p: np.ndarray, target_mean: float, max_iter: int) -> np.ndarray:
    """Exponential tilt p by exp(theta * k), solving for the target mean."""
    target_mean = float(np.clip(target_mean, 0.05, MAX_REMAINING - 1))
    lo, hi = -2.0, 2.0
    for _ in range(max_iter):
        theta = (lo + hi) / 2
        w = p * np.exp(theta * SUPPORT)
        w = w / w.sum()
        m = float((w * SUPPORT).sum())
        if m < target_mean:
            lo = theta
        else:
            hi = theta
    theta = (lo + hi) / 2
    w = p * np.exp(theta * SUPPORT)
    return w / w.sum()


def _shift_to_wp(ph: np.ndarray, pa: np.ndarray, dist_out: dict,
                 target_wp: float, max_iter: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Move probability between the two teams until the implied home win
    probability matches the market's, holding the total fixed.
    """
    target_wp = float(np.clip(target_wp, 0.001, 0.999))
    lo, hi = -3.0, 3.0
    for _ in range(max_iter):
        theta = (lo + hi) / 2
        h = _tilt_by(ph, theta)
        a = _tilt_by(pa, -theta)
        stub = {"joint_remaining": np.outer(h, a),
                "home_score": dist_out["home_score"],
                "away_score": dist_out["away_score"]}
        wp = price_moneyline(stub)["home"]
        if wp < target_wp:
            lo = theta
        else:
            hi = theta
    theta = (lo + hi) / 2
    return _tilt_by(ph, theta), _tilt_by(pa, -theta)


def _tilt_by(p: np.ndarray, theta: float) -> np.ndarray:
    w = p * np.exp(theta * SUPPORT)
    return w / w.sum()
