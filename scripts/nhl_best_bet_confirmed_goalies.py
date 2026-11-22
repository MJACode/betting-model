"""The best bet a night, re-tested on games whose goalies were confirmed in time.

The noon-ET result (scripts/nhl_best_bet_a_night_lab.py, docs/nhl_sharp_vs_soft.md)
decides before most goalies are confirmed, and mike's rule (2026-10-20) allows
no NHL bet before both are. DailyFaceoff's archive (`nhl_goalie_archive`, from
2021-11-18) says when each confirmation was posted: the earlier of the news
item's time and its X post's time. A team with no confirmed time counts as NOT
confirmed (the conservative read).

Three versions, seasons 2021-22 to 2025-26, Pinnacle's no-vig price against a
bettable book in the same fetch, one bet a game (its largest EV):
  A  noon: the game-date 15:00-17:59 UTC fetch, only games whose two goalies
     were confirmed before that fetch; then the night's largest EV.
  B  first fetch after both confirmed: each game at its first stored pre-game
     fetch after the second confirmation (history holds about noon and the
     start hour), every game that clears the floor (no nightly pick: the
     moments differ, so "the night's best" would look ahead).
  C  as B, but the FIRST bet of the night only (causal: once a night has a
     bet, later games are passed).

Read-only: odds from the local copy (scripts/nhl_sharp_vs_soft_lab.py), the
archive from the database (SELECT only; the database is read-only for Claude).

    python -m scripts.nhl_best_bet_confirmed_goalies --env-file ../../../.env [power]
"""
import argparse
import os

import numpy as np
import pandas as pd

from scripts import nhl_sharp_vs_soft_lab as L

MARKETS = ("spreads", "totals", "h2h", "h2h_3way", "totals_p1")


def confirmations(env_file: str) -> pd.Series:
    """game_id -> when the second goalie was confirmed (NaT if either never was)."""
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv(env_file)
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        cur = conn.cursor()
        cur.execute("SET default_transaction_read_only = on")
        cur.execute("SELECT game_id, team, status, news_created_at, post_at FROM nhl_goalie_archive")
        a = pd.DataFrame(cur.fetchall(), columns=["game_id", "team", "status", "news", "post"])
    finally:
        conn.close()
    for c in ("news", "post"):
        a[c] = pd.to_datetime(a[c], utc=True)
    a["at"] = a[["news", "post"]].min(axis=1)
    a.loc[a.status != "confirmed", "at"] = pd.NaT
    g = a.groupby("game_id").agg(n=("team", "size"), at=("at", "max"), missing=("at", lambda s: s.isna().sum()))
    g.loc[(g.n != 2) | (g.missing > 0), "at"] = pd.NaT
    print(f"archive: {len(g):,} games, {g['at'].notna().sum():,} with both goalies confirmed and timed")
    return g["at"]


def report(b, label):
    if b.empty:
        print(f"{label:58s} no bets")
        return
    n = len(b)
    mu, sd = b.flat.mean(), b.flat.std(ddof=1)
    top = b.groupby("day").units.sum().nlargest(10).index
    rest = b[~b.day.isin(top)]
    seas = " ".join(f"{s}:{g.units.sum():+.1f}({len(g)})" for s, g in b.groupby("season"))
    print(f"{label:58s} bets {n:5d} units {b.units.sum():+7.1f} flat {100*mu:+5.1f}% "
          f"({100*(mu-1.96*sd/np.sqrt(n)):+.1f}..{100*(mu+1.96*sd/np.sqrt(n)):+.1f}) "
          f"CLV {100*b.clv_ev.mean():+.2f}% w/o 10 best nights {rest.units.sum():+.1f}")
    print(f"{'':58s} {seas}")
    lead = (b.ct - b.fetch_time).dt.total_seconds() / 3600
    print(f"{'':58s} hours before start: median {lead.median():.1f}, under 1h {100*(lead < 1).mean():.0f}%, "
          f"3h+ {100*(lead >= 3).mean():.0f}%; markets " + ", ".join(f"{m} {len(g)}" for m, g in b.groupby("market")))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", required=True)
    ap.add_argument("devig", nargs="?", default="proportional", choices=("proportional", "power"))
    ap.add_argument("--reference", default="pinnacle", help="a retail book here is the placebo")
    ap.add_argument("--markets", nargs="*", default=list(MARKETS), choices=list(MARKETS))
    a = ap.parse_args()
    L.DEVIG = a.devig
    L.SHARP = a.reference
    L.SOFT = [b for b in L.SOFT if b != L.SHARP]
    conf = confirmations(a.env_file)
    games, odds = L.load()
    cands = []
    for mk in a.markets:
        o, outs, pcols = L.prepare(odds, games, mk)
        o = o[o.season.between(2022, 2026)]
        c = L.fetch_bests(o, outs, pcols)
        c["market"] = mk
        cl = L.closes(o, outs, pcols)
        cands.append((mk, c, cl, outs))
    print(f"de-vig {L.DEVIG}")
    for floor in (0.01, 0.02, 0.03):
        rows_a, rows_b = [], []
        for mk, c, cl, outs in cands:
            x = c[c.ev >= floor].join(conf.rename("conf_at"), on="game_id")
            ok = x.conf_at.notna() & (x.fetch_time >= x.conf_at)
            gd = x.ct.dt.tz_convert("America/New_York").dt.date
            noon = (x.fetch_time.dt.date == gd) & x.fetch_time.dt.hour.between(15, 17) & (x.fetch_time < x.ct)
            rows_a.append(L.grade(x[noon & ok].sort_values("ev", ascending=False).drop_duplicates("game_id"),
                                  mk, games, cl, outs).assign(market=mk))
            first = x[ok].sort_values(["game_id", "fetch_time", "ev"], ascending=[True, True, False])
            first = first[first.fetch_time == first.groupby("game_id").fetch_time.transform("min")]
            rows_b.append(L.grade(first.drop_duplicates("game_id"), mk, games, cl, outs).assign(market=mk))
        A = pd.concat(rows_a, ignore_index=True)
        B = pd.concat(rows_b, ignore_index=True)
        for d in (A, B):
            d["day"] = d.ct.dt.tz_convert("America/New_York").dt.date
        A1 = A.sort_values("ev", ascending=False).drop_duplicates("game_id").groupby("day").head(1)
        Bg = B.sort_values("ev", ascending=False).drop_duplicates("game_id")
        C1 = Bg.sort_values("fetch_time").groupby("day").head(1)
        report(A1, f"A noon, confirmed games only, best a night, EV>={floor}")
        report(Bg, f"B first fetch after both confirmed, every game, EV>={floor}")
        report(C1, f"C as B, first bet of the night only, EV>={floor}")


if __name__ == "__main__":
    main()
