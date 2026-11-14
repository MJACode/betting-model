"""Tennis match winner, round 1 checks on the saved candidates
(scripts/tennis_shop_study.py --save): is the reference calibrated, how old
was it, and does the result survive a fresher reference and a different
de-vig?

  calibration  every candidate row once per (decision, reference, event, side),
               binned by the reference probability; realised win rate against
               the mean probability, for the multiplicative de-vig the study
               used and for the power de-vig (each price's implied chance
               raised to the one power that makes the pair sum to 1), which
               gives the longshot less
  age          the reference quote's age at the decidable quote, by decision;
               the study's sets re-cut at 15 minutes and 1 hour
  overround    the reference pair's implied sum, by decision (an exchange's
               best back prices on a thin market sum far from 1.05)
  power grid   the study's shop grid with the power de-vig, Pinnacle only

    python -m scripts.tennis_shop_checks --candidates C:/Users/micha/tennis_research/cache/shop_candidates.parquet
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from models import tennis_common as tc
from scripts.tennis_shop_study import CUTS, best_per_event, table


def power_side(ia: np.ndarray, ib: np.ndarray) -> np.ndarray:
    """Power de-vig of the first side: find k with ia**k + ib**k = 1, by
    bisection (k > 1 when the pair carries a margin, k < 1 when it sums
    under 1)."""
    lo, hi = np.full(len(ia), 0.3), np.full(len(ia), 3.0)
    for _ in range(60):
        k = (lo + hi) / 2
        over = ia ** k + ib ** k > 1.0
        lo, hi = np.where(over, k, lo), np.where(over, hi, k)
    return ia ** ((lo + hi) / 2)


def calibration(c: pd.DataFrame, col: str) -> pd.DataFrame:
    g = c[c.grade.isin([tc.WIN, tc.LOSS])].drop_duplicates(["decision", "ref", "event_id", "side"])
    g = g.assign(won=(g.grade == tc.WIN).astype(float),
                 bin=pd.cut(g[col], [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0]))
    out = g.groupby(["ref", "decision", "bin"], observed=True).agg(n=("won", "size"), p=(col, "mean"), won=("won", "mean"))
    out["gap"] = out.won - out.p
    return out.round(4)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--candidates", required=True)
    a = ap.parse_args(argv)
    c = pd.read_parquet(a.candidates)
    c["age_min"] = (c.ts - c.ref_ts).dt.total_seconds() / 60
    ia, ib = c.r_side.map(tc.implied).values, c.r_other.map(tc.implied).values
    c["overround"] = ia + ib
    c["p_pow"] = power_side(ia, ib)
    d = c.price.map(tc.american_to_decimal)
    c["ev_pow"] = c.p_pow * d - 1 + c.opt
    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 400)

    print("CALIBRATION, multiplicative de-vig (the study's)")
    print(calibration(c, "p_ref").to_string())
    print("\nCALIBRATION, power de-vig")
    print(calibration(c, "p_pow").to_string())
    for col in ("p_ref", "p_pow"):
        g = c[c.grade.isin([tc.WIN, tc.LOSS])].drop_duplicates(["decision", "ref", "event_id", "side"])
        y = (g.grade == tc.WIN).astype(float)
        p = g[col].clip(1e-6, 1 - 1e-6)
        for (ref, dec), idx in g.groupby(["ref", "decision"]).groups.items():
            yy, pp = y.loc[idx], p.loc[idx]
            ll = -(yy * np.log(pp) + (1 - yy) * np.log(1 - pp)).mean()
            print(f"  {col} {ref:13s} {dec:5s} n {len(yy):6,}  brier {((pp - yy) ** 2).mean():.5f}  logloss {ll:.5f}")

    print("\nREFERENCE AGE (minutes) at the decidable quote")
    print(c.groupby(["ref", "decision"]).age_min.describe(percentiles=[.25, .5, .75, .9]).round(1).to_string())
    print("\nREFERENCE OVERROUND (implied sum of the pair)")
    print(c.drop_duplicates(["decision", "ref", "event_id", "ref_ts"]).groupby(["ref", "decision"]).overround
          .describe(percentiles=[.05, .25, .5, .75, .95]).round(4).to_string())

    print("\nTHE STUDY'S SETS, RE-CUT ON REFERENCE AGE (Pinnacle, multiplicative)")
    for dec, cut in (("first", 0.01), ("t12", 0.03), ("close", 0.01), ("close", 0.03)):
        for max_age in (15, 60, 360):
            x = c[(c.ref == "pinnacle") & (c.decision == dec) & (c.age_min <= max_age)]
            t = table(best_per_event(x, cut))
            print(f"  {dec:5s} EV>={cut:.2f} age<={max_age:3d}m  bets {t['bets']:5,}  units {t['units']:+8.2f}  "
                  f"roi {t['roi']:+.4f}  ci90 {t['ci90']}")

    print("\nBETFAIR, overround in a sane range only (1.00 to 1.06)")
    for dec in ("first", "t12", "close"):
        x = c[(c.ref == "betfair_ex_eu") & (c.decision == dec) & c.overround.between(1.0, 1.06)]
        for cut in (0.0, 0.02, 0.05):
            t = table(best_per_event(x, cut))
            print(f"  {dec:5s} EV>={cut:.2f}  bets {t['bets']:5,}  units {t['units']:+8.2f}  roi {t['roi']:+.4f}  ci90 {t['ci90']}")

    print("\nSHOP GRID, POWER DE-VIG, Pinnacle reference")
    p = c[c.ref == "pinnacle"].assign(ev=lambda f: f.ev_pow)
    for dec in ("first", "t12", "close"):
        for cut in CUTS:
            b = best_per_event(p[p.decision == dec], cut)
            if len(b):
                t = table(b)
                print(f"  {dec:5s} EV>={cut:.2f}  bets {t['bets']:5,}  units {t['units']:+8.2f}  roi {t['roi']:+.4f}  ci90 {t['ci90']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
