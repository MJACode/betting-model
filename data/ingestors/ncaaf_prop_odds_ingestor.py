"""
NCAAF player prop odds from The Odds API → player_prop_odds.

WHY THIS EXISTS
---------------
Matt, 2026-09-05, approving alternate lines: "Same with NFL NCAAF." NFL had a
prop ingestor to add alternates to; college football had nothing at all. The
Stats tab has listed NCAAF players since the CFBD player log landed --
passing yards, carries, tackles -- and every one of those rows shows a dash
where every other sport shows a line, because no college prop has ever been
stored. Asked what the gap was, Matt: "Yes do it."

WHAT A COLLEGE PROP ROW IS FOR. There are four NCAAF models and all four are
game-level; there is no NCAAF prop model and this does not add one. These rows
are RESEARCH: the Stats board's line column and the betslip's line legs
(mobile/src/lib/lineLegs.ts). Nothing here ever becomes a pick, so §6's
DraftKings-decides rule has no model decision to protect -- but the rows are
written exactly like every other sport's, one per book, so if a college prop
model is ever trained the substrate is already there and already honest.

THE THING THAT MAKES THIS DIFFERENT FROM THE NFL: SLATE SIZE
------------------------------------------------------------
Measured 2026-09-05, one Saturday:

    120  NCAAF games on the slate
     70  with a DraftKings game line
     39  FBS vs FBS
     34  priced by our own models

A prop pull is one call per event, so pulling all 120 would cost more than the
entire MLB program -- and the 50 games with no DK line (Lakeland at Carthage,
Division III) have no player props to sell us. `_scope_events` therefore keeps
only events DraftKings has already lined (config.NCAAF_PROP_REQUIRE_DK_LINE),
under a hard per-pass ceiling. Self-maintaining: no hand-kept list of "big
games" to rot by November.

THE GAME ID IS RESOLVED, NEVER CONSTRUCTED
-------------------------------------------
The NFL ingestor's lesson, and it bites harder here. The Odds API writes
"Ohio State Buckeyes"; CFBD's canonical school is "Ohio State", and its
spellings carry accents and punctuation this feed drops ("San José State",
"Hawai'i"). `resolve_odds_api_school` already solves exactly this for game
lines, so props reuse it rather than growing a second, differently-wrong copy.
An event whose resolved id is not in `games` is SKIPPED, not written: an
orphan prop row joins to nothing and would sit in the table forever looking
like coverage.

WHAT IS AND IS NOT ASSUMED ABOUT THE FEED
------------------------------------------
The Odds API uses one key namespace for both football leagues, so the market
list is the NFL's under the college sport key. Which of those keys the API
actually serves for NCAAF is NOT assumed: markets are requested in chunks, a
chunk the API rejects is skipped, and `probe()` REPORTS which markets, books
and players came back. That is the number Matt gets before this is scheduled.

Usage:
    python -m data.ingestors.ncaaf_prop_odds_ingestor --probe          # measures, writes nothing
    python -m data.ingestors.ncaaf_prop_odds_ingestor                  # today's scoped slate
    python -m data.ingestors.ncaaf_prop_odds_ingestor --date 2026-09-05
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config import (
    LINE_SHOP_BOOKMAKERS,
    NCAAF_PROP_MAX_EVENTS,
    NCAAF_PROP_REQUIRE_DK_LINE,
    ODDS_API_BASE,
    ODDS_API_BOOKMAKER,
    ODDS_API_BOOKMAKERS_PARAM,
    ODDS_API_KEY,
    ODDS_API_REGIONS,
    PROP_ALT_MARKETS,
    PROP_MARKETS_NCAAF,
)
from data.db import get_connection, DBConnection
from data.ingestors.cfbd_ingestor import build_ncaaf_game_id, resolve_odds_api_school
from data.ingestors.odds_quota import persist_quota, record_quota_headers
from data.ingestors.prop_odds_ingestor import _insert_prop_odds, _parse_prop_markets

SPORT_KEY = "americanfootball_ncaaf"
REQUEST_SLEEP = 0.5
# Same size as the NFL ingestor's. A rejected chunk costs its own markets and
# no others, so the chunk size is the blast radius of one unsupported key.
MARKET_CHUNK = 5

_ET = ZoneInfo("America/New_York")


def _market_chunks(markets: list[str]) -> list[list[str]]:
    """Standard markets first, alternates after, never mixed in one chunk.

    Same rule as the NFL ingestor: an alternate key the API does not serve for
    college must not be able to take a standard market down with it.
    """
    standard = [m for m in markets if not m.endswith("_alternate")]
    alternates = [m for m in markets if m.endswith("_alternate")]
    out: list[list[str]] = []
    for group in (standard, alternates):
        out.extend(group[i:i + MARKET_CHUNK] for i in range(0, len(group), MARKET_CHUNK))
    return out


# ── Events and scope ─────────────────────────────────────────────────────────

def _get_events(target_date: str) -> list[dict]:
    """Every NCAAF event whose kickoff falls on target_date (ET)."""
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set in .env")
    resp = requests.get(f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events",
                        params={"apiKey": ODDS_API_KEY, "dateFormat": "iso"},
                        timeout=15)
    record_quota_headers(resp)
    if resp.status_code == 401:
        raise ValueError("Invalid ODDS_API_KEY")
    if resp.status_code != 200:
        logger.warning(f"Events endpoint returned {resp.status_code}: {resp.text[:200]}")
        return []

    out = []
    for event in resp.json():
        commence = event.get("commence_time", "")
        try:
            dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
            event_date = dt.astimezone(_ET).strftime("%Y-%m-%d")
        except ValueError:
            event_date = target_date          # fail open: never drop on a bad clock
        if event_date == target_date:
            out.append({"id": event["id"],
                        "home_team": event.get("home_team", ""),
                        "away_team": event.get("away_team", ""),
                        "commence_time": commence})
    return out


def _dk_lined_game_ids(conn: DBConnection, game_date: str) -> set[str]:
    """Games DraftKings has posted a line for -- "a book is pricing this"."""
    rows = conn.execute("""
        SELECT DISTINCT o.game_id
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE g.sport = 'NCAAF'
          AND g.game_date = %s
          AND o.bookmaker = %s
    """, (game_date, ODDS_API_BOOKMAKER)).fetchall()
    return {r[0] for r in rows}


def _known_game_ids(conn: DBConnection, game_date: str) -> set[str]:
    rows = conn.execute(
        "SELECT game_id FROM games WHERE sport = 'NCAAF' AND game_date = %s",
        (game_date,)).fetchall()
    return {r[0] for r in rows}


def scope_events(conn: DBConnection, events: list[dict], game_date: str,
                 require_dk_line: bool | None = None,
                 max_events: int | None = None) -> tuple[list[tuple[dict, str]], dict]:
    """
    (kept events paired with their resolved game_id, why the rest went).

    Three gates, in order, each counted so a shrinking slate is legible in the
    log rather than mysterious:
      unresolved  -- the school name did not resolve to a game we know
      no_dk_line  -- no book we score against prices the game (Division III)
      over_cap    -- the per-pass ceiling
    """
    require_dk_line = NCAAF_PROP_REQUIRE_DK_LINE if require_dk_line is None else require_dk_line
    max_events = NCAAF_PROP_MAX_EVENTS if max_events is None else max_events

    known = _known_game_ids(conn, game_date)
    lined = _dk_lined_game_ids(conn, game_date) if require_dk_line else set()

    kept: list[tuple[dict, str]] = []
    dropped = {"unresolved": 0, "no_dk_line": 0, "over_cap": 0}
    for ev in events:
        home = resolve_odds_api_school(ev["home_team"], conn)
        away = resolve_odds_api_school(ev["away_team"], conn)
        game_id = build_ncaaf_game_id(game_date, away, home)
        if game_id not in known:
            # An orphan prop row joins to nothing and looks like coverage
            # forever. Skipping is the same choice the game-line resolver makes.
            dropped["unresolved"] += 1
            logger.debug(f"  unresolved: {ev['away_team']} @ {ev['home_team']} -> {game_id}")
            continue
        if require_dk_line and game_id not in lined:
            dropped["no_dk_line"] += 1
            continue
        kept.append((ev, game_id))

    if max_events and len(kept) > max_events:
        dropped["over_cap"] = len(kept) - max_events
        kept = kept[:max_events]
    return kept, dropped


# ── The event call ───────────────────────────────────────────────────────────

def _event_props(event_id: str, markets: list[str]) -> tuple[list[tuple[str, list]], int]:
    """
    ([(bookmaker, markets)], credits used) for one event, or ([], 0).

    Chunked, and a rejected chunk is skipped rather than retried whole: for
    college the likeliest 422 is a market the API simply does not serve here,
    and that is exactly what the probe is for.
    """
    url = f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events/{event_id}/odds"
    per_book: dict[str, list] = {}
    used_before = used_after = None

    for chunk in _market_chunks(markets):
        params = {
            "apiKey":       ODDS_API_KEY,
            "regions":      ODDS_API_REGIONS,
            "markets":      ",".join(chunk),
            "bookmakers":   ODDS_API_BOOKMAKERS_PARAM,
            "oddsFormat":   "american",
            "includeLinks": "true",
            "includeSids":  "true",
        }
        resp = requests.get(url, params=params, timeout=20)
        record_quota_headers(resp)
        if used_before is None:
            u = _credits_used(resp)
            used_before = u - 1 if u is not None else None
        used_after = _credits_used(resp) or used_after

        if resp.status_code == 422:
            logger.debug(f"  event {event_id}: 422 on {chunk}")
            continue
        if resp.status_code != 200:
            logger.warning(f"  event {event_id}: HTTP {resp.status_code}")
            continue

        for book in (resp.json() or {}).get("bookmakers", []):
            key = book.get("key")
            # Ignore anything we did not ask for, so an API-side change cannot
            # quietly write an unexpected book into player_prop_odds.
            if key not in LINE_SHOP_BOOKMAKERS:
                continue
            per_book.setdefault(key, []).extend(book.get("markets", []))
        time.sleep(REQUEST_SLEEP)

    credits = (used_after - used_before) if (used_after and used_before) else 0
    return [(k, v) for k, v in per_book.items() if k], max(credits, 0)


def _credits_used(resp) -> int | None:
    try:
        return int(resp.headers.get("x-requests-used"))
    except (TypeError, ValueError):
        return None


# ── Probe: measure before spending ───────────────────────────────────────────

def probe(target_date: str | None = None, limit_events: int = 3,
          with_alternates: bool = True) -> dict:
    """
    Call a few scoped events and REPORT. Writes nothing.

    This exists because the honest answer to "what will college props cost"
    is not derivable from the MLB figure: it depends on how many of these
    markets The Odds API serves for NCAAF and how many books answer, neither
    of which is documented. Matt sees this output before anything is
    scheduled.
    """
    target_date = target_date or datetime.now(_ET).strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        events = _get_events(target_date)
        kept, dropped = scope_events(conn, events, target_date)
        markets = list(PROP_MARKETS_NCAAF)
        if with_alternates:
            markets += PROP_ALT_MARKETS.get("NCAAF", [])

        sample = kept[:limit_events]
        by_market: dict[str, int] = {}
        by_book: dict[str, int] = {}
        credits = 0
        for ev, game_id in sample:
            per_book, used = _event_props(ev["id"], markets)
            credits += used
            for book_key, book_markets in per_book:
                for mkt in book_markets:
                    key = mkt.get("key", "")
                    n = len(mkt.get("outcomes", []))
                    by_market[key] = by_market.get(key, 0) + n
                    by_book[book_key] = by_book.get(book_key, 0) + n
            logger.info(f"  probed {game_id}: {used} credits")

        per_event = credits / len(sample) if sample else 0
        out = {
            "date": target_date,
            "events_on_slate": len(events),
            "events_in_scope": len(kept),
            "dropped": dropped,
            "events_probed": len(sample),
            "credits_total": credits,
            "credits_per_event": round(per_event, 1),
            "markets_returned": dict(sorted(by_market.items(), key=lambda kv: -kv[1])),
            "markets_requested": len(markets),
            "books_returned": dict(sorted(by_book.items(), key=lambda kv: -kv[1])),
            "projected_one_pass": round(per_event * len(kept)),
        }
        logger.success(
            f"NCAAF prop probe {target_date}: {len(kept)}/{len(events)} events in scope, "
            f"{out['credits_per_event']} credits/event, "
            f"{len(by_market)}/{len(markets)} markets served, "
            f"one full pass ≈ {out['projected_one_pass']} credits")
        return out
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()


# ── Ingest ───────────────────────────────────────────────────────────────────

def run_ncaaf_prop_odds_ingestor(target_date: str | None = None,
                                 snapshot_type: str = "open",
                                 with_alternates: bool = True) -> dict:
    """Today's scoped college slate. Off-season this is a clean no-op."""
    target_date = target_date or datetime.now(_ET).strftime("%Y-%m-%d")
    snapshot_at = datetime.now(_ET).isoformat()
    start = datetime.now()
    logger.info(f"NCAAF prop odds: {target_date} ({snapshot_type})")

    conn = get_connection()
    total_rows = total_events = credits = 0
    try:
        events = _get_events(target_date)
        if not events:
            logger.info(f"No NCAAF events for {target_date} — nothing to do")
            return {"target_date": target_date, "events": 0, "prop_rows": 0, "credits": 0}

        kept, dropped = scope_events(conn, events, target_date)
        logger.info(f"  {len(kept)}/{len(events)} events in scope "
                    f"(dropped: {dropped})")
        markets = list(PROP_MARKETS_NCAAF)
        if with_alternates:
            markets += PROP_ALT_MARKETS.get("NCAAF", [])
        allowed = set(markets)

        for ev, game_id in kept:
            try:
                per_book, used = _event_props(ev["id"], markets)
            except Exception as exc:            # one event must not end the pass
                logger.warning(f"Props fetch failed for {game_id}: {exc}")
                continue
            credits += used
            if not per_book:
                continue

            rows = []
            for book_key, book_markets in per_book:
                rows.extend(_parse_prop_markets(
                    book_markets, game_id, target_date, snapshot_type, snapshot_at,
                    allowed_markets=allowed, bookmaker=book_key))
            if rows:
                total_rows += _insert_prop_odds(conn, rows)
                total_events += 1
                conn.commit()
                logger.info(f"  {game_id}: {len(rows)} rows, "
                            f"{len(set(r['player_name'] for r in rows))} players")

        duration = (datetime.now() - start).total_seconds()
        logger.success(f"NCAAF prop odds: {total_events}/{len(kept)} games with props, "
                       f"{total_rows} rows, {credits} credits — {duration:.1f}s")
        return {"target_date": target_date, "events": total_events,
                "events_in_scope": len(kept), "prop_rows": total_rows,
                "credits": credits, "duration_s": duration}
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="NCAAF player prop odds → player_prop_odds")
    ap.add_argument("--date", default=None, help="ISO date (default: today ET)")
    ap.add_argument("--probe", action="store_true",
                    help="measure a few events and report; writes nothing")
    ap.add_argument("--limit-events", type=int, default=3, help="probe sample size")
    ap.add_argument("--no-alternates", action="store_true")
    args = ap.parse_args()

    if args.probe:
        import json
        print(json.dumps(probe(args.date, args.limit_events,
                               with_alternates=not args.no_alternates), indent=2))
    else:
        run_ncaaf_prop_odds_ingestor(args.date,
                                     with_alternates=not args.no_alternates)
