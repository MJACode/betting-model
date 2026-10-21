"""Is round two's moneyline result real? The checks, before anyone believes it.

Round two showed +8% on 1,561 bets at edge >= 0.06, decided and graded at the
archive's OPENING price. Ways that can be fake, each tested here:

  1. the edge is only open -> close drift: grade the SAME bets at the CLOSE;
  2. the model knows nothing the close does not: decide AND grade at the close;
  3. information the opener could not have had: a team that played the night
     before (its result post-dates the open) and the confirmed starting goalie
     (named hours after the open) — drop both;
  4. it is just the favourite lean: split by favourite / underdog;
  5. one good season: by season;
  6. the grader pays out regardless: shuffle the model's probabilities.

    python -m scripts.nhl_market_lab2_checks
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from data.db import get_connection
from scripts.nhl_market_lab import grade_ml, novig, summarise
from scripts.nhl_market_lab2 import GROUPS, build, logistic, walk

CUTS = (0.04, 0.06, 0.08)


def bets(pred: pd.DataFrame, mkt: np.ndarray, e: float):
    a, b = pred.p.values - mkt >= e, mkt - pred.p.values >= e
    return a | b, a


def line(tag, pred, mkt, e, snap="open", mask=None):
    pick, home = bets(pred, mkt, e)
    if mask is not None:
        pick = pick & mask
    if pick.sum() < 30:
        return {"check": tag, "edge>=": e, "bets": int(pick.sum())}
    pr, clv = grade_ml(pred[pick], home[pick], snap=snap)
    return {"check": tag, "edge>=": e, **summarise(pr, clv)}


def main() -> None:
    conn = get_connection()
    try:
        df = build(conn)
    finally:
        conn.close()
    df = df[df.season.between(2019, 2023)].copy()
    df["y_home"] = (df.hs > df.as_).astype(int)
    ml = df.dropna(subset=["mkt_home", "ml_home_close", "ml_away_close"]).copy()
    ml["mkt_close"] = [novig(h, a) for h, a in zip(ml.ml_home_close, ml.ml_away_close)]
    feats = [f for g in GROUPS.values() for f in g]
    pred = walk(ml, feats, "y_home", logistic)
    mo, mc = pred.mkt_home.values, pred.mkt_close.values
    rows = []
    for e in CUTS:
        rows.append(line("0. as reported: decide at open, grade at OPEN", pred, mo, e))
        rows.append(line("1. same bets, graded at the CLOSE price", pred, mo, e, snap="close"))
        rows.append(line("2. decide vs the CLOSE, grade at the CLOSE", pred, mc, e, snap="close"))
    # 3. only what the opener could have known
    honest = [f for f in feats if f not in GROUPS["goalie"]]
    rested = ((pred.h_rest > 1) & (pred.a_rest > 1)).values
    p2 = walk(ml, honest, "y_home", logistic)
    r2 = ((p2.h_rest > 1) & (p2.a_rest > 1)).values
    for e in CUTS:
        rows.append(line("3a. no goalie inputs, no team on a back-to-back", p2, p2.mkt_home.values, e, mask=r2))
        rows.append(line("3b. ...and graded at the CLOSE", p2, p2.mkt_home.values, e, snap="close", mask=r2))
    # 4. favourite / underdog
    for e in CUTS:
        pick, home = bets(pred, mo, e)
        on_fav = np.where(home, mo >= 0.5, mo < 0.5)
        rows.append(line("4. bets on the FAVOURITE", pred, mo, e, mask=on_fav))
        rows.append(line("4. bets on the UNDERDOG", pred, mo, e, mask=~on_fav))
    # 5. by season
    for s in sorted(pred.season.unique()):
        rows.append(line(f"5. season {s}", pred, mo, 0.06, mask=(pred.season == s).values))
    # 6. shuffled probabilities (50 draws)
    rng = np.random.default_rng(7)
    rois = []
    for _ in range(50):
        sh = pred.copy()
        sh["p"] = rng.permutation(sh.p.values)
        pick, home = bets(sh, mo, 0.06)
        pr, _ = grade_ml(sh[pick], home[pick])
        rois.append(pr.mean() * 100)
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"\n6. shuffled model probabilities, edge >= 0.06, 50 draws: mean ROI "
          f"{np.mean(rois):+.2f}%, 95% of draws within {np.percentile(rois, 2.5):+.1f}.."
          f"{np.percentile(rois, 97.5):+.1f}% (the real model: see row 0)")
    share_b2b = float((~rested).mean())
    print(f"games with a team on a back-to-back: {share_b2b:.1%} of {len(pred):,}")


if __name__ == "__main__":
    main()
