"""Can the live path meet the rule? Replays the open-anchored moneyline rule on
OUR OWN odds store (every pull, 2026-06 to 2026-11; ufc_odds.parquet from
odds_census.py) at a minimum lead, with the frozen model fitted on every
archive fight through 2025.

  A. a decidable book's first stored price, anchored on itself;
  B. Pinnacle's no-vig price with the best decidable price fetched within
     MAX_GAP_MIN of it; the first clearing pull locks.

Also: how often Pinnacle and each US book have a quote that far out, and
whether snapshot_at is the fetch time or the book's own clock.

    python live_replay.py [min lead hours, default 168]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

exec(Path(__file__).with_name("ml_open_2026.py").read_text(encoding="utf-8").split("last = O.groupby")[0])

MIN_LEAD = float(sys.argv[1]) if len(sys.argv) > 1 else 168.0
MAX_GAP_MIN = 10
DEC = ["draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics", "betrivers", "hardrockbet"]
O["lead_h"] = (O.ct - O.snap).dt.total_seconds() / 3600
O["created"] = pd.to_datetime(O.created_at, utc=True, format="mixed", errors="coerce")
gap = (O.created - O.snap).dt.total_seconds() / 60
print(f"snapshot_at vs created_at: median gap {gap.median():.1f} min, p90 {gap.quantile(.9):.1f} min, "
      f"share over 10 min {np.mean(gap.abs() > 10):.1%}")
W = O[O.lead_h >= MIN_LEAD]
print(f"fights {O.fid.nunique()}; with a quote at least {MIN_LEAD/24:.0f} days out: "
      + ", ".join(f"{b} {W[W.bookmaker == b].fid.nunique()}" for b in ["pinnacle"] + DEC))
pin_last = O[O.bookmaker == "pinnacle"].groupby("fid").tail(1).set_index("fid")


def show(label, K, take_a, price):
    if len(K) == 0:
        print(f"{label}: 0 bets"); return
    won = np.where(take_a, K.a_won, ~K.a_won)
    u, r = units(price, won)
    PL = pin_last.reindex(K.fid)
    pf = np.where(take_a, novig(PL.pa, PL.pb), 1 - novig(PL.pa, PL.pb))
    lo, hi = ci(u, r) if len(u) > 2 else (np.nan, np.nan)
    print(f"{label}: {len(u)} bets {u.sum():+.1f}u {100*u.sum()/r.sum():+.1f}% [{lo:+.0f},{hi:+.0f}] "
          f"EV vs Pinnacle close {100*np.nanmean(pf*dec(price)-1):+.2f}% cards {K.ct.dt.date.nunique()}")


for book in ("draftkings", "fanduel"):
    X = W[W.bookmaker == book].groupby("fid").head(1)
    pm = 1 / (1 + np.exp(-(A.logit(novig(X.pa, X.pb)) + X.xb)))
    ea, eb = pm * dec(X.pa) - 1, (1 - pm) * dec(X.pb) - 1
    ta = ea >= eb
    ev, price = np.where(ta, ea, eb), np.where(ta, X.pa, X.pb)
    for cut in (0.0, 0.06):
        s = (ev >= cut) & (price >= -300)
        show(f"A {book} first price, lead >= {MIN_LEAD:.0f}h, EV>={cut:.2f}", X[s], ta[s], price[s])

P = W[W.bookmaker == "pinnacle"][["fid", "snap", "pa", "pb"]].rename(columns={"snap": "psnap", "pa": "qa", "pb": "qb"})
S = W[W.bookmaker.isin(DEC)]
J = S.merge(P, on="fid")
J = J[(J.snap - J.psnap).abs() <= pd.Timedelta(minutes=MAX_GAP_MIN)]
pm = 1 / (1 + np.exp(-(A.logit(novig(J.qa, J.qb)) + J.xb)))
ea, eb = pm * dec(J.pa) - 1, (1 - pm) * dec(J.pb) - 1
J = J.assign(ta=ea >= eb, ev=np.where(ea >= eb, ea, eb), price=np.where(ea >= eb, J.pa, J.pb))
for cut in (0.0, 0.06):
    K = J[(J.ev >= cut) & (J.price >= -300)].sort_values(["snap", "ev"], ascending=[True, False]).groupby("fid").head(1)
    show(f"B Pinnacle-anchored best US price, lead >= {MIN_LEAD:.0f}h, EV>={cut:.2f}", K, K.ta.to_numpy(), K.price.to_numpy())
