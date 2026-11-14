"""Replay the tennis match-winner models (models/tennis_moneyline_shop.decide)
over the bought history, at the moment the live card decides, and grade every
decision at the deciding book's own retirement rule.

DECISION MOMENTS
  lead60   the first stored snapshot at or after the feed's listed start (as
           the feed listed it at that snapshot) minus 60 minutes. The history
           was bought one ask an hour, so this lands 0 to 60 minutes before
           the listed start, 30 on average; the live card polls every 10
           minutes and decides at the first poll 35 minutes or less before
           the listed start, 30 on average.
  close    the latest snapshot before the start (the round-1 study's close),
           for comparison only: a card cannot know which poll is the last.
Both use only quotes standing 10+ minutes before the earlier of ESPN's start
and the feed's last listed start (scripts/tennis_market_study.pre_match).

REFERENCES  pinnacle (the model); bovada and betonlineag as placebos: two soft
            books' prices in Pinnacle's place. If the rule wins against a soft
            reference as well, it is reading two soft books disagreeing, not
            Pinnacle's price.

Reads the local cache (scripts/tennis_cache.py); writes nothing but its report
and, with --save, the decisions.

    python -m scripts.tennis_moneyline_replay --cache C:/Users/micha/tennis_research/cache
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from models import tennis_common as tc
from models import tennis_moneyline_shop as ms
from scripts import tennis_market_study as st
from scripts.tennis_shop_study import load, table

LEADS = {"lead60": pd.Timedelta(minutes=60)}
REFS = ("pinnacle", "bovada", "betonlineag")
CUTS = (0.0, 0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04)


def decisions(q: pd.DataFrame, lk: pd.DataFrame, res: pd.DataFrame) -> pd.DataFrame:
    pm = st.pre_match(q, lk, res)
    h = pm[pm.market == "h2h"].dropna(subset=["home_price", "away_price"]).sort_values("snapshot_ts")
    res_by = res.set_index("comp_id")
    lki = lk.dropna(subset=["comp_id"]).set_index("event_id")
    out = []
    for eid, g in h.groupby("event_id", sort=False):
        if eid not in lki.index:
            continue
        link = lki.loc[eid]
        espn = res_by.loc[link.comp_id]
        result = st.espn_result(espn, a_is_p1=bool(link.home_is_p1))
        if result is None:
            continue
        sk = g.sport_key.iloc[0]
        snaps = g.drop_duplicates("snapshot_ts", keep="last")[["snapshot_ts", "commence_time"]]
        moments = {"close": snaps.snapshot_ts.iloc[-1]}
        for name, lead in LEADS.items():
            hit = snaps[snaps.snapshot_ts >= snaps.commence_time - lead]
            if len(hit):
                moments[name] = hit.snapshot_ts.iloc[0]
        for dec, s in moments.items():
            stand = g[g.snapshot_ts <= s].groupby("bookmaker").tail(1).set_index("bookmaker")
            listed = snaps[snaps.snapshot_ts <= s].commence_time.iloc[-1]
            quotes = [ms.Quote(b, int(r.home_price), int(r.away_price)) for b, r in stand.iterrows()]
            for ref_book in REFS:
                if ref_book not in stand.index:
                    continue
                r = stand.loc[ref_book]
                c = ms.decide(quotes, ms.Quote(ref_book, int(r.home_price), int(r.away_price)), sk,
                              ev_min=-1.0)
                if c is None or not c.book:
                    continue
                grade = tc.grade_moneyline(result, c.side, c.book)
                d = tc.american_to_decimal(c.price)
                out.append({"decision": dec, "ref": ref_book, "event_id": eid, "sport_key": sk,
                            "tour": ms.tour_of(sk), "season": int(espn.season), "start": espn.start_time,
                            "snapshot_ts": s, "ref_changed_min": (s - r.snapshot_ts).total_seconds() / 60,
                            "to_listed_min": (listed - s).total_seconds() / 60,
                            "to_start_min": (espn.start_time - s).total_seconds() / 60,
                            "book": c.book, "side": c.side, "price": c.price, "p_ref": c.p_ref,
                            "ev": c.ev, "grade": grade, "units": tc.units(grade, c.price),
                            "risk": min(1 / (d - 1), 3.0)})
    return pd.DataFrame(out)


def splits(b: pd.DataFrame) -> None:
    b = b.sort_values("start").copy()
    b["half"] = np.where(np.arange(len(b)) < len(b) / 2, "early", "late")
    b["fav"] = np.where(b.price < 0, "favourite", "underdog")
    b["band"] = pd.cut(b.price, [-100000, -300, -150, 100, 200, 100000],
                       labels=["-500..-300", "-300..-150", "-150..+100", "+100..+200", ">+200"])
    for col in ("season", "half", "tour", "fav", "band", "book"):
        parts = []
        for k, g in b.groupby(col, observed=True):
            t = table(g)
            parts.append(f"{k}: {t['bets']} {t['units']:+.1f}u {t['roi']:+.3f}")
        print(f"    by {col}: " + " | ".join(parts))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--save", type=Path)
    a = ap.parse_args(argv)
    q, res = load(a.cache)
    lk = st.link(q, res)
    d = decisions(q, lk, res)
    if a.save:
        d.to_parquet(a.save, index=False)
    print(f"decisions (one per match, moment and reference): {len(d):,}")
    for (dec, ref), g in d.groupby(["decision", "ref"]):
        print(f"\n=== {dec}, reference {ref}: {g.event_id.nunique():,} matches; minutes to the listed start "
              f"median {g.to_listed_min.median():.0f}; to ESPN's start median {g.to_start_min.median():.0f}, "
              f"10th pct {g.to_start_min.quantile(.1):.0f}, 90th {g.to_start_min.quantile(.9):.0f}")
        for cut in CUTS:
            t = table(g[g.ev >= cut])
            print(f"  EV>={cut:.3f}  bets {t['bets']:5,}  units {t['units']:+7.2f}  roi {t['roi']:+.4f}  ci90 {t['ci90']}")
        print("  banded:")
        for lo in np.arange(-0.03, 0.05, 0.01):
            t = table(g[(g.ev >= lo) & (g.ev < lo + 0.01)])
            print(f"    EV in [{lo:+.2f},{lo + 0.01:+.2f})  bets {t['bets']:5,}  units {t['units']:+7.2f}  roi {t['roi']:+.4f}")
        if ref == "pinnacle":
            b = g[g.ev >= ms.EV_MIN]
            print(f"  THE FROZEN RULE (EV in [{ms.EV_MIN}, {ms.EV_MAX}), price >= {ms.PRICE_FLOOR}): {table(b)}")
            splits(b)
            print("  walk-forward: the cut chosen on every earlier season (most units), applied to the next")
            wf = []
            for s in range(2022, 2027):
                train = g[g.season < s]
                k = max(CUTS[1:], key=lambda c: table(train[train.ev >= c])["units"])
                test = g[(g.season == s) & (g.ev >= k)]
                wf.append(test)
                t = table(test)
                print(f"    {s}: cut {k:.3f}  bets {t['bets']:4}  units {t['units']:+7.2f}  roi {t['roi']:+.4f}")
            print(f"    total: {table(pd.concat(wf))}")
            print(f"  price: median {b.price.median():.0f}, shortest {b.price.min()}, longest {b.price.max()}, "
                  f"share -300 or shorter {(b.price <= -300).mean():.3f}, +200 or longer {(b.price >= 200).mean():.3f}")
            per = b[b.season.between(2021, 2025)].groupby(["season", "tour"]).size().unstack(fill_value=0)
            print(f"  bets a season 2021-2025 by tour:\n{per.to_string()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
