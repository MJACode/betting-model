"""Replay the NHL best bet a night's LIVE rule over the stored seasons, bet for bet.

The research (scripts/nhl_best_bet_confirmed_goalies.py, version C) and the
live model (models/nhl_best_bet_night.py) are separate code. This runs the live
code itself over history and lines its bets up against the research's:

  every night, every stored fetch time in order is one pass. A pass sees only
  rows fetched by then, only games whose two goalies DailyFaceoff had confirmed
  by then (nhl_goalie_archive, the research's reading), only games whose
  scheduled puck drop is still ahead (see scheduled_start). The live card's own
  after_confirmation and game_candidates price it, with the pass time as `now`
  (so the live age check applies). The night's bet is the first pass with any
  candidate, its largest EV; the night then stops.

Not replayed: the skip of a game holding another model's NHL bet (no such
history), and the live passes' timing (history holds about noon and the start
hour, live passes run every few minutes).

Read-only: odds from the local copy (scripts/nhl_sharp_vs_soft_lab.py), the
archive from the database (SELECT only).

    python -m scripts.nhl_best_bet_night_replay --env-file ../../../.env
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

import models.nhl_best_bet_night as nb
from scripts import nhl_sharp_vs_soft_lab as L
from scripts.nhl_best_bet_confirmed_goalies import confirmations, report
from scripts.nhl_totals_card import after_confirmation

ET = "America/New_York"
SEASONS = (2022, 2026)
FLOOR = 0.01
_PRICE_COLS = ("home_price", "away_price", "draw_price", "spread_home", "total_line",
               "over_price", "under_price")


def quotes_frame(odds: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """The rows load_quotes would see, from the local copy: pre-game 'open'
    rows of the four markets, every book (the withdrawn check reads any book
    but DraftKings), each fetch timed by its newest snapshot as the research does."""
    o = odds[odds.market.isin(list(nb.SPEC)) & (odds.snapshot_type == "open")].copy()
    o = o[o.source.fillna("") != "sbr_archive_nhl"]
    o = o.merge(games[["game_id", "ct", "season"]], on="game_id", how="inner")
    o = o[o.season.between(*SEASONS)]
    for c in _PRICE_COLS:
        o[c] = pd.to_numeric(o[c], errors="coerce")
    o["snap"] = L.ts(o["snapshot_at"])
    o["cts"] = L.ts(o["created_at"])
    hist = o.source.fillna("").str.contains("histor")
    o = o[(o.snap <= o.ct) & (hist | (o.cts <= o.ct))]
    ft = o.groupby(["game_id", "market", "created_at"]).snap.max().rename("fetch_time")
    o = o.join(ft, on=["game_id", "market", "created_at"])
    o["night"] = o.ct.dt.tz_convert(ET).dt.date
    return o


def scheduled_start(ct: pd.Series) -> pd.Series:
    """The scheduled puck drop, which is the live rule's real cutoff.

    Live, the odds feed lists a game about ten minutes after its scheduled
    puck drop and the card stops config.NHL_DECIDE_BEFORE_START_MIN (10)
    before that, so it decides up to the scheduled time (config.py, the note
    on NHL_DECIDE_BEFORE_START_MIN). The stored history mixes the two: settled
    games carry either the feed's time or, once settlement moved it back, the
    scheduled one (measured 2026-11-22: 4% of 2021-22 games sit 5-15 minutes
    past the hour or half hour, 59% of 2023-24, 85% of 2025-26). So the replay
    snaps a start that sits 5-15 minutes past back to the hour or half hour.
    Cutting at the stored time less 10 minutes instead would stop 10 minutes
    early on every game stored at its scheduled time."""
    m = ct.dt.minute % 30
    back = np.where((m >= 5) & (m <= 15), m, 0)
    return ct.dt.floor("min") - pd.to_timedelta(back, unit="m")


def _records(df: pd.DataFrame) -> list[dict]:
    out = []
    for r in df.itertuples(index=False):
        q = {"game_id": r.game_id, "market": r.market, "book": r.bookmaker,
             "created_at": r.created_at, "created_ts": r.fetch_time.to_pydatetime(),
             "snapshot_at": r.snap.to_pydatetime()}
        for c in _PRICE_COLS:
            v = getattr(r, c)
            q[c] = None if pd.isna(v) else float(v)
        for k in ("home_link", "away_link", "draw_link", "over_link", "under_link"):
            q[k] = None
        out.append(q)
    return out


def replay(o: pd.DataFrame, conf: pd.Series) -> pd.DataFrame:
    o = o[o.game_id.isin(conf.dropna().index)].copy()
    o["conf_at"] = o.game_id.map(conf)
    o["puck_drop"] = scheduled_start(o.ct)
    bets = []
    for night, n in o.groupby("night"):
        for t in np.sort(n.fetch_time.unique()):
            t = pd.Timestamp(t)
            live = n[(n.fetch_time <= t) & (n.conf_at <= t) & (n["puck_drop"] > t)]
            if live.empty:
                continue
            known = {g: a.to_pydatetime() for g, a in live.groupby("game_id").conf_at.first().items()}
            quotes = after_confirmation(_records(live), known)
            best, _ = nb.game_candidates(quotes, now=t.to_pydatetime())
            if not best:
                continue
            c = max(best.values(), key=lambda c: (c.ev, -nb.MODEL_IDS.index(c.model_id)))
            g = live[live.game_id == c.game_id].iloc[0]
            bets.append({"game_id": c.game_id, "market": c.market, "side": c.side,
                         "line": 0.0 if c.line is None else c.line, "bookmaker": c.book,
                         "price": c.price, "fair": c.fair, "ev": c.ev, "pass_time": t,
                         "fetch_time": live[(live.game_id == c.game_id) & (live.market == c.market)
                                            & (live.created_at == c.created_at)].fetch_time.max(),
                         "ct": g.ct, "season": g.season, "day": night})
            break
    return pd.DataFrame(bets)


def research_c(odds, games, conf) -> pd.DataFrame:
    """Version C of scripts/nhl_best_bet_confirmed_goalies at the live floor."""
    rows = []
    for mk in nb.SPEC:
        o, outs, pcols = L.prepare(odds, games, mk)
        o = o[o.season.between(*SEASONS)]
        c = L.fetch_bests(o, outs, pcols)
        x = c[c.ev >= FLOOR].join(conf.rename("conf_at"), on="game_id")
        x = x[x.conf_at.notna() & (x.fetch_time >= x.conf_at)]
        first = x.sort_values(["game_id", "fetch_time", "ev"], ascending=[True, True, False])
        first = first[first.fetch_time == first.groupby("game_id").fetch_time.transform("min")]
        rows.append(first.drop_duplicates("game_id").assign(market=mk))
    b = pd.concat(rows, ignore_index=True)
    b["day"] = b.ct.dt.tz_convert(ET).dt.date
    bg = b.sort_values("ev", ascending=False).drop_duplicates("game_id")
    return bg.sort_values("fetch_time", kind="stable").groupby("day").head(1)


def graded(bets: pd.DataFrame, odds, games) -> pd.DataFrame:
    out = []
    for mk, b in bets.groupby("market"):
        o, outs, pcols = L.prepare(odds, games, mk)
        cl = L.closes(o, outs, pcols)
        out.append(L.grade(b, mk, games, cl, outs).assign(market=mk))
    return pd.concat(out, ignore_index=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", required=True)
    a = ap.parse_args()
    L.DEVIG = "power"
    conf = confirmations(a.env_file)
    games, odds = L.load()
    o = quotes_frame(odds, games)
    live = graded(replay(o, conf), odds, games)
    res = graded(research_c(odds, games, conf), odds, games)
    report(live, "LIVE RULE replayed (models/nhl_best_bet_night.py)")
    report(res, "research C, four markets, power, EV>=0.01")
    both = live.merge(res, on="day", suffixes=("_live", "_res"))
    same = both[(both.game_id_live == both.game_id_res) & (both.market_live == both.market_res)
                & (both.side_live == both.side_res)]
    print(f"nights: live {live.day.nunique()}, research {res.day.nunique()}, both {len(both)}, "
          f"same game+market+side {len(same)} "
          f"(same book and price {int(((same.bookmaker_live == same.bookmaker_res) & (same.price_live == same.price_res)).sum())})")
    only_live = live[~live.day.isin(res.day)]
    only_res = res[~res.day.isin(live.day)]
    diff = both.drop(same.index)
    print(f"nights only live: {len(only_live)} ({only_live.units.sum():+.1f}u); only research: "
          f"{len(only_res)} ({only_res.units.sum():+.1f}u); both but a different bet: {len(diff)} "
          f"(live {diff.units_live.sum():+.1f}u, research {diff.units_res.sum():+.1f}u)")
    # The price range the live rule bets at, and the stake there (1u to win,
    # risk capped at 3): the rules ask for it before a model ships.
    pr = live.price
    print(f"prices: median {pr.median():+.0f}, shortest {pr.min():+.0f}, longest {pr.max():+.0f}; "
          f"shorter than -150 {100*(pr < -150).mean():.0f}%, -175 {100*(pr < -175).mean():.0f}%; "
          f"risk per bet median {live.risk.median():.2f}u, largest {live.risk.max():.2f}u")
    for mk, g in live.groupby("market"):
        print(f"  {mk:9s} bets {len(g):3d} units {g.units.sum():+6.1f} flat {100*g.flat.mean():+5.1f}% "
              f"median price {g.price.median():+.0f}")
    half = live.sort_values("pass_time")
    early, late = half.iloc[:len(half) // 2], half.iloc[len(half) // 2:]
    print(f"early half {early.units.sum():+.1f}u ({len(early)}), late half {late.units.sum():+.1f}u ({len(late)})")


if __name__ == "__main__":
    main()
