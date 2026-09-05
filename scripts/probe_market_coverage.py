"""WHICH books serve WHICH prop market — asked one market at a time.

WHY THIS EXISTS
---------------
Matt, 2026-09-05: "Check all the sportsbooks we get betting lines for and see
if they publish stats under different keys and sync everything up with the
stats tab."

The prompt was FanDuel and Caesars showing nothing on the MLB hits board. The
cause was not that they do not price hits: they price hits for every hitter on
the slate, and publish them under `batter_hits_alternate` while never
returning a single `batter_hits` row. Measured 2026-09-05 across one MLB
slate, books that publish a market ONLY under its alternate key:

    FanDuel          hits, RBIs, runs scored, total bases
    Caesars          hits, RBIs, runs scored, strikeouts
    Bovada           hits, RBIs, runs scored
    BetRivers        runs scored
    BallyBet         runs scored
    betPARX          runs scored
    Fanatics         runs scored
    Rebet            hits

WHICH SIDE, NOT JUST WHICH KEY (added 2026-09-05). Knowing a book serves
`batter_hits` does not tell you a member can bet At Most on it, and the Stats
board greys that control out when none of their books prices the side. Our
table showed Bally Bet with 1,614 standard `batter_hits` rows and not one
Under, which is not a credible thing for a sportsbook to do -- so either the
feed is one-sided or our parser was dropping outcomes. Measured off two MLB
events, the feed is one-sided and the parser is exonerated:

    Bally Bet    hits, RBIs, total bases, stolen bases, outs   OVER-ONLY
    BetRivers    hits, RBIs, total bases, outs                 OVER-ONLY
    FanDuel / Fanatics / Hard Rock   stolen bases              OVER-ONLY
    DraftKings, BetMGM, betPARX, Fanatics, Hard Rock, ReBet, Caesars
                 every market they serve                       BOTH SIDES

So `sides` below counts Over and Under outcomes per (book, market). A market
a book serves on ONE side only is a real, permanent gap in what a member can
be shown -- not a bug to chase and not something more requests can fix.

STORED DATA CANNOT FINISH THIS AUDIT, which is the whole reason for this
script. A market we never REQUEST has no rows, and no query over what we hold
can distinguish "no book prices this" from "we never asked". The only way to
tell is to ask the API and see what comes back -- so this asks, and writes
NOTHING.

ONE MARKET PER CALL, deliberately. The ingestors chunk markets five at a time
because a chunk is the blast radius of one unsupported key; here the POINT is
to know exactly which key is unsupported, and The Odds API bills per market
returned either way, so one-per-call costs the same and attributes perfectly.

Usage:
    python -m scripts.probe_market_coverage --sport MLB
    python -m scripts.probe_market_coverage --sport MLB --markets a,b,c
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from config import (
    LINE_SHOP_BOOKMAKERS, ODDS_API_BASE, ODDS_API_BOOKMAKERS_PARAM,
    ODDS_API_KEY, ODDS_API_REGIONS,
)
from data.db import get_connection
from data.ingestors.odds_ingestor import SPORT_KEYS
from data.ingestors.odds_quota import persist_quota, record_quota_headers

_ET = ZoneInfo("America/New_York")

# What to ask about when the caller names no markets: everything we already
# pull, every one of those under its `_alternate` key, and the board stats
# that currently show a permanently blank column (mobile/src/lib/statCatalog).
# A key the API does not know 422s its own single-market call and is reported
# as unsupported, which is exactly the answer we came for.
BOARD_BLANKS = {
    "MLB": ["batter_doubles", "batter_triples", "batter_strikeouts",
            "batter_at_bats", "pitcher_home_runs_allowed", "pitcher_pitches"],
    "WNBA": ["player_steals", "player_blocks", "player_turnovers",
             "player_minutes", "player_blocks_steals"],
    "NBA": ["player_minutes", "player_double_double", "player_triple_double"],
    "NFL": ["player_rush_tds", "player_reception_tds", "player_targets",
            "player_pass_rush_reception_yds", "player_defensive_interceptions"],
    "NCAAF": ["player_rush_tds", "player_reception_tds", "player_targets",
              "player_tackles_assists", "player_rush_reception_yds"],
}


# The Odds API puts the side in `name` for some endpoints and in `description`
# for others -- the ingestor handles both (prop_odds_ingestor), and so must
# this: reading only one field would report a missing side that is merely in
# the other one, which is the false alarm this whole audit exists to kill.
_OU = {"over", "under"}
_YN = {"yes": "over", "no": "under"}


def _side_of(outcome: dict) -> str | None:
    """Which side is this outcome, whichever field carries it? None if neither."""
    for field in ("name", "description"):
        v = (outcome.get(field) or "").strip().lower()
        if v in _OU:
            return v
        if v in _YN:
            return _YN[v]
    return None


def _standard_markets(sport: str) -> list[str]:
    if sport == "NFL":
        return list(config.PROP_MARKETS_NFL)
    if sport == "NCAAF":
        return list(config.PROP_MARKETS_NCAAF)
    from data.ingestors.prop_odds_ingestor import PROP_MARKETS_BY_SPORT
    return list(PROP_MARKETS_BY_SPORT.get(sport, config.PROP_MARKETS_ALL))


def candidate_markets(sport: str) -> list[str]:
    """Every key worth asking about for this sport, de-duped, order kept."""
    out: list[str] = []
    for m in _standard_markets(sport):
        out.append(m)
        out.append(f"{m}_alternate")
    out.extend(BOARD_BLANKS.get(sport, []))
    seen, uniq = set(), []
    for m in out:
        if m not in seen:
            seen.add(m)
            uniq.append(m)
    return uniq


def _first_event(sport: str) -> dict | None:
    """One event on today's slate — coverage is a property of the book, not
    the game, so one is enough and every extra one is paid for twice."""
    resp = requests.get(f"{ODDS_API_BASE}/sports/{SPORT_KEYS[sport]}/events",
                        params={"apiKey": ODDS_API_KEY, "dateFormat": "iso"}, timeout=15)
    record_quota_headers(resp)
    if resp.status_code != 200:
        logger.warning(f"{sport}: events endpoint returned {resp.status_code}")
        return None
    today = datetime.now(_ET).strftime("%Y-%m-%d")
    for ev in resp.json():
        try:
            dt = datetime.fromisoformat(ev.get("commence_time", "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.astimezone(_ET).strftime("%Y-%m-%d") == today:
            return ev
    return None


def probe(sport: str, markets: list[str] | None = None) -> dict:
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set")
    markets = markets or candidate_markets(sport)
    conn = get_connection()
    try:
        ev = _first_event(sport)
        if ev is None:
            logger.info(f"{sport}: no events today — nothing to probe")
            return {"sport": sport, "event": None, "markets": {}}

        url = f"{ODDS_API_BASE}/sports/{SPORT_KEYS[sport]}/events/{ev['id']}/odds"
        served: dict[str, dict[str, int]] = {}
        unsupported: list[str] = []
        by_book: dict[str, list[str]] = defaultdict(list)
        sides: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
        one_sided: list[str] = []
        credits = 0

        for market in markets:
            resp = requests.get(url, params={
                "apiKey": ODDS_API_KEY, "regions": ODDS_API_REGIONS,
                "markets": market, "bookmakers": ODDS_API_BOOKMAKERS_PARAM,
                "oddsFormat": "american",
            }, timeout=20)
            record_quota_headers(resp)
            try:
                credits += int(resp.headers.get("x-requests-last", 0) or 0)
            except ValueError:
                pass
            if resp.status_code == 422:
                unsupported.append(market)
                continue
            if resp.status_code != 200:
                logger.warning(f"  {market}: HTTP {resp.status_code}")
                continue
            books: dict[str, int] = {}
            for book in (resp.json() or {}).get("bookmakers", []):
                key = book.get("key")
                if key not in LINE_SHOP_BOOKMAKERS:
                    continue
                outcomes = [o for m in book.get("markets", [])
                            if m.get("key") == market
                            for o in m.get("outcomes", [])]
                if outcomes:
                    books[key] = len(outcomes)
                    by_book[key].append(market)
                    over = sum(1 for o in outcomes if _side_of(o) == "over")
                    under = sum(1 for o in outcomes if _side_of(o) == "under")
                    sides[market][key] = {"over": over, "under": under}
                    if bool(over) != bool(under):
                        one_sided.append(
                            f"{key}|{market}|{'over' if over else 'under'}-only")
            if books:
                served[market] = dict(sorted(books.items(), key=lambda kv: -kv[1]))
            time.sleep(0.4)

        out = {
            "sport": sport,
            "event": f"{ev.get('away_team')} @ {ev.get('home_team')}",
            "markets_asked": len(markets),
            "markets_served": len(served),
            "unsupported_keys": unsupported,
            "empty_but_supported": [m for m in markets
                                    if m not in served and m not in unsupported],
            "served": served,
            "books": {b: sorted(ms) for b, ms in sorted(by_book.items())},
            # Per (market, book) Over/Under outcome counts, and the pairs that
            # came back with one side and not the other. A one-sided pair is a
            # permanent limit on what the board can offer for that book, not a
            # collection failure -- see the header.
            "sides": {m: dict(sorted(bs.items())) for m, bs in sorted(sides.items())},
            "one_sided": sorted(one_sided),
            "credits": credits,
        }
        logger.success(
            f"{sport} coverage probe: {len(served)}/{len(markets)} markets served, "
            f"{len(unsupported)} unsupported keys, {len(one_sided)} one-sided "
            f"(book, market) pairs, {credits} credits")
        return out
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Which books serve which prop markets")
    ap.add_argument("--sport", required=True, choices=sorted(SPORT_KEYS))
    ap.add_argument("--markets", default=None, help="comma-separated; default: every candidate")
    args = ap.parse_args()
    ms = [m.strip() for m in args.markets.split(",")] if args.markets else None
    print(json.dumps(probe(args.sport, ms), indent=2, sort_keys=True))
