"""Alternate spreads and totals for upcoming games: one per-event Odds API call
per game, once a day, so the betslip's edit sheet can offer more than the one
number each book hangs (mobile/src/lib/lineLegs.ts gameEditMenu).

Matt, 2026-10-29: "yes" to fetching alternate spreads and totals once a day,
after the cost was put to him as an estimate (~2-4 credits per game per fetch,
~160 upcoming games). The estimate was not a measurement, so this feed MEASURES:
every call's x-requests-last lands in the ledger (alt_game_line_fetches,
credits_last), and the first worker run is the real number.

WHY A FETCH OF ITS OWN. Alternate markets are "additional markets": the bulk
odds endpoint never returns them, only the per-event endpoint does
(odds_ingestor._get_event_odds). And `_process_events` stores one row per
(book, market), while a ladder is many rungs per book. Measured 2026-10-29: no
game after 2026-10-01 had an alternate_spreads / alternate_totals row; upcoming
games carried 1-2 main numbers across all books (NBA spreads 1.37 on average,
23 of 30 games with one).

WHAT ONE RUN STORES, per game starting within LOOKAHEAD_DAYS that is already in
`games` (odds has a foreign key to it):
  * every rung each line-shop book posts, in `odds` (the system of record),
    market alternate_spreads (spread_home = the HOME number, CLAUDE.md §4, both
    prices) or alternate_totals (both prices at one total), snapshot_type
    'open', source = SOURCE. A rung missing a side is not stored.
  * the same rungs in alt_game_lines, the CURRENT ladder: that game's rows are
    replaced in the same transaction. `latest_odds` is keyed (game, market,
    book), so it would keep one arbitrary rung per book; the app reads this
    table instead (data/migrations/add_alt_game_lines_2026_10_29.sql).
  * one ledger row per call (the event list, and each game's event call):
    ok, rows stored, books, credits_last, detail.

SOURCE is in data/prune_odds.PROTECTED_SOURCES: the pruner keeps one row per
(game, market, book), which would thin a paid ladder to an arbitrary rung.

EVERY PASS TOO (Matt, 2026-10-29, option B). The refresh pass's odds step
buys the same markets for games starting in the next 24 hours
(odds_ingestor._fetch_alternate_game_lines) and hands them to
store_pass_ladders, which replaces those games' rows here and ledgers the
pass (endpoint 'pass'). This daily run is the 3-day look-ahead.

COST BOUND. One call per game in the window, nothing else; a game that has
started is never fetched. There is no credit ceiling constant here on purpose:
a ceiling not derived from a measurement is decoration (.claude/rules/
operations.md). The ledger is the measurement; a ceiling can be set from it.

    python -m data.ingestors.alt_game_lines              # all sports, 3 days
    python -m data.ingestors.alt_game_lines --sport NBA
    python -m data.ingestors.alt_game_lines --plan       # list games, buy nothing
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from loguru import logger

from config import LINE_SHOP_BOOKMAKERS
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.ingestors import odds_quota
from data.ingestors.odds_ingestor import (REQUEST_SLEEP, RESOLVE_ONLY_SPORTS, SPORT_KEYS,
                                          _build_game_id, _get_event_odds, _insert_odds,
                                          _list_events, _name_key, _normalize_team,
                                          _schedule_resolver)

ET = ZoneInfo("America/New_York")
SOURCE = "odds_api_alt_game_lines_live"
API_MARKETS = ("alternate_spreads", "alternate_totals")
# Every sport with game spreads and totals. UFC has neither.
SPORTS = ("NFL", "NCAAF", "NBA", "NHL", "MLB", "WNBA", "NCAAB")
LOOKAHEAD_DAYS = 3
STATE_TABLE = "alt_game_lines"

_ODDS_KEYS = ("game_id", "sport", "market", "bookmaker", "snapshot_type", "snapshot_at",
              "home_price", "away_price", "draw_price", "spread_home", "total_line",
              "over_price", "under_price", "home_link", "away_link", "draw_link",
              "over_link", "under_link", "home_sid", "away_sid", "draw_sid",
              "over_sid", "under_sid", "source")

# ── the ledger (worker-only) ─────────────────────────────────────────────────
LEDGER_TABLE = "alt_game_line_fetches"
LEDGER_COLS = ("requested_at", "fetch_at", "sport", "endpoint", "game_id", "event_id", "ok",
               "rows_stored", "books", "credits_last", "detail")
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS alt_game_line_fetches (
    requested_at  TIMESTAMPTZ NOT NULL,
    fetch_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sport         TEXT NOT NULL,
    endpoint      TEXT NOT NULL,
    game_id       TEXT,
    event_id      TEXT,
    ok            BOOLEAN NOT NULL,
    rows_stored   INTEGER NOT NULL DEFAULT 0,
    books         TEXT,
    credits_last  REAL,
    detail        TEXT
)
"""
_INSERT_LEDGER = (
    "INSERT INTO alt_game_line_fetches (requested_at, sport, endpoint, game_id, event_id, ok, "
    "rows_stored, books, credits_last, detail) VALUES (%(requested_at)s, %(sport)s, "
    "%(endpoint)s, %(game_id)s, %(event_id)s, %(ok)s, %(rows_stored)s, %(books)s, "
    "%(credits_last)s, %(detail)s)")
EVENTS, EVENT_ODDS = "events", "event_odds"


def ensure_ledger(conn) -> None:
    """Create the ledger once, locked down; a catalog read after that
    (data/ddl_guard.schema_is_current)."""
    if schema_is_current(conn, LEDGER_TABLE, columns=LEDGER_COLS,
                         rls=True, revoked_from=API_ROLES):
        return
    conn.execute(LEDGER_DDL)
    lock_down(conn, LEDGER_TABLE)
    conn.commit()


def _ledger(conn, requested_at: datetime, sport: str, endpoint: str, *, ok: bool,
            game_id: str | None = None, event_id: str | None = None, rows_stored: int = 0,
            books=(), credits: float | None = None, detail: str | None = None) -> None:
    conn.execute(_INSERT_LEDGER, {
        "requested_at": requested_at, "sport": sport, "endpoint": endpoint,
        "game_id": game_id, "event_id": event_id, "ok": ok, "rows_stored": rows_stored,
        "books": ",".join(sorted(books)) or None, "credits_last": credits,
        "detail": (detail or None) and detail[:500]})


def _state_table_exists(conn) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' "
        "AND table_name = %s", (STATE_TABLE,)).fetchone())


# ── parsing ──────────────────────────────────────────────────────────────────

def parse_ladder(book_markets: list[dict], home_name: str) -> list[dict]:
    """One book's markets -> one odds-shaped dict per rung.

    alternate_spreads: the home outcome at point p pairs with the away outcome
    at -p, stored as spread_home = p with both prices and links.
    alternate_totals: over and under at one total. A rung missing either side
    is not stored (it cannot be a two-way line). The rung's snapshot_at is its
    market's own last_update. nba_odds_history.parse_alternates, with links
    and sids kept, for every sport."""
    rows: list[dict] = []
    hkey = _name_key(home_name)
    for m in book_markets:
        key, outs = m.get("key"), m.get("outcomes") or []
        stamp = m.get("last_update")
        if key == "alternate_spreads":
            home_at: dict[float, dict] = {}
            away_at: dict[float, dict] = {}
            for o in outs:
                if o.get("point") is None or o.get("price") is None:
                    continue
                side = home_at if _name_key(o.get("name") or "") == hkey else away_at
                side[float(o["point"])] = o
            for p, h in home_at.items():
                a = away_at.get(-p)
                if a is None:
                    continue
                rows.append({"market": key, "spread_home": p,
                             "home_price": h["price"], "away_price": a["price"],
                             "home_link": h.get("link"), "away_link": a.get("link"),
                             "home_sid": h.get("sid"), "away_sid": a.get("sid"),
                             "snapshot_at": stamp})
        elif key == "alternate_totals":
            slots: dict[float, dict] = {}
            for o in outs:
                side = (o.get("name") or "").lower()
                if side in ("over", "under") and o.get("point") is not None \
                        and o.get("price") is not None:
                    slots.setdefault(float(o["point"]), {})[side] = o
            for pt, s in slots.items():
                if "over" in s and "under" in s:
                    rows.append({"market": key, "total_line": pt,
                                 "over_price": s["over"]["price"],
                                 "under_price": s["under"]["price"],
                                 "over_link": s["over"].get("link"),
                                 "under_link": s["under"].get("link"),
                                 "over_sid": s["over"].get("sid"),
                                 "under_sid": s["under"].get("sid"),
                                 "snapshot_at": stamp})
    return rows


def event_rows(body: dict | None, game_id: str, sport: str, home_name: str,
               fetched_at: datetime) -> list[dict]:
    """One event response -> full odds rows for the line-shop books."""
    out: list[dict] = []
    fallback = fetched_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for book in (body or {}).get("bookmakers") or []:
        key = book.get("key")
        if key not in LINE_SHOP_BOOKMAKERS:
            continue
        for rung in parse_ladder(book.get("markets") or [], home_name):
            row = dict.fromkeys(_ODDS_KEYS)
            row.update(rung)
            row.update({"game_id": game_id, "sport": sport, "bookmaker": key,
                        "snapshot_type": "open", "source": SOURCE,
                        "snapshot_at": rung.get("snapshot_at") or book.get("last_update")
                        or fallback})
            out.append(row)
    return out


# ── which games ──────────────────────────────────────────────────────────────

def _when(stamp) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def in_window(ev: dict, now: datetime, days: int = LOOKAHEAD_DAYS) -> bool:
    """Not started, and starting within `days`. Fails CLOSED on a missing or
    unparseable start: unlike a board refresh, this buys a call per game, and a
    game we cannot date is one we cannot bound."""
    t = _when(ev.get("commence_time"))
    return t is not None and now < t <= now + timedelta(days=days)


def game_for_event(sport: str, ev: dict, resolve=None) -> tuple[str, str] | None:
    """(game_id, the feed's name for the schedule's HOME team), or None.

    The same id the live odds pass gives the event (odds_ingestor
    ._process_events): a resolver-backed sport asks the schedule, flipping
    home/away when the feed has them reversed; every other sport builds the
    id from the Eastern date and the two normalized teams."""
    home_name, away_name = ev.get("home_team") or "", ev.get("away_team") or ""
    start = _when(ev.get("commence_time"))
    if start is None or not home_name or not away_name:
        return None
    if resolve is not None:
        hit = resolve(home_name, away_name, ev.get("commence_time"))
        if isinstance(hit, tuple):
            gid, flipped = hit
        else:
            gid, flipped = hit, False
        if not gid:
            return None
        return gid, (away_name if flipped else home_name)
    if sport in RESOLVE_ONLY_SPORTS:
        return None   # never mint an id for a schedule-resolved sport
    gid = _build_game_id(sport, start.astimezone(ET).strftime("%Y-%m-%d"),
                         _normalize_team(away_name, sport), _normalize_team(home_name, sport))
    return gid, home_name


def _known_games(conn, sport: str, game_ids: list[str]) -> dict[str, str]:
    """{game_id: game_date} for the ids already in `games`."""
    if not game_ids:
        return {}
    rows = conn.execute("SELECT game_id, game_date FROM games WHERE sport = %s AND game_id = ANY(%s)",
                        (sport, list(game_ids))).fetchall()
    return {r[0]: str(r[1]) for r in rows}


# ── the run ──────────────────────────────────────────────────────────────────

def _billed(before: dict | None) -> float | None:
    after = odds_quota.latest()
    if after is None or after is before:
        return None
    return after.get("last")


def _replace_state(conn, game_id: str, game_date: str, rows: list[dict]) -> None:
    """This game's current ladder becomes `rows` (same transaction as the
    odds insert, so the app never reads half a ladder)."""
    conn.execute(f"DELETE FROM {STATE_TABLE} WHERE game_id = %s", (game_id,))
    if not rows:
        return
    conn.executemany(f"""
        INSERT INTO {STATE_TABLE} (game_id, game_date, sport, market, bookmaker, point,
            spread_home, total_line, home_price, away_price, over_price, under_price,
            home_link, away_link, over_link, under_link, snapshot_at)
        VALUES (%(game_id)s, %(game_date)s, %(sport)s, %(market)s, %(bookmaker)s, %(point)s,
            %(spread_home)s, %(total_line)s, %(home_price)s, %(away_price)s,
            %(over_price)s, %(under_price)s, %(home_link)s, %(away_link)s,
            %(over_link)s, %(under_link)s, %(snapshot_at)s)
        ON CONFLICT (game_id, market, bookmaker, point) DO NOTHING
    """, [{**r, "game_date": game_date,
           "point": r["spread_home"] if r["market"] == "alternate_spreads" else r["total_line"]}
          for r in rows])


def store_pass_ladders(conn, sport: str, rows: list[dict], meter: dict | None,
                       asked_at: datetime) -> dict:
    """The refresh pass's half (option B, Matt 2026-10-29: every pass, games in
    the next 24 hours). The pass has already written `rows` to `odds`
    (odds_ingestor._fetch_alternate_game_lines); this replaces those games'
    ladders in alt_game_lines, which the app reads, and writes one ledger row
    for the pass with the credits the feed reported.

    Runs inside a SAVEPOINT on the pass's own connection: a failure here rolls
    back only this, never the pass's main odds rows, and is logged, not
    raised. A game the pass bought nothing for keeps its daily ladder (whose
    rows say how old they are)."""
    out = {"games": 0, "rows": 0}
    meter = meter or {}
    if not rows and not meter.get("calls"):
        return out
    try:
        # Before the savepoint: the first call creates the ledger and commits,
        # which would end a savepoint opened first. After that it is a
        # catalog read.
        ensure_ledger(conn)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"{sport} alt ledger unavailable: {exc!r}")
        return out
    try:
        conn.execute("SAVEPOINT alt_pass_ladders")
        if not _state_table_exists(conn):
            conn.execute("RELEASE SAVEPOINT alt_pass_ladders")
            return out
        by_game: dict[str, list[dict]] = {}
        for r in rows:
            if r.get("market") in API_MARKETS:
                by_game.setdefault(r["game_id"], []).append(r)
        dates = {}
        if by_game:
            dates = {gid: str(gd) for gid, gd in conn.execute(
                "SELECT game_id, game_date FROM games WHERE game_id = ANY(%s)",
                (list(by_game),)).fetchall()}
        for gid, game_rows in by_game.items():
            if gid not in dates:
                continue
            _replace_state(conn, gid, dates[gid], game_rows)
            out["games"] += 1
            out["rows"] += len(game_rows)
        _ledger(conn, asked_at, sport, "pass", ok=True, rows_stored=out["rows"],
                books={r["bookmaker"] for r in rows}, credits=meter.get("credits"),
                detail=f"{meter.get('calls', 0)} calls, {out['games']} games, "
                       f"{meter.get('unreported', 0)} calls with no credit header")
        conn.execute("RELEASE SAVEPOINT alt_pass_ladders")
    except Exception as exc:  # noqa: BLE001 - never takes the pass's odds down
        try:
            conn.execute("ROLLBACK TO SAVEPOINT alt_pass_ladders")
        except Exception:  # noqa: BLE001
            pass
        logger.warning(f"{sport} alt ladder refresh failed (main odds kept): {exc!r}")
    return out


def plan(conn, sports=SPORTS, days: int = LOOKAHEAD_DAYS, now: datetime | None = None
         ) -> dict[str, list[tuple[str, str, str, str]]]:
    """{sport: [(game_id, event_id, home_name, game_date), ...]} that a run would buy.
    Listing events is a call, recorded in the ledger by `run`; `plan` alone
    records nothing."""
    now = now or datetime.now(timezone.utc)
    out: dict[str, list[tuple[str, str, str]]] = {}
    for sport in sports:
        events = [ev for ev in _list_events(SPORT_KEYS[sport]) if in_window(ev, now, days)]
        out[sport] = _match(conn, sport, events, now)
    return out


def _match(conn, sport: str, events: list[dict], now: datetime) -> list[tuple[str, str, str, str]]:
    resolve = _schedule_resolver(sport, conn, now.astimezone(ET).strftime("%Y-%m-%d"))
    if sport in RESOLVE_ONLY_SPORTS and resolve is None:
        logger.warning(f"{sport} alt lines: no schedule resolver; skipped")
        return []
    cand: dict[str, tuple[str, str]] = {}
    for ev in events:
        hit = game_for_event(sport, ev, resolve)
        if hit and ev.get("id"):
            cand[hit[0]] = (ev["id"], hit[1])
    known = _known_games(conn, sport, list(cand))
    return [(gid, cand[gid][0], cand[gid][1], known[gid]) for gid in sorted(known)]


def run(sports=SPORTS, days: int = LOOKAHEAD_DAYS, conn=None) -> dict:
    """Fetch and store the alternate ladders of every game in the window.
    -> a summary per sport: games bought, rows stored, failures, and the
    credits the feed reported."""
    out: dict = {"sports": {}, "rows": 0, "games": 0, "failed": 0, "credits": 0.0,
                 "credits_unreported": 0}
    own = conn is None
    if own:
        from data.db import get_connection
        conn = get_connection()
    try:
        ensure_ledger(conn)
        if not _state_table_exists(conn):
            logger.warning(f"{STATE_TABLE} does not exist yet "
                           f"(add_alt_game_lines_2026_10_29.sql); nothing bought")
            out["skipped"] = "no state table"
            return out
        conn.commit()
        now = datetime.now(timezone.utc)
        # Ladders for games that started more than a day ago are not shown
        # anywhere; the odds rows keep the history.
        # Keyed on game_date (ISO text): commence_time arrives in mixed shapes.
        conn.execute(f"""DELETE FROM {STATE_TABLE} a USING games g
                         WHERE g.game_id = a.game_id AND g.game_date < %s""",
                     ((now.astimezone(ET) - timedelta(days=1)).strftime("%Y-%m-%d"),))
        conn.commit()
        for sport in sports:
            s = {"games": 0, "rows": 0, "failed": [], "credits": {}}
            out["sports"][sport] = s
            asked = datetime.now(timezone.utc)
            before = odds_quota.latest()
            try:
                events, why = _list_events(SPORT_KEYS[sport]), None
            except Exception as exc:  # noqa: BLE001 - recorded; the sport is skipped
                events, why = [], f"event list failed: {exc!r}"
            credits = _billed(before)
            near = [ev for ev in events if in_window(ev, now, days)]
            _ledger(conn, asked, sport, EVENTS, ok=why is None, rows_stored=len(near),
                    credits=credits, detail=why or f"{len(events)} listed, {len(near)} in window")
            conn.commit()
            if why:
                logger.error(f"{sport} alt lines: {why}")
                continue
            games = _match(conn, sport, near, now)
            conn.rollback()   # end the read: created_at is now() at transaction start
            for gid, ev_id, home_name, game_date in games:
                asked = datetime.now(timezone.utc)
                before = odds_quota.latest()
                try:
                    body = _get_event_odds(SPORT_KEYS[sport], ev_id, list(API_MARKETS))
                except Exception as exc:  # noqa: BLE001 - one game's failure is its own
                    credits = _billed(before)
                    _ledger(conn, asked, sport, EVENT_ODDS, game_id=gid, event_id=ev_id,
                            ok=False, credits=credits, detail=f"call failed: {exc!r}")
                    conn.commit()
                    s["failed"].append(gid)
                    continue
                credits = _billed(before)
                s["credits"][gid] = credits
                if credits is None:
                    out["credits_unreported"] += 1
                else:
                    out["credits"] += credits
                if body is None:
                    _ledger(conn, asked, sport, EVENT_ODDS, game_id=gid, event_id=ev_id,
                            ok=False, credits=credits, detail="HTTP 404 or 422: no body")
                    conn.commit()
                    s["failed"].append(gid)
                    continue
                rows = event_rows(body, gid, sport, home_name, datetime.now(timezone.utc))
                books = {r["bookmaker"] for r in rows}
                try:
                    if rows:
                        _insert_odds(conn, rows)
                    _replace_state(conn, gid, game_date, rows)
                    _ledger(conn, asked, sport, EVENT_ODDS, game_id=gid, event_id=ev_id,
                            ok=True, rows_stored=len(rows), books=books, credits=credits)
                    conn.commit()        # per game: one failure cannot unwrite the rest
                except Exception as exc:  # noqa: BLE001
                    conn.rollback()
                    _ledger(conn, asked, sport, EVENT_ODDS, game_id=gid, event_id=ev_id,
                            ok=False, credits=credits, detail=f"store failed: {exc!r}")
                    conn.commit()
                    s["failed"].append(gid)
                    continue
                s["games"] += 1
                s["rows"] += len(rows)
                time.sleep(REQUEST_SLEEP)
            out["games"] += s["games"]
            out["rows"] += s["rows"]
            out["failed"] += len(s["failed"])
            logger.info(f"{sport} alt lines: {s['games']} games, {s['rows']} rungs, "
                        f"{len(s['failed'])} failed")
        return out
    finally:
        if own:
            conn.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sport", action="append", choices=SPORTS)
    ap.add_argument("--days", type=int, default=LOOKAHEAD_DAYS)
    ap.add_argument("--plan", action="store_true", help="list the games; buy nothing")
    args = ap.parse_args(argv)
    sports = tuple(args.sport or SPORTS)
    if args.plan:
        from data.db import get_connection
        conn = get_connection()
        try:
            print(json.dumps({k: len(v) for k, v in plan(conn, sports, args.days).items()}))
        finally:
            conn.close()
        return 0
    summary = run(sports, args.days)
    print(json.dumps({k: v for k, v in summary.items() if k != "sports"}))
    return 1 if summary.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
