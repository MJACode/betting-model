"""UFC prop prices from BestFightOdds' event pages, 2021-06 on.

WHY. The UFC build of 2026-11-13 (docs/ufc_market_audit.md) bet only the
fight winner, because the odds feed returns nothing for method of victory,
goes the distance or round betting (HTTP 422 on every such key). PR #1304
found the route: BestFightOdds keeps a page per UFC card holding every book's
price on every prop, and a price history behind each one. This stores both,
so the prop markets can be graded at the prices that were really offered.

WHAT THE SITE HOLDS (measured 2026-11-13/14). robots.txt allows everything
but /cnadm/. An event page shows, per fight, each book's LAST RECORDED price
on the fight winner and on ~150 props (method by fighter, inside the
distance, goes the distance, round betting, round totals, ...). The page's
columns are the site's current books: DraftKings, FanDuel, BetMGM, Caesars,
BetRivers, BetWay and Unibet carry prices from the June 2021 cards. Two
books are not on the page: Bet365 (id 19) and the site's unnamed "Ref" line
(id 12). Both answered with prop histories for two 2022 fights and with
nothing for two 2024 fights, so neither covers the whole window. Ref's
fight-winner prices on those 2022 fights moved with Pinnacle's but were not
Pinnacle's (on one fight, 7 of 15 pulls within 5 cents).

TWO STAGES.

  * PAGES: every UFC event page in the sitemap from FIRST_DAY to the last
    completed card, one request each (328 from 2021-06 to 2026-11-07). The
    page does not date its prices: a book that stopped moving days before the
    fight shows that older price. So the tables call it the last recorded
    price, not the close.
  * CHARTS: one request per (book, fight, prop, side) history, from
    /api/ggd. Each answer is every price change with its time. By default the
    priced CORE_SERIES cells at the five books a pick may name: 147,356
    histories, about five days at PAUSE_S. --sample N asks a seeded random N
    of them; --jobs FILE asks a study's own list.

FETCH, THEN STORE. --fetch asks each page or history once, politely (one
request at a time, PAUSE_S apart, a User-Agent that names us), and writes the
answer to the spool (DIR/pages/<event id>.html.gz, DIR/charts/<key>.txt.gz),
so a stopped run asks nothing twice. --store reads the spool and writes:

  * ufc_prop_history_fights: one row per BFO fight (matchup): the card, both
    fighters, and our ufc_fight_log game id and fighter id for each: the
    fighter pair within two days, matched by name (config.UFC_NAME_ALIASES,
    BFO_NAME_ALIASES, BFO's own slug, other name orders, no hyphens), or one
    fighter by name and the log's other fighter in that fight spelled close.
    Unplaced fights (mostly bouts that fell through) are kept with game_id
    NULL. BFO sometimes splits one fight in two when books spell a fighter
    differently; both halves are placed on the same game.
  * ufc_prop_history: one row per (fight, book, prop, fighter, side), the
    page's last recorded price. prop_type 0 is the fight winner.
  * ufc_prop_history_ticks: one row per price change in a history.
  * ufc_prop_history_pulls: the ledger, one row per page or history stored,
    written in the same transaction as its rows.

An event dated after the last card in ufc_fight_log is neither spooled nor
ledgered, so a later run asks for it again once it has been fought. One dated
before FIRST_DAY is spooled (never asked again) and not stored. --replace
places every stored fight again after an alias is added.

    python -m data.ingestors.ufc_prop_history --spool DIR                  # the plan
    python -m data.ingestors.ufc_prop_history --spool DIR --stage pages --fetch --store
    python -m data.ingestors.ufc_prop_history --spool DIR --stage charts --jobs FILE --fetch --store
"""
from __future__ import annotations

import argparse
import base64
import difflib
import gzip
import html
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

SITE = "https://www.bestfightodds.com"
SOURCE = "bestfightodds"
UA = "Mozilla/5.0 (compatible; Signalbase research; signalbaseskinny@gmail.com)"
PAUSE_S = 3.0
FIRST_DAY = date(2021, 6, 1)
MATCH_DAYS = 2
HEADER_AHEAD_DAYS = 120  # a card page is up weeks, not months, before the card
SIMILAR = 0.7           # name likeness that places a fighter anchored by his opponent
STAGES = ("pages", "charts")

# BFO book id -> our bookmaker key (the Odds API's, where the book is one).
BOOKS = {12: "bfo_ref", 19: "bet365", 20: "betway", 21: "fanduel", 22: "draftkings",
         23: "betmgm", 24: "williamhill_us", 25: "betrivers", 26: "unibet",
         28: "polymarket", 29: "kalshi"}

# BFO spells a few fighters differently from ufcstats. Keys BFO, values ufcstats.
# Each was found on the same card in the log under the second spelling
# (2026-11-14, the unplaced fights that had props posted).
BFO_NAME_ALIASES: dict[str, str] = {
    "Bobby Green": "King Green",
    "Ariane Lipski": "Ariane da Silva",
    "Katlyn Chookagian": "Katlyn Cerminara",
    "Tecia Torres": "Tecia Pennington",
    "Cheyanne Buys": "Cheyanne Vlismas",
    "Sumudaerji Sumudaerji": "Sumudaerji",
    "Hayisaer Maheshate": "Maheshate",
    "Maheshate Hayisaer": "Maheshate",
    "Mizuki Inoue": "Mizuki",
    "Yana Kunitskaya": "Yana Santos",
    "Rodrigo Vargas": "Kazula Vargas",
    "Joshua Culibao": "Josh Culibao",
    "Alex Volkanovski": "Alexander Volkanovski",
    "Charlie Radtke": "Charles Radtke",
    "Mike Diamond": "Blood Diamond",
    "Viacheslav Borschev": "Viacheslav Borshchev",
    "Montserrat Rendon": "Montse Rendon",
    "Elizeu Zaleski": "Elizeu Zaleski dos Santos",
    "Zach Scroggin": "Zachary Scroggin",
    "Damon Blackshear": "Da'Mon Blackshear",
}

FIGHTS = "ufc_prop_history_fights"
FIGHT_COLS = ("matchup_id", "event_id", "event_slug", "event_date", "fighter1_name",
              "fighter1_bfo_slug", "fighter2_name", "fighter2_bfo_slug", "game_id",
              "fighter1_id", "fighter2_id", "source")
FIGHTS_DDL = """
CREATE TABLE IF NOT EXISTS ufc_prop_history_fights (
    matchup_id         INTEGER PRIMARY KEY,
    event_id           INTEGER NOT NULL,
    event_slug         TEXT NOT NULL,
    event_date         DATE NOT NULL,
    fighter1_name      TEXT NOT NULL,
    fighter1_bfo_slug  TEXT,
    fighter2_name      TEXT NOT NULL,
    fighter2_bfo_slug  TEXT,
    game_id            TEXT,
    fighter1_id        TEXT,
    fighter2_id        TEXT,
    source             TEXT NOT NULL
)
"""
FIGHTS_INDEX = "ufc_prop_history_fights_game_idx"
FIGHTS_INDEX_DDL = f"CREATE INDEX IF NOT EXISTS {FIGHTS_INDEX} ON {FIGHTS} (game_id)"

TABLE = "ufc_prop_history"
COLS = ("matchup_id", "book_id", "bookmaker", "prop_type", "team", "side", "label",
        "price", "event_id", "fetched_at", "source")
DDL = """
CREATE TABLE IF NOT EXISTS ufc_prop_history (
    matchup_id   INTEGER NOT NULL,
    book_id      INTEGER NOT NULL,
    bookmaker    TEXT NOT NULL,
    prop_type    INTEGER NOT NULL,
    team         INTEGER NOT NULL,
    side         INTEGER NOT NULL,
    label        TEXT NOT NULL,
    price        INTEGER NOT NULL,
    event_id     INTEGER NOT NULL,
    fetched_at   TIMESTAMPTZ NOT NULL,
    source       TEXT NOT NULL,
    PRIMARY KEY (matchup_id, book_id, prop_type, team, side)
)
"""

TICKS = "ufc_prop_history_ticks"
TICK_COLS = ("matchup_id", "book_id", "bookmaker", "prop_type", "team", "side",
             "quoted_at", "price_decimal", "price", "source")
TICKS_DDL = """
CREATE TABLE IF NOT EXISTS ufc_prop_history_ticks (
    matchup_id     INTEGER NOT NULL,
    book_id        INTEGER NOT NULL,
    bookmaker      TEXT NOT NULL,
    prop_type      INTEGER NOT NULL,
    team           INTEGER NOT NULL,
    side           INTEGER NOT NULL,
    quoted_at      TIMESTAMPTZ NOT NULL,
    price_decimal  REAL NOT NULL,
    price          INTEGER NOT NULL,
    source         TEXT NOT NULL,
    PRIMARY KEY (matchup_id, book_id, prop_type, team, side, quoted_at)
)
"""

PULLS = "ufc_prop_history_pulls"
PULL_COLS = ("pull_key", "kind", "event_id", "rows_stored", "fetched_at", "stored_at")
PULLS_DDL = """
CREATE TABLE IF NOT EXISTS ufc_prop_history_pulls (
    pull_key     TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,
    event_id     INTEGER,
    rows_stored  INTEGER NOT NULL,
    fetched_at   TIMESTAMPTZ,
    stored_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


def ensure_tables(conn) -> None:
    changed = False
    for name, cols, ddl, idx in ((FIGHTS, FIGHT_COLS, FIGHTS_DDL, (FIGHTS_INDEX,)),
                                 (TABLE, COLS, DDL, ()), (TICKS, TICK_COLS, TICKS_DDL, ()),
                                 (PULLS, PULL_COLS, PULLS_DDL, ())):
        if not schema_is_current(conn, name, columns=cols, indexes=idx, rls=True,
                                 revoked_from=API_ROLES):
            conn.execute(ddl)
            if name == FIGHTS:
                conn.execute(FIGHTS_INDEX_DDL)
            lock_down(conn, name)
            changed = True
    if changed:
        conn.commit()


# ── parsing (pure) ───────────────────────────────────────────────────────────

MONTHS = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
ROT = "".join(chr(c) for c in range(33, 127))          # the 94 printable characters


@dataclass
class Fight:
    matchup_id: int
    fighter1_name: str
    fighter1_bfo_slug: str | None = None
    fighter2_name: str | None = None
    fighter2_bfo_slug: str | None = None


@dataclass
class Cell:
    matchup_id: int
    book_id: int
    prop_type: int          # 0 = fight winner
    team: int               # 0 = the fight, 1 or 2 = that fighter
    side: int               # 1 = the row's own outcome, 2 = its opposite
    label: str
    price: int


@dataclass
class EventPage:
    event_date: date
    title: str
    books: dict[int, str] = field(default_factory=dict)
    fights: list[Fight] = field(default_factory=list)
    cells: list[Cell] = field(default_factory=list)


def sitemap_events(xml: str) -> list[tuple[int, str]]:
    """(event id, slug) for every UFC card in the events sitemap; the BJJ
    events the UFC also runs are left out."""
    out = []
    for slug in re.findall(r"<loc>[^<]*/events/([^<]+)</loc>", xml):
        m = re.fullmatch(r"(ufc-[a-z0-9-]*?)-?(\d+)", slug)
        if m and "bjj" not in slug:
            out.append((int(m.group(2)), slug))
    return sorted(set(out))


def american(text: str) -> int | None:
    t = text.strip().replace("−", "-").replace("–", "-")
    if t.lower() in ("ev", "even"):
        return 100
    m = re.fullmatch(r"([+-])(\d{3,6})", t)
    if not m:
        return None
    v = int(m.group(2))
    return v if m.group(1) == "+" else -v


def decimal_to_american(d: float) -> int:
    return int(round((d - 1) * 100)) if d >= 2 else int(round(-100 / (d - 1)))


def _text(fragment: str) -> str:
    # labels are escaped twice on the page ("1&amp;#189;")
    return html.unescape(html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def _page_date(title: str, page: str, today: date) -> date:
    """The card's date: from the title ("... – Jun 26, 2021 | Best Fight
    Odds"); on the 2026 pages whose title carries none, from the page's
    structured-data startDate; failing both, from the odds table's header
    ("May 9th", no year), in the year of `today` (the day the page was
    fetched) unless that lands more than HEADER_AHEAD_DAYS ahead of it."""
    m = re.search(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4}) \| Best Fight Odds", title)
    if m:
        return date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)))
    m = re.search(r'"startDate":\s*"(\d{4}-\d{2}-\d{2})', page)
    if m:
        return date.fromisoformat(m.group(1))
    m = re.search(r'table-header-date">([A-Z][a-z]{2})[a-z]* (\d{1,2})', page)
    if m:
        d = date(today.year, MONTHS[m.group(1)], int(m.group(2)))
        return d if (d - today).days <= HEADER_AHEAD_DAYS else d.replace(year=today.year - 1)
    raise ValueError(f"no date in title {title!r} or page")


def parse_event(page: str, today: date | None = None) -> EventPage:
    """The odds table of one event page: its books, fights and priced cells.
    `today`: the day the page was fetched (dates a page whose only date has
    no year)."""
    title = _text(re.search(r"<title>(.*?)</title>", page, re.S).group(1))
    ev = EventPage(event_date=_page_date(title, page, today or _now().date()), title=title)
    start = page.find('<table class="odds-table">')
    if start < 0:
        return ev
    body = page[start:]
    head = re.search(r"<thead>(.*?)</thead>", body, re.S)
    if head:
        for b, name in re.findall(r'data-b="(\d+)">(.*?)</th>', head.group(1), re.S):
            ev.books[int(b)] = _text(name.split("<br")[0])
    by_id: dict[int, Fight] = {}
    for attrs, head_cell, cells in re.findall(
            r'<tr([^>]*)><th scope="row"[^>]*>(.*?)</th>(.*?)</tr>', body, re.S):
        if 'class="pr"' in attrs:
            label = _text(head_cell)
            for b, side, mu, pt, tn, inner in re.findall(
                    r'<td class="but-sgp" data-li="\[(\d+),(\d+),(\d+),(\d+),(\d+)\]"[^>]*>(.*?)</td>',
                    cells, re.S):
                price = american(_text(re.sub(r"<span class=\"ar[^>]*>.*?</span>", "", inner)))
                if price is not None:
                    ev.cells.append(Cell(int(mu), int(b), int(pt), int(tn), int(side), label, price))
            continue
        slug = re.search(r'href="/fighters/([^"]+)"', head_cell)
        name = _text(head_cell)
        mu = re.search(r'data-mu="(\d+)"', cells) or re.search(
            r'data-li="\[(?:\d+,)?\d+,(\d+)\]"', cells)
        if not mu:
            continue
        mid = int(mu.group(1))
        f = by_id.get(mid)
        if f is None:
            f = by_id[mid] = Fight(mid, name, slug.group(1) if slug else None)
            ev.fights.append(f)
        else:
            f.fighter2_name, f.fighter2_bfo_slug = name, slug.group(1) if slug else None
        for b, side, inner in re.findall(
                r'<td class="but-sg" data-li="\[(\d+),(\d+),\d+\]"[^>]*>(.*?)</td>', cells, re.S):
            price = american(_text(re.sub(r"<span class=\"ar[^>]*>.*?</span>", "", inner)))
            if price is not None:
                ev.cells.append(Cell(mid, int(b), 0, 0, int(side), name, price))
    ev.fights = [f for f in ev.fights if f.fighter2_name]
    return ev


def decode_chart(raw: str) -> list[tuple[str, list[tuple[datetime, float]]]]:
    """A /api/ggd answer: base64, then ROT47, then JSON (the site's own
    notIn()). Each series is (name, [(time, decimal price)])."""
    raw = raw.strip()
    if len(raw) < 8:
        return []
    text = base64.b64decode(raw).decode("utf-8")
    data = json.loads("".join(ROT[(ROT.index(c) + 47) % 94] if c in ROT else c for c in text))
    out = []
    for s in data:
        pts = []
        for p in s.get("data", []):
            x, y = (p["x"], p["y"]) if isinstance(p, dict) else (p[0], p[1])
            pts.append((datetime.fromtimestamp(x / 1000, timezone.utc), float(y)))
        out.append((s.get("name") or "", pts))
    return out


# ── placement ────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    n = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")


SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


def compact(slug: str) -> str:
    """A slug without its hyphens: "seung-woo-choi" and "seungwoo-choi" meet."""
    return slug.replace("-", "")


def name_slugs(name: str, bfo_slug: str | None) -> set[str]:
    """Every compact slug a BFO fighter might carry in ufc_fight_log: the
    name, its aliases and BFO's own slug, each also without a generational
    suffix and in the other name orders ufcstats uses ("Kenan Song" is
    "Song Kenan", "Kang Kyung-Ho" is "Kyung Ho Kang")."""
    base = {slugify(name)}
    for alias_map in (BFO_NAME_ALIASES, config.UFC_NAME_ALIASES):
        if name in alias_map:
            base.add(slugify(alias_map[name]))
    if bfo_slug:
        base.add(re.sub(r"-\d+$", "", bfo_slug))
    out = set()
    for s in base:
        t = [x for x in s.split("-") if x]
        if len(t) > 2 and t[-1] in SUFFIXES:
            t = t[:-1]
        for order in (t, t[::-1], t[1:] + t[:1], t[-1:] + t[:-1]):
            out.add(compact("-".join(order)))
    out.discard("")
    return out


class FightPlacer:
    """Places a BFO fight on a ufc_fight_log game id, and each of its two
    fighters on a fight-log fighter id, by slug, never by position."""

    def __init__(self, rows: list[tuple[str, str, str, str]]):
        # rows: (game_id, game_date, fighter_id, fighter_name), two per fight
        per_game: dict[str, dict] = defaultdict(lambda: {"slugs": {}})
        for gid, d, fid, name in rows:
            g = per_game[gid]
            g["day"] = date.fromisoformat(str(d)[:10])
            g["slugs"][compact(slugify(name))] = fid
        self._by_slug: dict[str, list[str]] = defaultdict(list)
        self._games = per_game
        for gid, g in per_game.items():
            for s in g["slugs"]:
                self._by_slug[s].append(gid)
        self.last_day = max((g["day"] for g in per_game.values()), default=None)

    def __call__(self, f: Fight, day: date) -> tuple[str, str, str] | None:
        s1 = name_slugs(f.fighter1_name, f.fighter1_bfo_slug)
        s2 = name_slugs(f.fighter2_name or "", f.fighter2_bfo_slug)
        near = sorted(g for g in {g for s in s1 | s2 for g in self._by_slug.get(s, [])}
                      if abs((self._games[g]["day"] - day).days) <= MATCH_DAYS)
        found = []
        for gid in near:
            slugs = self._games[gid]["slugs"]
            a = [slugs[s] for s in s1 if s in slugs]
            b = [slugs[s] for s in s2 if s in slugs]
            if a and b and a[0] != b[0]:
                return gid, a[0], b[0]
            found.append((gid, a, b))
        # One fighter by name, and the log's only other fighter in that fight
        # spelled close to BFO's ("Ovince St. Preux" / "Ovince Saint Preux").
        for gid, a, b in found:
            if bool(a) == bool(b):
                continue
            known, names = (a[0], s2) if a else (b[0], s1)
            rest = [(s, fid) for s, fid in self._games[gid]["slugs"].items() if fid != known]
            if len(rest) == 1 and max(_similar(rest[0][0], n) for n in names) >= SIMILAR:
                return (gid, known, rest[0][1]) if a else (gid, rest[0][1], known)
        return None


def _similar(x: str, y: str) -> float:
    return difflib.SequenceMatcher(None, x, y).ratio()


def load_placer(conn) -> FightPlacer:
    rows = conn.execute(
        "SELECT game_id, game_date, fighter_id, fighter_name FROM ufc_fight_log").fetchall()
    return FightPlacer([tuple(r) for r in rows])


# ── the spool and the polite fetch ───────────────────────────────────────────

def _get(path: str, xhr: bool = False) -> str:
    headers = {"User-Agent": UA}
    if xhr:
        headers.update({"Referer": SITE + "/", "X-Requested-With": "XMLHttpRequest"})
    with urllib.request.urlopen(urllib.request.Request(SITE + path, headers=headers),
                                timeout=60) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8")


def _write_gz(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        fh.write(text)
    tmp.replace(p)


def _read_gz(p: Path) -> str:
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        return fh.read()


def page_path(spool: Path, event_id: int) -> Path:
    return spool / "pages" / f"{event_id}.html.gz"


def chart_key(b: int, m: int, pt: int, tn: int, p: int) -> str:
    return f"{b}_{m}_{pt}_{tn}_{p}"


def chart_path(spool: Path, key: str) -> Path:
    return spool / "charts" / key.split("_")[1][-2:] / f"{key}.txt.gz"


def chart_query(b: int, m: int, pt: int, tn: int, p: int) -> str:
    q = f"/api/ggd?b={b}&m={m}&p={p}"
    return q + (f"&pt={pt}&tn={tn}" if pt else "")


def fetch_pages(spool: Path, events: list[tuple[int, str]], last_day: date,
                held: set[str], pause: float = PAUSE_S) -> dict:
    stats = {"asked": 0, "spooled": 0, "future": 0, "failed": 0, "already": 0}
    for eid, slug in events:
        if page_path(spool, eid).exists() or f"page:{eid}" in held:
            stats["already"] += 1
            continue
        time.sleep(pause)
        stats["asked"] += 1
        try:
            body = _get(f"/events/{slug}")
        except (urllib.error.URLError, TimeoutError) as e:
            stats["failed"] += 1
            logger.warning(f"{slug}: {e}")
            continue
        try:
            day = parse_event(body).event_date
        except (ValueError, AttributeError) as e:
            stats["failed"] += 1
            logger.warning(f"{slug}: unreadable page ({e})")
            continue
        if day > last_day:
            stats["future"] += 1           # not fought yet: ask again later
            continue
        _write_gz(page_path(spool, eid), json.dumps({"event_id": eid, "slug": slug,
                                                     "fetched_at": _stamp(_now()),
                                                     "html": body}))
        stats["spooled"] += 1
    return stats


def fetch_charts(spool: Path, jobs: list[tuple[int, int, int, int, int]], held: set[str],
                 pause: float = PAUSE_S) -> dict:
    stats = {"asked": 0, "spooled": 0, "failed": 0, "already": 0}
    for job in jobs:
        key = chart_key(*job)
        if chart_path(spool, key).exists() or f"chart:{key}" in held:
            stats["already"] += 1
            continue
        time.sleep(pause)
        stats["asked"] += 1
        try:
            raw = _get(chart_query(*job), xhr=True)
        except (urllib.error.URLError, TimeoutError) as e:
            stats["failed"] += 1
            logger.warning(f"{key}: {e}")
            continue
        _write_gz(chart_path(spool, key), json.dumps({"key": key, "fetched_at": _stamp(_now()),
                                                      "raw": raw}))
        stats["spooled"] += 1
        if stats["asked"] % 500 == 0:
            logger.info(f"charts: {stats}")
    return stats


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── store ────────────────────────────────────────────────────────────────────

def _held(conn) -> set[str]:
    return {r[0] for r in conn.execute(f"SELECT pull_key FROM {PULLS}").fetchall()}


def _insert(conn, table: str, cols: tuple, rows: list[tuple], conflict: str) -> None:
    from psycopg2.extras import execute_values
    if not rows:
        return
    cur = conn._conn.cursor()
    execute_values(cur, f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s "
                        f"ON CONFLICT ({conflict}) DO NOTHING", rows, page_size=1000)
    cur.close()


def page_rows(event_id: int, slug: str, fetched_at: str, ev: EventPage,
              placer: FightPlacer) -> tuple[list[tuple], list[tuple]]:
    fights, cells = [], []
    known = set()
    for f in ev.fights:
        placed = placer(f, ev.event_date)
        gid, id1, id2 = placed if placed else (None, None, None)
        fights.append((f.matchup_id, event_id, slug, ev.event_date, f.fighter1_name,
                       f.fighter1_bfo_slug, f.fighter2_name, f.fighter2_bfo_slug, gid, id1,
                       id2, SOURCE))
        known.add(f.matchup_id)
    seen = set()
    for c in ev.cells:
        k = (c.matchup_id, c.book_id, c.prop_type, c.team, c.side)
        if c.matchup_id not in known or k in seen:
            continue
        seen.add(k)
        cells.append((c.matchup_id, c.book_id, BOOKS.get(c.book_id, f"bfo_{c.book_id}"),
                      c.prop_type, c.team, c.side, c.label, c.price, event_id, fetched_at,
                      SOURCE))
    return fights, cells


def store_pages(conn, spool: Path, placer: FightPlacer) -> dict:
    ensure_tables(conn)
    held = _held(conn)
    stats = {"pages": 0, "already": 0, "before_window": 0, "fights": 0, "placed": 0, "rows": 0}
    for p in sorted((spool / "pages").glob("*.html.gz"), key=lambda q: int(q.name.split(".")[0])):
        doc = json.loads(_read_gz(p))
        eid = doc["event_id"]
        if f"page:{eid}" in held:
            stats["already"] += 1
            continue
        ev = parse_event(doc["html"], date.fromisoformat(doc["fetched_at"][:10]))
        if ev.event_date < FIRST_DAY:
            stats["before_window"] += 1    # spooled so it is never asked again; not stored
            continue
        fights, cells = page_rows(eid, doc["slug"], doc["fetched_at"], ev, placer)
        _insert(conn, FIGHTS, FIGHT_COLS, fights, "matchup_id")
        _insert(conn, TABLE, COLS, cells, "matchup_id, book_id, prop_type, team, side")
        conn.execute(f"""INSERT INTO {PULLS} (pull_key, kind, event_id, rows_stored, fetched_at)
                         VALUES (%s, 'page', %s, %s, %s) ON CONFLICT (pull_key) DO NOTHING""",
                     (f"page:{eid}", eid, len(cells), doc["fetched_at"]))
        conn.commit()
        stats["pages"] += 1
        stats["fights"] += len(fights)
        stats["placed"] += sum(1 for f in fights if f[8])
        stats["rows"] += len(cells)
    return stats


def replace_fights(conn, placer: FightPlacer) -> dict:
    """Place every stored fight again (after an alias or a fight-log fix) and
    write the game and fighter ids that changed."""
    rows = conn.execute(f"""SELECT matchup_id, event_date, fighter1_name, fighter1_bfo_slug,
                                   fighter2_name, fighter2_bfo_slug, game_id, fighter1_id,
                                   fighter2_id FROM {FIGHTS}""").fetchall()
    changed = []
    for m, d, n1, b1, n2, b2, gid, i1, i2 in rows:
        day = d if isinstance(d, date) else date.fromisoformat(str(d)[:10])
        got = placer(Fight(m, n1, b1, n2, b2), day) or (None, None, None)
        if got != (gid, i1, i2):
            changed.append((*got, m))
    if changed:
        conn.executemany(f"UPDATE {FIGHTS} SET game_id = %s, fighter1_id = %s, fighter2_id = %s "
                         f"WHERE matchup_id = %s", changed)
        conn.commit()
    return {"fights": len(rows), "changed": len(changed),
            "placed_now": sum(1 for c in changed if c[0])}


def tick_rows(key: str, raw: str) -> list[tuple]:
    b, m, pt, tn, p = (int(x) for x in key.split("_"))
    out, seen = [], set()
    for _name, pts in decode_chart(raw):
        for t, d in pts:
            if d <= 1 or t in seen:
                continue
            seen.add(t)
            out.append((m, b, BOOKS.get(b, f"bfo_{b}"), pt, tn, p, t, d, decimal_to_american(d),
                        SOURCE))
    return out


def store_charts(conn, spool: Path) -> dict:
    ensure_tables(conn)
    held = _held(conn)
    stats = {"charts": 0, "already": 0, "empty": 0, "rows": 0}
    batch_keys, batch_rows = [], []

    def flush():
        _insert(conn, TICKS, TICK_COLS, batch_rows,
                "matchup_id, book_id, prop_type, team, side, quoted_at")
        from psycopg2.extras import execute_values
        cur = conn._conn.cursor()
        execute_values(cur, f"INSERT INTO {PULLS} (pull_key, kind, event_id, rows_stored, "
                            f"fetched_at) VALUES %s ON CONFLICT (pull_key) DO NOTHING",
                       batch_keys, page_size=1000)
        cur.close()
        conn.commit()
        batch_keys.clear()
        batch_rows.clear()

    for p in sorted((spool / "charts").rglob("*.txt.gz")):
        doc = json.loads(_read_gz(p))
        key = doc["key"]
        if f"chart:{key}" in held:
            stats["already"] += 1
            continue
        rows = tick_rows(key, doc["raw"])
        stats["charts"] += 1
        stats["empty"] += not rows
        stats["rows"] += len(rows)
        batch_rows.extend(rows)
        batch_keys.append((f"chart:{key}", "chart", None, len(rows), doc["fetched_at"]))
        if len(batch_keys) >= 500:
            flush()
    if batch_keys:
        flush()
    return stats


# ── which histories to ask for ───────────────────────────────────────────────

# (prop_type, team, side): the method, distance and round markets graded in
# docs/ufc_market_audit.md section 5. prop_type 0 is the fight winner.
CORE_SERIES = ([(0, 0, 1), (0, 0, 2), (1, 0, 1), (1, 0, 2)]
               + [(pt, tn, 1) for pt in (8, 9, 11) for tn in (1, 2)]
               + [(10, tn, s) for tn in (1, 2) for s in (1, 2)]
               + [(pt, tn, 1) for pt in (13, 14, 15) for tn in (1, 2)]
               + [(pt, 0, 1) for pt in (22, 23, 24)])


def chart_jobs(conn, books: list[int], series=CORE_SERIES, priced_only: bool = True,
               ) -> list[tuple[int, int, int, int, int]]:
    """(book, fight, prop, team, side) histories to ask for. A book shown on
    the page is asked only where the page priced that cell (priced_only); a
    book the page does not show (Ref, Bet365) is asked on every series."""
    fights = [r[0] for r in conn.execute(
        f"SELECT matchup_id FROM {FIGHTS} WHERE game_id IS NOT NULL ORDER BY event_date, "
        f"matchup_id").fetchall()]
    priced = {tuple(r) for r in conn.execute(
        f"SELECT book_id, matchup_id, prop_type, team, side FROM {TABLE}").fetchall()}
    want = set(series)
    out = []
    for m in fights:
        for b in books:
            for pt, tn, p in series:
                if b in (12, 19) or not priced_only:
                    out.append((b, m, pt, tn, p))
                elif (b, m, pt, tn, p) in priced and (pt, tn, p) in want:
                    out.append((b, m, pt, tn, p))
    return out


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spool", required=True, type=Path)
    ap.add_argument("--stage", choices=STAGES)
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--store", action="store_true")
    ap.add_argument("--events", help="comma-separated BFO event ids (a trial)")
    ap.add_argument("--books", default="22,21,23,24,25",
                    help="chart stage: BFO book ids to ask histories for")
    ap.add_argument("--jobs", type=Path,
                    help="chart stage: a file of histories to ask for, one 'book,matchup,prop,team,side' a line")
    ap.add_argument("--sample", type=int, default=0,
                    help="chart stage: ask only this many histories, drawn at random (seeded)")
    ap.add_argument("--pause", type=float, default=PAUSE_S)
    ap.add_argument("--replace", action="store_true",
                    help="place every stored fight again and write what changed")
    a = ap.parse_args()
    from data.db import get_connection
    conn = get_connection()
    try:
        ensure_tables(conn)
        placer = load_placer(conn)
        held = _held(conn)
        if a.replace:
            logger.success(f"replace fights: {replace_fights(conn, placer)}")
        if a.stage in (None, "pages"):
            xml = _get("/sitemap-events.xml")
            events = [e for e in sitemap_events(xml) if e[0] >= 2000]
            if a.events:
                keep = {int(x) for x in a.events.split(",")}
                events = [e for e in events if e[0] in keep]
            todo = [e for e in events if not page_path(a.spool, e[0]).exists()
                    and f"page:{e[0]}" not in held]
            logger.info(f"pages: {len(events)} UFC event pages from id 2000, {len(todo)} not "
                        f"spooled; last card in the fight log {placer.last_day}")
            if a.fetch and a.stage == "pages":
                logger.info(f"fetch pages: {fetch_pages(a.spool, events, placer.last_day, held, a.pause)}")
            if a.store and a.stage == "pages":
                logger.success(f"store pages: {store_pages(conn, a.spool, placer)}")
        if a.stage in (None, "charts"):
            if a.jobs:
                # a study's own list: "book,matchup,prop_type,team,side" per line
                jobs = [tuple(int(x) for x in ln.split(",")) for ln in
                        a.jobs.read_text(encoding="utf-8").splitlines() if ln.strip()]
            else:
                jobs = chart_jobs(conn, [int(b) for b in a.books.split(",")])
            if a.sample:
                import random
                jobs = sorted(random.Random(20261113).sample(jobs, min(a.sample, len(jobs))))
            todo = [j for j in jobs if not chart_path(a.spool, chart_key(*j)).exists()
                    and f"chart:{chart_key(*j)}" not in held]
            logger.info(f"charts: {len(jobs):,} histories, {len(todo):,} not spooled, "
                        f"~{len(todo) * (a.pause + 0.4) / 3600:.1f} h at {a.pause}s apart")
            if a.fetch and a.stage == "charts":
                logger.info(f"fetch charts: {fetch_charts(a.spool, jobs, held, a.pause)}")
            if a.store and a.stage == "charts":
                logger.success(f"store charts: {store_charts(conn, a.spool)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
