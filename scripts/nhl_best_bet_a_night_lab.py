"""The best bet a night across NHL markets, decided at ONE moment (read-only).

Every game's quotes at the game-date ~16:00 UTC snapshot (the bought history's
daily moment), every market, Pinnacle's no-vig price against the bettable books
in that same fetch. Per date: take the k largest EVs (>= floor). Causal: every
game of the date is compared at the same moment. Seasons 2020-21 to 2025-26.

    python -m scripts.nhl_best_bet_a_night_lab            # proportional de-vig (the live rule's)
    python -m scripts.nhl_best_bet_a_night_lab power      # power de-vig
    python -m scripts.nhl_best_bet_a_night_lab ref=draftkings   # placebo: a retail book as the reference

Results: docs/nhl_sharp_vs_soft.md, "Fewer bets, bigger stakes". Read-only; reads
the local copy of the database through scripts/nhl_sharp_vs_soft_lab.py.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from scripts import nhl_sharp_vs_soft_lab as L  # noqa: E402

if "power" in sys.argv[1:]:
    L.DEVIG = "power"
for a in sys.argv[1:]:
    if a.startswith("ref="):            # a placebo: a retail book in Pinnacle's place
        L.SHARP = a[4:]
        L.SOFT = [b for b in L.SOFT if b != L.SHARP]
games, odds = L.load()
MARKETS = ("spreads", "totals", "h2h", "h2h_3way", "totals_p1")

rows = []
for mk in MARKETS:
    o, outs, pcols = L.prepare(odds, games, mk)
    o = o[o.season.between(2021, 2026)]
    c = L.fetch_bests(o, outs, pcols)
    gd = c.ct.dt.tz_convert("America/New_York").dt.date
    ft_day = c.fetch_time.dt.date
    hr = c.fetch_time.dt.hour
    # the game date's 15:00-17:59 UTC fetch (10am-1pm ET), before every puck drop that day
    c = c[(ft_day == gd) & hr.between(15, 17) & (c.fetch_time < c.ct)]
    cl = L.closes(o, outs, pcols)
    b = L.grade(c.sort_values("ev", ascending=False).drop_duplicates("game_id"), mk, games, cl, outs)
    b["market"] = mk
    rows.append(b)
allb = pd.concat(rows, ignore_index=True)
allb["day"] = allb.ct.dt.tz_convert("America/New_York").dt.date
print(f"de-vig {L.DEVIG}: {allb.game_id.nunique():,} games with a game-day 15-18Z quote in at least one market")


def report(b, label):
    top = b.groupby("day").units.sum().nlargest(10).index
    rest = b[~b.day.isin(top)]
    n = len(b)
    mu, sd = b.flat.mean(), b.flat.std(ddof=1)
    seas = " ".join(f"{s}:{g.units.sum():+.1f}({len(g)})" for s, g in b.groupby("season"))
    half = b.sort_values("ct")
    print(f"{label:52s} bets {n:5d}  units {b.units.sum():+7.1f}  per bet {b.units.sum()/n:+.3f}  "
          f"flat {100*mu:+5.1f}% ({100*(mu-1.96*sd/np.sqrt(n)):+.1f}..{100*(mu+1.96*sd/np.sqrt(n)):+.1f})  "
          f"CLV {100*b.clv_ev.mean():+.2f}%  w/o 10 best nights {rest.units.sum():+.1f}  "
          f"early {half.iloc[:n//2].units.sum():+.1f} late {half.iloc[n//2:].units.sum():+.1f}")
    print(f"{'':52s} seasons {seas}")


for floor in (0.01, 0.02, 0.03):
    one = allb[allb.ev >= floor].sort_values("ev", ascending=False).drop_duplicates("game_id")
    for k in (1, 2, None):
        pick = one if k is None else one.groupby("day").head(k)
        report(pick, f"EV>={floor}, {'every game' if k is None else f'best {k} a night'}")
        if k == 1:
            print(f"{'':52s} markets: " + ", ".join(f"{m} {len(g)}" for m, g in pick.groupby("market")))

print("\nStakes on the best bet a night (EV >= 1%), X units to win:")
one = allb[allb.ev >= 0.01].sort_values("ev", ascending=False).drop_duplicates("game_id").groupby("day").head(1)
for name, f in (("flat 1u", lambda e: np.ones_like(e)),
                ("tiers 1/2/3/4/5u at 1/2/3/4/5%+ EV", lambda e: np.clip(np.floor(e * 100), 1, 5)),
                ("1u under 2%, 3u at 2-4%, 5u at 4%+", lambda e: np.where(e >= 0.04, 5.0, np.where(e >= 0.02, 3.0, 1.0))),
                ("skip under 2%, 3u at 2-4%, 5u at 4%+", lambda e: np.where(e >= 0.04, 5.0, np.where(e >= 0.02, 3.0, 0.0)))):
    x = f(one.ev.values)
    b = one.assign(u=one.units * x, stake=x)
    b = b[b.stake > 0]
    top = b.groupby("day").u.sum().nlargest(10).index
    cum = b.sort_values("ct").u.cumsum()
    seas = " ".join(f"{s}:{g.u.sum():+.1f}" for s, g in b.groupby("season"))
    print(f"  {name:40s} bets {len(b):4d}  avg stake {b.stake.mean():.2f}  units {b.u.sum():+7.1f}  "
          f"per unit staked {b.u.sum()/b.stake.sum():+.3f}  max drawdown {float((cum.cummax()-cum).max()):.1f}  "
          f"w/o 10 best nights {b[~b.day.isin(top)].u.sum():+.1f}  | {seas}")
