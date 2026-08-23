"""
NFL player prop odds from The Odds API → player_prop_odds.

Two paths, one parser:
  • run_nfl_prop_odds_ingestor()  — the upcoming slate, live prices
  • backfill_nfl_prop_odds()      — the historical per-event endpoint

Both reuse `prop_odds_ingestor`'s parser and insert, so an NFL prop row is
shaped exactly like an MLB/NBA one and the scorer needs no special case.

Three things this module gets right that are expensive to retrofit:

1. **Every book keeps its own row.** `_parse_prop_markets` is called once per
   bookmaker and the book is stamped on the row. Screening books is a selection
   -time decision; baking a "best line" in at ingest makes it unfixable, and
   picking the best line across books preferentially samples bad data.
2. **The snapshot timestamp is the line's, not the run's.** For historical
   pulls it is the timestamp The Odds API reports for the snapshot it served,
   not `now()`. A line whose post time relative to injury news is unknown is a
   leak, and this repo has already shipped months of props graded against
   in-play prices.
3. **The game id is RESOLVED, never constructed.** The modelling tables key on
   the nflverse id (NFL_2026_01_KC_BUF); The Odds API knows only team names and
   a kickoff. The resolver looks the pair up in `nfl_team_game_stats`, so an
   unmapped or mismatched team yields a SKIPPED event rather than an orphan row
   the scorer would never join to.

Credit cost is measured, not assumed. Every response's quota headers are
recorded (`data.ingestors.odds_quota`) and the backfill reports the actual
credits consumed per event so a full backfill is priced from a probe rather
than from a guess about the historical multiplier.

Usage:
    python -m data.ingestors.nfl_prop_odds_ingestor                      # upcoming slate
    python -m data.ingestors.nfl_prop_odds_ingestor --probe 2024-10-06   # 1 date, report cost
    python -m data.ingestors.nfl_prop_odds_ingestor --backfill 2023 2025
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import config
from config import (
    ODDS_API_KEY, ODDS_API_BASE, ODDS_API_REGIONS, ODDS_API_BOOKMAKER,
    ODDS_API_BOOKMAKERS_PARAM, PROP_MARKETS_NFL, NFL_ODDS_API_MAP,
)
from data.db import get_connection, DBConnection
from data.ingestors.odds_quota import record_quota_headers, persist_quota
from data.ingestors.nfl_props_data_ingestor import norm_player_name
from data.ingestors.prop_odds_ingestor import _parse_prop_markets, _insert_prop_odds

try:
    from loguru import logger
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)


SPORT_KEY = "americanfootball_nfl"
REQUEST_SLEEP = 0.4          # polite spacing between per-event calls
# The Odds API serves at most ~5 prop markets per request cleanly; chunking also
# means one unsupported market cannot 422 the whole basket for an event.
MARKET_CHUNK = 5


# ── Game-id resolution ────────────────────────────────────────────────────────

def _load_nfl_games(conn: DBConnection, start: str, end: str) -> dict:
    """{(away_abbrev, home_abbrev, game_date): (game_id, game_date)} for a window."""
    rows = conn.execute("""
        SELECT game_id, team, opponent, game_date, is_home
        FROM nfl_team_game_stats
        WHERE game_date BETWEEN %s AND %s
    """, (start, end)).fetchall()
    out: dict[tuple[str, str, str], tuple[str, str]] = {}
    for game_id, team, opp, game_date, is_home in rows:
        if is_home != 1:
            continue                     # one row per game, from the home side
        d = game_date.isoformat() if hasattr(game_date, "isoformat") else str(game_date)[:10]
        out[(opp, team, d)] = (game_id, d)
    return out


def resolve_nfl_game_id(games: dict, home_name: str, away_name: str,
                        commence_time: str) -> tuple[str, str] | None:
    """
    (game_id, game_date) for an Odds API event, or None.

    Kickoff is a UTC instant, so a Sunday-night or Monday-night game lands on
    the NEXT calendar day in UTC. Both the UTC date and the day before are
    tried — matching only on the exact UTC date would silently drop every
    prime-time game.
    """
    home = NFL_ODDS_API_MAP.get(home_name)
    away = NFL_ODDS_API_MAP.get(away_name)
    if not home or not away:
        return None
    try:
        ts = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    for delta in (0, -1, 1):
        d = (ts.date() + timedelta(days=delta)).isoformat()
        hit = games.get((away, home, d))
        if hit:
            return hit
    return None


# ── API ───────────────────────────────────────────────────────────────────────

def _require_key() -> None:
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set")


def _credits_used(resp) -> int | None:
    try:
        return int(resp.headers.get("x-requests-used"))
    except (TypeError, ValueError):
        return None


def _get(url: str, params: dict, timeout: int = 30):
    resp = requests.get(url, params=params, timeout=timeout)
    record_quota_headers(resp)
    return resp


def list_events(days_ahead: int = 8) -> list[dict]:
    """Upcoming NFL events inside the window. The events list costs no credits."""
    _require_key()
    resp = _get(f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events",
                {"apiKey": ODDS_API_KEY, "dateFormat": "iso"}, timeout=20)
    if resp.status_code != 200:
        logger.warning(f"NFL events: HTTP {resp.status_code}")
        return []
    cutoff = datetime.now(timezone.utc) + timedelta(days=days_ahead)
    out = []
    for ev in resp.json():
        try:
            ts = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if ts <= cutoff:
            out.append(ev)
    return out


def list_historical_events(snapshot_iso: str) -> tuple[list[dict], str | None]:
    """
    (events, snapshot timestamp actually served) for a past instant.

    The Odds API snaps to its nearest stored snapshot; the returned timestamp is
    the one that matters for leak discipline, so it is threaded through to the
    rows rather than being replaced by the run time.
    """
    _require_key()
    resp = _get(f"{ODDS_API_BASE}/historical/sports/{SPORT_KEY}/events",
                {"apiKey": ODDS_API_KEY, "date": snapshot_iso, "dateFormat": "iso"})
    if resp.status_code != 200:
        logger.warning(f"NFL historical events {snapshot_iso}: HTTP {resp.status_code} "
                       f"{resp.text[:160]}")
        return [], None
    body = resp.json()
    return body.get("data", []), body.get("timestamp")


def _event_props(event_id: str, markets: list[str],
                 snapshot_iso: str | None = None) -> tuple[list[tuple[str, list]], str | None, int]:
    """
    ([(bookmaker, markets)], snapshot timestamp, credits used) for one event.

    Markets are requested in chunks so one unsupported market cannot 422 the
    whole basket. A 422 on a chunk is logged and skipped — the remaining chunks
    still land, which is the difference between losing one market and losing the
    event.
    """
    base = f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events/{event_id}/odds"
    if snapshot_iso:
        base = f"{ODDS_API_BASE}/historical/sports/{SPORT_KEY}/events/{event_id}/odds"

    per_book: dict[str, list] = {}
    stamp = None
    used_before = used_after = None

    for i in range(0, len(markets), MARKET_CHUNK):
        chunk = markets[i:i + MARKET_CHUNK]
        params = {
            "apiKey": ODDS_API_KEY, "regions": ODDS_API_REGIONS,
            "markets": ",".join(chunk), "bookmakers": ODDS_API_BOOKMAKERS_PARAM,
            "oddsFormat": "american", "dateFormat": "iso",
            "includeLinks": "true", "includeSids": "true",
        }
        if snapshot_iso:
            params["date"] = snapshot_iso
        resp = _get(base, params)
        if used_before is None:
            u = _credits_used(resp)
            used_before = u - 1 if u is not None else None
        used_after = _credits_used(resp) or used_after

        if resp.status_code == 422:
            # unsupported market OR unsupported book — retry DK-only so a
            # renamed display book can never cost the prices we score against
            if params["bookmakers"] != ODDS_API_BOOKMAKER:
                params["bookmakers"] = ODDS_API_BOOKMAKER
                resp = _get(base, params)
                used_after = _credits_used(resp) or used_after
            if resp.status_code != 200:
                logger.debug(f"  event {event_id}: 422 on {chunk}")
                continue
        elif resp.status_code != 200:
            logger.warning(f"  event {event_id}: HTTP {resp.status_code}")
            continue

        body = resp.json()
        data = body.get("data", body) if snapshot_iso else body
        stamp = body.get("timestamp") if snapshot_iso else stamp
        for book in (data or {}).get("bookmakers", []):
            per_book.setdefault(book.get("key", ""), []).extend(book.get("markets", []))
        time.sleep(REQUEST_SLEEP)

    credits = (used_after - used_before) if (used_after and used_before) else 0
    return [(k, v) for k, v in per_book.items() if k], stamp, max(credits, 0)


# ── Ingest ────────────────────────────────────────────────────────────────────

def _ingest_events(conn: DBConnection, events: list[dict], games: dict,
                   snapshot_iso: str | None, snapshot_type: str,
                   markets: list[str] | None = None) -> dict:
    rows_total = skipped = credits = 0
    for ev in events:
        resolved = resolve_nfl_game_id(games, ev.get("home_team", ""),
                                       ev.get("away_team", ""), ev.get("commence_time", ""))
        if resolved is None:
            skipped += 1
            logger.debug(f"  unresolved event: {ev.get('away_team')} @ {ev.get('home_team')}")
            continue
        game_id, game_date = resolved

        want = list(markets or PROP_MARKETS_NFL)
        books, served_stamp, used = _event_props(ev["id"], want, snapshot_iso)
        credits += used
        # the line's own timestamp, never the run's — see module docstring
        stamp = served_stamp or snapshot_iso or datetime.now(timezone.utc).isoformat()

        rows = []
        # NOT `markets` — that is this function's parameter, and shadowing it
        # here left the next event asking the API for a list of dicts.
        for book_key, book_markets in books:
            rows.extend(_parse_prop_markets(
                book_markets, game_id=game_id, game_date=game_date,
                snapshot_type=snapshot_type, snapshot_at=stamp,
                allowed_markets=want, bookmaker=book_key))
        if rows:
            rows_total += _insert_prop_odds(conn, rows)
            conn.commit()
    return {"rows": rows_total, "events": len(events) - skipped,
            "skipped": skipped, "credits": credits}


def run_nfl_prop_odds_ingestor(days_ahead: int = 8) -> dict:
    """Live prices for the upcoming slate. Off-season this is a clean no-op."""
    conn = get_connection()
    try:
        events = list_events(days_ahead)
        if not events:
            logger.info("NFL prop odds: no events in window")
            return {"rows": 0, "events": 0, "skipped": 0, "credits": 0}
        today = datetime.now(timezone.utc).date()
        games = _load_nfl_games(conn, (today - timedelta(days=2)).isoformat(),
                                (today + timedelta(days=days_ahead + 2)).isoformat())
        got = _ingest_events(conn, events, games, None, "open")
        logger.success(f"NFL prop odds: {got}")
        return got
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()


def backfill_nfl_prop_odds(dates: list[str], hours_before: int = 3,
                           limit_events: int | None = None,
                           markets: list[str] | None = None) -> dict:
    """
    Historical prop lines for each game date, snapshotted `hours_before` kickoff.

    One snapshot per date rather than a dense series: a prop backfill is priced
    per event per market, and the first question is whether an edge survives at
    a single pre-game instant. Densifying later is cheap; the schema is
    append-only and a second snapshot is a new row.
    """
    _require_key()
    conn = get_connection()
    total = {"rows": 0, "events": 0, "skipped": 0, "credits": 0, "dates": 0}
    try:
        for d in dates:
            # kickoffs are UTC; a 13:00 ET Sunday game is 17:00 UTC, so a
            # snapshot at 14:00 UTC is ~3h before the early window
            snap = f"{d}T{17 - hours_before:02d}:00:00Z"
            events, served = list_historical_events(snap)
            if not events:
                logger.info(f"  {d}: no historical events at {snap}")
                continue
            if limit_events:
                events = events[:limit_events]
            games = _load_nfl_games(conn, (datetime.fromisoformat(d).date()
                                           - timedelta(days=1)).isoformat(),
                                   (datetime.fromisoformat(d).date()
                                    + timedelta(days=1)).isoformat())
            got = _ingest_events(conn, events, games, served or snap, "open", markets)
            for k in ("rows", "events", "skipped", "credits"):
                total[k] += got[k]
            total["dates"] += 1
            logger.info(f"  {d}: {got}")
        return total
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()


def load_nfl_prop_odds(conn: DBConnection, game_ids: list[str],
                       markets: list[str] | None = None,
                       bookmaker: str = ODDS_API_BOOKMAKER,
                       before: str | None = None) -> dict:
    """
    {(game_id, norm_name, market): {line, over_price, under_price, ...}} for a slate.

    Joined on the NORMALISED player name, not the exact string. The odds feed
    and nflverse do not spell names the same way ("Marvin Harrison Jr." vs
    "Marvin Harrison", accents, "II"), so the platform's exact-match
    `_get_prop_dk_odds` — written for MLB, where both sources use one canonical
    name — silently returns nothing for a chunk of the NFL board. Same bridge as
    the snap-count join.

    `before` (an ISO timestamp) keeps only snapshots strictly earlier, which is
    how the backtest enforces its timestamp rule; the live scorer leaves it None
    and takes the newest. Either way the LATEST qualifying snapshot per
    (game, player, market) wins.
    """
    if not game_ids:
        return {}
    sql = """
        SELECT game_id, player_name, market, line, over_price, under_price,
               over_link, under_link, snapshot_at, bookmaker
        FROM player_prop_odds
        WHERE game_id = ANY(%s) AND bookmaker = %s
    """
    params: list = [list(game_ids), bookmaker]
    if markets:
        sql += " AND market = ANY(%s)"
        params.append(list(markets))
    if before:
        sql += " AND snapshot_at < %s"
        params.append(before)
    sql += " ORDER BY snapshot_at ASC"     # later rows overwrite earlier ones

    out: dict = {}
    for r in conn.execute(sql, tuple(params)).fetchall():
        key = (r[0], norm_player_name(r[1]), r[2])
        out[key] = {"line": r[3], "over_price": r[4], "under_price": r[5],
                    "over_link": r[6], "under_link": r[7], "snapshot_at": r[8],
                    "bookmaker": r[9], "player_name": r[1]}
    return out


def nfl_game_dates(conn: DBConnection, seasons: list[int]) -> list[str]:
    """Distinct NFL game dates for the given seasons, from nfl_team_game_stats."""
    rows = conn.execute("""
        SELECT DISTINCT game_date FROM nfl_team_game_stats
        WHERE season = ANY(%s) AND plays IS NOT NULL
        ORDER BY game_date
    """, (list(seasons),)).fetchall()
    return [r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0])[:10] for r in rows]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="NFL player prop odds → player_prop_odds")
    ap.add_argument("--probe", metavar="DATE",
                    help="one historical date, a few events — reports measured credit cost")
    ap.add_argument("--backfill", nargs=2, type=int, metavar=("START", "END"),
                    help="season range, e.g. --backfill 2023 2025")
    ap.add_argument("--limit-events", type=int, default=None)
    ap.add_argument("--days-ahead", type=int, default=8)
    ap.add_argument("--markets", nargs="+", default=None,
                    help="restrict to these market keys — re-pulling ONE market "
                         "costs a fraction of the full basket and avoids "
                         "duplicating rows already stored for the others")
    args = ap.parse_args()

    if args.probe:
        got = backfill_nfl_prop_odds([args.probe], limit_events=args.limit_events or 3,
                                     markets=args.markets)
        per = got["credits"] / got["events"] if got["events"] else 0
        logger.success(f"PROBE {args.probe}: {got} | {per:.1f} credits/event measured")
    elif args.backfill:
        c = get_connection()
        try:
            dates = nfl_game_dates(c, list(range(args.backfill[0], args.backfill[1] + 1)))
        finally:
            c.close()
        logger.info(f"Backfilling {len(dates)} NFL game dates")
        logger.success(f"BACKFILL: "
                       f"{backfill_nfl_prop_odds(dates, limit_events=args.limit_events, markets=args.markets)}")
    else:
        run_nfl_prop_odds_ingestor(args.days_ahead)
