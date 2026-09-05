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
import math
import json
from collections import Counter
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import config
from config import (
    ODDS_API_KEY, ODDS_API_BASE, ODDS_API_REGIONS, ODDS_API_BOOKMAKER,
    ODDS_API_BOOKMAKERS_PARAM, PROP_MARKETS_NFL, PROP_ALT_MARKETS, NFL_ODDS_API_MAP,
)
from data.db import get_connection, DBConnection
from data import local_store
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

# The market-relative rule (models/nfl_prop_market) needs a market maker, and
# Pinnacle is served in the `eu` region while the platform's ODDS_API_REGIONS is
# `us` for every other sport. Widening the global would change MLB/NBA/NHL
# fetches too, so NFL props carry their own pair and nothing else sees it.
#
# On cost: the API counts an explicit `bookmakers` list as ONE region (the same
# finding that made line-shopping free in docs/config_topology.md), so naming the region as
# well is expected to be free rather than double. Expected, not assumed — every
# run reports its own `credits` from the response headers, so if that is wrong
# the first live pull says so instead of quietly billing twice.
ANY_BOOK = "*"          # census sentinel: send no bookmakers param

# The pre-game series every consumer means when it says "the line". Timing
# experiments are written under their own labels precisely so they cannot
# displace it — and then no loader enforced that, so a t24 row (stamped a day
# earlier) could win "latest snapshot" over the open row and silently put a
# different price in front of the card AND the backtest. Measured: it moved 435
# of the card's selections.
PREGAME_SNAPSHOT_TYPES = ("open",)
MARKET_REGIONS = "us,eu"
MARKET_BOOKS = f"{ODDS_API_BOOKMAKERS_PARAM},pinnacle"


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


def _market_chunks(markets: list[str]) -> list[list[str]]:
    """Standard markets first, alternates after, never mixed in one chunk."""
    standard = [m for m in markets if not m.endswith("_alternate")]
    alternates = [m for m in markets if m.endswith("_alternate")]
    out: list[list[str]] = []
    for group in (standard, alternates):
        out.extend(group[i:i + MARKET_CHUNK] for i in range(0, len(group), MARKET_CHUNK))
    return out


def _event_props(event_id: str, markets: list[str],
                 snapshot_iso: str | None = None,
                 regions: str | None = None,
                 books: str | None = None) -> tuple[list[tuple[str, list]], str | None, int]:
    """
    ([(bookmaker, markets)], snapshot timestamp, credits used) for one event.

    Markets are requested in chunks so one unsupported market cannot 422 the
    whole basket. A 422 on a chunk is logged and skipped — the remaining chunks
    still land, which is the difference between losing one market and losing the
    event. Alternate-line markets (`*_alternate`, config.PROP_ALT_MARKETS) are
    chunked SEPARATELY from the standard ones, so a rejected alternate key can
    cost its own chunk and never a standard market the models price off.
    """
    base = f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events/{event_id}/odds"
    if snapshot_iso:
        base = f"{ODDS_API_BASE}/historical/sports/{SPORT_KEY}/events/{event_id}/odds"

    per_book: dict[str, list] = {}
    stamp = None
    used_before = used_after = None

    for chunk in _market_chunks(markets):
        params = {
            "apiKey": ODDS_API_KEY, "regions": regions or ODDS_API_REGIONS,
            "markets": ",".join(chunk),
            "bookmakers": books or ODDS_API_BOOKMAKERS_PARAM,
            "oddsFormat": "american", "dateFormat": "iso",
            "includeLinks": "true", "includeSids": "true",
        }
        # ANY_BOOK drops the param entirely; the regions then govern and the
        # response carries every book the API has for them. Census only.
        if params["bookmakers"] == ANY_BOOK:
            params.pop("bookmakers")
        if snapshot_iso:
            params["date"] = snapshot_iso
        resp = _get(base, params)
        if used_before is None:
            u = _credits_used(resp)
            used_before = u - 1 if u is not None else None
        used_after = _credits_used(resp) or used_after

        if resp.status_code == 422:
            # Unsupported market OR unsupported book — retry DK-only so a
            # renamed display book can never cost the prices we score against.
            #
            # Only when DK was actually asked for. A targeted backfill that
            # requests one other book means "add what is missing"; substituting
            # DK there would re-fetch rows the table already has, and the
            # inserter appends without dedup, so it would silently duplicate
            # them.
            dk_requested = ODDS_API_BOOKMAKER in params.get("bookmakers", "").split(",")
            if dk_requested and params["bookmakers"] != ODDS_API_BOOKMAKER:
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
                   markets: list[str] | None = None,
                   regions: str | None = None,
                   books: str | None = None) -> dict:
    rows_total = skipped = credits = 0
    by_book: Counter = Counter()
    for ev in events:
        resolved = resolve_nfl_game_id(games, ev.get("home_team", ""),
                                       ev.get("away_team", ""), ev.get("commence_time", ""))
        if resolved is None:
            skipped += 1
            logger.debug(f"  unresolved event: {ev.get('away_team')} @ {ev.get('home_team')}")
            continue
        game_id, game_date = resolved

        # The live slate carries the alternate lines (Matt, 2026-09-05); a
        # backfill or probe that names its markets gets exactly those.
        want = list(markets) if markets else list(PROP_MARKETS_NFL) + list(PROP_ALT_MARKETS.get("NFL", []))
        per_book, served_stamp, used = _event_props(ev["id"], want, snapshot_iso,
                                                    regions=regions, books=books)
        credits += used
        # the line's own timestamp, never the run's — see module docstring
        stamp = served_stamp or snapshot_iso or datetime.now(timezone.utc).isoformat()

        rows = []
        # NOT `markets` — that is this function's parameter, and shadowing it
        # here left the next event asking the API for a list of dicts.
        for book_key, book_markets in per_book:
            got = _parse_prop_markets(
                book_markets, game_id=game_id, game_date=game_date,
                snapshot_type=snapshot_type, snapshot_at=stamp,
                allowed_markets=want, bookmaker=book_key)
            rows.extend(got)
            # Which books actually answered, per market. A book that is asked
            # for and never returns is indistinguishable from one that returned
            # nothing useful unless it is counted here, and "does Pinnacle serve
            # NFL player props" is exactly that question.
            for r in got:
                by_book[(book_key, r["market"])] += 1
        if rows:
            rows_total += _insert_prop_odds(conn, rows)
            conn.commit()
    books_seen = {}
    for (bk, mkt), n in sorted(by_book.items()):
        books_seen.setdefault(bk, {})[mkt] = n
    return {"rows": rows_total, "events": len(events) - skipped,
            "skipped": skipped, "credits": credits, "books": books_seen}


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
        got = _ingest_events(conn, events, games, None, "open",
                             regions=MARKET_REGIONS, books=MARKET_BOOKS)
        logger.success(f"NFL prop odds: {got}")
        return got
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()


def backfill_nfl_prop_odds(dates: list[str], hours_before: int = 3,
                           limit_events: int | None = None,
                           markets: list[str] | None = None,
                           snapshot_type: str = "open") -> dict:
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
            # Kickoffs are UTC; a 13:00 ET Sunday game is 17:00 UTC, so the
            # early window is anchored there and the offset counted back from
            # it. Computed as a real datetime, not 17 - hours_before: past 17
            # that formats a negative hour, so every offset of a day or more
            # would have asked the API for a malformed timestamp.
            anchor = datetime.fromisoformat(f"{d}T17:00:00+00:00")
            snap = (anchor - timedelta(hours=hours_before)).strftime("%Y-%m-%dT%H:%M:%SZ")
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
            got = _ingest_events(conn, events, games, served or snap, snapshot_type, markets)
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


def census_books(date: str, limit_events: int = 2,
                 regions: str = "us,us2,eu,uk,au",
                 markets: list[str] | None = None,
                 hours_before: int = 3) -> dict:
    """
    WHICH books serve which NFL prop markets. Read-only — writes nothing.

    Deliberately not a variant of the probe. The probe INSERTS, and the prop
    odds inserter is append-only with no dedup, so discovering books by
    backfilling them would leave rows for books we have not decided to keep and
    would duplicate the ones we already have. A census answers "what is out
    there" without committing to any of it.

    No `bookmakers` param at all (ANY_BOOK), so the regions govern and the
    response carries every book the API has for them. That costs a credit
    multiple per region, which is why this runs on two events, not a season.
    """
    _require_key()
    want = list(markets or PROP_MARKETS_NFL)
    anchor = datetime.fromisoformat(f"{date}T17:00:00+00:00")
    snap = (anchor - timedelta(hours=hours_before)).strftime("%Y-%m-%dT%H:%M:%SZ")

    events, served = list_historical_events(snap)
    if not events:
        logger.warning(f"census {date}: no historical events at {snap}")
        return {}
    events = events[:limit_events]

    grid: dict[str, Counter] = {}
    credits = 0
    for ev in events:
        per_book, _stamp, used = _event_props(ev["id"], want, served or snap,
                                              regions=regions, books=ANY_BOOK)
        credits += used
        for book_key, book_markets in per_book:
            for m in book_markets:
                key = m.get("key", "")
                if key in want:
                    # count OUTCOMES, not markets: a book listing a market with
                    # two players is not the same coverage as one listing forty,
                    # and coverage is the whole question.
                    grid.setdefault(book_key, Counter())[key] += len(m.get("outcomes", []))

    logger.success(f"CENSUS {date}: {len(grid)} books over {len(events)} events, "
                   f"{credits} credits")
    # Plain print, not logger: every loguru line carries ~90 characters of
    # timestamp/module prefix, and the runner's annotation is length-capped —
    # the first census lost the top of the table to exactly that.
    print(f"{'book':<22}" + "".join(f"{m.replace('player_', '')[:9]:>10}" for m in want)
          + f"{'TOTAL':>8}")
    for bk in sorted(grid, key=lambda b: -sum(grid[b].values())):
        print(f"{bk:<22}" + "".join(f"{grid[bk].get(m, 0):>10}" for m in want)
              + f"{sum(grid[bk].values()):>8}")
    # Written to disk, not just logged. A runner's step log is ephemeral and
    # its annotations are length-capped, so a census read only from the log
    # costs a fresh API spend every time someone wants the numbers again.
    out = {"date": date, "events": len(events), "regions": regions,
           "credits": credits, "markets": want,
           "books": {b: dict(c) for b, c in grid.items()}}
    path = Path("data/local/book_census.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, sort_keys=True))
    logger.success(f"wrote {path}")
    return out


def _p(v):
    """NaN -> None.

    SQL returns None for a missing price; parquet returns NaN, and
    `NaN is not None`. Callers gate on `price is None`, so an unnormalised NaN
    makes a one-way market look two-sided — anytime-TD has no under price, and
    the cached path took 5,915 phantom under bets at a nan price before this
    existed.
    """
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def _odds_from_frame(df, game_ids, markets, bookmaker, before,
                     snapshot_types=PREGAME_SNAPSHOT_TYPES) -> dict:
    """
    The local-cache path of `load_nfl_prop_odds`, with identical semantics.

    Same filters, and the same "latest qualifying snapshot per (game, player,
    market) wins" rule the SQL gets from ORDER BY snapshot_at ASC — here a
    stable sort plus last-write. If these two ever disagree the backtest and the
    live scorer are grading different lines, so the ordering is not incidental.
    """
    d = df[df["game_id"].isin(set(game_ids)) & (df["bookmaker"] == bookmaker)]
    if snapshot_types and "snapshot_type" in d.columns:
        d = d[d["snapshot_type"].isin(set(snapshot_types))]
    if markets:
        d = d[d["market"].isin(set(markets))]
    if before is not None:
        d = d[d["snapshot_at"].astype(str) < str(before)]
    if d.empty:
        return {}
    d = d.sort_values("snapshot_at", kind="stable")

    out: dict = {}
    for r in d.itertuples(index=False):
        out[(r.game_id, norm_player_name(r.player_name), r.market)] = {
            "line": _p(r.line), "over_price": _p(r.over_price),
            "under_price": _p(r.under_price),
            "over_link": None, "under_link": None, "snapshot_at": r.snapshot_at,
            "bookmaker": r.bookmaker, "player_name": r.player_name,
        }
    return out


def load_nfl_prop_odds(conn: DBConnection, game_ids: list[str],
                       markets: list[str] | None = None,
                       bookmaker: str = ODDS_API_BOOKMAKER,
                       before: str | None = None,
                       snapshot_types: tuple[str, ...] = PREGAME_SNAPSHOT_TYPES) -> dict:
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
    cached = local_store.read_table("nfl_prop_odds")
    if cached is not None:
        return _odds_from_frame(cached, game_ids, markets, bookmaker, before,
                                snapshot_types)
    sql = """
        SELECT game_id, player_name, market, line, over_price, under_price,
               over_link, under_link, snapshot_at, bookmaker
        FROM player_prop_odds
        WHERE game_id = ANY(%s) AND bookmaker = %s
    """
    params: list = [list(game_ids), bookmaker]
    if snapshot_types:
        sql += " AND snapshot_type = ANY(%s)"
        params.append(list(snapshot_types))
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
    ap.add_argument("--hours-before", type=int, default=3,
                    help="snapshot this many hours before the 17:00 UTC anchor")
    ap.add_argument("--snapshot-type", default="open",
                    help="label for these rows; use a distinct one for a timing "
                         "experiment so it cannot displace the 'open' series")
    ap.add_argument("--census", metavar="DATE",
                    help="read-only: which books serve which prop markets. "
                         "Writes nothing.")
    ap.add_argument("--regions", default=None,
                    help="override the region list (census / live)")
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

    if args.census:
        census_books(args.census, limit_events=args.limit_events or 2,
                     regions=args.regions or "us,us2,eu,uk,au",
                     markets=args.markets, hours_before=args.hours_before)
    elif args.probe:
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
        logger.info(f"Backfilling {len(dates)} NFL game dates "
                    f"at T-{args.hours_before}h as '{args.snapshot_type}'")
        got = backfill_nfl_prop_odds(dates, hours_before=args.hours_before,
                                     limit_events=args.limit_events,
                                     markets=args.markets,
                                     snapshot_type=args.snapshot_type)
        logger.success(f"BACKFILL: {got}")
    else:
        run_nfl_prop_odds_ingestor(args.days_ahead)


def load_nfl_prop_quotes(conn: DBConnection, game_ids: list[str],
                         markets: list[str] | None = None,
                         books: tuple[str, ...] | None = None,
                         before: str | None = None,
                         snapshot_types: tuple[str, ...] = PREGAME_SNAPSHOT_TYPES) -> dict:
    """
    Multi-book board: {(game_id, norm_name, market, book): {line, over_price, ...}}.

    This is what the market-relative rule consumes (models/nfl_prop_market), and
    it is deliberately a different function from `load_nfl_prop_odds` rather than
    a flag on it. The projection path prices against ONE book and must keep doing
    so; this one keeps every book's own row, because which book is sharp and
    which is soft is the entire question and collapsing them would answer it by
    accident.

    Same "latest qualifying snapshot wins" rule as the single-book loader, now
    per (game, player, market, BOOK) — one book going quiet must not let another
    book's older row stand in for it.
    """
    if not game_ids:
        return {}
    cached = local_store.read_table("nfl_prop_odds")
    if cached is not None:
        d = cached[cached["game_id"].isin(set(game_ids))]
        if snapshot_types and "snapshot_type" in d.columns:
            d = d[d["snapshot_type"].isin(set(snapshot_types))]
        if markets:
            d = d[d["market"].isin(set(markets))]
        if books:
            d = d[d["bookmaker"].isin(set(books))]
        if before is not None:
            d = d[d["snapshot_at"].astype(str) < str(before)]
        if d.empty:
            return {}
        out: dict = {}
        for r in d.sort_values("snapshot_at", kind="stable").itertuples(index=False):
            out[(r.game_id, norm_player_name(r.player_name), r.market, r.bookmaker)] = {
                "line": _p(r.line), "over_price": _p(r.over_price),
                "under_price": _p(r.under_price), "over_link": None,
                "under_link": None, "snapshot_at": r.snapshot_at,
                "bookmaker": r.bookmaker, "player_name": r.player_name,
            }
        return out

    sql = """
        SELECT game_id, player_name, market, line, over_price, under_price,
               over_link, under_link, snapshot_at, bookmaker
        FROM player_prop_odds
        WHERE game_id = ANY(%s)
    """
    params: list = [list(game_ids)]
    if snapshot_types:
        sql += " AND snapshot_type = ANY(%s)"
        params.append(list(snapshot_types))
    if markets:
        sql += " AND market = ANY(%s)"
        params.append(list(markets))
    if books:
        sql += " AND bookmaker = ANY(%s)"
        params.append(list(books))
    if before:
        sql += " AND snapshot_at < %s"
        params.append(before)
    sql += " ORDER BY snapshot_at ASC"

    out = {}
    for r in conn.execute(sql, tuple(params)).fetchall():
        out[(r[0], norm_player_name(r[1]), r[2], r[9])] = {
            "line": r[3], "over_price": r[4], "under_price": r[5],
            "over_link": r[6], "under_link": r[7], "snapshot_at": r[8],
            "bookmaker": r[9], "player_name": r[1],
        }
    return out
