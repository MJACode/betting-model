"""
Market-relative WNBA prop selection: de-vig Pinnacle, bet the soft outlier.

THE PORT, AND WHY NOW. The model-first path for WNBA props was tested to a
verdict on 2026-08-31: the points rebuild (availability + minutes model + NB
head) STOPped in both availability modes, and the leak-free all-props sweep put
four of five markets at or under the vig. The construction that IS validated in
this repo is `models/nfl_prop_market` — Pinnacle's de-vigged price as the
estimate of truth, bet wherever a retail book disagrees by more than the juice
(+10.2% train / +10.8% blind over 954 NFL bets at the pre-committed 5pp). This
module is that rule pointed at WNBA, sharing the NFL module's selection
functions outright so the two rules can never drift on de-vig math, like-line
discipline, or one-bet-per-proposition dedupe.

WHAT PINNACLE QUOTES FOR WNBA (measured 2026-08-31, first 4 days of coverage):
player_points (62 players/12 games), player_rebounds (34), player_assists (20).
It declines player_threes — a market maker declining to quote is information,
and threes stays out of SHARP_MARKETS rather than being anchored to a weaker
book.

The like-line rule is inherited and non-negotiable: Pinnacle at 15.5 points and
DraftKings at 16.5 are different propositions, and the NFL work already paid
once for learning that (the tackles +13% artifact).

PAPER-FIRST. Kill criterion, pre-committed: no positive blind month at >= 50
flags → the rule is closed for WNBA, not re-thresholded.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Selection machinery is IMPORTED, not copied — one implementation of de-vig,
# like-line matching, edge, and per-proposition dedupe across both sports.
from models.nfl_prop_market import (  # noqa: F401  (re-exported for callers)
    MarketBet,
    SHARP_BOOK,
    best_per_prop,
    devig,
    find_bets,
    implied,
)

from data.db import DBConnection
from features.feature_engine import _parse_iso_ts

# Markets Pinnacle was measured to quote for WNBA. Explicit, not discovered at
# runtime, so a silent coverage change surfaces as a missing market rather than
# a quietly smaller bet set (the NFL module's convention).
SHARP_MARKETS = ("player_points", "player_rebounds", "player_assists")

# The books we BET at. The blanket WNBA-prop -140 floor (config.MODEL_MIN_ODDS)
# is applied by the card on top of these.
SOFT_BOOKS = ("draftkings", "fanduel", "betmgm", "williamhill_us", "espnbet")

# Settlement: picks carry model_id 'wnba_prop_market' and the market on
# picks.prop_market; paper_tracker resolves the stat through this map (the
# FROM_PROP_MARKET sentinel, same as NFL).
MARKET_STAT = {
    "player_points":   "points",
    "player_rebounds": "rebounds",
    "player_assists":  "assists",
}


def load_wnba_prop_quotes(conn: DBConnection, game_date: str) -> dict:
    """
    {(game_id, player, market, book): {line, over_price, under_price, links}}
    for one WNBA slate — the LATEST PRE-TIP snapshot per proposition per book.

    Pre-tip is decided on PARSED timestamps in Python, never by SQL string
    comparison — snapshot_at/commence_time are TEXT in mixed 'Z'/offset shapes
    and string order is not chronological order (the session-106 leak, which
    invalidated an entire WNBA threshold sweep). An unparseable snapshot loses
    to any parsed one; a game with no commence_time is treated as pre-tip
    (fail-open matches _is_pregame_snapshot's convention).
    """
    mkts = ",".join(["%s"] * len(SHARP_MARKETS))
    books = ",".join(["%s"] * (len(SOFT_BOOKS) + 1))
    rows = conn.execute(f"""
        SELECT o.game_id, o.player_name, o.market, o.bookmaker,
               o.line, o.over_price, o.under_price, o.over_link, o.under_link,
               o.snapshot_at, g.commence_time
        FROM player_prop_odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE g.sport = 'WNBA' AND o.game_date = %s
          AND o.market IN ({mkts})
          AND o.bookmaker IN ({books})
        ORDER BY o.snapshot_at
    """, [game_date] + list(SHARP_MARKETS) + list(SOFT_BOOKS) + [SHARP_BOOK]
    ).fetchall()

    quotes: dict = {}
    best_ts: dict = {}
    for gid, player, market, book, line, over_p, under_p, over_l, under_l, snap, tip in rows:
        if line is None:
            continue
        tip_dt = _parse_iso_ts(tip)
        snap_dt = _parse_iso_ts(snap)
        if tip_dt is not None and snap_dt is not None and snap_dt >= tip_dt:
            continue                                      # post-tip snapshot
        key = (gid, player, market, book)
        if key in best_ts:
            prev = best_ts[key]
            if not (snap_dt is not None and (prev is None or snap_dt > prev)):
                continue
        best_ts[key] = snap_dt
        quotes[key] = {
            "line": float(line), "over_price": over_p, "under_price": under_p,
            "over_link": over_l, "under_link": under_l,
        }
    return quotes
