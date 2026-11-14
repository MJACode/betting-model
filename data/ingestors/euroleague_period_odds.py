"""Live EuroLeague first-half, quarter and full-game lines at the decision
times: one per-event Odds API call per game per fetch time, stored before
anything is decided on it (scripts/euroleague_pregame_card.py).

WHY A FETCH OF ITS OWN. The bulk odds endpoint the refresh passes call never
returns a period market, and the history purchase
(data/ingestors/euroleague_period_history.py) is history. Two of the five
EuroLeague pre-game rules bet a period market (the first-half moneyline, the
first-quarter total), and the five decide ten minutes before tip, an instant
the hourly refresh passes do not reach: EuroLeague tips at 17:00-20:30 UTC,
inside the hourly window (7am-5pm ET), so a stored full-game quote can be
nearly an hour old at tip minus 10.

WHAT ONE CALL BUYS. One game, every market key the feed has served for
EuroLeague (euroleague_period_history.PERIOD_MARKETS: the first half, the
quarters, team totals, the alternate ladders, the 3-way moneylines) plus the
full game's moneyline, spread and total, at the ten books of
config.EUROLEAGUE_PERIOD_BOOKMAKERS. Ten named books bill as one region.

THE BILL, FROM THE CODE'S OWN BILLING MODEL, NOT MEASURED LIVE. The per-event
endpoint bills per market RETURNED per region (odds_ingestor._get_event_odds:
measured on the MLB first-five and UFC calls; the NCAAB first-half feed's
ledger). The history purchase billed 10 credits per market returned
(euroleague_period_history: its trial, 24 answers, 2,821 credits, 11 to 13
markets returned), and the historical endpoint bills ten times the live one,
so a live call is about 1 credit per market returned: about 14-16 for the 11-13
period markets the trial saw plus the three full-game ones, at most
MAX_CREDITS_PER_CALL (34). Three calls a game (MARKS): about 45 credits a game,
at most 102. A 380-game regular season: about 17,000 credits, at most about
39,000. credits_last records the feed's own x-requests-last for every call, so
the first live call measures it.

WHEN (scripts/euroleague_pregame_window.py plans it, every minute). MARKS:
60, 10 and 2 minutes before EuroLeague's start. The call at tip minus 10
(DECISION_MARK) is the one every rule decides on; it is retried every minute
until one lands. The other two are one attempt each: tip minus 60 is the
research's second read, tip minus 2 the closing read every pick's closing-line
value is measured on (tracking/paper_tracker: a period close must be pulled
after the pick).

WHAT ONE CALL STORES, in EuroLeague's home/away orientation (the feed's event is
placed on EuroLeague's game by euroleague_teams.Resolver; when the feed calls
EuroLeague's away club home the names are swapped before parsing, as the
purchase does, so a stored spread is the home club's number, CLAUDE.md 4): the
purchase's own parsing (euroleague_period_history.parse_book and split_main),
so the main number of each market is chosen exactly as the research's rows were
(two prices present, closest to even, ties to the lower number) and every
other rung is filed under <market>_alternate. snapshot_type 'open',
snapshot_at the market's own last_update, created_at the fetch instant (the
ledger's fetch_at), source SOURCE. Only quotes last updated at or before the
start are stored. Only games already in `games` are fetched, and only the ids
the caller names: the event list (free) is matched to them BEFORE any paid
call, so a tick never buys a game it did not plan. A game that has started is
never called.

SOURCE IS NEVER THE PURCHASE'S MARKER, and the odds prune protects it
(data/prune_odds.PROTECTED_SOURCES).

THE BALANCE. Before any paid call the run reads the newest recorded balance
(odds_quota.latest_remaining) and the platform's measured daily burn
(odds_quota.daily_burn). Under EUROLEAGUE_PERIOD_RESERVE_DAYS (default 1) of
that burn it buys nothing, writes a failed ledger row per game and the window
exits non-zero, so the failure alerter says so. Not a spending limit: above the
floor every planned game is fetched. It keeps the account off zero, where every
live feed stops (the September 2026 outage).

THE LEDGER (euroleague_period_live_fetches, worker-only): one row per call,
with the fetch time it served (mark). A call that came back (HTTP 200) with no
period market is still a fetch; a failed call is not (an HTTP 404 or 422
included), and the next tick tries again.

    python -m scripts.euroleague_pregame_window --fetch GAME_ID ...
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.ingestors import euroleague_period_history as eph
from data.ingestors import euroleague_teams as et
from data.ingestors import odds_quota
from data.ingestors.odds_ingestor import _get_event_odds, _insert_odds, _list_events
from data.ingestors.odds_quota import persist_quota

SPORT = et.SPORT
SPORT_KEY = et.ODDS_API_SPORT_KEY
FULL_GAME_MARKETS = ("h2h", "spreads", "totals")
API_MARKETS = list(eph.PERIOD_MARKETS) + list(FULL_GAME_MARKETS)
# The marker on every row this feed writes. Not the purchase's
# (odds_api_euroleague_period_history).
SOURCE = "odds_api_euroleague_period_live"
SNAPSHOT_TYPE = "open"
EVENTS, EVENT_ODDS = "events", "event_odds"

MARKS = (("T-60", 60), ("T-10", 10), ("T-2", 2))
DECISION_MARK = "T-10"
DECISION_MARKS = (DECISION_MARK,)
MAX_CREDITS_PER_CALL = len(API_MARKETS)      # one per market returned, one region
# No call this close to tip: the answer could land after the start.
LAST_CALL_LEAD = timedelta(seconds=30)


def enabled() -> bool:
    """RUN_EUROLEAGUE_PERIOD_FEED=0 (or false/off/no) stops the calls alone;
    the cards still decide the full-game rules on the stored board."""
    return (os.environ.get("RUN_EUROLEAGUE_PERIOD_FEED", "1").strip().lower()
            not in ("0", "false", "off", "no"))


def reserve_days() -> float:
    try:
        return float(os.environ.get("EUROLEAGUE_PERIOD_RESERVE_DAYS", "1"))
    except ValueError:
        return 1.0


def books_param() -> str:
    return ",".join(config.EUROLEAGUE_PERIOD_BOOKMAKERS)


# ── the ledger ───────────────────────────────────────────────────────────────
LEDGER_TABLE = "euroleague_period_live_fetches"
LEDGER_COLS = ("requested_at", "fetch_at", "endpoint", "mark", "game_id", "event_id", "ok",
               "rows_stored", "main_rows", "markets", "books", "credits_last", "detail")
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS euroleague_period_live_fetches (
    requested_at  TIMESTAMPTZ NOT NULL,
    fetch_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    endpoint      TEXT NOT NULL,
    mark          TEXT,
    game_id       TEXT,
    event_id      TEXT,
    ok            BOOLEAN NOT NULL,
    rows_stored   INTEGER NOT NULL DEFAULT 0,
    main_rows     INTEGER NOT NULL DEFAULT 0,
    markets       TEXT,
    books         TEXT,
    credits_last  REAL,
    detail        TEXT
)
"""
LEDGER_INDEX_NAME = "idx_euroleague_period_live_fetches_game"
LEDGER_INDEX = (f"CREATE INDEX IF NOT EXISTS {LEDGER_INDEX_NAME} "
                "ON euroleague_period_live_fetches (game_id, fetch_at)")
_INSERT_LEDGER = (
    "INSERT INTO euroleague_period_live_fetches (requested_at, endpoint, mark, game_id, event_id, "
    "ok, rows_stored, main_rows, markets, books, credits_last, detail) VALUES "
    "(%(requested_at)s, %(endpoint)s, %(mark)s, %(game_id)s, %(event_id)s, %(ok)s, "
    "%(rows_stored)s, %(main_rows)s, %(markets)s, %(books)s, %(credits_last)s, %(detail)s)")


def ensure_ledger(conn) -> None:
    """Create the ledger once, locked down; free after that. Only the fetch
    calls it: the plan and the card read, and never create."""
    if schema_is_current(conn, LEDGER_TABLE, columns=LEDGER_COLS, indexes=(LEDGER_INDEX_NAME,),
                         rls=True, revoked_from=API_ROLES):
        return
    conn.execute(LEDGER_DDL)
    conn.execute(LEDGER_INDEX)
    lock_down(conn, LEDGER_TABLE)
    conn.commit()


def ledger_exists(conn) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' "
        "AND table_name = %s", (LEDGER_TABLE,)).fetchone())


def _ledger_row(conn, requested_at: datetime, endpoint: str, mark: str | None, *,
                game_id: str | None = None, event_id: str | None = None, ok: bool,
                rows_stored: int = 0, main_rows: int = 0, markets=(), books=(),
                credits: float | None = None, detail: str | None = None) -> None:
    conn.execute(_INSERT_LEDGER, {
        "requested_at": requested_at, "endpoint": endpoint, "mark": mark,
        "game_id": game_id, "event_id": event_id, "ok": ok, "rows_stored": rows_stored,
        "main_rows": main_rows, "markets": ",".join(sorted(markets)) or None,
        "books": ",".join(sorted(books)) or None, "credits_last": credits,
        "detail": (detail or None) and detail[:500]})


def _when(stamp) -> datetime | None:
    if stamp is None:
        return None
    if isinstance(stamp, datetime):
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def last_fetches(conn, game_ids: list[str], ok_only: bool = True) -> dict[str, datetime]:
    """Each game's newest event call (ok only, or any attempt). Reads only."""
    if not game_ids or not ledger_exists(conn):
        return {}
    ok = "AND ok" if ok_only else ""
    rows = conn.execute(f"""
        SELECT game_id, MAX(fetch_at) FROM {LEDGER_TABLE}
        WHERE game_id = ANY(%s) AND endpoint = %s {ok} GROUP BY game_id
    """, (list(game_ids), EVENT_ODDS)).fetchall()
    return {gid: t for gid, ts in rows if (t := _when(ts)) is not None}


def decision_fetches(conn, game_ids: list[str], now: datetime | None = None) -> dict[str, datetime]:
    """{game_id: fetch_at} of each game's newest ok call made for DECISION_MARK,
    at or before `now` when given. Reads only."""
    if not game_ids or not ledger_exists(conn):
        return {}
    bound, params = "", [list(game_ids), EVENT_ODDS, DECISION_MARK]
    if now is not None:
        bound = "AND fetch_at <= %s"
        params.append(now)
    rows = conn.execute(f"""
        SELECT DISTINCT ON (game_id) game_id, fetch_at FROM {LEDGER_TABLE}
        WHERE game_id = ANY(%s) AND endpoint = %s AND mark = %s AND ok {bound}
        ORDER BY game_id, fetch_at DESC
    """, tuple(params)).fetchall()
    return {gid: t for gid, ts in rows if (t := _when(ts)) is not None}


# ── the schedule ─────────────────────────────────────────────────────────────

def slots(tip: datetime) -> list[tuple[str, datetime]]:
    """The game's fetch times, earliest first."""
    return sorted(((m, tip - timedelta(minutes=lead)) for m, lead in MARKS), key=lambda x: x[1])


def due_mark(tip: datetime, now: datetime, last_ok: datetime | None,
             last_try: datetime | None = None) -> tuple[str, datetime] | None:
    """(mark, its time) when this game needs a call now: the newest fetch time
    that has passed with no ok call landed at or after it. None otherwise, and
    always None within LAST_CALL_LEAD of tip or after it. Only the decision
    time is retried every tick; another that has had one failed attempt waits
    for the next fetch time."""
    if now >= tip - LAST_CALL_LEAD:
        return None
    passed = [(m, t) for m, t in slots(tip) if t <= now]
    if not passed:
        return None
    mark, t = passed[-1]
    if last_ok is not None and last_ok >= t:
        return None
    if mark not in DECISION_MARKS and last_try is not None and last_try >= t:
        return None
    return mark, t


# ── parsing ──────────────────────────────────────────────────────────────────

def event_rows(body: dict | None, game_id: str, home_name: str, away_name: str,
               fetched_at: datetime, tip: datetime | None) -> tuple[list[dict], set, set, int]:
    """One live event response -> (rows, markets returned, books, main rows).
    The purchase's parsing (euroleague_period_history.answer_rows: the live
    endpoint returns the event itself, the history wraps it in 'data'), this
    feed's source, and only quotes last updated at or before the tip."""
    rows, markets, books = eph.answer_rows({"data": body or {}}, game_id, home_name, away_name,
                                           fetched_at)
    out = []
    for r in rows:
        r["source"] = SOURCE
        r["snapshot_type"] = SNAPSHOT_TYPE
        t = _when(r.get("snapshot_at")) or fetched_at
        if tip is None or t <= tip:
            out.append(r)
    main = sum(1 for r in out if not str(r["market"]).endswith("_alternate")
               and not str(r["market"]).startswith("alternate_"))
    return out, set(markets), set(books), main


# ── the fetch ────────────────────────────────────────────────────────────────

def _billed(before: dict | None) -> float | None:
    after = odds_quota.latest()
    if after is None or after is before:
        return None
    return after.get("last")


def _known_games(conn, game_ids: list[str]) -> dict[str, dict]:
    rows = conn.execute(
        "SELECT game_id, game_date, commence_time, home_team, away_team FROM games "
        "WHERE sport = %s AND game_id = ANY(%s)", (SPORT, list(game_ids))).fetchall()
    return {gid: {"game_date": str(gd)[:10], "tip": _when(ct), "home": home, "away": away}
            for gid, gd, ct, home, away in rows}


def balance_floor(conn) -> tuple[int | None, int, str]:
    left = odds_quota.latest_remaining(conn)
    burn = odds_quota.daily_burn(conn)
    days = reserve_days()
    floor = int(burn * days) if burn else 0
    why = (f"balance {left if left is not None else 'unknown'}, floor {floor:,} = {days:g} day(s) "
           f"of the measured burn ({burn if burn is not None else 'not on record'}/day)")
    return left, floor, why


def fetch_periods(game_ids, conn=None, now: datetime | None = None) -> dict:
    """Fetch and store exactly `game_ids` (one event call each, its ledger row
    beside it), the decision fetches first. -> a summary; `failed` lists the
    games whose call failed (the window script turns it into exit 1)."""
    ids = sorted(set(game_ids))
    out = {"asked": ids, "not_in_games": [], "started": [], "fetched": [], "rows": 0,
           "main_rows": 0, "no_markets": [], "failed": [], "credits": {}, "marks": {}}
    own = conn is None
    if own:
        from data.db import get_connection
        conn = get_connection()
    try:
        if not ids:
            return out
        ensure_ledger(conn)
        games = _known_games(conn, ids)
        out["not_in_games"] = [g for g in ids if g not in games]
        now = now or datetime.now(timezone.utc)
        last = last_fetches(conn, sorted(games))
        tried = last_fetches(conn, sorted(games), ok_only=False)
        marks = {}
        for gid, g in games.items():
            if g["tip"] is None or g["tip"] - LAST_CALL_LEAD <= now:
                out["started"].append(gid)
                continue
            due = due_mark(g["tip"], now, last.get(gid), tried.get(gid))
            marks[gid] = due[0] if due else "manual"
        out["marks"] = marks
        if not marks:
            return out
        left, floor, why = balance_floor(conn)
        conn.rollback()
        logger.info(f"EuroLeague periods: {why}")
        if left is not None and floor and left < floor:
            asked = datetime.now(timezone.utc)
            for gid in sorted(marks):
                _ledger_row(conn, asked, EVENT_ODDS, marks[gid], game_id=gid, ok=False,
                            detail=f"not bought: {why}")
            conn.commit()
            out["failed"] = sorted(marks)
            out["refused"] = why
            logger.error(f"EuroLeague periods: nothing bought, the balance is under its floor: {why}")
            return out
        resolver = et.make_resolver(conn, now.date().isoformat(), days_back=1, days_fwd=3)
        # End the reads before the first call: created_at (and fetch_at) is
        # now() at the start of a transaction.
        conn.rollback()
        asked = datetime.now(timezone.utc)
        before = odds_quota.latest()
        try:
            events, err = _list_events(SPORT_KEY), None
        except Exception as exc:  # noqa: BLE001 - recorded; every game fails below
            events, err = [], f"event list failed: {exc!r}"
        credits = _billed(before)
        out["credits"]["events"] = credits
        _ledger_row(conn, asked, EVENTS, None, ok=err is None, rows_stored=len(events),
                    credits=credits, detail=err or f"{len(events)} events listed")
        conn.commit()
        if resolver is None and err is None:
            err = "no schedule resolver (no stored EuroLeague games near today)"
        by_game: dict[str, tuple[str, bool, dict]] = {}
        for ev in events or []:
            hit = resolver(ev.get("home_team") or "", ev.get("away_team") or "",
                           ev.get("commence_time")) if resolver else None
            if hit and hit[0] in marks and ev.get("id"):
                by_game[hit[0]] = (str(ev["id"]), bool(hit[1]), ev)
        order = sorted(marks, key=lambda g: (marks[g] not in DECISION_MARKS, games[g]["tip"], g))
        for gid in order:
            mark = marks[gid]
            hit = by_game.get(gid)
            asked = datetime.now(timezone.utc)
            if hit is None:
                _ledger_row(conn, asked, EVENT_ODDS, mark, game_id=gid, ok=False,
                            detail=err or "not in the feed's event list")
                conn.commit()
                out["failed"].append(gid)
                logger.error(f"EuroLeague periods: {gid}: {err or 'not in the event list'}; nothing bought")
                continue
            ev_id, flipped, ev = hit
            if games[gid]["tip"] - LAST_CALL_LEAD <= asked:
                out["started"].append(gid)
                continue
            home_name, away_name = ev.get("home_team") or "", ev.get("away_team") or ""
            if flipped:
                # the feed called EuroLeague's away club home: parse in EuroLeague's orientation
                home_name, away_name = away_name, home_name
            before = odds_quota.latest()
            try:
                body = _get_event_odds(SPORT_KEY, ev_id, API_MARKETS, bookmakers=books_param())
            except Exception as exc:  # noqa: BLE001 - one game's failure is its own
                credits = _billed(before)
                _ledger_row(conn, asked, EVENT_ODDS, mark, game_id=gid, event_id=ev_id, ok=False,
                            credits=credits, detail=f"call failed: {exc!r}")
                conn.commit()
                out["failed"].append(gid)
                out["credits"][gid] = credits
                logger.error(f"EuroLeague periods: {gid}: call failed: {exc!r}")
                continue
            credits = _billed(before)
            out["credits"][gid] = credits
            if body is None:
                _ledger_row(conn, asked, EVENT_ODDS, mark, game_id=gid, event_id=ev_id, ok=False,
                            credits=credits, detail="HTTP 404 or 422: no body")
                conn.commit()
                out["failed"].append(gid)
                logger.error(f"EuroLeague periods: {gid}: HTTP 404 or 422 for event {ev_id}")
                continue
            rows, mkts, books, main = event_rows(body, gid, home_name, away_name,
                                                 datetime.now(timezone.utc), games[gid]["tip"])
            try:
                if rows:
                    _insert_odds(conn, rows)
                _ledger_row(conn, asked, EVENT_ODDS, mark, game_id=gid, event_id=ev_id, ok=True,
                            rows_stored=len(rows), main_rows=main, markets=mkts, books=books,
                            credits=credits, detail="flipped" if flipped else None)
                conn.commit()            # per game: one failure cannot unwrite the rest
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                _ledger_row(conn, asked, EVENT_ODDS, mark, game_id=gid, event_id=ev_id, ok=False,
                            credits=credits, detail=f"store failed: {exc!r}")
                conn.commit()
                out["failed"].append(gid)
                logger.error(f"EuroLeague periods: {gid}: store failed: {exc!r}")
                continue
            out["fetched"].append(gid)
            out["rows"] += len(rows)
            out["main_rows"] += main
            if not any(m.endswith(("_h1", "_q1")) for m in mkts):
                out["no_markets"].append(gid)
            logger.info(f"  {gid} [{mark}]: {len(rows)} rows ({main} main), markets {sorted(mkts)}, "
                        f"{len(books)} books, x-requests-last {credits}")
        return out
    finally:
        try:
            persist_quota(conn)
        finally:
            if own:
                conn.close()


def ledger_summary(conn) -> dict:
    """For the docs and the first-run check: calls, ok calls, credits."""
    if not ledger_exists(conn):
        return {}
    r = conn.execute(f"""
        SELECT COUNT(*), COUNT(*) FILTER (WHERE ok), COALESCE(SUM(credits_last), 0)
        FROM {LEDGER_TABLE} WHERE endpoint = %s
    """, (EVENT_ODDS,)).fetchone()
    return {"calls": int(r[0]), "ok": int(r[1]), "credits": float(r[2])}

