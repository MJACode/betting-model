"""Live NBA team totals: one per-event Odds API call per game, stored before
anything is decided on it (`nba_team_total_luck`, models/nba_team_total_luck.py).

WHY A FETCH OF ITS OWN. Team totals are an additional market: the bulk odds
endpoint the refresh pass and the NBA totals window call never returns them;
only the per-event endpoint does (odds_ingestor._get_event_odds). And the
refresh pass's parser could not store them: _process_events has no team-total
branch, and it drops every event DraftKings does not list, while DraftKings was
the book on only 85 of the model's 349 graded bets.

WHAT ONE CALL STORES. One game, markets=team_totals, the configured regions and
books, links and sids on (all of it _get_event_odds' own parameters):
  * home or away read off each outcome exactly as the historical purchase reads
    it (nba_odds_history.parse_derivatives): Over/Under from whichever of name
    and description holds it, the team from the other; a team that is neither
    side of the game is dropped. Links and sids are kept, as the NHL parser
    keeps them (nhl_derivative_odds_history.parse_markets).
  * each book's MAIN number for each team (models/nba_book_numbers
    .split_main_rungs: coherent first, prices closest to even, ties to the lower
    number) under team_totals_home / team_totals_away, and every other rung
    under team_totals_home_alternate / team_totals_away_alternate. Every reader
    of one row per (game, market, book) -- the latest_odds trigger, the app's
    other-books prices, closing-line value -- then lands on the main number.
  * snapshot_type 'open' for a decision fetch, 'close' for the closing
    snapshot; snapshot_at = the market's own last_update (else the book's,
    else the fetch time), the live `odds` convention; created_at = the fetch
    instant: the column default, now() at the start of the game's own
    transaction, which begins only after the response has arrived (no
    statement runs on the connection between one game's commit and the next
    game's call); source = SOURCE.
Only games already in `games` are fetched (odds has a foreign key to it), and
only the ids the caller names: the event list is matched to them BEFORE any
paid call, so a tick never buys a game it did not plan.

SOURCE IS NEVER THE PURCHASE'S MARKER. nba_odds_history._deriv_done treats a
row whose source starts 'odds_api_nba_derivative_history' as already bought,
and the lab's loader reads that source as a purchase. The odds prune protects
SOURCE (data/prune_odds.PROTECTED_SOURCES): its keepers are one row per (game,
market, book), which would thin a ladder to arbitrary rungs.

THE LEDGER (nba_team_total_fetches, worker-only). One row per call -- the event
list, and each game's event call -- with when it was asked, the rows stored,
the main rows among them, the books that returned a team total, each book's
last_update age at the fetch (minutes), the feed's x-requests-last header and
whether the call failed. A game's row is written in the game's own transaction,
so its fetch_at IS its odds rows' created_at. The card decides on the newest ok
'open' row: a call that came back (HTTP 200) with no team total is still a
fetch (the game is decided with nothing offered, as the lab's one purchase a
game was); a failed call is not, an HTTP 404 or 422 included, and the next
tick tries again.

COST is read, never assumed: credits_last is the feed's own x-requests-last for
that call (data/ingestors/odds_quota.latest). No live team-total call had been
made before this model, so the first rows are the measurement. When
_get_event_odds falls back to DraftKings only after a 400, two calls were
billed and credits_last holds the second.

    python -m scripts.nba_team_total_luck_window --fetch GAME_ID ...   # a decision fetch
    python -m scripts.nba_team_total_luck_window --close GAME_ID ...   # the closing snapshot
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from loguru import logger

from config import LINE_SHOP_BOOKMAKERS
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.ingestors import odds_quota
from data.ingestors.nba_odds_history import _ODDS_KEYS, _nba_abbrev
from data.ingestors.odds_ingestor import (SPORT_KEYS, _build_game_id, _get_event_odds,
                                          _insert_odds, _list_events)
from data.ingestors.odds_quota import persist_quota
from models.nba_book_numbers import split_main_rungs

ET = ZoneInfo("America/New_York")
SPORT = "NBA"
SPORT_KEY = SPORT_KEYS[SPORT]
API_MARKET = "team_totals"
# The marker on every row this feed writes. Not the purchase's prefix
# (module docstring).
SOURCE = "odds_api_nba_team_totals_live"
SNAPSHOT_TYPES = ("open", "close")

# ── the ledger ───────────────────────────────────────────────────────────────
LEDGER_TABLE = "nba_team_total_fetches"
LEDGER_COLS = ("requested_at", "fetch_at", "endpoint", "snapshot_type", "game_id", "event_id",
               "ok", "rows_stored", "main_rows", "books", "book_ages", "credits_last", "detail")
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS nba_team_total_fetches (
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
    "INSERT INTO nba_team_total_fetches (requested_at, endpoint, snapshot_type, game_id, "
    "event_id, ok, rows_stored, main_rows, books, book_ages, credits_last, detail) VALUES "
    "(%(requested_at)s, %(endpoint)s, %(snapshot_type)s, %(game_id)s, %(event_id)s, %(ok)s, "
    "%(rows_stored)s, %(main_rows)s, %(books)s, %(book_ages)s, %(credits_last)s, %(detail)s)")
EVENTS, EVENT_ODDS = "events", "event_odds"


def ensure_ledger(conn) -> None:
    """Create the ledger once, locked down, and cost nothing after that
    (data/ddl_guard.schema_is_current), as scripts/nba_total_luck_card.py's
    ensure_decisions_table does. Only the fetch calls it: the plan and the
    card read, and never create."""
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
    """Games whose closing snapshot has been fetched (an ok 'close' call, team
    totals offered or not). Reads only."""
    return set(fetches(conn, game_ids, "close"))


# ── parsing ──────────────────────────────────────────────────────────────────

def parse_team_totals(book_markets: list[dict], home: str, away: str,
                      unknown: set | None = None) -> list[dict]:
    """One book's markets -> one odds-row dict per (team_totals_home /
    team_totals_away, line): total_line, the over and under prices, links and
    sids. nba_odds_history.parse_derivatives' team-total branch, with the
    links and sids kept. A team that is neither `home` nor `away` (our
    abbreviations) is dropped, and its name added to `unknown`."""
    slots: dict[tuple, dict] = {}
    for m in book_markets:
        if m.get("key") != API_MARKET:
            continue
        for o in m.get("outcomes") or []:
            name, desc = (o.get("name") or ""), (o.get("description") or "")
            side, team = (name, desc) if name.lower() in ("over", "under") else (desc, name)
            if side.lower() not in ("over", "under") or o.get("point") is None:
                continue
            ab = _nba_abbrev(team)
            stored = ("team_totals_home" if ab == home else
                      "team_totals_away" if ab == away else None)
            if stored is None:
                if unknown is not None:
                    unknown.add(team)
                continue
            slot = slots.setdefault((stored, float(o["point"])), {})
            which = side.lower()
            slot[which + "_price"] = o.get("price")
            slot[which + "_link"] = o.get("link")
            slot[which + "_sid"] = o.get("sid")
    return [{"market": stored, "total_line": pt,
             "over_price": s.get("over_price"), "under_price": s.get("under_price"),
             "over_link": s.get("over_link"), "under_link": s.get("under_link"),
             "over_sid": s.get("over_sid"), "under_sid": s.get("under_sid")}
            for (stored, pt), s in slots.items()]


def _z(t: datetime) -> str:
    """The feed's own stamp shape ('...Z'), so a fallback sorts with real ones."""
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _when(stamp) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def event_rows(body: dict | None, game_id: str, home: str, away: str, snapshot_type: str,
               fetched_at: datetime, unknown: set | None = None
               ) -> tuple[list[dict], list[dict], dict[str, float]]:
    """One event response -> (main rows, alternate rows, {book: minutes from
    its team-total last_update to the fetch}). Only the line-shop books, as
    the refresh pass stores. Every row carries every odds column."""
    rows: list[dict] = []
    ages: dict[str, float] = {}
    for book in (body or {}).get("bookmakers") or []:
        key = book.get("key")
        if key not in LINE_SHOP_BOOKMAKERS:
            continue
        markets = book.get("markets") or []
        parsed = parse_team_totals(markets, home, away, unknown)
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


def event_ids(events: list[dict], game_ids) -> dict[str, str]:
    """{game_id: event id} for the feed's events that are these games: the
    game id built from the event's Eastern date and the two teams. An event
    whose team the map does not know is no game of ours."""
    want = set(game_ids)
    out: dict[str, str] = {}
    for ev in events or []:
        start = _when(ev.get("commence_time"))
        home, away = _nba_abbrev(ev.get("home_team") or ""), _nba_abbrev(ev.get("away_team") or "")
        if start is None or not home or not away or not ev.get("id"):
            continue
        gid = _build_game_id(SPORT, start.astimezone(ET).strftime("%Y-%m-%d"), away, home)
        if gid in want:
            out[gid] = ev["id"]
    return out


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


def fetch_team_totals(game_ids, snapshot_type: str = "open", conn=None) -> dict:
    """Fetch and store the team totals of exactly `game_ids` (one event call
    each, the ledger written beside every call). -> a summary: the games
    fetched, rows stored, and the games whose call failed (`failed`, which the
    window script turns into a non-zero exit)."""
    if snapshot_type not in SNAPSHOT_TYPES:
        raise ValueError(f"snapshot_type {snapshot_type!r}: one of {SNAPSHOT_TYPES}")
    ids = sorted(set(game_ids))
    out = {"snapshot_type": snapshot_type, "asked": ids, "not_in_games": [], "fetched": [],
           "rows": 0, "main_rows": 0, "no_team_total": [], "failed": [], "credits": {}}
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
            logger.warning(f"NBA team totals: not in games, not fetched: {out['not_in_games']}")
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
            g = games[gid]
            ev = by_game.get(gid)
            asked = datetime.now(timezone.utc)
            if ev is None:
                _ledger_row(conn, asked, EVENT_ODDS, snapshot_type, game_id=gid, ok=False,
                            detail=why or "not in the feed's event list")
                conn.commit()
                out["failed"].append(gid)
                logger.error(f"NBA team totals: {gid}: {why or 'not in the event list'}; "
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
                logger.error(f"NBA team totals: {gid}: call failed: {exc!r}")
                continue
            credits = _billed(before)
            out["credits"][gid] = credits
            if body is None:
                # _get_event_odds returns None for an HTTP 404 or 422: the
                # event or the request was refused, which is not the books
                # offering nothing (that is a 200 with no bookmakers). Counted
                # as a fetch, it would decide the game with no bet, or count a
                # close as taken, with nothing ever saying so. It fails, the
                # run exits non-zero, and the next tick asks again.
                _ledger_row(conn, asked, EVENT_ODDS, snapshot_type, game_id=gid, event_id=ev,
                            ok=False, credits=credits, detail="HTTP 404 or 422: no body")
                conn.commit()
                out["failed"].append(gid)
                logger.error(f"NBA team totals: {gid}: HTTP 404 or 422 for event {ev}")
                continue
            unknown: set = set()
            main, alt, ages = event_rows(body, gid, g["home"], g["away"], snapshot_type,
                                         datetime.now(timezone.utc), unknown)
            if unknown:
                logger.warning(f"NBA team totals: {gid}: team names that are neither side "
                               f"({g['away']} @ {g['home']}), dropped: {sorted(unknown)}")
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
                logger.error(f"NBA team totals: {gid}: store failed: {exc!r}")
                continue
            out["fetched"].append(gid)
            out["rows"] += len(rows)
            out["main_rows"] += len(main)
            if not main:
                out["no_team_total"].append(gid)
            logger.info(f"  {gid}: {snapshot_type} team totals, {len(main)} main + {len(alt)} "
                        f"alternate rows, {len(books)} books, x-requests-last {credits}, "
                        f"book ages (min) {ages}")
        return out
    finally:
        try:
            persist_quota(conn)
        finally:
            if own:
                conn.close()
