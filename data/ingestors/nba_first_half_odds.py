"""Live NBA first-half totals: one per-event Odds API call per game, stored before
anything is decided on it (`nba_first_half_total_luck`,
models/nba_first_half_total_luck.py).

WHY A FETCH OF ITS OWN. Nothing stored first-half lines for 2026-27 before this
model: the bulk odds endpoint never returns them, the refresh pass has no
first-half branch, and the history purchase is history. And it is its OWN call,
not one more market on the team-total call (data/ingestors/nba_team_total_odds.py),
so each model's decision stays its own: a request refused because of one market
would otherwise refuse the other, a 200 with no first-half total must not read
as a team-total fetch that came back empty (or the reverse), and each model's
retry buys only its own market. The per-event endpoint bills per market returned
(odds_ingestor._get_event_odds, measured 2026-09-03), so one call for two markets
and two calls for one each are billed alike.

WHAT ONE CALL STORES. One game, markets=totals_h1, the configured regions and
books, links and sids on (_get_event_odds' own parameters):
  * each book's MAIN number (models/nba_book_numbers.split_main_rungs: coherent
    first, prices closest to even, ties to the lower number) under totals_h1, and
    any other rung under totals_h1_alternate. Every reader of one row per (game,
    market, book) -- the latest_odds trigger, the app's other-books prices,
    closing-line value -- then lands on the main number. The history purchase
    held exactly one rung per (game, book, market) on all 25,917 of its rows,
    because its parser keeps one pair (nba_odds_history.parse_derivatives), so a
    live ladder, if a book hangs one, is measured here for the first time:
    rows_stored minus main_rows in the ledger.
  * snapshot_type 'open' for a decision fetch, 'close' for the closing snapshot;
    snapshot_at = the market's own last_update (else the book's, else the fetch
    time), the live `odds` convention; created_at = the fetch instant, as the
    team-total feed explains; source = SOURCE.
Only games already in `games` are fetched (odds has a foreign key to it), and
only the ids the caller names: the event list is matched to them BEFORE any paid
call, so a tick never buys a game it did not plan.

SOURCE IS NEVER THE PURCHASE'S MARKER (nba_team_total_odds.py says why), and the
odds prune protects it (data/prune_odds.PROTECTED_SOURCES).

THE LEDGER (nba_first_half_total_fetches, worker-only): the team-total ledger's
columns, one row per call. The card decides on the newest ok 'open' row: a call
that came back (HTTP 200) with no first-half total is still a fetch (the game is
decided with nothing offered, as the lab's one purchase a game was); a failed
call is not, an HTTP 404 or 422 included, and the next tick tries again.

COST is read, never assumed: credits_last is the feed's own x-requests-last for
that call (data/ingestors/odds_quota.latest). No live first-half call had been
made before this model, so the first rows are the measurement.

    python -m scripts.nba_first_half_total_luck_window --fetch GAME_ID ...   # a decision fetch
    python -m scripts.nba_first_half_total_luck_window --close GAME_ID ...   # the closing snapshot
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
from data.ingestors.nba_team_total_odds import (EVENT_ODDS, EVENTS, SNAPSHOT_TYPES, SPORT,
                                                SPORT_KEY, _when, _z, event_ids)
from data.ingestors.odds_ingestor import _get_event_odds, _insert_odds, _list_events
from data.ingestors.odds_quota import persist_quota
from models.nba_book_numbers import split_main_rungs

API_MARKET = "totals_h1"
# The marker on every row this feed writes. Not the purchase's prefix.
SOURCE = "odds_api_nba_first_half_live"

# ── the ledger ───────────────────────────────────────────────────────────────
LEDGER_TABLE = "nba_first_half_total_fetches"
LEDGER_COLS = ("requested_at", "fetch_at", "endpoint", "snapshot_type", "game_id", "event_id",
               "ok", "rows_stored", "main_rows", "books", "book_ages", "credits_last", "detail")
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS nba_first_half_total_fetches (
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
    "INSERT INTO nba_first_half_total_fetches (requested_at, endpoint, snapshot_type, game_id, "
    "event_id, ok, rows_stored, main_rows, books, book_ages, credits_last, detail) VALUES "
    "(%(requested_at)s, %(endpoint)s, %(snapshot_type)s, %(game_id)s, %(event_id)s, %(ok)s, "
    "%(rows_stored)s, %(main_rows)s, %(books)s, %(book_ages)s, %(credits_last)s, %(detail)s)")


def ensure_ledger(conn) -> None:
    """Create the ledger once, locked down, and cost nothing after that. Only
    the fetch calls it: the plan and the card read, and never create."""
    if schema_is_current(conn, LEDGER_TABLE, columns=LEDGER_COLS,
                         rls=True, revoked_from=API_ROLES):
        return
    conn.execute(LEDGER_DDL)
    lock_down(conn, LEDGER_TABLE)
    conn.commit()


def ledger_exists(conn) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' "
        "AND table_name = %s", (LEDGER_TABLE,)).fetchone())


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


def fetches(conn, game_ids: list[str], snapshot_type: str,
            now: datetime | None = None) -> dict[str, datetime]:
    """Each game's newest ok event call of this type (at or before `now` when
    given): the ledger's fetch_at, which is the stored rows' created_at. Reads
    only: no ledger yet, no fetch."""
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
    """Games whose closing snapshot has been fetched (an ok 'close' call, a
    first-half total offered or not). Reads only."""
    return set(fetches(conn, game_ids, "close"))


# ── parsing ──────────────────────────────────────────────────────────────────

def parse_first_half(book_markets: list[dict]) -> list[dict]:
    """One book's markets -> one odds-row dict per first-half line: total_line,
    the over and under prices, links and sids. A pair with no number is dropped;
    a one-sided rung is kept and split_main_rungs files it as an alternate."""
    slots: dict[float, dict] = {}
    for m in book_markets:
        if m.get("key") != API_MARKET:
            continue
        for o in m.get("outcomes") or []:
            name, desc = (o.get("name") or ""), (o.get("description") or "")
            side = name if name.lower() in ("over", "under") else desc
            if side.lower() not in ("over", "under") or o.get("point") is None:
                continue
            slot = slots.setdefault(float(o["point"]), {})
            which = side.lower()
            slot[which + "_price"] = o.get("price")
            slot[which + "_link"] = o.get("link")
            slot[which + "_sid"] = o.get("sid")
    return [{"market": API_MARKET, "total_line": pt,
             "over_price": s.get("over_price"), "under_price": s.get("under_price"),
             "over_link": s.get("over_link"), "under_link": s.get("under_link"),
             "over_sid": s.get("over_sid"), "under_sid": s.get("under_sid")}
            for pt, s in slots.items()]


def event_rows(body: dict | None, game_id: str, snapshot_type: str, fetched_at: datetime
               ) -> tuple[list[dict], list[dict], dict[str, float]]:
    """One event response -> (main rows, alternate rows, {book: minutes from its
    first-half last_update to the fetch}). Only the line-shop books, as the
    refresh pass stores. Every row carries every odds column."""
    rows: list[dict] = []
    ages: dict[str, float] = {}
    for book in (body or {}).get("bookmakers") or []:
        key = book.get("key")
        if key not in LINE_SHOP_BOOKMAKERS:
            continue
        markets = book.get("markets") or []
        parsed = parse_first_half(markets)
        if not parsed:
            continue
        stamp = (next((m.get("last_update") for m in markets
                       if m.get("key") == API_MARKET and m.get("last_update")), None)
                 or book.get("last_update") or _z(fetched_at))
        for p in parsed:
            row = dict.fromkeys(_ODDS_KEYS)
            row.update(p)
            row.update({"game_id": game_id, "sport": SPORT, "bookmaker": key,
                        "snapshot_type": snapshot_type, "snapshot_at": stamp,
                        "source": SOURCE})
            rows.append(row)
        t = _when(stamp)
        if t is not None:
            ages[key] = round((fetched_at - t).total_seconds() / 60.0, 1)
    main, alt = split_main_rungs(rows)
    return main, alt, ages


# ── the fetch ────────────────────────────────────────────────────────────────

def _billed(before: dict | None) -> float | None:
    """The x-requests-last of the call just made, None when it recorded none."""
    after = odds_quota.latest()
    if after is None or after is before:
        return None
    return after.get("last")


def _known_games(conn, game_ids: list[str]) -> dict[str, dict]:
    rows = conn.execute(
        "SELECT game_id, home_team, away_team FROM games WHERE sport = %s AND game_id = ANY(%s)",
        (SPORT, list(game_ids))).fetchall()
    return {gid: {"home": home, "away": away} for gid, home, away in rows}


def fetch_first_half(game_ids, snapshot_type: str = "open", conn=None) -> dict:
    """Fetch and store the first-half totals of exactly `game_ids` (one event
    call each, the ledger written beside every call). -> a summary: the games
    fetched, rows stored, and the games whose call failed (`failed`, which the
    window script turns into a non-zero exit)."""
    if snapshot_type not in SNAPSHOT_TYPES:
        raise ValueError(f"snapshot_type {snapshot_type!r}: one of {SNAPSHOT_TYPES}")
    ids = sorted(set(game_ids))
    out = {"snapshot_type": snapshot_type, "asked": ids, "not_in_games": [], "fetched": [],
           "rows": 0, "main_rows": 0, "no_first_half": [], "failed": [], "credits": {}}
    own = conn is None
    if own:
        from data.db import get_connection
        conn = get_connection()
    try:
        if not ids:
            return out
        ensure_ledger(conn)
        games = _known_games(conn, ids)
        # End the read before the first call: created_at (and fetch_at) is
        # now() at the start of a transaction, and an open one would date
        # every row to before its fetch.
        conn.rollback()
        out["not_in_games"] = [g for g in ids if g not in games]
        if out["not_in_games"]:
            logger.warning(f"NBA first-half totals: not in games, not fetched: {out['not_in_games']}")
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
                logger.error(f"NBA first-half totals: {gid}: {why or 'not in the event list'}; "
                             f"nothing bought")
                continue
            before = odds_quota.latest()
            try:
                body = _get_event_odds(SPORT_KEY, ev, [API_MARKET])
            except Exception as exc:  # noqa: BLE001 - one game's failure is its own
                credits = _billed(before)
                _ledger_row(conn, asked, EVENT_ODDS, snapshot_type, game_id=gid, event_id=ev,
                            ok=False, credits=credits, detail=f"call failed: {exc!r}")
                conn.commit()
                out["failed"].append(gid)
                out["credits"][gid] = credits
                logger.error(f"NBA first-half totals: {gid}: call failed: {exc!r}")
                continue
            credits = _billed(before)
            out["credits"][gid] = credits
            if body is None:
                # _get_event_odds returns None for an HTTP 404 or 422: the event
                # or the request was refused, which is not the books offering
                # nothing (that is a 200 with no bookmakers). It fails, the run
                # exits non-zero, and the next tick asks again.
                _ledger_row(conn, asked, EVENT_ODDS, snapshot_type, game_id=gid, event_id=ev,
                            ok=False, credits=credits, detail="HTTP 404 or 422: no body")
                conn.commit()
                out["failed"].append(gid)
                logger.error(f"NBA first-half totals: {gid}: HTTP 404 or 422 for event {ev}")
                continue
            main, alt, ages = event_rows(body, gid, snapshot_type, datetime.now(timezone.utc))
            rows = main + alt
            books = {r["bookmaker"] for r in rows}
            try:
                if rows:
                    _insert_odds(conn, rows)
                _ledger_row(conn, asked, EVENT_ODDS, snapshot_type, game_id=gid, event_id=ev,
                            ok=True, rows_stored=len(rows), main_rows=len(main), books=books,
                            ages=ages, credits=credits)
                conn.commit()            # per game: one failure cannot unwrite the rest
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                _ledger_row(conn, asked, EVENT_ODDS, snapshot_type, game_id=gid, event_id=ev,
                            ok=False, credits=credits, detail=f"store failed: {exc!r}")
                conn.commit()
                out["failed"].append(gid)
                logger.error(f"NBA first-half totals: {gid}: store failed: {exc!r}")
                continue
            out["fetched"].append(gid)
            out["rows"] += len(rows)
            out["main_rows"] += len(main)
            if not main:
                out["no_first_half"].append(gid)
            logger.info(f"  {gid}: {snapshot_type} first-half totals, {len(main)} main + {len(alt)} "
                        f"alternate rows, {len(books)} books, x-requests-last {credits}, "
                        f"book ages (min) {ages}")
        return out
    finally:
        try:
            persist_quota(conn)
        finally:
            if own:
                conn.close()
