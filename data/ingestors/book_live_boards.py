"""Every other sportsbook's own live page, read from mike's machine beside
DraftKings' board (data/ingestors/dk_live_board.py), into Supabase.

mike, 2026-11-25: "yes do it for all books" (after "why not FanDuel, mgm etc").
The odds feed carries FanDuel, BetMGM, Caesars and the rest in play, but a
live game's row per book is a median of about 10 minutes old (NBA in-play
spreads, 2026-11-22..25). A book's own page is the number it is offering now.

RUNS ON MIKE'S MACHINE, IN DRAFTKINGS' BOARD PROCESS, ON ITS OWN THREAD.
These books refuse a datacentre address (docs/live_odds_freshness.md sections
7-8, measured 2026-08-31) and the scheduled task there already relaunches the
board on every merge that changes FEED_FILES. The thread has its own HTTP
sessions and its own database connection, never shares the board's request
pacing, and catches everything: nothing here can delay or stop a DraftKings
read, which the NCAAB in-play models decide on. BOOK_LIVE_BOARDS=0 turns it off.

WHAT EACH BOOK IS, AND WHAT IS KNOWN ABOUT IT. Every endpoint below is what
the book's own website calls, taken from open-source scrapers (named per
book); none is documented by the book, none was reachable from a Claude
session to check (DraftKings, the books and the proxy all refuse it), and any
can change. So a book is one of two kinds:
  * PARSED: its answer's shape was seen in a real capture, and its live main
    lines go to `odds` as in-play rows (source '<book>_board'). FanDuel.
  * CAPTURED: the answer is stored raw in `book_live_raw` and nothing is parsed
    until a stored answer shows the shape. BetMGM, BetRivers, Caesars, and the
    Fanatics and Hard Rock home pages (no endpoint is known for either; the
    page names the hosts its scripts call).
Every read, either kind, upserts `book_live_feed` (book, sport): when it last
answered, its HTTP status, and how many live games it listed and placed on our
games rows. A refusal, a bot challenge or a wrong guess is a row there, never
a crash and never a retry storm: a refused book backs off.

NO BOT-WALL WORK. A request is a plain HTTPS GET in a browser's TLS shape (the
same client DraftKings' board uses), at most one per book and sport every
BOOK_POLL_SEC. A book that answers with a challenge page is recorded as
refused and left alone.

NOT NCAAF, NOT MLB (dk_live_board.ODDS_LOG_SPORTS). Both sports' live picks
are stamped off the newest in-play `odds` row per book
(models.scorer._best_live_price), so a new writer for any book would move the
price a live pick is stamped at. No other decision reads another book's
in-play rows (checked 2026-11-25).

    python -m data.ingestors.book_live_boards --once --dry-run   # one pass, print, write nothing
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

log = logging.getLogger("data.ingestors.book_live_boards")

STATE = os.environ.get("BOOK_LIVE_STATE", "oh")      # DraftKings' board reads dkusoh
POLL_SEC = float(os.environ.get("BOOK_POLL_SEC", "30"))
DISCOVER_SEC = 6 * 3600.0                            # a home page, for its API hosts
BACKOFF_SEC = 600.0                                  # after REFUSALS_BEFORE_BACKOFF refusals
REFUSALS_BEFORE_BACKOFF = 3
CAPTURES_PER_DAY = int(os.environ.get("BOOK_CAPTURES_PER_DAY", "3"))
RESOLVER_REFRESH_SEC = 600.0
MAX_BODY_TEXT = 200_000

RAW_TABLE = "book_live_raw"
RAW_COLS = ("fetched_at", "book", "sport", "url", "status", "bytes", "payload", "body")
RAW_DDL = """
CREATE TABLE IF NOT EXISTS book_live_raw (
    fetched_at  TIMESTAMPTZ NOT NULL,
    book        TEXT NOT NULL,
    sport       TEXT NOT NULL,
    url         TEXT NOT NULL,
    status      INTEGER NOT NULL,
    bytes       INTEGER NOT NULL,
    payload     JSONB,
    body        TEXT,
    PRIMARY KEY (fetched_at, book, sport)
)
"""
FEED_TABLE = "book_live_feed"
FEED_COLS = ("book", "sport", "last_read_at", "ok", "status", "live_events", "matched", "written", "detail")
FEED_DDL = """
CREATE TABLE IF NOT EXISTS book_live_feed (
    book          TEXT NOT NULL,
    sport         TEXT NOT NULL,
    last_read_at  TIMESTAMPTZ NOT NULL,
    ok            BOOLEAN NOT NULL,
    status        INTEGER,
    live_events   INTEGER NOT NULL DEFAULT 0,
    matched       INTEGER NOT NULL DEFAULT 0,
    written       INTEGER NOT NULL DEFAULT 0,
    detail        TEXT,
    PRIMARY KEY (book, sport)
)
"""

# The query values a stored URL leaves out: public web keys, but keys.
_KEY_PARAMS = ("_ak", "x-bwin-accessid")


# ── FanDuel: PARSED ───────────────────────────────────────────────────────────
#
# sbapi.<state>.sportsbook.fanduel.com/api/content-managed-page, the call the
# league page makes (jbarkie/fanduel-mcp, jackrekrutiak/nfl-odds-board and
# DionHuang06/Oddiqo all use it). `_ak` is the public application key the site
# sends logged out; the three projects carry the same value. One answer holds
# every game on the league page, pre-game and in play: a capture of the NBA
# page recorded 2026-11-23 01:17Z held 31 events and 93 markets, 9 games with
# their moneyline, spread and total marked inPlay. A market: marketType,
# inPlay, marketStatus, eventId, runners[]; a runner: result.type HOME / AWAY /
# OVER / UNDER, handicap (that runner's own number), runnerStatus, and
# winRunnerOdds.americanDisplayOdds.americanOddsInt. Events: name "Away @
# Home", openDate. The page is served through a cache (max-age 30 reported by
# the projects), so a read can be up to that much behind the book.

FANDUEL_AK = os.environ.get("FANDUEL_AK", "FhMFpcPWXMeyZxOx")
FANDUEL_PAGES = {"NBA": "nba", "NFL": "nfl", "NHL": "nhl", "NCAAB": "ncaab", "NCAABW": "wncaab",
                 "EUROLEAGUE": "euroleague"}
# Seen in the NBA capture: MONEY_LINE, MATCH_HANDICAP_(2-WAY),
# TOTAL_POINTS_(OVER/UNDER). The hockey names are not yet seen; a market type
# not listed is no line (its answer is captured, so the next change can add it).
FANDUEL_TYPES = {"MONEY_LINE": "h2h", "MATCH_HANDICAP_(2-WAY)": "spreads", "PUCK_LINE": "spreads",
                 "TOTAL_POINTS_(OVER/UNDER)": "totals", "TOTAL_GOALS_(OVER/UNDER)": "totals"}


@dataclass
class BookEvent:
    """One live game on a book's page, on THE BOOK'S sides."""
    event_id: str
    name: str
    start: str | None
    home_name: str
    away_name: str
    spread_home: float | None = None
    spread_home_price: float | None = None
    spread_away_price: float | None = None
    total_line: float | None = None
    over_price: float | None = None
    under_price: float | None = None
    home_ml: float | None = None
    away_ml: float | None = None


def _price(runner: dict) -> float | None:
    v = (((runner.get("winRunnerOdds") or {}).get("americanDisplayOdds") or {}).get("americanOddsInt"))
    try:
        return None if v is None else float(int(v))
    except (TypeError, ValueError):
        return None


def parse_fanduel(body: dict) -> list[BookEvent]:
    """Every in-play game on one FanDuel league page, with its main lines.
    A market with more than one live market of its kind on the same game is
    left out (it is not knowable which one the page shows as main). Pure."""
    att = (body or {}).get("attachments") or {}
    events = att.get("events") or {}
    by_event: dict[str, dict[str, list[dict]]] = {}
    for m in (att.get("markets") or {}).values():
        kind = FANDUEL_TYPES.get(m.get("marketType"))
        if not kind or m.get("inPlay") is not True or m.get("marketStatus") != "OPEN":
            continue
        by_event.setdefault(str(m.get("eventId")), {}).setdefault(kind, []).append(m)
    out = []
    for eid, kinds in by_event.items():
        ev = events.get(eid) or {}
        names: dict[str, str] = {}
        row = {}
        for kind, markets in kinds.items():
            if len(markets) != 1:
                log.info("FanDuel event %s: %d live %s markets; none taken", eid, len(markets), kind)
                continue
            runners = {}
            for r in markets[0].get("runners") or []:
                side = str((r.get("result") or {}).get("type") or "").upper()
                if r.get("runnerStatus") == "ACTIVE" and side in ("HOME", "AWAY", "OVER", "UNDER"):
                    runners[side] = r
            if kind in ("h2h", "spreads"):
                h, a = runners.get("HOME"), runners.get("AWAY")
                if not h or not a or _price(h) is None or _price(a) is None:
                    continue
                names.setdefault("home", str(h.get("runnerName") or ""))
                names.setdefault("away", str(a.get("runnerName") or ""))
                if kind == "h2h":
                    row.update(home_ml=_price(h), away_ml=_price(a))
                else:
                    try:
                        line = float(h.get("handicap"))
                    except (TypeError, ValueError):
                        continue
                    row.update(spread_home=line, spread_home_price=_price(h), spread_away_price=_price(a))
            else:
                o, u = runners.get("OVER"), runners.get("UNDER")
                if not o or not u or _price(o) is None or _price(u) is None:
                    continue
                try:
                    line = float(o.get("handicap"))
                except (TypeError, ValueError):
                    continue
                row.update(total_line=line, over_price=_price(o), under_price=_price(u))
        if not row:
            continue
        home, away = names.get("home"), names.get("away")
        if not (home and away):
            n = str(ev.get("name") or "")
            if " @ " not in n:
                continue
            away, home = (s.strip() for s in n.split(" @ ", 1))
        out.append(BookEvent(event_id=eid, name=str(ev.get("name") or ""), start=ev.get("openDate"),
                             home_name=home, away_name=away, **row))
    return out


# ── The captured books ───────────────────────────────────────────────────────

# BetMGM: /cds-api/bettingoffer/fixtures, state=Live (MetaphorOS/
# Websocket_Sportsbook_Scraper research notes: sportIds 7 basketball, 11
# football; NBA competition 6004, NFL 35). The access id is the logged-out web
# value; two have been published (declanwalpole/sportsbook-odds-scraper, and
# the MetaphorOS notes for Ontario), and one was refused from mike's machine in
# August with "Access id is invalid". The notes also report the standalone
# request blocked; if it is, the status row says so.
BETMGM_ACCESS_IDS = tuple(v for v in os.environ.get(
    "BETMGM_ACCESS_IDS",
    "OTU4NDk3MzEtOTAyNS00MjQzLWIxNWEtNTI2MjdhNWM3Zjk3,ZjNmOGM4OTAtZmVhOS00ZTZiLWE5MDQtNGVjNWM5MDkxNjQ1",
).split(",") if v)
BETMGM_SPORT_IDS = {"NBA": "7", "NCAAB": "7", "NCAABW": "7", "EUROLEAGUE": "7", "NFL": "11", "NHL": "12"}

# BetRivers: <state>.betrivers.com/api/service/sportsbook/offering/listview/
# events (DionHuang06/Oddiqo: cageCode per state, NJ 2, Ontario 249; NBA
# groupId 1000093652; pageSize at most 20). The Ohio cage code is not
# published, so the state's home page is captured for it first.

# Caesars: api.americanwagering.com/regions/us/locations/<state>/brands/czr/
# sb/v3/... (declanwalpole/sportsbook-odds-scraper, events by id). The live
# list path is not published; this asks for the sport's schedule.
CAESARS_SPORTS = {"NBA": "basketball", "NCAAB": "basketball", "NCAABW": "basketball",
                  "EUROLEAGUE": "basketball", "NFL": "americanfootball", "NHL": "icehockey"}


@dataclass(frozen=True)
class Book:
    key: str                      # our bookmaker key (odds.bookmaker)
    sports: tuple[str, ...]       # the sports it is asked about while live
    url: Callable[[str], str | None]
    parse: Callable[[dict], list[BookEvent]] | None = None
    discover: bool = False        # a home page, read every DISCOVER_SEC, sport '*'


def _fanduel_url(sport: str) -> str | None:
    page = FANDUEL_PAGES.get(sport)
    if not page:
        return None
    return (f"https://sbapi.{STATE}.sportsbook.fanduel.com/api/content-managed-page"
            f"?page=CUSTOM&customPageId={page}&_ak={FANDUEL_AK}&timezone=America%2FNew_York")


def _betmgm_url(sport: str) -> str | None:
    sid = BETMGM_SPORT_IDS.get(sport)
    if not sid or not BETMGM_ACCESS_IDS:
        return None
    return (f"https://sports.{STATE}.betmgm.com/cds-api/bettingoffer/fixtures"
            f"?x-bwin-accessid={BETMGM_ACCESS_IDS[0]}&lang=en-us&country=US&userCountry=US"
            f"&subdivision=US-{STATE.upper()}&fixtureTypes=Standard&state=Live&offerMapping=Filtered"
            f"&offerCategories=Gridable&sportIds={sid}&skip=0&take=50")


def _caesars_url(sport: str) -> str | None:
    s = CAESARS_SPORTS.get(sport)
    if not s:
        return None
    return f"https://api.americanwagering.com/regions/us/locations/{STATE}/brands/czr/sb/v3/sports/{s}/events/schedule"


LIVE_SPORTS = ("NBA", "NFL", "NHL", "NCAAB", "NCAABW", "EUROLEAGUE")

BOOKS: tuple[Book, ...] = (
    Book("fanduel", tuple(s for s in LIVE_SPORTS if s in FANDUEL_PAGES), _fanduel_url, parse_fanduel),
    Book("betmgm", tuple(s for s in LIVE_SPORTS if s in BETMGM_SPORT_IDS), _betmgm_url),
    Book("williamhill_us", tuple(s for s in LIVE_SPORTS if s in CAESARS_SPORTS), _caesars_url),
    Book("betrivers", ("*",), lambda _s: f"https://{STATE}.betrivers.com/", discover=True),
    Book("fanatics", ("*",), lambda _s: "https://sportsbook.fanatics.com/", discover=True),
    Book("hardrockbet", ("*",), lambda _s: "https://app.hardrock.bet/", discover=True),
)


def stored_url(url: str) -> str:
    """The URL as stored: the public web keys taken out of the query."""
    for k in _KEY_PARAMS:
        url = re.sub(rf"([?&]){re.escape(k)}=[^&]*&?", r"\1", url)
    return url.rstrip("?&")


def is_challenge(status: int, text: str) -> bool:
    """A bot-wall answer: recorded as refused, never worked around."""
    head = (text or "")[:4000].lower()
    return status in (403, 429, 503) or "captcha" in head or "challenge-platform" in head \
        or "px-captcha" in head or "access denied" in head


# ── Writing ──────────────────────────────────────────────────────────────────

def ensure_tables(conn) -> None:
    from data.anon_readable import API_ROLES, lock_down
    from data.ddl_guard import schema_is_current
    if not schema_is_current(conn, RAW_TABLE, columns=RAW_COLS, rls=True, revoked_from=API_ROLES):
        conn.execute(RAW_DDL)
        lock_down(conn, RAW_TABLE)
    if not schema_is_current(conn, FEED_TABLE, columns=FEED_COLS, rls=True, revoked_from=API_ROLES):
        conn.execute(FEED_DDL)
        lock_down(conn, FEED_TABLE)
    conn.commit()


def _et_day(at: datetime) -> str:
    from zoneinfo import ZoneInfo
    return at.astimezone(ZoneInfo("America/New_York")).date().isoformat()


class Captures:
    """How many raw answers a (book, sport, status) has stored today: at most
    CAPTURES_PER_DAY, the first of each hour while live. Enough to write a
    parser from, without storing every answer of every live game."""

    def __init__(self, per_day: int = CAPTURES_PER_DAY):
        self.per_day = per_day
        self.seen: dict[tuple, list[datetime]] = {}

    def want(self, book: str, sport: str, status: int, at: datetime) -> bool:
        key = (book, sport, status // 100, _et_day(at))
        stamps = self.seen.setdefault(key, [])
        if len(stamps) >= self.per_day or (stamps and (at - stamps[-1]).total_seconds() < 3600):
            return False
        stamps.append(at)
        return True


def odds_rows(prev: dict | None, row: dict, sport: str, book: str) -> list[dict]:
    """The board's change-only `odds` rows for another book: dk_live_board's
    rule, with this book's key and source."""
    from data.ingestors import dk_live_board as B
    out = []
    for r in B.odds_rows(prev, row, sport):
        r["bookmaker"] = book
        r["source"] = f"{book}_board"
        out.append(r)
    return out


class BookFeeds:
    """One pass over every book: each live sport it carries, POLL_SEC apart."""

    def __init__(self, connect, live_sports: Callable[[], list[str]], *, session_factory=None,
                 resolvers=None, odds_log=None, clock=None, monotonic=time.monotonic, dry_run=False):
        self.connect, self.live_sports, self.dry_run = connect, live_sports, dry_run
        self.session_factory = session_factory or _session
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.monotonic = monotonic
        self.odds_log = odds_log
        if resolvers is None:
            from data.ingestors.dk_live_board import RESOLVERS
            resolvers = RESOLVERS
        self.resolver_factories = resolvers
        self.resolvers: dict[str, tuple[float, object]] = {}
        self.sessions: dict[str, object] = {}
        self.due: dict[tuple, float] = {}
        self.refusals: dict[str, int] = {}
        self.last: dict[tuple, dict] = {}          # (book, game_id) -> last row
        self.ids: dict[tuple, tuple | None] = {}   # (book, event_id) -> (game_id, flipped)
        self.captures = Captures()
        self.conn = None
        self.ready = False
        self.games_live: tuple[float, set] = (-1e9, set())

    def c(self):
        if self.conn is None:
            self.conn = self.connect()
        return self.conn

    def _recycle(self):
        try:
            if self.conn is not None:
                self.conn.close()
        except Exception:                 # noqa: BLE001
            pass
        self.conn = None

    def _resolver(self, sport: str):
        at, r = self.resolvers.get(sport, (-1e9, None))
        if r is None or self.monotonic() - at > RESOLVER_REFRESH_SEC:
            factory = self.resolver_factories.get(sport)
            r = factory(self.c()) if factory else None
            self.resolvers[sport] = (self.monotonic(), r)
        return r

    def _live_from_games(self) -> set:
        """Sports with a game on our schedule that has started and has no
        final score, re-read every minute: EuroLeague is asked about though
        DraftKings may not list it."""
        at, sports = self.games_live
        if self.dry_run or self.monotonic() - at < 60.0:
            return sports
        from config import live_slate_dates
        try:
            rows = self.c().execute("""
                SELECT DISTINCT sport FROM games
                 WHERE sport = ANY(%s) AND game_date::text = ANY(%s)
                   AND (home_score IS NULL OR away_score IS NULL)
                   AND commence_time::timestamptz <= now()
                   AND commence_time::timestamptz > now() - interval '4 hours'
            """, (list(LIVE_SPORTS), live_slate_dates())).fetchall()
            self.c().commit()
            sports = {str(r[0]) for r in rows}
        except Exception as exc:          # noqa: BLE001
            log.warning("live sports from games failed: %s", exc)
            self._recycle()
        self.games_live = (self.monotonic(), sports)
        return sports

    def pass_once(self) -> list[dict]:
        """Every read that is due now. Returns one result per read."""
        if not self.dry_run and not self.ready:
            ensure_tables(self.c())
            self.ready = True
        live = set(self.live_sports()) | self._live_from_games()
        now = self.monotonic()
        results = []
        for book in BOOKS:
            sports = ("*",) if book.discover else tuple(s for s in book.sports if s in live)
            for sport in sports:
                if book.discover and not live:
                    continue
                key = (book.key, sport)
                if now < self.due.get(key, 0.0):
                    continue
                gap = DISCOVER_SEC if book.discover else POLL_SEC
                self.due[key] = now + gap
                res = self.read(book, sport)
                if res.get("refused"):
                    self.refusals[book.key] = self.refusals.get(book.key, 0) + 1
                    if self.refusals[book.key] >= REFUSALS_BEFORE_BACKOFF:
                        log.warning("%s: %d refusals in a row - leaving it alone %.0f s",
                                    book.key, self.refusals[book.key], BACKOFF_SEC)
                        for k in list(self.due):
                            if k[0] == book.key:
                                self.due[k] = now + BACKOFF_SEC
                        self.due[key] = now + BACKOFF_SEC
                        self.refusals[book.key] = 0
                else:
                    self.refusals[book.key] = 0
                results.append(res)
        return results

    def read(self, book: Book, sport: str) -> dict:
        """One request. Never raises."""
        url = book.url(sport)
        if url is None:
            return {"book": book.key, "sport": sport, "ok": False, "detail": "no url"}
        sess = self.sessions.get(book.key)
        if sess is None:
            sess = self.sessions[book.key] = self.session_factory()
        at = self.clock()
        try:
            r = sess.get(url, timeout=15)
            status, text = int(r.status_code), r.text or ""
        except Exception as exc:          # noqa: BLE001
            return self._finish(book, sport, at, url, None, "", False, 0, 0, 0,
                                f"{type(exc).__name__}: {exc}"[:300])
        refused = is_challenge(status, text)
        body = None
        if status == 200 and not refused:
            try:
                body = json.loads(text)
            except ValueError:
                body = None
        live = matched = written = 0
        detail = "refused" if refused else ("" if status == 200 else f"HTTP {status}")
        if body is not None and book.parse is not None:
            try:
                live, matched, written = self._lines(book, sport, book.parse(body), at)
            except Exception as exc:      # noqa: BLE001
                detail = f"parse failed: {type(exc).__name__}: {exc}"[:300]
        res = self._finish(book, sport, at, url, status, text, status == 200 and not refused,
                           live, matched, written, detail, body=body)
        res["refused"] = refused
        return res

    def _lines(self, book: Book, sport: str, events: list[BookEvent], at: datetime) -> tuple[int, int, int]:
        """Place each live game on our games row and log the changed lines."""
        from data.ingestors import dk_live_board as B
        if sport not in B.ODDS_LOG_SPORTS:
            return len(events), 0, 0
        resolve = None if self.dry_run else self._resolver(sport)
        rows = []
        matched = 0
        for ev in events:
            k = (book.key, ev.event_id)
            if k not in self.ids:
                hit = None if resolve is None else resolve(ev.home_name, ev.away_name, ev.start or "")
                self.ids[k] = None if hit is None else (str(hit[0]), bool(hit[1]))
                if hit is None:
                    log.info("%s %s: %s does not resolve onto a game", book.key, sport, ev.name)
            hit = self.ids[k]
            if hit is None:
                continue
            matched += 1
            row = {"game_id": hit[0], "read_at": at, **_oriented(ev, hit[1])}
            prev = self.last.get((book.key, hit[0]))
            new = odds_rows(prev, row, sport, book.key)
            if new:
                rows.extend(new)
                self.last[(book.key, hit[0])] = row
        if not rows or self.dry_run:
            return len(events), matched, 0
        if self.odds_log is None:
            from data.ingestors.live_price_log import record_live_prices
            self.odds_log = record_live_prices
        return len(events), matched, int(self.odds_log(self.c(), rows) or 0)

    def _finish(self, book, sport, at, url, status, text, ok, live, matched, written, detail, body=None) -> dict:
        res = {"book": book.key, "sport": sport, "ok": ok, "status": status, "live": live,
               "matched": matched, "written": written, "detail": detail}
        if self.dry_run:
            log.info("[dry-run] %s %s: %s", book.key, sport, res)
            return res
        try:
            conn = self.c()
            if status is not None and self.captures.want(book.key, sport, status, at):
                conn.execute(
                    f"INSERT INTO {RAW_TABLE} (fetched_at, book, sport, url, status, bytes, payload, body) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s) ON CONFLICT DO NOTHING",
                    (at, book.key, sport, stored_url(url), status, len(text.encode("utf-8", "ignore")),
                     json.dumps(body) if body is not None else None,
                     None if body is not None else text[:MAX_BODY_TEXT]))
            conn.execute(f"""
                INSERT INTO {FEED_TABLE} (book, sport, last_read_at, ok, status, live_events, matched, written, detail)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (book, sport) DO UPDATE SET last_read_at = EXCLUDED.last_read_at, ok = EXCLUDED.ok,
                    status = EXCLUDED.status, live_events = EXCLUDED.live_events, matched = EXCLUDED.matched,
                    written = EXCLUDED.written, detail = EXCLUDED.detail
            """, (book.key, sport, at, ok, status, live, matched, written, detail))
            conn.commit()
        except Exception as exc:          # noqa: BLE001
            log.error("%s %s: write failed: %s", book.key, sport, exc)
            self._recycle()
        return res


def _oriented(ev: BookEvent, flipped: bool) -> dict:
    if not flipped:
        return {"spread_home": ev.spread_home, "spread_home_price": ev.spread_home_price,
                "spread_away_price": ev.spread_away_price, "total_line": ev.total_line,
                "over_price": ev.over_price, "under_price": ev.under_price,
                "home_ml": ev.home_ml, "away_ml": ev.away_ml}
    return {"spread_home": None if ev.spread_home is None else -ev.spread_home,
            "spread_home_price": ev.spread_away_price, "spread_away_price": ev.spread_home_price,
            "total_line": ev.total_line, "over_price": ev.over_price, "under_price": ev.under_price,
            "home_ml": ev.away_ml, "away_ml": ev.home_ml}


def _session():
    from curl_cffi import requests as cr
    return cr.Session(impersonate="chrome124")


def start_in_background(connect, live_sports: Callable[[], list[str]]) -> threading.Thread | None:
    """The thread DraftKings' board starts beside itself. None when turned off."""
    if os.environ.get("BOOK_LIVE_BOARDS", "1") == "0":
        log.info("BOOK_LIVE_BOARDS=0: other books not read")
        return None
    feeds = BookFeeds(connect, live_sports)

    def run():
        while True:
            try:
                feeds.pass_once()
            except Exception as exc:      # noqa: BLE001
                log.error("book feeds pass failed: %s", exc)
                feeds._recycle()
            time.sleep(1.0)

    t = threading.Thread(target=run, name="book_live_boards", daemon=True)
    t.start()
    log.info("other books: %s, every %.0f s per live sport", ", ".join(b.key for b in BOOKS), POLL_SEC)
    return t


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sports", nargs="*", default=list(LIVE_SPORTS))
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from data.db import get_connection
    feeds = BookFeeds(get_connection, lambda: list(a.sports), dry_run=a.dry_run)
    while True:
        for res in feeds.pass_once():
            print(res)
        if a.once:
            return 0
        time.sleep(1.0)


if __name__ == "__main__":
    raise SystemExit(main())
