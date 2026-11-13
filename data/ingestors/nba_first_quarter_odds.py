"""Live NBA first-quarter spreads and moneylines: one per-event Odds API call per game, stored before anything is
decided on it (`nba_q1_trend`, models/nba_q1_trend.py, and `nba_q1_trend_ml`, models/nba_q1_trend_ml.py).

WHY A FETCH OF ITS OWN. Nothing stores first-quarter spreads live: the bulk odds endpoint never returns them and the
refresh pass has no first-quarter branch. It is its own call, not one more market on another model's, for the reason
data/ingestors/nba_first_half_odds.py gives: each model's decision stays its own, and a request refused because of one
market cannot refuse the other. The per-event endpoint bills per market returned, so one market costs at most one
credit a call (the regions are one, the bookmakers parameter counting as a region).

ONE CALL FOR BOTH FIRST-QUARTER MODELS (2026-11-07). The moneyline model bets the spread model's own signal, and
the graded bets of both were decided on ONE per-game purchase holding both markets. So the moneyline rides on this
call (markets=spreads_q1,h2h_q1) rather than a call of its own: both models decide on the same fetch instant, as
graded. Measured before it shipped: the two-market call answered 200 with both markets (docs/sports/nba.md). The
per-event endpoint bills per market returned, so a call costs at most two credits.

WHAT ONE CALL STORES. One game, markets=spreads_q1,h2h_q1, every line-shop book and Pinnacle (_get_event_odds' own
parameters):
  * each book's MAIN number (models/nba_book_numbers.split_main_rungs: coherent first, prices closest to even, ties
    to the lower number) under spreads_q1, keyed on the HOME number (CLAUDE.md section 4: the home outcome at point p
    and the away outcome at -p are one pair), and any other rung under spreads_q1_alternate;
  * each book's first-quarter moneyline under h2h_q1: one pair a book, home_price / away_price, no number and no
    ladder, so it never goes through the main-rung splitter;
  * snapshot_type 'open' for a decision fetch, 'close' for the closing snapshot; snapshot_at = the market's own
    last_update (else the book's, else the fetch time); created_at = the fetch instant; source = SOURCE.
The event's own team names orient the pair: the feed's home team is the game id's home team (event_ids builds the id
from the event's home and away teams), so the home outcome is the home number.

THE LEDGER (nba_first_quarter_fetches, worker-only): the first-half ledger's columns, one row per call. The card
decides on the newest ok 'open' row: a 200 with no first-quarter spread is still a fetch (the game is decided with
nothing offered); a failed call is not, and the next tick tries again.

    python -m scripts.nba_q1_trend_window --fetch GAME_ID ...   # a decision fetch
    python -m scripts.nba_q1_trend_window --close GAME_ID ...   # the closing snapshot
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from loguru import logger

from config import LINE_SHOP_BOOKMAKERS
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.ingestors import odds_quota
from data.ingestors.nba_odds_history import _ODDS_KEYS
from data.ingestors.nba_team_total_odds import (EVENT_ODDS, EVENTS, SNAPSHOT_TYPES, SPORT, SPORT_KEY, _when, _z,
                                                event_ids)
from data.ingestors.odds_ingestor import _get_event_odds, _insert_odds, _list_events
from data.ingestors.odds_quota import persist_quota
from models.nba_book_numbers import split_main_rungs
from models.nba_q1_trend import LIVE_SOURCE

API_MARKET = "spreads_q1"
ML_MARKET = "h2h_q1"
# The markets one call asks for: the spread model's and the moneyline model's.
API_MARKETS = (API_MARKET, ML_MARKET)
# The marker on every row this feed writes. Never the purchase's (odds_api_nba_derivative_history).
SOURCE = LIVE_SOURCE
# Pinnacle is read for the game's number and the market's fair line, never bet.
READ_BOOKS = tuple(dict.fromkeys((*LINE_SHOP_BOOKMAKERS, "pinnacle")))

# ── the ledger ───────────────────────────────────────────────────────────────
LEDGER_TABLE = "nba_first_quarter_fetches"
LEDGER_COLS = ("requested_at", "fetch_at", "endpoint", "snapshot_type", "game_id", "event_id",
               "ok", "rows_stored", "main_rows", "books", "book_ages", "credits_last", "detail")
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS nba_first_quarter_fetches (
    requested_at  TIMESTAMPTZ NOT NULL,
    fetch_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    endpoint      TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,
    game_id       TEXT,
    event_id      TEXT,
    ok            BOOLEAN NOT NULL,
    rows_stored   INTEGER NOT NULL DEFAULT 0,
    main_rows     INTEGER NOT NULL DEFAULT 0,
    books         TEXT,
    book_ages     TEXT,
    credits_last  REAL,
    detail        TEXT
)
"""
_INSERT_LEDGER = (
    "INSERT INTO nba_first_quarter_fetches (requested_at, endpoint, snapshot_type, game_id, "
    "event_id, ok, rows_stored, main_rows, books, book_ages, credits_last, detail) VALUES "
    "(%(requested_at)s, %(endpoint)s, %(snapshot_type)s, %(game_id)s, %(event_id)s, %(ok)s, "
    "%(rows_stored)s, %(main_rows)s, %(books)s, %(book_ages)s, %(credits_last)s, %(detail)s)")


def ensure_ledger(conn) -> None:
    if schema_is_current(conn, LEDGER_TABLE, columns=LEDGER_COLS, rls=True, revoked_from=API_ROLES):
        return
    conn.execute(LEDGER_DDL)
    lock_down(conn, LEDGER_TABLE)
    conn.commit()


def ledger_exists(conn) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s",
        (LEDGER_TABLE,)).fetchone())


def _ledger_row(conn, requested_at: datetime, endpoint: str, snapshot_type: str, *,
                game_id: str | None = None, event_id: str | None = None, ok: bool,
                rows_stored: int = 0, main_rows: int = 0, books=(), ages: dict | None = None,
                credits: float | None = None, detail: str | None = None) -> None:
    conn.execute(_INSERT_LEDGER, {
        "requested_at": requested_at, "endpoint": endpoint, "snapshot_type": snapshot_type,
        "game_id": game_id, "event_id": event_id, "ok": ok, "rows_stored": rows_stored,
        "main_rows": main_rows, "books": ",".join(sorted(books)) or None,
        "book_ages": json.dumps(ages, sort_keys=True) if ages else None,
        "credits_last": credits, "detail": (detail or None) and detail[:500]})


def fetches(conn, game_ids: list[str], snapshot_type: str, now: datetime | None = None) -> dict[str, datetime]:
    """Each game's newest ok event call of this type (at or before `now` when given): the ledger's fetch_at, which
    is the stored rows' created_at. Reads only."""
    if not game_ids or not ledger_exists(conn):
        return {}
    bound, params = "", [list(game_ids), EVENT_ODDS, snapshot_type]
    if now is not None:
        bound = "AND fetch_at <= %s"
        params.append(now)
    rows = conn.execute(f"""
        SELECT game_id, MAX(fetch_at) FROM {LEDGER_TABLE}
        WHERE game_id = ANY(%s) AND endpoint = %s AND snapshot_type = %s AND ok {bound}
        GROUP BY game_id
    """, tuple(params)).fetchall()
    out = {}
    for gid, ts in rows:
        t = _when(ts) if not isinstance(ts, datetime) else ts
        if t is not None:
            out[gid] = t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    return out


def closes_taken(conn, game_ids: list[str]) -> set[str]:
    return set(fetches(conn, game_ids, "close"))


# ── parsing ──────────────────────────────────────────────────────────────────

def parse_first_quarter(book_markets: list[dict], home_name: str, away_name: str) -> list[dict]:
    """One book's markets -> one odds-row dict per first-quarter spread number, keyed on the HOME number: the home
    outcome at point p and the away outcome at -p are one pair (data/ingestors/ncaab_first_half_odds.parse_book's
    spread rule). A one-sided rung is kept and split_main_rungs files it as an alternate."""
    slots: dict[float, dict] = {}
    for m in book_markets:
        if m.get("key") != API_MARKET:
            continue
        for o in m.get("outcomes") or []:
            name, pt = o.get("name") or "", o.get("point")
            if pt is None:
                continue
            if name == home_name:
                s = slots.setdefault(float(pt), {})
                s.update(home_price=o.get("price"), home_link=o.get("link"), home_sid=o.get("sid"))
            elif name == away_name:
                s = slots.setdefault(-float(pt), {})
                s.update(away_price=o.get("price"), away_link=o.get("link"), away_sid=o.get("sid"))
    return [{"market": API_MARKET, "spread_home": pt, **s} for pt, s in slots.items()]


def parse_first_quarter_ml(book_markets: list[dict], home_name: str, away_name: str) -> list[dict]:
    """One book's markets -> its first-quarter moneyline as one odds-row dict (market h2h_q1, home_price /
    away_price), or nothing. Oriented by the event's own team names, as the spread is. A one-sided quote is kept;
    the readers drop a quote without both prices (scripts.nba_game_harness.frame_quotes)."""
    out: dict = {}
    for m in book_markets:
        if m.get("key") != ML_MARKET:
            continue
        for o in m.get("outcomes") or []:
            name = o.get("name") or ""
            if name == home_name:
                out.update(home_price=o.get("price"), home_link=o.get("link"), home_sid=o.get("sid"))
            elif name == away_name:
                out.update(away_price=o.get("price"), away_link=o.get("link"), away_sid=o.get("sid"))
    return [{"market": ML_MARKET, **out}] if out else []


def event_rows(body: dict | None, game_id: str, snapshot_type: str, fetched_at: datetime
               ) -> tuple[list[dict], list[dict], dict[str, float]]:
    """One event response -> (main rows, alternate rows, {book: minutes from its first-quarter spread's
    last_update, else its moneyline's, to the fetch}). The line-shop books and Pinnacle. Every row carries every
    odds column. The spreads go through the main-rung splitter; each book's one moneyline pair is a main row."""
    body = body or {}
    home_name, away_name = body.get("home_team") or "", body.get("away_team") or ""
    rows: list[dict] = []
    ml_rows: list[dict] = []
    ages: dict[str, float] = {}

    def stamp_of(markets, market, book):
        return (next((m.get("last_update") for m in markets
                      if m.get("key") == market and m.get("last_update")), None)
                or book.get("last_update") or _z(fetched_at))

    for book in body.get("bookmakers") or []:
        key = book.get("key")
        if key not in READ_BOOKS:
            continue
        markets = book.get("markets") or []
        age_stamp = None
        for market, parsed, into in ((API_MARKET, parse_first_quarter(markets, home_name, away_name), rows),
                                     (ML_MARKET, parse_first_quarter_ml(markets, home_name, away_name), ml_rows)):
            if not parsed:
                continue
            stamp = stamp_of(markets, market, book)
            age_stamp = age_stamp or stamp
            for p in parsed:
                row = dict.fromkeys(_ODDS_KEYS)
                row.update(p)
                row.update({"game_id": game_id, "sport": SPORT, "bookmaker": key,
                            "snapshot_type": snapshot_type, "snapshot_at": stamp, "source": SOURCE})
                into.append(row)
        t = _when(age_stamp) if age_stamp else None
        if t is not None:
            ages[key] = round((fetched_at - t).total_seconds() / 60.0, 1)
    main, alt = split_main_rungs(rows) if rows else ([], [])
    return main + ml_rows, alt, ages


# ── the fetch ────────────────────────────────────────────────────────────────

def _billed(before: dict | None) -> float | None:
    after = odds_quota.latest()
    if after is None or after is before:
        return None
    return after.get("last")


def _known_games(conn, game_ids: list[str]) -> dict[str, dict]:
    rows = conn.execute(
        "SELECT game_id, home_team, away_team FROM games WHERE sport = %s AND game_id = ANY(%s)",
        (SPORT, list(game_ids))).fetchall()
    return {gid: {"home": home, "away": away} for gid, home, away in rows}


def fetch_first_quarter(game_ids, snapshot_type: str = "open", conn=None) -> dict:
    """Fetch and store the first-quarter spreads of exactly `game_ids` (one event call each, the ledger written beside
    every call). -> a summary; `failed` names the games whose call failed (the window turns it into exit 1)."""
    if snapshot_type not in SNAPSHOT_TYPES:
        raise ValueError(f"snapshot_type {snapshot_type!r}: one of {SNAPSHOT_TYPES}")
    ids = sorted(set(game_ids))
    out = {"snapshot_type": snapshot_type, "asked": ids, "not_in_games": [], "fetched": [],
           "rows": 0, "main_rows": 0, "no_first_quarter": [], "failed": [], "credits": {}}
    own = conn is None
    if own:
        from data.db import get_connection
        conn = get_connection()
    try:
        if not ids:
            return out
        ensure_ledger(conn)
        games = _known_games(conn, ids)
        conn.rollback()          # no transaction across a call: created_at must be the fetch instant
        out["not_in_games"] = [g for g in ids if g not in games]
        if out["not_in_games"]:
            logger.warning(f"NBA first-quarter spreads: not in games, not fetched: {out['not_in_games']}")
        if not games:
            return out
        asked = datetime.now(timezone.utc)
        before = odds_quota.latest()
        try:
            events, why = _list_events(SPORT_KEY), None
        except Exception as exc:  # noqa: BLE001 - recorded, and every game fails below
            events, why = [], f"event list failed: {exc!r}"
        credits = _billed(before)
        out["credits"]["events"] = credits
        _ledger_row(conn, asked, EVENTS, snapshot_type, ok=why is None, rows_stored=len(events),
                    credits=credits, detail=why or f"{len(events)} events listed")
        conn.commit()
        by_game = event_ids(events, games)
        for gid in sorted(games):
            ev = by_game.get(gid)
            asked = datetime.now(timezone.utc)
            if ev is None:
                _ledger_row(conn, asked, EVENT_ODDS, snapshot_type, game_id=gid, ok=False,
                            detail=why or "not in the feed's event list")
                conn.commit()
                out["failed"].append(gid)
                logger.error(f"NBA first-quarter spreads: {gid}: {why or 'not in the event list'}; nothing bought")
                continue
            before = odds_quota.latest()
            try:
                body = _get_event_odds(SPORT_KEY, ev, list(API_MARKETS))
            except Exception as exc:  # noqa: BLE001 - one game's failure is its own
                credits = _billed(before)
                _ledger_row(conn, asked, EVENT_ODDS, snapshot_type, game_id=gid, event_id=ev, ok=False,
                            credits=credits, detail=f"call failed: {exc!r}")
                conn.commit()
                out["failed"].append(gid)
                out["credits"][gid] = credits
                logger.error(f"NBA first-quarter spreads: {gid}: call failed: {exc!r}")
                continue
            credits = _billed(before)
            out["credits"][gid] = credits
            if body is None:
                _ledger_row(conn, asked, EVENT_ODDS, snapshot_type, game_id=gid, event_id=ev, ok=False,
                            credits=credits, detail="HTTP 404 or 422: no body")
                conn.commit()
                out["failed"].append(gid)
                logger.error(f"NBA first-quarter spreads: {gid}: HTTP 404 or 422 for event {ev}")
                continue
            main, alt, ages = event_rows(body, gid, snapshot_type, datetime.now(timezone.utc))
            rows = main + alt
            books = {r["bookmaker"] for r in rows}
            try:
                if rows:
                    _insert_odds(conn, rows)
                _ledger_row(conn, asked, EVENT_ODDS, snapshot_type, game_id=gid, event_id=ev, ok=True,
                            rows_stored=len(rows), main_rows=len(main), books=books, ages=ages, credits=credits)
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                _ledger_row(conn, asked, EVENT_ODDS, snapshot_type, game_id=gid, event_id=ev, ok=False,
                            credits=credits, detail=f"store failed: {exc!r}")
                conn.commit()
                out["failed"].append(gid)
                logger.error(f"NBA first-quarter spreads: {gid}: store failed: {exc!r}")
                continue
            out["fetched"].append(gid)
            out["rows"] += len(rows)
            out["main_rows"] += len(main)
            if not main:
                out["no_first_quarter"].append(gid)
            logger.info(f"  {gid}: {snapshot_type} first-quarter spreads, {len(main)} main + {len(alt)} alternate "
                        f"rows, {len(books)} books, x-requests-last {credits}, book ages (min) {ages}")
        return out
    finally:
        try:
            persist_quota(conn)
        finally:
            if own:
                conn.close()
