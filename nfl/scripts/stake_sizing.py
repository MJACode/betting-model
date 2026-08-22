#!/usr/bin/env python3
"""
How big should a wind-under bet be?

The card has always printed a stake, but the number was asserted rather than
derived: 25% Kelly hard-capped at 1% of bankroll, with a comment saying the cap
should bind. This script derives a unit size from the same validated inputs the
rule itself uses, and reports what each candidate size does to growth, drawdown
and ruin over a realistic three-season horizon.

    python scripts/stake_sizing.py                      # all sections
    python scripts/stake_sizing.py --section sim
    python scripts/stake_sizing.py --p-dead 0.35        # more pessimistic
    python scripts/stake_sizing.py --price -104         # better juice

Sections
  kelly        Kelly at the point estimate, and what true win rate each stake needs
  uncertainty  the posterior over the true under rate, and the Kelly it implies
  sim          Monte Carlo over worlds, seasons, slates and correlated outcomes
  recommend    the unit table

INPUTS, ALL FROM THIS REPO
--------------------------
Deployment config is threshold 11 on the raw Open-Meteo forecast. From
`validate_wind_forecast.py --section sim` at lead 3:

    under 56.72%, 95% CI [52.5, 61.0], 49.1 bets per season, P(beat vig) 0.980

Those CIs bootstrap over games AND forecast noise jointly, so they are the right
width for sampling error. They do NOT cover model risk: 2024 and 2025 both lost,
and the live reading that the market has started pricing wind correctly cannot
yet be separated from variance. `--p-dead` puts explicit prior mass on that
reading, which is the single biggest driver of the answer.

Costs zero Odds API credits and reads no network.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

RNG = np.random.default_rng(20260817)

# Measured at the deployment config (threshold 11, lead 3).
UNDER_MEAN = 0.5672
UNDER_CI = (0.525, 0.610)
BETS_PER_SEASON = 49.1
WEEKS_PER_SEASON = 18


def american_to_decimal(px: float) -> float:
    return 1.0 + (px / 100.0 if px > 0 else 100.0 / -px)


def breakeven(px: float) -> float:
    d = american_to_decimal(px)
    return 1.0 / d


def kelly(p: float, px: float) -> float:
    b = american_to_decimal(px) - 1.0
    return max(0.0, (b * p - (1 - p)) / b)


def log_growth(p: float, f: float, px: float) -> float:
    """Expected log growth per bet at true win probability p and stake fraction f."""
    b = american_to_decimal(px) - 1.0
    if f <= 0:
        return 0.0
    if f >= 1:
        return -np.inf
    return p * np.log(1 + f * b) + (1 - p) * np.log(1 - f)


def posterior(n_draws: int, p_dead: float, price: float) -> np.ndarray:
    """
    Mixture posterior over the true under rate.

    Live component: Beta matched to the measured mean and bootstrap CI.
    Dead component: the market has adjusted and the bet is exactly breakeven at
    the quoted price. This is not a straw man; it is one of the two readings the
    runbook says cannot yet be separated.
    """
    sd = (UNDER_CI[1] - UNDER_CI[0]) / (2 * 1.959964)
    nu = UNDER_MEAN * (1 - UNDER_MEAN) / sd**2 - 1
    a, b = UNDER_MEAN * nu, (1 - UNDER_MEAN) * nu
    live = RNG.beta(a, b, n_draws)
    dead = np.full(n_draws, breakeven(price))
    return np.where(RNG.random(n_draws) < p_dead, dead, live)


# --------------------------------------------------------------------------- #

def sec_kelly(a) -> None:
    px = a.price
    be = breakeven(px)
    print(f"\n=== KELLY AT THE POINT ESTIMATE ({px:+.0f}, breakeven {be*100:.2f}%) ===")
    f_star = kelly(UNDER_MEAN, px)
    print(f"  measured under rate      {UNDER_MEAN*100:.2f}%")
    print(f"  edge over breakeven      {(UNDER_MEAN-be)*100:+.2f} pp")
    print(f"  full Kelly               {f_star*100:.2f}% of bankroll")
    print(f"  quarter Kelly            {f_star*25:.2f}%   <- what the card computes")
    print(f"  shipped cap              1.00%   <- what the card actually stakes")
    print("\n  Full Kelly here is a 10-bet-a-month program betting a tenth of the roll")
    print("  per game. Nobody should run that on a 49-bet sample. The question is not")
    print("  whether to shade it down but by how much, and against what risk.")

    print("\n  --- what true under rate does each flat stake need to break even? ---")
    print("  (flat staking is EV-driven, so the answer is just the vig line; the")
    print("   difference between sizes is entirely risk, shown in the sim section)")
    rows = []
    for f in (0.0025, 0.005, 0.0075, 0.01, 0.02, 0.03, 0.05, f_star / 2, f_star):
        rows.append(dict(
            stake_pct=round(f * 100, 2),
            g_at_measured=round(log_growth(UNDER_MEAN, f, px) * 1e4, 2),
            g_at_lo_ci=round(log_growth(UNDER_CI[0], f, px) * 1e4, 2),
            g_at_breakeven=round(log_growth(be, f, px) * 1e4, 2),
            g_at_52pct=round(log_growth(0.52, f, px) * 1e4, 2),
        ))
    t = pd.DataFrame(rows).sort_values("stake_pct")
    print("\n  expected log growth per bet, in basis points, by TRUE under rate:")
    print(t.to_string(index=False))
    g1 = -log_growth(0.52, 0.01, px) * 1e4
    gk = -log_growth(0.52, f_star, px) * 1e4
    u1 = log_growth(UNDER_MEAN, 0.01, px) * 1e4
    uk = log_growth(UNDER_MEAN, f_star, px) * 1e4
    print(f"\n  Read the last column. At a true rate of 52% - inside the CI - a 1% flat")
    print(f"  stake loses {g1:.2f} bp a bet and full Kelly loses {gk:.2f} bp, "
          f"{gk/g1:.0f}x the damage,")
    print(f"  for only {uk/u1:.1f}x the upside if the measured rate is right. That")
    print("  asymmetry is the whole argument for a small flat stake.")


def sec_uncertainty(a) -> None:
    px = a.price
    be = breakeven(px)
    post = posterior(200_000, a.p_dead, px)
    ks = np.array([kelly(p, px) for p in post[:20_000]])
    print(f"\n=== POSTERIOR OVER THE TRUE UNDER RATE (p_dead={a.p_dead:.2f}) ===")
    q = np.percentile(post, [2.5, 10, 25, 50, 75, 90, 97.5])
    print("  percentiles: " + "  ".join(f"p{k}={v*100:.1f}%" for k, v in
                                        zip([2.5, 10, 25, 50, 75, 90, 97.5], q)))
    print(f"  P(true rate at or below breakeven {be*100:.2f}%) = "
          f"{(post <= be + 1e-9).mean()*100:.1f}%")
    print(f"  mean                        {post.mean()*100:.2f}%")

    print("\n  implied Kelly fraction:")
    kq = np.percentile(ks, [5, 25, 50, 75, 95])
    print("  " + "  ".join(f"p{k}={v*100:.2f}%" for k, v in zip([5, 25, 50, 75, 95], kq)))
    print(f"  P(Kelly = 0, i.e. no bet) = {(ks <= 1e-9).mean()*100:.1f}%")

    print("\n  A NOTE ON WHY UNCERTAINTY ALONE DOES NOT SHRINK KELLY")
    print("  Expected log growth is linear in p, so maximising it over a posterior")
    print("  gives the same answer as plugging in the posterior mean. Uncertainty")
    print("  does not bite through the expectation; it bites because the draw is")
    print("  made ONCE and then repeated across every bet you place. You do not get")
    print("  a fresh p each week. That is what the sim below models, and it is why")
    print("  the sensible stake is far below the Kelly implied by the mean.")


def _simulate(f_rule, post, a) -> dict:
    """
    One pass over `n_worlds` worlds. In each world the true rate is drawn once and
    held for the whole horizon, then seasons of correlated slates are played out.
    Stakes inside a slate come out of the bankroll at the same time, because they
    do in real life.
    """
    n = a.worlds
    px, dec = a.price, american_to_decimal(a.price)
    b = dec - 1.0
    rho = a.rho
    z_thresh = post  # p per world

    bank = np.ones(n)
    peak = np.ones(n)
    maxdd = np.zeros(n)
    n_bets = np.zeros(n)
    weeks = int(WEEKS_PER_SEASON * a.seasons)
    per_week = BETS_PER_SEASON / WEEKS_PER_SEASON

    for _ in range(weeks):
        k = RNG.poisson(per_week, n)
        kmax = int(k.max()) if k.max() > 0 else 0
        if kmax == 0:
            continue
        # Gaussian copula: one shock per slate, one idiosyncratic draw per bet.
        # Same-day wind games often sit under the same synoptic system, so their
        # outcomes are not independent.
        shock = RNG.standard_normal((n, 1))
        eps = RNG.standard_normal((n, kmax))
        z = np.sqrt(rho) * shock + np.sqrt(1 - rho) * eps
        thr = _norm_ppf(z_thresh)[:, None]
        win = z < thr                                   # under hits
        live = np.arange(kmax)[None, :] < k[:, None]
        win = win & live

        stake = f_rule(bank)[:, None] * live            # fraction of bankroll per bet
        pnl = np.where(win, stake * b, -stake)
        bank = bank * (1 + pnl.sum(axis=1))
        bank = np.maximum(bank, 1e-9)
        n_bets += k
        peak = np.maximum(peak, bank)
        maxdd = np.maximum(maxdd, 1 - bank / peak)

    growth = bank - 1
    return dict(
        median=np.median(growth), p05=np.percentile(growth, 5),
        p25=np.percentile(growth, 25), p75=np.percentile(growth, 75),
        mean_log=np.mean(np.log(bank)),
        p_down=(bank < 1).mean(), p_dd20=(maxdd > 0.20).mean(),
        p_dd35=(maxdd > 0.35).mean(), p_half=(bank < 0.5).mean(),
        med_dd=np.median(maxdd), bets=n_bets.mean(),
    )


def _norm_ppf(p):
    """Acklam's inverse normal CDF. Avoids a scipy import for one function."""
    p = np.asarray(p, dtype=float)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    q = np.empty_like(p)
    lo, hi = p < plow, p > phigh
    mid = ~(lo | hi)
    if lo.any():
        s = np.sqrt(-2 * np.log(p[lo]))
        q[lo] = (((((c[0]*s+c[1])*s+c[2])*s+c[3])*s+c[4])*s+c[5]) / \
                ((((d[0]*s+d[1])*s+d[2])*s+d[3])*s+1)
    if hi.any():
        s = np.sqrt(-2 * np.log(1 - p[hi]))
        q[hi] = -(((((c[0]*s+c[1])*s+c[2])*s+c[3])*s+c[4])*s+c[5]) / \
                 ((((d[0]*s+d[1])*s+d[2])*s+d[3])*s+1)
    if mid.any():
        r = p[mid] - 0.5
        s = r * r
        q[mid] = (((((a[0]*s+a[1])*s+a[2])*s+a[3])*s+a[4])*s+a[5])*r / \
                 (((((b[0]*s+b[1])*s+b[2])*s+b[3])*s+b[4])*s+1)
    return q


def _rules(px):
    kf = kelly(UNDER_MEAN, px)
    out = {}
    for pct in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
        out[f"flat {pct:.2f}%"] = (lambda p: (lambda bank: np.full_like(bank, p / 100)))(pct)
    out["quarter Kelly, capped 1%"] = lambda bank: np.full_like(bank, min(kf * 0.25, 0.01))
    out["quarter Kelly, uncapped"] = lambda bank: np.full_like(bank, kf * 0.25)
    out["half Kelly"] = lambda bank: np.full_like(bank, kf * 0.5)
    out["full Kelly"] = lambda bank: np.full_like(bank, kf)
    return out


def sec_sim(a) -> pd.DataFrame:
    px = a.price
    post = posterior(a.worlds, a.p_dead, px)
    print(f"\n=== {a.seasons}-SEASON MONTE CARLO "
          f"({a.worlds:,} worlds, rho={a.rho}, {px:+.0f}, p_dead={a.p_dead}) ===")
    print("  True rate drawn ONCE per world and held. Stakes are a constant fraction")
    print("  of the CURRENT bankroll, so a losing run cuts the next bet automatically.")
    rows = []
    for name, rule in _rules(px).items():
        r = _simulate(rule, post, a)
        rows.append(dict(
            rule=name,
            median_ret=f"{r['median']*100:+.1f}%",
            p05=f"{r['p05']*100:+.1f}%",
            p75=f"{r['p75']*100:+.1f}%",
            P_down=f"{r['p_down']*100:.0f}%",
            med_maxDD=f"{r['med_dd']*100:.0f}%",
            P_DD_20=f"{r['p_dd20']*100:.0f}%",
            P_DD_35=f"{r['p_dd35']*100:.0f}%",
            P_half_roll=f"{r['p_half']*100:.1f}%",
        ))
    t = pd.DataFrame(rows)
    print("\n" + t.to_string(index=False))
    print(f"\n  ~{BETS_PER_SEASON*a.seasons:.0f} bets over the horizon.")
    print("  P_down is the chance of being behind after three full seasons.")
    print("  P_half_roll is the chance of ever being down 50% along the way.")
    return t


def sec_recommend(a) -> None:
    px = a.price
    be = breakeven(px)
    post = posterior(a.worlds, a.p_dead, px)
    print("\n=== THE RISK FRONTIER ===")
    grid = np.arange(0.0025, 0.0325, 0.0025)
    rows = []
    for f in grid:
        r = _simulate((lambda ff: (lambda bank: np.full_like(bank, ff)))(f), post, a)
        rows.append(dict(stake=f, median=r["median"], p05=r["p05"],
                         p_dd20=r["p_dd20"], p_dd35=r["p_dd35"], p_half=r["p_half"]))
    T = pd.DataFrame(rows)
    show = pd.DataFrame({
        "stake_pct": (T.stake * 100).round(2),
        "median_3yr": (T["median"] * 100).round(1),
        "p05_3yr": (T.p05 * 100).round(1),
        "P_DD_20": (T.p_dd20 * 100).round(0),
        "P_DD_35": (T.p_dd35 * 100).round(0),
        "P_half": (T.p_half * 100).round(1),
    })
    print(show.to_string(index=False))

    lin = T[T.stake <= 0.02]
    ratio = (lin["median"] / lin.stake).round(2)
    print(f"\n  Median return per unit of stake is {ratio.min():.1f}-{ratio.max():.1f} across")
    print("  the whole 0.25-2.00% range: the growth curve is still LINEAR there. The")
    print("  log-optimal peak sits an order of magnitude higher, so no amount of")
    print("  further modelling picks a number in this range. Only a drawdown budget")
    print("  does. That is the honest answer to 'what unit size', and it is why this")
    print("  is stated as a policy below rather than derived as an optimum.")

    ok = T[(T.p_dd35 <= a.dd_budget) & (T.p_half <= 0.02)]
    ceiling = ok.stake.max() if len(ok) else 0.0
    print(f"\n  Ceiling under the stated budget (P(DD>35%) <= {a.dd_budget*100:.0f}%, "
          f"P(halve) <= 2%): {ceiling*100:.2f}%")
    print(f"  Recommended standard unit: {a.unit*100:.2f}% of bankroll.")
    print("  Below the ceiling on purpose. Three things the sim does not price:")
    print("    1. totals limits are low, so the top of the range is not executable")
    print("       at size anyway (runbook: 'this is a low-capacity program');")
    print("    2. the threshold and lead were picked on the same 2016-2025 sample")
    print("       the CI is bootstrapped from, so the CI is mildly optimistic;")
    print("    3. 2024 and 2025 both lost. p_dead covers that as a coin flip on a")
    print("       dead market, not as a slow decay, which is the likelier shape.")

    print("\n=== MULTIPLIERS THAT ARE DERIVED, NOT CHOSEN ===")
    ref_kelly = kelly(UNDER_MEAN, -110)
    print(f"\n  Sizing is Kelly-proportional: units = this bet's full Kelly over the")
    print(f"  reference bet's ({ref_kelly*100:.2f}%, lead 3 at -110), capped at 2 units.")
    print("  Scale-free, and it picks up price and lead without a second knob.")

    print("\n  --- price ---")
    print("  The card takes the highest total first and the best price at it, so what")
    print("  it ends up paying varies. That has to move the stake:")
    for q in (-104, -108, -110, -112, -115, -120):
        u = min(kelly(UNDER_MEAN, q) / ref_kelly, 2.0)
        print(f"    {q:+4.0f}: {u:.2f} units ({u*a.unit*100:.2f}% of bankroll)")

    print("\n  --- forecast lead ---")
    print("  Measured under rate by lead at threshold 11, from calibrate_lead.py.")
    print("  The stake falls out of it; there is no separate lead multiplier:")
    for lead, rate in ((1, 0.5741), (3, 0.5670), (5, 0.5582), (6, 0.5551), (7, 0.5489)):
        u = min(kelly(rate, px) / ref_kelly, 2.0)
        print(f"    lead {lead}: under {rate*100:.2f}%  edge over vig "
              f"{(rate-be)*100:.2f} pp  -> {u:.2f} units")
    print("  Lead 8+ has no measured forecast error at all, so it is sized at ZERO")
    print("  rather than at the lead-7 row. Open-Meteo's previous_dayN stops at 7.")
    print("  Lead 0 is not live either: that row is ERA5 truth, a perfect-knowledge")
    print("  upper bound. A bet placed ten minutes before kickoff still only has a")
    print("  forecast, so live probabilities floor at the lead-1 row.")

    print("\n  --- same-day slates ---")
    print("  Wind games on one slate share a weather system, so k bets are not k")
    print(f"  independent bets. At rho={a.rho}, holding slate risk equal to k")
    print("  independent bets means shading each bet by 1/sqrt(1+(k-1)rho):")
    for k in (1, 2, 3, 4, 5):
        keff = k / (1 + (k - 1) * a.rho)
        print(f"    k={k}: effective independent bets {keff:.2f}, "
              f"per-bet multiplier {1/np.sqrt(1+(k-1)*a.rho):.3f}")

    print("\n=== UNIT POLICY ===")
    print(f"  1 unit               = {a.unit*100:.2f}% of bankroll")
    print("  standard bet         = 1.0 unit at lead 3 and -110")
    print("  scaled               = own full Kelly / reference full Kelly, max 2 units")
    print("  gate                 = unchanged: 3% edge against the DE-VIGGED market")
    print("                         probability. The gate and the sizing input are")
    print("                         different numbers; do not merge them.")
    print("  lead 8+              = 0 units, no measured calibration exists")
    print("  slate shading        = 1/sqrt(1+(k-1)rho) on every bet of a k-game slate")
    print(f"  hard per-bet cap     = {a.unit*200:.2f}% of bankroll (2 units)")
    print("  slate cap            = 3 units of total exposure in one day")
    print("  drawdown stop        = review at -15 units on the season, do not re-tune")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", choices=["kelly", "uncertainty", "sim", "recommend", "all"],
                    default="all")
    ap.add_argument("--price", type=float, default=-110)
    ap.add_argument("--p-dead", type=float, default=0.25,
                    help="prior probability the market has already priced wind")
    ap.add_argument("--rho", type=float, default=0.10,
                    help="within-slate outcome correlation")
    ap.add_argument("--worlds", type=int, default=40_000)
    ap.add_argument("--seasons", type=int, default=3)
    ap.add_argument("--dd-budget", type=float, default=0.05,
                    help="tolerated P(max drawdown > 35%%)")
    ap.add_argument("--unit", type=float, default=0.01,
                    help="proposed unit as a fraction of bankroll")
    a = ap.parse_args()

    if a.section in ("kelly", "all"):
        sec_kelly(a)
    if a.section in ("uncertainty", "all"):
        sec_uncertainty(a)
    if a.section in ("sim", "all"):
        sec_sim(a)
    if a.section in ("recommend", "all"):
        sec_recommend(a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())