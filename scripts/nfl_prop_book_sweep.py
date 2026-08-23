"""
Does adding books add edge, and is Pinnacle still the only sharp reference?

Two questions, and they are not the same question.

  BREADTH — every soft book is an independent chance at an outlier, so more
  books should mean more bets at the same threshold. This reports the marginal
  contribution of each one, because a book that adds volume and loses money is
  worth knowing about before it is switched on.

  THE SHARP REFERENCE — the placebo that made the rule believable (§5c) was
  that swapping Pinnacle for any retail book destroyed the result. With more
  books on the board that test has to be re-run, and it now has real candidates:
  betonlineag and hardrockbet are the only books reaching sacks and
  tackles+assists, the markets Pinnacle declines entirely.

A book qualifies as a sharp reference on the same bar Pinnacle cleared: a
positive return at volume, positive in every season, and not reproduced by
using a retail book in its place. Nothing looser.

    python -m scripts.nfl_prop_book_sweep
    python -m scripts.nfl_prop_book_sweep --min-edge 0.05 --min-bets 100
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from data import local_store
from data.ingestors.nfl_props_data_ingestor import norm_player_name
import models.nfl_prop_market as mk

# Every book the census found. Order is irrelevant; membership is not.
# Markets Pinnacle does not quote, so they are invisible to the rule today. A
# second sharp reference is the only thing that could open them, which is why
# betonlineag and hardrockbet matter beyond adding volume.
#
# tackles+assists is deliberately EXCLUDED: §5b established that our count runs
# ~9pp under the number books grade, so a result there would be measuring our
# own definition error, not a book's sharpness. Fix the target first.
EXTRA_MARKETS = ("player_rush_attempts", "player_rush_reception_yds", "player_sacks")

ALL_BOOKS = (
    "pinnacle", "draftkings", "fanduel", "betmgm", "williamhill_us", "espnbet",
    "fliff", "fanatics", "betparx", "betrivers", "bovada", "hardrockbet",
    "betonlineag", "ballybet",
)


def _actuals(log: pd.DataFrame) -> dict:
    log = log.copy()
    log["k"] = log.player_name.map(norm_player_name)
    log["ANY_TD"] = ((log.rushing_tds.fillna(0) + log.receiving_tds.fillna(0)) >= 1).astype(float)
    out = {}
    for r in log.itertuples(index=False):
        for m, c in mk.MARKET_STAT.items():
            v = getattr(r, c, None)
            if v is not None and not pd.isna(v):
                out[(r.game_id, r.k, m)] = float(v)
    return out


def _board(odds: pd.DataFrame, markets) -> tuple[dict, dict]:
    """(quotes, snapshots) at the pre-game 'open' series."""
    d = odds[(odds.market.isin(markets)) & (odds.snapshot_type == "open")].copy()
    d["k"] = d.player_name.map(norm_player_name)
    d = d.sort_values("snapshot_at", kind="stable")
    q, snaps = {}, {}
    for r in d.itertuples(index=False):
        def p(v):
            return None if v is None or (isinstance(v, float) and pd.isna(v)) else v
        key = (r.game_id, r.k, r.market, r.bookmaker)
        q[key] = {"line": p(r.line), "over_price": p(r.over_price),
                  "under_price": p(r.under_price)}
        snaps[key] = r.snapshot_at
    return q, snaps


def _run(quotes, snaps, act, ko, sharp, soft, min_edge):
    """Grade the rule with an arbitrary book as the sharp reference."""
    real = mk.SHARP_BOOK
    try:
        mk.SHARP_BOOK = sharp
        bets, diag = mk.find_bets(quotes, min_edge=min_edge, soft_books=tuple(soft))
    finally:
        mk.SHARP_BOOK = real
    return mk.grade(bets, act, snaps, ko), diag


def _line(label, s, extra=""):
    if not s.get("bets"):
        return f"{label:<20}{'0':>6}   no bets"
    seasons = " ".join(f"{k}:{v['roi_pct']:+.1f}%({v['bets']})"
                       for k, v in sorted(s["per_season"].items()))
    return (f"{label:<20}{s['bets']:>6}{s['win_pct']:>7.1f}%{s['roi_pct']:>+8.2f}%"
            f"  ({s['roi_ci'][0]:+.1f},{s['roi_ci'][1]:+.1f}){extra:>4}  {seasons}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-edge", type=float, default=0.05)
    ap.add_argument("--min-bets", type=int, default=100,
                    help="below this a reference book is reported but not judged")
    ap.add_argument("--markets", nargs="+", default=None,
                    help="market keys to sweep (default: the rule's SHARP_MARKETS)")
    ap.add_argument("--extended", action="store_true",
                    help="also sweep the markets Pinnacle does not quote — only "
                         "meaningful with a non-Pinnacle reference")
    a = ap.parse_args()

    local_store.activate()
    odds = local_store.read_table("nfl_prop_odds")
    act = _actuals(local_store.read_table("nfl_player_game_log"))
    ko = {r.game_id: r.commence_time for r in
          local_store.read_table("nfl_team_game_stats",
                                 columns=["game_id", "commence_time"])
          .dropna(subset=["commence_time"]).itertuples(index=False)}

    present = sorted(set(odds.bookmaker) & set(ALL_BOOKS))
    missing = [b for b in ALL_BOOKS if b not in present]
    print(f"books in the cache: {len(present)}  {', '.join(present)}")
    if missing:
        print(f"NOT yet backfilled: {', '.join(missing)}")
    print(f"min edge {a.min_edge:.0%}\n")

    markets = tuple(a.markets) if a.markets else (
        mk.SHARP_MARKETS + EXTRA_MARKETS if a.extended else mk.SHARP_MARKETS)
    print(f"markets: {len(markets)}"
          + ("  (+ the ones Pinnacle does not quote)" if a.extended else ""))
    quotes, snaps = _board(odds, markets)

    # ── 1. breadth: the rule with every available soft book ──────────────────
    soft_all = [b for b in present if b != mk.SHARP_BOOK]
    graded, diag = _run(quotes, snaps, act, ko, mk.SHARP_BOOK, soft_all, a.min_edge)
    print(f"{'':<20}{'bets':>6}{'win%':>7}{'ROI%':>8}{'  CI':>14}      per season")
    print(_line(f"ALL {len(soft_all)} soft books", mk.summarise(graded, draws=5000)))

    old = [b for b in ("draftkings", "fanduel", "betmgm", "williamhill_us", "espnbet")
           if b in present]
    g_old, _ = _run(quotes, snaps, act, ko, mk.SHARP_BOOK, old, a.min_edge)
    print(_line(f"the original {len(old)}", mk.summarise(g_old, draws=5000)))

    # ── 2. marginal contribution of each soft book ───────────────────────────
    # Counted on the DEDUPED selection: a book that only ever ties an existing
    # book's price adds nothing, and counting its raw edges would say otherwise.
    # Coverage first. A book that only reaches a third of the slate cannot be
    # compared to one that reaches all of it on ROI alone, and a new book with a
    # short history will look thin for a reason that is not about its prices.
    total_games = odds[odds.snapshot_type == "open"].game_id.nunique()
    cov = (odds[odds.snapshot_type == "open"]
           .groupby("bookmaker").game_id.nunique().to_dict())
    print(f"\n{'soft book':<20}{'games':>7}{'bets':>7}{'win%':>7}{'ROI%':>8}"
          f"   (as the ONLY soft book; {total_games} games have any quote)")
    for bk in soft_all:
        g, _ = _run(quotes, snaps, act, ko, mk.SHARP_BOOK, [bk], a.min_edge)
        s = mk.summarise(g, draws=2000)
        games_pct = f"{100 * cov.get(bk, 0) / total_games:.0f}%" if total_games else "-"
        if s.get("bets"):
            print(f"{bk:<20}{games_pct:>7}{s['bets']:>7}{s['win_pct']:>6.1f}%"
                  f"{s['roi_pct']:>+8.2f}%")
        else:
            print(f"{bk:<20}{games_pct:>7}{'0':>7}")

    # ── 3. the placebo, re-run over every book as the sharp reference ────────
    print(f"\n{'sharp reference':<20}{'bets':>6}{'win%':>7}{'ROI%':>8}{'  CI':>14}      per season")
    rows = []
    for sharp in present:
        soft = [b for b in present if b != sharp]
        g, _ = _run(quotes, snaps, act, ko, sharp, soft, a.min_edge)
        s = mk.summarise(g, draws=5000)
        rows.append((sharp, s))
    for sharp, s in sorted(rows, key=lambda r: -(r[1].get("roi_pct") or -99)):
        seasons = list((s.get("per_season") or {}).values())
        allpos = seasons and all(v["roi_pct"] > 0 for v in seasons)
        judged = (s.get("bets") or 0) >= a.min_bets
        tag = " **" if (allpos and judged and s["roi_pct"] > 0) else ("" if judged else " thin")
        print(_line(sharp, s, tag))
    print("\n** = positive at volume AND positive in every season — the bar "
          "Pinnacle cleared in §5c. Anything else is not a sharp reference.")


if __name__ == "__main__":
    main()
