"""Tennis total games and games spreads, round 1: the baselines, and the
decidable books' prices against Pinnacle's no-vig price on the same line at the
same moment. Reads the local cache (scripts/tennis_cache.py); writes nothing
but its own report and, with --save, the candidate rows.

FIXED BEFORE ANY RESULT WAS READ (the match-winner study's choices, carried):
  population  feed events linked to their ESPN result, pre-match quotes only
              (scripts/tennis_market_study.pre_match)
  decisions   first, t12, close (scripts/tennis_market_study.decision_quotes)
  books       the decidable books that post these markets: BetMGM, Caesars,
              BetRivers. Every other book is listed for scale, never bet
  reference   Pinnacle's pair on the SAME line (total, or the home handicap)
              standing at the decidable quote's snapshot, multiplicative de-vig,
              last changed no more than 15 minutes before it (--ref-max-age-min;
              the store is change-only, so this is the time since Pinnacle's
              price last moved, not proof it was still listed)
  grade       completed matches only: a retirement or walkover is VOID
              (models/tennis_common.grade_total, grade_games_spread); units at
              the published stake
  one bet     per event, market and decision: the best EV quote across books
              and sides
  cuts        EV >= 0.00, 0.01, 0.02, 0.03, 0.05, 0.08

    python -m scripts.tennis_games_study --cache C:/Users/micha/tennis_research/cache
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from models import tennis_common as tc
from scripts import tennis_market_study as st
from scripts.tennis_shop_study import CUTS, load, table

GAMES_BOOKS = ("betmgm", "williamhill_us", "betrivers")


def outcomes(lk: pd.DataFrame, res: pd.DataFrame) -> pd.DataFrame:
    """Per linked event, from the feed home player's side: status, total games,
    and the games margin (home minus away)."""
    res_by = res.set_index("comp_id")
    rows = []
    for r in lk.dropna(subset=["comp_id"]).itertuples(index=False):
        e = res_by.loc[r.comp_id]
        x = st.espn_result(e, a_is_p1=bool(r.home_is_p1))
        if x is None:
            continue
        rows.append({"event_id": r.event_id, "status": x.status, "best_of": x.best_of,
                     "total": x.total_games if x.status == "complete" else np.nan,
                     "margin": (sum(x.a_games) - sum(x.b_games)) if x.status == "complete" else np.nan,
                     "start": e.start_time, "season": int(e.season)})
    return pd.DataFrame(rows)


def _grade(won: np.ndarray, push: np.ndarray, void: np.ndarray) -> np.ndarray:
    g = np.where(won, tc.WIN, tc.LOSS).astype(object)
    g[push] = tc.PUSH
    g[void] = tc.VOID
    return g


def _units(grade: np.ndarray, price: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    d = np.where(price > 0, 1 + price / 100, 1 + 100 / np.abs(price))
    risk = np.minimum(1 / (d - 1), 3.0)
    u = np.where(grade == tc.WIN, risk * (d - 1), np.where(grade == tc.LOSS, -risk, 0.0))
    return u, risk


def sides(dq: pd.DataFrame, market: str) -> pd.DataFrame:
    """Both sides of each quote as rows: side, price, point, the reference's
    pair for that side, and the grade."""
    if market == "totals":
        a = dq.assign(side="over", price=dq.over_price, point=dq.total_point,
                      r_side=dq.r_a, r_other=dq.r_b)
        b = dq.assign(side="under", price=dq.under_price, point=dq.total_point,
                      r_side=dq.r_b, r_other=dq.r_a)
        x = pd.concat([a, b], ignore_index=True)
        diff = np.where(x.side == "over", x.total - x.point, x.point - x.total)
    else:
        a = dq.assign(side="home", price=dq.home_price, point=dq.home_point,
                      r_side=dq.r_a, r_other=dq.r_b)
        b = dq.assign(side="away", price=dq.away_price, point=dq.away_point,
                      r_side=dq.r_b, r_other=dq.r_a)
        x = pd.concat([a, b], ignore_index=True)
        diff = np.where(x.side == "home", x.margin + x.point, -x.margin + x.point)
    void = (x.status != "complete").values
    diff = np.nan_to_num(diff)
    x["grade"] = _grade(diff > 0, diff == 0, void)
    x["units"], x["risk"] = _units(x.grade.values, x.price.values.astype(float))
    if "r_side" in x and x.r_side.notna().any():
        ia = x.r_side.map(lambda p: tc.implied(p) if pd.notna(p) else np.nan)
        ib = x.r_other.map(lambda p: tc.implied(p) if pd.notna(p) else np.nan)
        x["p_ref"] = ia / (ia + ib)
        d = x.price.map(tc.american_to_decimal)
        x["ev"] = x.p_ref * d - 1
    return x


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--save", type=Path)
    ap.add_argument("--ref-max-age-min", type=int, default=15)
    a = ap.parse_args(argv)
    max_age = pd.Timedelta(minutes=a.ref_max_age_min)
    q, res = load(a.cache)
    lk = st.link(q, res)
    oc = outcomes(lk, res)
    print(f"linked events with a result {len(oc):,}; completed {int((oc.status == 'complete').sum()):,}")
    pm = st.pre_match(q, lk, res)
    saved = []
    for market, pt_a, pr_a, pr_b in (("totals", "total_point", "over_price", "under_price"),
                                     ("spreads", "home_point", "home_price", "away_price")):
        h = pm[pm.market == market].dropna(subset=[pt_a, pr_a, pr_b])
        ref = (h[h.bookmaker == "pinnacle"].sort_values("snapshot_ts")
               [["event_id", "snapshot_ts", pt_a, pr_a, pr_b]]
               .rename(columns={"snapshot_ts": "ref_ts", pr_a: "r_a", pr_b: "r_b"}))
        print(f"\n===== {market.upper()} =====")
        for dec in st.DECISIONS:
            dq = st.decision_quotes(h, dec).merge(oc, on="event_id")
            if dec == "close":
                print(f"\nBASELINE at the close, every book, both sides blind (VOID on a retirement)")
                for book, g in dq.groupby("bookmaker"):
                    x = sides(g.assign(r_a=np.nan, r_b=np.nan), market)
                    for s, gs in x.groupby("side"):
                        t = table(gs)
                        print(f"  {book:15s} {s:5s} quotes {t['bets']:6,}  won {t['won']:5,}  roi {t['roi']:+.4f}")
                pin = dq[dq.bookmaker == "pinnacle"]
                if market == "totals" and len(pin):
                    c = pin[pin.status == "complete"]
                    print(f"  Pinnacle close total: mean line {c.total_point.mean():.2f}, mean result "
                          f"{c.total.mean():.2f}, over {np.mean(c.total > c.total_point):.4f}, "
                          f"under {np.mean(c.total < c.total_point):.4f} ({len(c):,} matches)")
            d = dq[dq.bookmaker.isin(GAMES_BOOKS)].sort_values("snapshot_ts")
            m = pd.merge_asof(d, ref, left_on="snapshot_ts", right_on="ref_ts", by=["event_id", pt_a],
                              direction="backward").dropna(subset=["r_a", "r_b"])
            m = m[(m.snapshot_ts - m.ref_ts) <= max_age]
            x = sides(m, market).assign(decision=dec, market=market)
            saved.append(x)
            print(f"\nSHOP {market} {dec}: {m.event_id.nunique():,} events with a same-line Pinnacle pair "
                  f"last changed within {a.ref_max_age_min} minutes; quotes both sides {len(x):,}; median EV {x.ev.median():+.4f}")
            for cut in CUTS:
                b = x[x.ev >= cut].sort_values("ev", ascending=False).drop_duplicates(["event_id"])
                if len(b):
                    t = table(b)
                    print(f"  EV>={cut:.2f}  bets {t['bets']:5,} won {t['won']:5,} void {t['void']:3}  "
                          f"units {t['units']:+8.2f}  roi {t['roi']:+.4f}  ci90 {t['ci90']}")
    if a.save and saved:
        keep = ["decision", "market", "event_id", "bookmaker", "side", "price", "point", "p_ref", "ev",
                "snapshot_ts", "ref_ts", "status", "best_of", "total", "margin", "start", "season",
                "grade", "units", "risk", "sport_key"]
        pd.concat(saved, ignore_index=True)[keep].to_parquet(a.save, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
