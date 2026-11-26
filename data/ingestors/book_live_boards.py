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
book) and read from this machine; none is documented by the book, and any can
change. So a book is one of two kinds:
  * PARSED: its answer's shape was seen in a real capture, and its live main
    lines go to `odds` as in-play rows (source '<book>_board'). FanDuel and
    BetRivers (Kambi), both measured live from mike's machine 2026-11-26.
  * CAPTURED: the answer is stored raw in `book_live_raw` and nothing is parsed
    until a stored answer shows the shape. BetMGM, Caesars, and the Fanatics
    and Hard Rock home pages (no endpoint is known for either; the page names
    the hosts its scripts call).
A book's page that lists more than our league (eBasketball on FanDuel's NBA
page, women's games on its men's college page, AHL beside NHL on BetRivers)
is cut to the competitions named here, by exact name; a competition that is
not named gets no lines.
Every read, either kind, upserts `book_live_feed` (book, sport): when it last
answered, its HTTP status, and how many live games it listed and placed on our
games rows. A refusal, a bot challenge or a wrong guess is a row there, never
a crash and never a retry storm: a refused book backs off.

NO BOT-WALL WORK. A request is a plain HTTPS GET in a browser's TLS shape (the
same client DraftKings' board uses), at most one per book and sport every
BOOK_POLL_SEC. A book that answers with a challenge page is recorded as
refused and left alone.

WHAT EACH BOOK HAS ON OFFER, PER READ (2026-11-26, mike: "We want best line").
`book_live_reads` (READS_TABLE below) records each game's eight numbers on
each book whenever they change, a suspended market or a game leaving the page
included, the answer's own age (FanDuel's page is a CDN copy up to 30 s old,
90 s while it revalidates), and which rows are a game's first since a start.
It is what a live decision needs before it can bet another book's number;
nothing decides on it yet.

NOT NCAAF, NOT MLB (dk_live_board.ODDS_LOG_SPORTS). Both sports' live picks
are stamped off the newest in-play `odds` row per book
(models.scorer._best_live_price), so a new writer for any book would move the
price a live pick is stamped at. No other decision reads another book's
in-play rows (checked 2026-11-25).

    python -m data.ingestors.book_live_boards --once --dry-run   # one pass, print, write nothing
"""
from __future__ import annotations

import argparse
import base64
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
# A book is polled this fast while its league has a game live (mike,
# 2026-11-26: "Everything needs to be 1 second or less"), AS FAST AS THE BOOK
# ALLOWS: POLL_SEC between clean reads, doubling to MAX_POLL_SEC each time the
# book pushes back (429/403/5xx/challenge), halving back to the floor as it
# answers cleanly again. This finds each book's fastest safe rate instead of a
# guessed constant. These pages cost no Odds API credits.
POLL_SEC = float(os.environ.get("BOOK_POLL_SEC", "1.0"))
MAX_POLL_SEC = float(os.environ.get("BOOK_MAX_POLL_SEC", "30"))
# No two book requests from this thread are closer than this, whichever book:
# the DraftKings feed runs in the same process on the same home IP, and a burst
# of scraping is what gets a residential address flagged. At 0.2 s the thread
# makes at most five requests a second across every book, each to a different
# host, so no one host sees more than ~1/s.
MIN_REQUEST_GAP_SEC = float(os.environ.get("BOOK_MIN_REQUEST_GAP_SEC", "0.2"))
DISCOVER_SEC = 6 * 3600.0                            # a home page, for its API hosts
BACKOFF_SEC = 600.0                                  # after REFUSALS_BEFORE_BACKOFF refusals
REFUSALS_BEFORE_BACKOFF = 3
# One answer serves every sport that reads the same URL within this long
# (BetRivers' one basketball list is NBA, NCAAB and NCAABW): a book is asked
# once, not once per sport. At the 1 s poll this only dedupes within a pass.
SHARED_READ_SEC = 1.0


def next_book_gap(gap: float, refused: bool, floor: float = POLL_SEC, ceiling: float = MAX_POLL_SEC) -> float:
    """The next interval for a book: the floor after a clean read, doubled
    (to the ceiling) each time it pushes back. Pure."""
    if refused:
        return min(ceiling, max(gap, floor) * 2.0)
    return floor
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
FEED_COLS = ("book", "sport", "last_read_at", "ok", "status", "live_events", "matched", "written", "detail",
             "page_age_s")
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
    page_age_s    DOUBLE PRECISION,
    PRIMARY KEY (book, sport)
)
"""
# The table predates page_age_s (2026-11-26): added in place, never recreated.
FEED_ALTER = "ALTER TABLE book_live_feed ADD COLUMN IF NOT EXISTS page_age_s DOUBLE PRECISION"

# WHAT EACH BOOK HAS ON OFFER AT EACH READ (mike, 2026-11-26: "We want best
# line"). The record a live decision needs before it may bet another book's
# number, which `odds` cannot give: a market the book suspends adds no row
# there, so its last number reads as current, and a restart writes every number
# again as if new. Here, per (book, game): a row whenever any of the eight
# numbers changes, a market leaving the page included (its columns go NULL),
# and an all-NULL row when a game the last clean read listed is not on this
# one. Only a clean, parsed read writes; a refusal, an error or a backed-off
# book writes nothing, so the last row stands only while book_live_feed says
# the book is being read.
#   after_start  the game's first row since this process started: how long
#                that number had already been up is unknown.
#   page_age_s   the answer's own Age header. FanDuel's page is a CDN copy
#                (max-age 30, stale-while-revalidate 60; an answer read
#                2026-11-26 17:35Z was 13 s old), so its numbers were on the
#                book's site at read_at - page_age_s. NULL when the book sends
#                no Age (BetRivers' answer, same day, was a CDN miss with none).
# Nothing decides on it yet: the loops that will are the next change.
READS_TABLE = "book_live_reads"
READ_LINE_COLS = ("spread_home", "spread_home_price", "spread_away_price", "total_line",
                  "over_price", "under_price", "home_ml", "away_ml")
READS_COLS = ("book", "sport", "game_id", "read_at", "page_age_s", "after_start", *READ_LINE_COLS)
READS_INDEX = "book_live_reads_sport_read_idx"
READS_DDL = """
CREATE TABLE IF NOT EXISTS book_live_reads (
    book               TEXT NOT NULL,
    sport              TEXT NOT NULL,
    game_id            TEXT NOT NULL,
    read_at            TIMESTAMPTZ NOT NULL,
    page_age_s         DOUBLE PRECISION,
    after_start        BOOLEAN NOT NULL DEFAULT FALSE,
    spread_home        DOUBLE PRECISION,
    spread_home_price  DOUBLE PRECISION,
    spread_away_price  DOUBLE PRECISION,
    total_line         DOUBLE PRECISION,
    over_price         DOUBLE PRECISION,
    under_price        DOUBLE PRECISION,
    home_ml            DOUBLE PRECISION,
    away_ml            DOUBLE PRECISION,
    PRIMARY KEY (book, game_id, read_at)
)
"""
READS_INDEX_DDL = f"CREATE INDEX IF NOT EXISTS {READS_INDEX} ON book_live_reads (sport, read_at)"
READS_INSERT = (f"INSERT INTO {READS_TABLE} ({', '.join(READS_COLS)}) "
                f"VALUES ({', '.join(['%s'] * len(READS_COLS))}) ON CONFLICT DO NOTHING")
_OFF = (None,) * len(READ_LINE_COLS)       # a game not on the page: nothing on offer
_UNSEEN = object()


def page_age(resp) -> float | None:
    """The answer's own Age header in seconds (how old a CDN copy is), or None
    when the book sends none or it does not parse. Pure."""
    headers = getattr(resp, "headers", None)
    if not headers:
        return None
    try:
        items = headers.items()
    except AttributeError:
        return None
    for k, v in items:
        if str(k).lower() == "age":
            try:
                return float(str(v).strip())
            except ValueError:
                return None
    return None

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
# sport -> (the page FanDuel's site reads it from, the competitions on that
# page that ARE this sport). Read from mike's machine 2026-11-26 01:00Z:
#   nba    NBA (10 games) beside "eBasketball H2H GG League 4x5 Mins" (14)
#   ncaab  "NCAA Basketball Mens Games" (50) beside "NCAA Basketball Women’s
#          Games" (1: Oregon State (W) @ Vanderbilt (W)), so a women's line
#          could land on a men's game without the cut
#   ncaaw  the women's page (the old id 'wncaab' answers 404); the same
#          women's competition, with a curly apostrophe (U+2019)
#   nhl    NHL (14);  nfl  NFL (31)
#   EuroLeague has no page id ('euroleague' answers 404); it is a tab of the
#   basketball page (page=SPORT&eventTypeId=7522), whose own text names
#   "Men's Euroleague Games". No EuroLeague game was listed that night (a FIBA
#   window), so that name is not yet seen on a game.
FANDUEL_PAGES = {
    "NBA": ("page=CUSTOM&customPageId=nba", ("NBA",)),
    "NFL": ("page=CUSTOM&customPageId=nfl", ("NFL",)),
    "NHL": ("page=CUSTOM&customPageId=nhl", ("NHL",)),
    "NCAAB": ("page=CUSTOM&customPageId=ncaab", ("NCAA Basketball Mens Games",)),
    "NCAABW": ("page=CUSTOM&customPageId=ncaaw", ("NCAA Basketball Women’s Games",)),
    "EUROLEAGUE": ("page=SPORT&eventTypeId=7522", ("Men's Euroleague Games",)),
}
# Seen in the NBA and NHL captures (2026-11-23, 11-26): MONEY_LINE,
# MATCH_HANDICAP_(2-WAY) (the NHL puck line too), TOTAL_POINTS_(OVER/UNDER)
# (the NHL total too). A market type not listed is no line.
FANDUEL_TYPES = {"MONEY_LINE": "h2h", "MATCH_HANDICAP_(2-WAY)": "spreads",
                 "TOTAL_POINTS_(OVER/UNDER)": "totals"}


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


_RANK = re.compile(r"^\(\d+\)\s*")
_WOMEN_TAG = re.compile(r"\s*[\(\[]W[\)\]]\s*$")
# College names these books write that our resolvers do not read, each one a
# live game that did not place on 2026-11-26 01:10Z although it is on our
# schedule (games: UConn, Omaha, The Citadel, Cal State Bakersfield, South
# Carolina Upstate, St. Thomas). FanDuel's first four, BetRivers' last two.
BOOK_CBB_ALIASES = {"Connecticut": "UConn", "Nebraska Omaha": "Omaha", "Citadel": "The Citadel",
                    "CSU Bakersfield": "Cal State Bakersfield", "USC Upstate": "South Carolina Upstate",
                    "St. Thomas (MN)": "St. Thomas"}


def team_name(name: str, sport: str) -> str:
    """A book's team name as our resolvers read it: a college ranking
    ("(12) Vanderbilt") off the front, and on WOMEN'S games only, the "(W)"
    tag off the end, then BOOK_CBB_ALIASES. The tag is never taken off a
    men's name, so a women's game that reached a men's reader stays
    unmatched. Pure."""
    n = (name or "").strip()
    if sport in ("NCAAB", "NCAABW"):
        n = _RANK.sub("", n)
    if sport == "NCAABW":
        n = _WOMEN_TAG.sub("", n)
    n = n.strip()
    if sport in ("NCAAB", "NCAABW"):
        n = BOOK_CBB_ALIASES.get(n, n)
    return n


_unlisted_seen: set[tuple[str, str, str]] = set()


def _note_unlisted(book: str, sport: str, name: str) -> None:
    if (book, sport, name) not in _unlisted_seen:
        _unlisted_seen.add((book, sport, name))
        log.info("%s %s: live games in %r are not this sport's; no lines", book, sport, name)


def parse_fanduel(body: dict, sport: str) -> list[BookEvent]:
    """Every in-play game of `sport` on one FanDuel page, with its main lines:
    only games in a competition FANDUEL_PAGES names for the sport (exact
    name); an unnamed competition gets no lines. A market with more than one
    live market of its kind on the same game is left out (it is not knowable
    which one the page shows as main). Pure."""
    att = (body or {}).get("attachments") or {}
    events = att.get("events") or {}
    comps = att.get("competitions") or {}
    keep = set(FANDUEL_PAGES.get(sport, ("", ()))[1])
    by_event: dict[str, dict[str, list[dict]]] = {}
    for m in (att.get("markets") or {}).values():
        kind = FANDUEL_TYPES.get(m.get("marketType"))
        if not kind or m.get("inPlay") is not True or m.get("marketStatus") != "OPEN":
            continue
        ev = events.get(str(m.get("eventId"))) or {}
        comp = str((comps.get(str(ev.get("competitionId"))) or {}).get("name") or "")
        if comp not in keep:
            _note_unlisted("fanduel", sport, comp)
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
                             home_name=team_name(home, sport), away_name=team_name(away, sport), **row))
    return out


# ── BetRivers: PARSED (Kambi) ────────────────────────────────────────────────
#
# BetRivers is Kambi's platform. Ohio's offering is 'rsiusoh', market 'US-OH'
# (read off oh.betrivers.com's own page, 2026-11-25). One call per sport,
# listView/<sport>/all/all/all/in-play.json, lists every live game of every
# league in that sport WITH its main moneyline, spread and total: measured
# 2026-11-26 01:00Z, 24 live basketball games (NBA 5, NCAAB 17, NCAAW 2) and
# 17 hockey (NHL 11, AHL 6), and the three NCAAB games listed without a
# moneyline had none in their own bet-offer call either (Kambi pulls it in a
# lopsided game), so no per-game call is made. Ohio's league list (group.json)
# has NBA, NBA Cup, NCAAB, NCAAW, NHL and NFL, and no EuroLeague.
#
# A game: event.homeName / awayName / start / state 'STARTED' / path[].termKey
# (['basketball', 'nba']). An offer: criterion.label, tags (MAIN on the main
# moneyline, MAIN_LINE on the main spread and total; team totals and
# second-half lines carry MAIN_LINE too, so the LABEL decides), outcomes[]
# with participant (the team), line in thousandths (-22500 is -22.5),
# oddsAmerican as a string, status OPEN / SUSPENDED. A suspended offer loses
# its MAIN_LINE tag. Names: "CHI Bulls", "NY Knicks" (our nickname resolver
# reads the nickname), "(12) Vanderbilt (W)" on women's games.

KAMBI_OFFERING = os.environ.get("BETRIVERS_OFFERING", f"rsius{STATE}")
KAMBI_MARKET = os.environ.get("BETRIVERS_MARKET", f"US-{STATE.upper()}")
KAMBI_BASE = os.environ.get("BETRIVERS_KAMBI", "https://eu.offering-api.kambicdn.com/offering/v2018")
# sport -> (Kambi's sport path, the league termKeys that ARE this sport)
KAMBI_LEAGUES = {"NBA": ("basketball", ("nba", "nba_cup")), "NCAAB": ("basketball", ("ncaab",)),
                 "NCAABW": ("basketball", ("ncaaw",)), "NHL": ("ice_hockey", ("nhl",)),
                 "NFL": ("american_football", ("nfl",))}
# The main markets' labels, exactly as seen (NFL's on its pre-game list, the
# same offers it keeps open in play). Anything else is not a main line.
KAMBI_LABELS = {
    "Moneyline": "h2h", "Moneyline - Inc. OT and Shootout": "h2h",
    "Point Spread": "spreads", "Puck Line - Inc. OT and Shootout": "spreads",
    "Total Points - Including Overtime": "totals", "Total Points": "totals",
    "Total Goals - Inc. OT and Shootout": "totals",
}
KAMBI_HEADERS = {"Origin": "https://oh.betrivers.com", "Referer": "https://oh.betrivers.com/"}


def _kambi_price(o: dict) -> float | None:
    try:
        return float(int(str(o.get("oddsAmerican")).replace("+", "")))
    except (TypeError, ValueError):
        return None


def parse_kambi(body: dict, sport: str) -> list[BookEvent]:
    """Every started game of `sport` on one Kambi in-play list, with its main
    lines: only leagues KAMBI_LEAGUES names for the sport, only offers whose
    label is in KAMBI_LABELS and whose tag marks them main, only OPEN outcomes
    with a price, each team's side read off its own participant name. A kind
    with two main offers on one game is left out. Pure."""
    keep = set(KAMBI_LEAGUES.get(sport, ("", ()))[1])
    out = []
    for item in (body or {}).get("events") or []:
        ev = item.get("event") or {}
        leagues = {str(p.get("termKey")) for p in ev.get("path") or []}
        if not leagues & keep:
            if ev.get("group"):
                _note_unlisted("betrivers", sport, str(ev.get("group")))
            continue
        if ev.get("state") != "STARTED":
            continue
        home, away = str(ev.get("homeName") or ""), str(ev.get("awayName") or "")
        if not home or not away or home == away:
            continue
        by_kind: dict[str, list[dict]] = {}
        for bo in item.get("betOffers") or []:
            kind = KAMBI_LABELS.get(str((bo.get("criterion") or {}).get("label") or ""))
            tags = set(bo.get("tags") or [])
            if kind and tags & {"MAIN", "MAIN_LINE"}:
                by_kind.setdefault(kind, []).append(bo)
        row = {}
        for kind, offers in by_kind.items():
            if len(offers) != 1:
                log.info("BetRivers event %s: %d main %s offers; none taken", ev.get("id"), len(offers), kind)
                continue
            outs = [o for o in offers[0].get("outcomes") or []
                    if o.get("status") == "OPEN" and _kambi_price(o) is not None]
            if kind in ("h2h", "spreads"):
                h = [o for o in outs if o.get("participant") == home]
                a = [o for o in outs if o.get("participant") == away]
                if len(h) != 1 or len(a) != 1:
                    continue
                h, a = h[0], a[0]
                if kind == "h2h":
                    row.update(home_ml=_kambi_price(h), away_ml=_kambi_price(a))
                else:
                    try:
                        line = int(h["line"]) / 1000.0
                    except (KeyError, TypeError, ValueError):
                        continue
                    row.update(spread_home=line, spread_home_price=_kambi_price(h),
                               spread_away_price=_kambi_price(a))
            else:
                o = [x for x in outs if x.get("type") == "OT_OVER"]
                u = [x for x in outs if x.get("type") == "OT_UNDER"]
                if len(o) != 1 or len(u) != 1:
                    continue
                try:
                    line = int(o[0]["line"]) / 1000.0
                except (KeyError, TypeError, ValueError):
                    continue
                row.update(total_line=line, over_price=_kambi_price(o[0]), under_price=_kambi_price(u[0]))
        if not row:
            continue
        out.append(BookEvent(event_id=str(ev.get("id")), name=str(ev.get("name") or ""), start=ev.get("start"),
                             home_name=team_name(home, sport), away_name=team_name(away, sport), **row))
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

# The access id is a PUBLIC web token BetMGM's own logged-out page ships in its
# query string, the same kind of value as FanDuel's public `_ak` key. The two
# hardcoded above are for other BetMGM sites and the Ohio API answers them with
# a clean JSON 400 "Access id not allowed for application" (every read
# 2026-11-26): the request reaches the app, it is just the wrong site's token.
# So the right one is read off BetMGM's own public Ohio page (and the config/JS
# it names), exactly as FanDuel's key is. A US id is a UUID, base64-encoded (48
# chars). A 400'd id is marked bad and never sent again.
BETMGM_PAGE = "https://sports.{state}.betmgm.com/en/sports"
BETMGM_PAGE_EXTRA = 6           # same-site config/JS files read beside the page
_B64_48 = re.compile(r"(?<![A-Za-z0-9+/])([A-Za-z0-9+/]{48})(?![A-Za-z0-9+/=])")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def access_ids_in(text: str) -> list[str]:
    """Every 48-char base64 token in `text` that decodes to a UUID (a BetMGM
    access id), in order, de-duplicated. Pure."""
    out: list[str] = []
    for tok in _B64_48.findall(text or ""):
        try:
            dec = base64.b64decode(tok, validate=True).decode("ascii")
        except Exception:                 # noqa: BLE001
            continue
        if _UUID.match(dec) and tok not in out:
            out.append(tok)
    return out


def page_assets(page: str, origin: str, limit: int = BETMGM_PAGE_EXTRA) -> list[str]:
    """Same-site config and script URLs a page names, configs first. Pure."""
    scripts = re.findall(r'(?:src|href)="(/[^"#]+\.js[^"]*)"', page or "")
    configs = re.findall(r'"(/[a-z]{2}/api/[a-z/]*config[^"]*)"', page or "", re.I)
    out: list[str] = []
    for path in configs + scripts:
        url = origin + path
        if url not in out:
            out.append(url)
    return out[:limit]


class BetMGMKeys:
    """The access ids to try, discovered ones first; a 400'd id is marked bad
    and never offered again."""

    def __init__(self, ids: tuple[str, ...] = ()):
        self.ids = list(ids)
        self.bad: set[str] = set()
        self.page_at: float | None = None

    def current(self) -> str | None:
        return next((i for i in self.ids if i not in self.bad), None)

    def add(self, found: list[str]) -> list[str]:
        new = [i for i in found if i not in self.ids]
        self.ids = new + self.ids
        return new

# Caesars: api.americanwagering.com/regions/us/locations/<state>/brands/czr/
# sb/v3/... (declanwalpole/sportsbook-odds-scraper, events by id). The live
# list path is not published; this asks for the sport's schedule.
CAESARS_SPORTS = {"NBA": "basketball", "NCAAB": "basketball", "NCAABW": "basketball",
                  "EUROLEAGUE": "basketball", "NFL": "americanfootball", "NHL": "icehockey"}
# A cold hit on Caesars' API host got a CloudFront 403: the site's own JS calls
# that host cross-origin with these headers and after loading the site, so the
# feed does the same: loads the site once for cookies (CAESARS_SITE), then
# sends the Origin / Referer / Accept the browser's XHR sends. This is making
# the request the way the site does, not defeating a bot wall: if CloudFront
# still blocks a browser-shaped request it stays recorded as refused, and
# nothing here solves a challenge or rotates fingerprints to get past one.
CAESARS_SITE = "https://sportsbook.caesars.com/"
CAESARS_HEADERS = {"Origin": "https://sportsbook.caesars.com",
                   "Referer": "https://sportsbook.caesars.com/",
                   "Accept": "application/json, text/plain, */*"}


@dataclass(frozen=True)
class Book:
    key: str                      # our bookmaker key (odds.bookmaker)
    sports: tuple[str, ...]       # the sports it is asked about while live
    url: Callable[[str], str | None]
    parse: Callable[[dict, str], list[BookEvent]] | None = None
    discover: bool = False        # a home page, read every DISCOVER_SEC, sport '*'
    headers: dict | None = None   # sent with every request, as the book's own page sends them


def _fanduel_url(sport: str) -> str | None:
    page = FANDUEL_PAGES.get(sport)
    if not page:
        return None
    return (f"https://sbapi.{STATE}.sportsbook.fanduel.com/api/content-managed-page"
            f"?{page[0]}&_ak={FANDUEL_AK}&timezone=America%2FNew_York")


def _betrivers_url(sport: str) -> str | None:
    league = KAMBI_LEAGUES.get(sport)
    if not league:
        return None
    return (f"{KAMBI_BASE}/{KAMBI_OFFERING}/listView/{league[0]}/all/all/all/in-play.json"
            f"?lang=en_US&market={KAMBI_MARKET}&useCombined=true")


def _betmgm_url(sport: str, key: str | None = None) -> str | None:
    sid = BETMGM_SPORT_IDS.get(sport)
    key = key or (BETMGM_ACCESS_IDS[0] if BETMGM_ACCESS_IDS else None)
    if not sid or not key:
        return None
    return (f"https://sports.{STATE}.betmgm.com/cds-api/bettingoffer/fixtures"
            f"?x-bwin-accessid={key}&lang=en-us&country=US&userCountry=US"
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
    Book("betrivers", tuple(s for s in LIVE_SPORTS if s in KAMBI_LEAGUES), _betrivers_url, parse_kambi,
         headers=KAMBI_HEADERS),
    Book("betmgm", tuple(s for s in LIVE_SPORTS if s in BETMGM_SPORT_IDS), _betmgm_url),
    Book("williamhill_us", tuple(s for s in LIVE_SPORTS if s in CAESARS_SPORTS), _caesars_url,
         headers=CAESARS_HEADERS),
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
        conn.execute(FEED_ALTER)
        lock_down(conn, FEED_TABLE)
    if not schema_is_current(conn, READS_TABLE, columns=READS_COLS, indexes=(READS_INDEX,), rls=True,
                             revoked_from=API_ROLES):
        conn.execute(READS_DDL)
        conn.execute(READS_INDEX_DDL)
        lock_down(conn, READS_TABLE)
    conn.commit()
    from data.ingestors.book_throttle import ensure_table as ensure_throttle_table
    ensure_throttle_table(conn)


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
                 resolvers=None, odds_log=None, clock=None, monotonic=time.monotonic, dry_run=False,
                 sleep=time.sleep):
        self.connect, self.live_sports, self.dry_run = connect, live_sports, dry_run
        self.session_factory = session_factory or _session
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.monotonic = monotonic
        self.sleep = sleep
        self.gap: dict[str, float] = {}            # book -> current poll interval (adaptive)
        self.last_http = None                      # monotonic of the last request, for MIN_REQUEST_GAP_SEC
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
        # book_live_reads: (book, game_id) -> the eight numbers last stored, and
        # (book, sport) -> the games the last clean read listed.
        self.state: dict[tuple, tuple] = {}
        self.listed: dict[tuple, set] = {}
        self.ids: dict[tuple, tuple | None] = {}   # (book, event_id) -> (game_id, flipped)
        self.shared: dict[str, tuple] = {}         # url -> (when, status, text, page age)
        self.betmgm_keys = BetMGMKeys(BETMGM_ACCESS_IDS)
        self._booted: set[str] = set()             # books whose session was warmed (Caesars)
        self.captures = Captures()
        # A book rate limiting or refusing us: one row per episode in
        # book_throttle_events, which the worker turns into an ops alert
        # (data/ingestors/book_throttle.py).
        from data.ingestors.book_throttle import ThrottleTracker
        self.throttle = ThrottleTracker(REFUSALS_BEFORE_BACKOFF, clock=self.clock)
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
            self.throttle.table_ready = True
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
                # Never burst the home IP: space real requests across all books.
                if self.last_http is not None:
                    wait = MIN_REQUEST_GAP_SEC - (self.monotonic() - self.last_http)
                    if wait > 0:
                        self.sleep(wait)
                self.last_http = self.monotonic()
                res = self.read(book, sport)
                now = self.monotonic()
                was = self.gap.get(book.key, POLL_SEC)
                self._note_throttle(book, sport, res, DISCOVER_SEC if book.discover else was)
                if book.discover:
                    self.due[key] = now + DISCOVER_SEC
                    results.append(res)
                    continue
                refused = bool(res.get("refused")) and not res.get("shared")
                gap = next_book_gap(was, refused)
                self.gap[book.key] = gap
                self.due[key] = now + gap
                if refused:
                    self.refusals[book.key] = self.refusals.get(book.key, 0) + 1
                    if self.refusals[book.key] >= REFUSALS_BEFORE_BACKOFF:
                        log.warning("%s: %d refusals in a row - leaving it alone %.0f s",
                                    book.key, self.refusals[book.key], BACKOFF_SEC)
                        for k in list(self.due):
                            if k[0] == book.key:
                                self.due[k] = now + BACKOFF_SEC
                        self.due[key] = now + BACKOFF_SEC
                        self.refusals[book.key] = 0
                        self.gap[book.key] = POLL_SEC
                        self.throttle.backoff(book.key, sport, BACKOFF_SEC, poll_s=was)
                elif not res.get("shared"):
                    self.refusals[book.key] = 0
                results.append(res)
        if not self.dry_run and self.throttle.pending:
            try:
                self.throttle.flush(self.c())
            except Exception as exc:      # noqa: BLE001
                log.error("throttle events: %s", exc)
                self._recycle()
        return results

    def _note_throttle(self, book: Book, sport: str, res: dict, poll_s: float) -> None:
        """Hand one real request's answer to the throttle tracker. A shared
        answer was already counted, and "no url" sent no request."""
        from data.ingestors.book_throttle import reason_for
        if res.get("shared") or res.get("detail") == "no url":
            return
        status = res.get("status")
        self.throttle.observe(book.key, sport, clean=bool(res.get("ok")),
                              reason=reason_for(status, bool(res.get("refused")), status is not None),
                              status=status, poll_s=poll_s, detail=str(res.get("detail") or ""))

    def _url_for(self, book: Book, sport: str) -> str | None:
        """The book's url for this sport, with BetMGM's current access id."""
        if book.key == "betmgm":
            key = self.betmgm_keys.current()
            return _betmgm_url(sport, key) if key else None
        return book.url(sport)

    def _warm(self, book: Book, sess) -> None:
        """Load Caesars' site once per session so its cookies are set, the way
        a browser does before the site's JS calls the API cross-origin."""
        if book.key != "williamhill_us" or book.key in self._booted:
            return
        self._booted.add(book.key)
        try:
            sess.get(CAESARS_SITE, timeout=15)
        except Exception:                 # noqa: BLE001
            pass

    def _betmgm_page(self, book: Book, sess) -> None:
        """Read BetMGM's public page (and up to BETMGM_PAGE_EXTRA of the config
        and script files it names) for the access ids it ships, at most every
        DISCOVER_SEC. The page's answer is stored like a home page (sport '*')."""
        k = self.betmgm_keys
        if k.page_at is not None and self.monotonic() - k.page_at < DISCOVER_SEC:
            return
        k.page_at = self.monotonic()
        url = BETMGM_PAGE.format(state=STATE)
        origin = url.split("/en/", 1)[0]
        at = self.clock()
        try:
            r = sess.get(url, timeout=15)
            status, text = int(r.status_code), r.text or ""
        except Exception as exc:          # noqa: BLE001
            self._finish(book, "*", at, url, None, "", False, 0, 0, 0, f"page: {type(exc).__name__}"[:120])
            return
        found = access_ids_in(text)
        if status == 200 and not is_challenge(status, text):
            for extra in page_assets(text, origin):
                try:
                    found += [i for i in access_ids_in(sess.get(extra, timeout=15).text or "") if i not in found]
                except Exception:         # noqa: BLE001
                    continue
        new = k.add(found)
        log.info("betmgm page: %d access id(s), %d new", len(found), len(new))
        self._finish(book, "*", at, url, status, text, status == 200, 0, 0, 0,
                     f"page: {len(found)} access id(s), {len(new)} new")

    def read(self, book: Book, sport: str) -> dict:
        """One request. Never raises."""
        sess = self.sessions.get(book.key)
        if sess is None:
            sess = self.sessions[book.key] = self.session_factory()
        self._warm(book, sess)
        url = self._url_for(book, sport)
        if url is None:
            if book.key == "betmgm":
                self._betmgm_page(book, sess)
            return {"book": book.key, "sport": sport, "ok": False, "detail": "no url"}
        at = self.clock()
        shared = self.shared.get(url)
        if shared is not None and self.monotonic() - shared[0] < SHARED_READ_SEC:
            status, text, age = shared[1], shared[2], shared[3]
        else:
            shared = None
            try:
                kw = {"headers": book.headers} if book.headers else {}
                r = sess.get(url, timeout=15, **kw)
                status, text, age = int(r.status_code), r.text or "", page_age(r)
            except Exception as exc:          # noqa: BLE001
                return self._finish(book, sport, at, url, None, "", False, 0, 0, 0,
                                    f"{type(exc).__name__}: {exc}"[:300])
            self.shared[url] = (self.monotonic(), status, text, age)
        if book.key == "betmgm" and status == 400 and "access id" in (text or "").lower():
            # This id is for another BetMGM site: never send it again, and read
            # the public page for the one this site ships.
            m = re.search(r"x-bwin-accessid=([^&]+)", url)
            if m:
                self.betmgm_keys.bad.add(m.group(1))
            self._betmgm_page(book, sess)
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
                live, matched, written = self._lines(book, sport, book.parse(body, sport), at, age)
            except Exception as exc:      # noqa: BLE001
                detail = f"parse failed: {type(exc).__name__}: {exc}"[:300]
        res = self._finish(book, sport, at, url, status, text, status == 200 and not refused,
                           live, matched, written, detail, body=body, capture=shared is None,
                           page_age_s=age)
        res["refused"] = refused
        res["shared"] = shared is not None
        return res

    def _lines(self, book: Book, sport: str, events: list[BookEvent], at: datetime,
               page_age_s: float | None = None) -> tuple[int, int, int]:
        """Place each live game on our games row, record what the book has on
        offer (book_live_reads), and log the changed lines to `odds`."""
        from data.ingestors import dk_live_board as B
        if sport not in B.ODDS_LOG_SPORTS:
            return len(events), 0, 0
        resolve = None if self.dry_run else self._resolver(sport)
        rows = []
        matched = 0
        seen: dict[str, tuple] = {}
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
            seen[hit[0]] = tuple(row[c] for c in READ_LINE_COLS)
            prev = self.last.get((book.key, hit[0]))
            new = odds_rows(prev, row, sport, book.key)
            if new:
                rows.extend(new)
                self.last[(book.key, hit[0])] = row
        if not self.dry_run:
            self._log_offer(book, sport, seen, at, page_age_s)
        if not rows or self.dry_run:
            return len(events), matched, 0
        if self.odds_log is None:
            from data.ingestors.live_price_log import record_live_prices
            self.odds_log = record_live_prices
        return len(events), matched, int(self.odds_log(self.c(), rows) or 0)

    def offer_rows(self, book: Book, sport: str, seen: dict, at: datetime,
                   page_age_s: float | None) -> tuple[list[tuple], dict]:
        """(the book_live_reads rows one clean read adds, the state they leave).
        A game is written when its numbers differ from its last stored row,
        its first row since this process started carrying after_start; a game
        the last clean read listed that is not on this one gets one all-NULL
        row. Pure given self.state and self.listed."""
        out, nxt = [], {}
        for gid, nums in seen.items():
            prev = self.state.get((book.key, gid), _UNSEEN)
            if prev is _UNSEEN or prev != nums:
                out.append((book.key, sport, gid, at, page_age_s, prev is _UNSEEN, *nums))
                nxt[(book.key, gid)] = nums
        for gid in sorted(self.listed.get((book.key, sport), set()) - set(seen)):
            prev = self.state.get((book.key, gid), _OFF)
            if prev != _OFF:
                out.append((book.key, sport, gid, at, page_age_s, False, *_OFF))
                nxt[(book.key, gid)] = _OFF
        return out, nxt

    def _log_offer(self, book: Book, sport: str, seen: dict, at: datetime, page_age_s: float | None) -> int:
        """Store one clean read's book_live_reads rows. A failed write leaves
        the state as it was, so the next clean read writes the change again."""
        out, nxt = self.offer_rows(book, sport, seen, at, page_age_s)
        if out:
            try:
                conn = self.c()
                conn.executemany(READS_INSERT, out)
                conn.commit()
            except Exception as exc:      # noqa: BLE001
                log.error("%s %s: book_live_reads write failed: %s", book.key, sport, exc)
                self._recycle()
                return 0
        self.state.update(nxt)
        self.listed[(book.key, sport)] = set(seen)
        return len(out)

    def _finish(self, book, sport, at, url, status, text, ok, live, matched, written, detail, body=None,
                capture=True, page_age_s=None) -> dict:
        res = {"book": book.key, "sport": sport, "ok": ok, "status": status, "live": live,
               "matched": matched, "written": written, "detail": detail}
        if self.dry_run:
            log.info("[dry-run] %s %s: %s", book.key, sport, res)
            return res
        try:
            conn = self.c()
            if capture and status is not None and self.captures.want(book.key, sport, status, at):
                conn.execute(
                    f"INSERT INTO {RAW_TABLE} (fetched_at, book, sport, url, status, bytes, payload, body) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s) ON CONFLICT DO NOTHING",
                    (at, book.key, sport, stored_url(url), status, len(text.encode("utf-8", "ignore")),
                     json.dumps(body) if body is not None else None,
                     None if body is not None else text[:MAX_BODY_TEXT]))
            conn.execute(f"""
                INSERT INTO {FEED_TABLE} (book, sport, last_read_at, ok, status, live_events, matched, written, detail,
                                          page_age_s)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (book, sport) DO UPDATE SET last_read_at = EXCLUDED.last_read_at, ok = EXCLUDED.ok,
                    status = EXCLUDED.status, live_events = EXCLUDED.live_events, matched = EXCLUDED.matched,
                    written = EXCLUDED.written, detail = EXCLUDED.detail, page_age_s = EXCLUDED.page_age_s
            """, (book.key, sport, at, ok, status, live, matched, written, detail, page_age_s))
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
            time.sleep(0.3)

    t = threading.Thread(target=run, name="book_live_boards", daemon=True)
    t.start()
    log.info("other books: %s, up to every %.1f s per live sport (backing off on refusal)",
             ", ".join(b.key for b in BOOKS), POLL_SEC)
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
