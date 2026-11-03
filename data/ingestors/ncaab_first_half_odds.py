"""Live NCAAB first-half lines: one per-event Odds API call per game per fetch
time, stored before anything is decided on it (`ncaab_first_half_spread`,
models/ncaab_first_half_spread.py, and `ncaab_first_half_total`,
models/ncaab_first_half_total.py).

WHY A FETCH OF ITS OWN. Nothing stored NCAAB first-half lines for 2026-27
before this model: the bulk odds endpoint never returns them (the capture job,
scripts/ncaab_odds_capture.py, and the refresh passes call it), and the history
purchase (data/ingestors/ncaab_odds_history.py) is history.

WHAT ONE CALL BUYS. One game, markets h2h_h1, spreads_h1, totals_h1 and
team_totals, the configured region and line-shop books, links and sids on
(odds_ingestor._get_event_odds). The spread and the total decide bets; the
other two are stored because the next first-half models (moneyline, team
total) need their history, and a market the call does not return costs
nothing. The endpoint bills per market RETURNED per region (measured on the NBA
and NCAAB live feeds, odds_ingestor._get_event_odds), so a call costs at most 4
credits and an empty answer 0. credits_last records the feed's own
x-requests-last for each call: the bill is read, never assumed.

WHEN (scripts/ncaab_first_half_window.py plans it, every minute). Nine fetch
times per game: 15:00 UTC on its Eastern date, then 180, 120, 60, 50, 40, 30,
20 and 10 minutes before tip (MARKS). A time is due once it has passed and no
ok call for the game has landed since; a missed time is covered by the next
tick, and a time the next one overtakes is skipped. A failed call at a history
time waits for the next time; a failed call at a decision time (DECISION_MARKS)
is retried every minute. At most 9 x 4 = 36 credits a game (an empty answer and an HTTP
404 billed 0 in the measured calls, the purchase's api_call_log). The call at tip minus 10 (DECISION_MARK) is the one the spread card decides
on (scripts/ncaab_first_half_spread_card.py); the call at tip minus 60
(TOTAL_DECISION_MARK) is the one the total card decides on
(scripts/ncaab_first_half_total_card.py).

WHAT ONE CALL STORES, per line-shop book, in ESPN's home/away orientation (the
feed's event is placed on ESPN's game by ncaab_teams' resolver; when the feed
calls ESPN's away team home, the names are swapped before parsing, as the
purchase does, so spreads_h1's spread_home is ESPN's home number, CLAUDE.md 4):
  * h2h_h1: one row, home and away prices (a draw price when a book sends one).
  * spreads_h1, totals_h1, team_totals_home / team_totals_away: one row per
    number the book lists; each book's MAIN number keeps the market name and
    every other rung is filed under <market>_alternate
    (models/nba_book_numbers.split_main_rungs: coherent first, prices closest
    to even, ties to the lower number). So every reader of one row per (game,
    market, book) lands on the main number. The purchase kept the last pair a
    book listed; its spreads_h1 close held one number per book and game on all
    106,830 rows (the research's n_points), so the two agree wherever the
    history can be checked.
  * snapshot_type 'open' (pre-game), snapshot_at the market's own last_update
    (else the book's, else the fetch time), created_at the fetch instant (the
    ledger's fetch_at), source SOURCE.
Only games already in `games` are fetched (odds has a foreign key to it), and
only the ids the caller names: the event list is matched to them BEFORE any
paid call, so a tick never buys a game it did not plan. A game whose tip has
passed is never called: its prices would be in-play.

SOURCE IS NEVER THE PURCHASE'S MARKER, and the odds prune protects it
(data/prune_odds.PROTECTED_SOURCES).

THE BALANCE. Before any paid call the run reads the newest recorded balance
(odds_quota.latest_remaining) and the platform's measured daily burn
(odds_quota.daily_burn, the median day of the last two weeks). Under
RESERVE_DAYS of that burn it buys nothing, writes a failed ledger row per game
and exits non-zero, so the failure alerter says so. This is not a spending
limit: above the floor every planned game is fetched. It keeps the account off
zero, where every live feed stops (the September 2026 outage), and this feed
is the one that yields first. No burn on record: no floor (logged).

THE LEDGER (ncaab_first_half_fetches, worker-only): one row per call, with the
fetch time it served (mark). A call that came back (HTTP 200) with no first-half
market is still a fetch; a failed call is not (an HTTP 404 or 422 included),
and the next tick tries again.

    python -m scripts.ncaab_first_half_window --fetch GAME_ID ...
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from loguru import logger

from config import LINE_SHOP_BOOKMAKERS
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.ingestors import ncaab_teams, odds_quota
from data.ingestors.nba_odds_history import _ODDS_KEYS
from data.ingestors.odds_ingestor import _get_event_odds, _insert_odds, _list_events
from data.ingestors.odds_quota import persist_quota
from models.nba_book_numbers import split_main_rungs

SPORT = ncaab_teams.SPORT
SPORT_KEY = ncaab_teams.ODDS_API_SPORT_KEY
API_MARKETS = ["h2h_h1", "spreads_h1", "totals_h1", "team_totals"]
# The marker on every row this feed writes. Not the purchase's
# (odds_api_ncaab_derivative_open / _close).
SOURCE = "odds_api_ncaab_first_half_live"
SNAPSHOT_TYPE = "open"
EVENTS, EVENT_ODDS = "events", "event_odds"
_ET = ZoneInfo("America/New_York")

# The fetch times: (mark, minutes before tip), None = 15:00 UTC on the game's
# Eastern date. DECISION_MARK is the research's close (tip minus 10 minutes),
# the first-half spread's decision; TOTAL_DECISION_MARK the research's tip60
# purchase (tip minus 60), the first-half total's. A call at either is retried
# every minute until one lands (due_mark).
MARKS = (("15z", None), ("T-180", 180), ("T-120", 120), ("T-60", 60), ("T-50", 50),
         ("T-40", 40), ("T-30", 30), ("T-20", 20), ("T-10", 10))
DECISION_MARK = "T-10"
TOTAL_DECISION_MARK = "T-60"
DECISION_MARKS = (DECISION_MARK, TOTAL_DECISION_MARK)
MAX_CREDITS_PER_CALL = len(API_MARKETS)      # one per market returned, one region
# No call this close to tip: the answer could land after the start.
LAST_CALL_LEAD = timedelta(seconds=30)


def reserve_days() -> float:
    """NCAAB_FIRST_HALF_RESERVE_DAYS, default 1: the balance floor in days of
    the platform's own measured burn (module docstring, THE BALANCE)."""
    try:
        return float(os.environ.get("NCAAB_FIRST_HALF_RESERVE_DAYS", "1"))
    except ValueError:
        return 1.0


# ── the ledger ───────────────────────────────────────────────────────────────
LEDGER_TABLE = "ncaab_first_half_fetches"
LEDGER_COLS = ("requested_at", "fetch_at", "endpoint", "mark", "game_id", "event_id", "ok",
               "rows_stored", "main_rows", "markets", "books", "book_ages", "credits_last",
               "detail")
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_first_half_fetches (
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
    book_ages     TEXT,
    credits_last  REAL,
    detail        TEXT
)
"""
LEDGER_INDEX = ("CREATE INDEX IF NOT EXISTS idx_ncaab_first_half_fetches_game "
                "ON ncaab_first_half_fetches (game_id, fetch_at)")
_INSERT_LEDGER = (
    "INSERT INTO ncaab_first_half_fetches (requested_at, endpoint, mark, game_id, event_id, ok, "
    "rows_stored, main_rows, markets, books, book_ages, credits_last, detail) VALUES "
    "(%(requested_at)s, %(endpoint)s, %(mark)s, %(game_id)s, %(event_id)s, %(ok)s, "
    "%(rows_stored)s, %(main_rows)s, %(markets)s, %(books)s, %(book_ages)s, %(credits_last)s, "
    "%(detail)s)")


def ensure_ledger(conn) -> None:
    """Create the ledger once, locked down, and cost nothing after that. Only
    the fetch calls it: the plan and the card read, and never create."""
    if schema_is_current(conn, LEDGER_TABLE, columns=LEDGER_COLS,
                         indexes=("idx_ncaab_first_half_fetches_game",),
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
                ages: dict | None = None, credits: float | None = None,
                detail: str | None = None) -> None:
    conn.execute(_INSERT_LEDGER, {
        "requested_at": requested_at, "endpoint": endpoint, "mark": mark,
        "game_id": game_id, "event_id": event_id, "ok": ok, "rows_stored": rows_stored,
        "main_rows": main_rows, "markets": ",".join(sorted(markets)) or None,
        "books": ",".join(sorted(books)) or None,
        "book_ages": json.dumps(ages, sort_keys=True) if ages else None,
        "credits_last": credits, "detail": (detail or None) and detail[:500]})


def _aware(ts) -> datetime | None:
    if ts is None:
        return None
    t = ts if isinstance(ts, datetime) else _when(ts)
    if t is None:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def last_fetches(conn, game_ids: list[str], now: datetime | None = None,
                 ok_only: bool = True) -> dict[str, datetime]:
    """Each game's newest ok event call (any mark), at or before `now` when
    given; with ok_only=False its newest attempt, ok or not. Reads only: no
    ledger yet, no fetch."""
    if not game_ids or not ledger_exists(conn):
        return {}
    bound, params = "", [list(game_ids), EVENT_ODDS]
    if now is not None:
        bound = "AND fetch_at <= %s"
        params.append(now)
    ok = "AND ok" if ok_only else ""
    rows = conn.execute(f"""
        SELECT game_id, MAX(fetch_at) FROM {LEDGER_TABLE}
        WHERE game_id = ANY(%s) AND endpoint = %s {ok} {bound}
        GROUP BY game_id
    """, tuple(params)).fetchall()
    return {gid: t for gid, ts in rows if (t := _aware(ts)) is not None}


def decision_fetches(conn, game_ids: list[str], now: datetime | None = None,
                     mark: str = DECISION_MARK) -> dict[str, tuple[datetime, dict]]:
    """{game_id: (fetch_at, book ages)} for each game's newest ok call made for
    `mark` (DECISION_MARK, the spread's; TOTAL_DECISION_MARK, the total's), at
    or before `now` when given. Reads only."""
    if not game_ids or not ledger_exists(conn):
        return {}
    bound, params = "", [list(game_ids), EVENT_ODDS, mark]
    if now is not None:
        bound = "AND fetch_at <= %s"
        params.append(now)
    rows = conn.execute(f"""
        SELECT DISTINCT ON (game_id) game_id, fetch_at, book_ages FROM {LEDGER_TABLE}
        WHERE game_id = ANY(%s) AND endpoint = %s AND mark = %s AND ok {bound}
        ORDER BY game_id, fetch_at DESC
    """, tuple(params)).fetchall()
    out = {}
    for gid, ts, ages in rows:
        t = _aware(ts)
        if t is None:
            continue
        try:
            a = json.loads(ages) if ages else {}
        except (TypeError, ValueError):
            a = {}
        out[gid] = (t, a)
    return out


# ── the schedule ─────────────────────────────────────────────────────────────

def _when(stamp) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _z(t: datetime) -> str:
    """The feed's own stamp shape ('...Z'), so a fallback sorts with real ones."""
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slots(game_date: str, tip: datetime) -> list[tuple[str, datetime]]:
    """The game's fetch times before its tip, earliest first. Two marks at the
    same instant are one fetch time: the earlier-listed mark names it, unless
    the later is a decision mark (an 11am ET tip's 15:00 UTC call IS its tip
    minus 60, and is retried and decided on as that)."""
    out: dict[datetime, str] = {}
    for mark, lead in MARKS:
        if lead is None:
            d = datetime.fromisoformat(str(game_date)[:10])
            t = datetime(d.year, d.month, d.day, 15, tzinfo=timezone.utc)
        else:
            t = tip - timedelta(minutes=lead)
        if t < tip and (t not in out or mark in DECISION_MARKS):
            out[t] = mark
    return sorted(((m, t) for t, m in out.items()), key=lambda x: x[1])


def due_mark(game_date: str, tip: datetime, now: datetime, last_ok: datetime | None,
             last_try: datetime | None = None) -> tuple[str, datetime] | None:
    """(mark, its time) when this game needs a call now: the newest fetch time
    that has passed, with no ok call landed at or after it. None otherwise, and
    always None within LAST_CALL_LEAD of tip or after it.

    Only the decision times (DECISION_MARKS) are retried every tick: a history
    fetch time that has had one failed attempt waits for the next fetch time,
    so a game the feed keeps refusing is called once per fetch time, not once
    a minute."""
    if now >= tip - LAST_CALL_LEAD:
        return None
    passed = [(m, t) for m, t in slots(game_date, tip) if t <= now]
    if not passed:
        return None
    mark, t = passed[-1]
    if last_ok is not None and last_ok >= t:
        return None
    if mark not in DECISION_MARKS and last_try is not None and last_try >= t:
        return None
    return mark, t


# ── parsing ──────────────────────────────────────────────────────────────────

def _side_team(o: dict) -> tuple[str, str]:
    """(over/under, team) of a team-total outcome, whichever field carries which."""
    name, desc = (o.get("name") or ""), (o.get("description") or "")
    return (name, desc) if name.lower() in ("over", "under") else (desc, name)


def parse_book(book_markets: list[dict], home_name: str, away_name: str) -> list[dict]:
    """One book's markets -> odds-row dicts, one per number listed (a ladder
    stays a ladder here; split_main_rungs picks the main number).

    `home_name` / `away_name` are the feed's names in ESPN's orientation (the
    caller swaps them for a flipped event). A spread pair is keyed on the HOME
    number: the home outcome at point p and the away outcome at -p. A team
    total whose description names neither team is filed under neither side."""
    rows: list[dict] = []
    for m in book_markets:
        key, outs = m.get("key"), m.get("outcomes") or []
        if key == "h2h_h1":
            row = {"market": key}
            for o in outs:
                name = o.get("name") or ""
                slot = ("draw" if name == "Draw" else "home" if name == home_name
                        else "away" if name == away_name else None)
                if slot is None:
                    continue
                row.update({f"{slot}_price": o.get("price"), f"{slot}_link": o.get("link"),
                            f"{slot}_sid": o.get("sid")})
            if row.get("home_price") is not None or row.get("away_price") is not None:
                rows.append(row)
        elif key == "spreads_h1":
            slots_: dict[float, dict] = {}
            for o in outs:
                name, pt = o.get("name") or "", o.get("point")
                if pt is None:
                    continue
                if name == home_name:
                    s = slots_.setdefault(float(pt), {})
                    s.update(home_price=o.get("price"), home_link=o.get("link"),
                             home_sid=o.get("sid"))
                elif name == away_name:
                    s = slots_.setdefault(-float(pt), {})
                    s.update(away_price=o.get("price"), away_link=o.get("link"),
                             away_sid=o.get("sid"))
            for pt, s in slots_.items():
                rows.append({"market": key, "spread_home": pt, **s})
        elif key == "totals_h1":
            slots_ = {}
            for o in outs:
                side = (o.get("name") or "").lower()
                if side not in ("over", "under") or o.get("point") is None:
                    continue
                s = slots_.setdefault(float(o["point"]), {})
                s.update({f"{side}_price": o.get("price"), f"{side}_link": o.get("link"),
                          f"{side}_sid": o.get("sid")})
            for pt, s in slots_.items():
                rows.append({"market": key, "total_line": pt, **s})
        elif key == "team_totals":
            slots_t: dict[tuple, dict] = {}
            for o in outs:
                side, team = _side_team(o)
                if side.lower() not in ("over", "under") or o.get("point") is None:
                    continue
                stored = ("team_totals_home" if team == home_name else
                          "team_totals_away" if team == away_name else None)
                if stored is None:
                    continue
                s = slots_t.setdefault((stored, float(o["point"])), {})
                s.update({f"{side.lower()}_price": o.get("price"),
                          f"{side.lower()}_link": o.get("link"),
                          f"{side.lower()}_sid": o.get("sid")})
            for (stored, pt), s in slots_t.items():
                rows.append({"market": stored, "total_line": pt, **s})
    return rows


def event_rows(body: dict | None, game_id: str, home_name: str, away_name: str,
               fetched_at: datetime) -> tuple[list[dict], list[dict], dict[str, float], set]:
    """One event response -> (main rows, alternate rows, {book: minutes from
    its first-half spread's last_update to the fetch}, markets returned). Only
    the line-shop books. Every row carries every odds column."""
    rows: list[dict] = []
    ages: dict[str, float] = {}
    markets: set[str] = set()
    for book in (body or {}).get("bookmakers") or []:
        key = book.get("key")
        if key not in LINE_SHOP_BOOKMAKERS:
            continue
        bm = book.get("markets") or []
        stamps = {m.get("key"): m.get("last_update") for m in bm if m.get("key")}
        for p in parse_book(bm, home_name, away_name):
            api_key = "team_totals" if p["market"].startswith("team_totals") else p["market"]
            stamp = stamps.get(api_key) or book.get("last_update") or _z(fetched_at)
            row = dict.fromkeys(_ODDS_KEYS)
            row.update(p)
            row.update({"game_id": game_id, "sport": SPORT, "bookmaker": key,
                        "snapshot_type": SNAPSHOT_TYPE, "snapshot_at": stamp, "source": SOURCE})
            rows.append(row)
            markets.add(api_key)
        t = _when(stamps.get("spreads_h1")) if stamps.get("spreads_h1") else None
        if t is not None:
            ages[key] = round((fetched_at - t).total_seconds() / 60.0, 1)
    laddered = [r for r in rows if r["market"] != "h2h_h1"]
    main, alt = split_main_rungs(laddered)
    main = [r for r in rows if r["market"] == "h2h_h1"] + main
    return main, alt, ages, markets


# ── the fetch ────────────────────────────────────────────────────────────────

def _billed(before: dict | None) -> float | None:
    """The x-requests-last of the call just made, None when it recorded none."""
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
    """(newest recorded balance, the floor, why). The floor is RESERVE_DAYS of
    the platform's measured median daily burn; 0 when no burn is on record."""
    left = odds_quota.latest_remaining(conn)
    burn = odds_quota.daily_burn(conn)
    days = reserve_days()
    floor = int(burn * days) if burn else 0
    why = (f"balance {left if left is not None else 'unknown'}, floor {floor:,} = {days:g} day(s) "
           f"of the measured burn ({burn if burn is not None else 'not on record'}/day)")
    return left, floor, why


def fetch_first_half(game_ids, conn=None, now: datetime | None = None) -> dict:
    """Fetch and store the first-half lines of exactly `game_ids` (one event
    call each, the ledger written beside every call), the decision fetches
    first. -> a summary: the games fetched, rows stored, and the games whose
    call failed (`failed`, which the window script turns into exit 1)."""
    ids = sorted(set(game_ids))
    out = {"asked": ids, "not_in_games": [], "started": [], "fetched": [], "rows": 0,
           "main_rows": 0, "no_first_half": [], "failed": [], "credits": {}, "marks": {}}
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
        if out["not_in_games"]:
            logger.warning(f"NCAAB first half: not in games, not fetched: {out['not_in_games']}")
        now = now or datetime.now(timezone.utc)
        last = last_fetches(conn, sorted(games))
        tried = last_fetches(conn, sorted(games), ok_only=False)
        marks = {}
        for gid, g in games.items():
            if g["tip"] is None or g["tip"] - LAST_CALL_LEAD <= now:
                out["started"].append(gid)
                continue
            due = due_mark(g["game_date"], g["tip"], now, last.get(gid), tried.get(gid))
            marks[gid] = due[0] if due else "manual"
        out["marks"] = marks
        if out["started"]:
            logger.warning(f"NCAAB first half: tipped or about to, not fetched: {out['started']}")
        if not marks:
            return out

        left, floor, why = balance_floor(conn)
        # Both reads swallow their own failure; end the read transaction so a
        # failed one cannot leave it aborted for the reads after it.
        conn.rollback()
        logger.info(f"NCAAB first half: {why}")
        if left is not None and floor and left < floor:
            asked = datetime.now(timezone.utc)
            for gid in sorted(marks):
                _ledger_row(conn, asked, EVENT_ODDS, marks[gid], game_id=gid, ok=False,
                            detail=f"not bought: {why}")
            conn.commit()
            out["failed"] = sorted(marks)
            out["refused"] = why
            logger.error(f"NCAAB first half: nothing bought, the balance is under its floor: {why}")
            return out

        resolver = ncaab_teams.make_resolver(conn, now.astimezone(_ET).date().isoformat(),
                                             days_back=1, days_fwd=2)
        # End the reads before the first call: created_at (and fetch_at) is
        # now() at the start of a transaction, and an open one would date
        # every row to before its fetch.
        conn.rollback()

        asked = datetime.now(timezone.utc)
        before = odds_quota.latest()
        try:
            events, err = _list_events(SPORT_KEY), None
        except Exception as exc:  # noqa: BLE001 - recorded, and every game fails below
            events, err = [], f"event list failed: {exc!r}"
        credits = _billed(before)
        out["credits"]["events"] = credits
        _ledger_row(conn, asked, EVENTS, None, ok=err is None, rows_stored=len(events),
                    credits=credits, detail=err or f"{len(events)} events listed")
        conn.commit()
        if resolver is None and err is None:
            err = "no schedule resolver (team registry or schedule window empty)"
        by_game: dict[str, tuple[str, bool, dict]] = {}
        for ev in events or []:
            hit = resolver(ev.get("home_team") or "", ev.get("away_team") or "",
                           ev.get("commence_time")) if resolver else None
            if hit and hit[0] in marks and ev.get("id"):
                by_game[hit[0]] = (str(ev["id"]), bool(hit[1]), ev)

        # The decision fetches first, then by tip: on a dense slate the call a
        # card decides on is never queued behind a history fetch.
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
                logger.error(f"NCAAB first half: {gid}: {err or 'not in the event list'}; "
                             f"nothing bought")
                continue
            ev_id, flipped, ev = hit
            if games[gid]["tip"] - LAST_CALL_LEAD <= asked:
                out["started"].append(gid)
                continue
            home_name, away_name = ev.get("home_team") or "", ev.get("away_team") or ""
            if flipped:
                # the feed called ESPN's away team home: parse in ESPN's orientation
                home_name, away_name = away_name, home_name
            before = odds_quota.latest()
            try:
                body = _get_event_odds(SPORT_KEY, ev_id, API_MARKETS)
            except Exception as exc:  # noqa: BLE001 - one game's failure is its own
                credits = _billed(before)
                _ledger_row(conn, asked, EVENT_ODDS, mark, game_id=gid, event_id=ev_id,
                            ok=False, credits=credits, detail=f"call failed: {exc!r}")
                conn.commit()
                out["failed"].append(gid)
                out["credits"][gid] = credits
                logger.error(f"NCAAB first half: {gid}: call failed: {exc!r}")
                continue
            credits = _billed(before)
            out["credits"][gid] = credits
            if body is None:
                # _get_event_odds returns None for an HTTP 404 or 422: refused,
                # which is not the books offering nothing (a 200 with no
                # bookmakers). It fails, and the next tick asks again.
                _ledger_row(conn, asked, EVENT_ODDS, mark, game_id=gid, event_id=ev_id,
                            ok=False, credits=credits, detail="HTTP 404 or 422: no body")
                conn.commit()
                out["failed"].append(gid)
                logger.error(f"NCAAB first half: {gid}: HTTP 404 or 422 for event {ev_id}")
                continue
            main, alt, ages, mkts = event_rows(body, gid, home_name, away_name,
                                               datetime.now(timezone.utc))
            rows = main + alt
            books = {r["bookmaker"] for r in rows}
            try:
                if rows:
                    _insert_odds(conn, rows)
                _ledger_row(conn, asked, EVENT_ODDS, mark, game_id=gid, event_id=ev_id,
                            ok=True, rows_stored=len(rows), main_rows=len(main), markets=mkts,
                            books=books, ages=ages, credits=credits,
                            detail="flipped" if flipped else None)
                conn.commit()            # per game: one failure cannot unwrite the rest
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                _ledger_row(conn, asked, EVENT_ODDS, mark, game_id=gid, event_id=ev_id,
                            ok=False, credits=credits, detail=f"store failed: {exc!r}")
                conn.commit()
                out["failed"].append(gid)
                logger.error(f"NCAAB first half: {gid}: store failed: {exc!r}")
                continue
            out["fetched"].append(gid)
            out["rows"] += len(rows)
            out["main_rows"] += len(main)
            if "spreads_h1" not in mkts:
                out["no_first_half"].append(gid)
            logger.info(f"  {gid} [{mark}]: {len(main)} main + {len(alt)} alternate rows, "
                        f"markets {sorted(mkts)}, {len(books)} books, x-requests-last {credits}, "
                        f"spread ages (min) {ages}")
        return out
    finally:
        try:
            persist_quota(conn)
        finally:
            if own:
                conn.close()
