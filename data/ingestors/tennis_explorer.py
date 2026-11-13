"""TennisExplorer's daily results pages: every professional singles match with
its score and one pair of prices, for the levels nothing else here carries.

WHY. ESPN carries the whole men's and women's tours (every 250 and WTA 125)
but no Challenger and no ITF match; the match archive stops at its June 2026
snapshot; the odds feed prices only its 53 top-tier tournaments. TennisExplorer
lists every level on one page a day:

    https://www.tennisexplorer.com/results/?type=<type>&year=Y&month=M&day=D
    types read off its own page (2026-11-13): all, atp-single, wta-single,
    itf-men, atp-double, wta-double

Each match is two table rows: the time, each player (a profile link that is the
player's stable id here, e.g. /player/musetti/), sets won, games in each set
(a tiebreak's points in <sup>), and two decimal prices, the winner's marked
`coursew`. Its robots.txt allows the results pages; its terms page is closed to
crawlers (robots.txt disallows /terms-of-use/), so the terms are not read.

WHAT THE TWO PRICES ARE (which book, which moment) is measured before anything
treats them as a price we could bet or as a close: docs/sports/tennis.md,
"TennisExplorer's prices".

This module parses a page. A crawl, when it runs, fetches one page every two
seconds or slower.
"""
from __future__ import annotations

import html as htmlmod
import re
from dataclasses import dataclass

_ROW = re.compile(r'<tr id="r(\d+)(b?)"[^>]*>(.*?)</tr>', re.S)
_HEAD = re.compile(r'<tr class="head flags">(.*?)</tr>', re.S)
_PLAYER = re.compile(r'<td class="t-name"><a href="(/player/[^"]+)">([^<]+)</a>')
_TOURNEY = re.compile(r'<a href="(/[^"]+/\d{4}/[^"]+/)">(?:<span[^>]*>&nbsp;</span>)*([^<]+)</a>')
_CELL = re.compile(r'<td class="(result|score|course|coursew|first time)"[^>]*>(.*?)</td>', re.S)
_DETAIL = re.compile(r'/match-detail/\?id=(\d+)')


def level_of(tournament: str | None, path: str | None) -> str:
    """'tour', 'challenger', '125', 'itf' or 'other' (UTR series, team leagues,
    exhibitions), from TennisExplorer's own names and paths. Read off its
    pages of 2025-08-31: men's ITF events sit under one unlinked "Futures
    2025" header; women's ITF events end in " ITF" ("Bytom ITF"); the WTA 125
    events end in " WTA" ("Changsha WTA", "Montreux WTA"); men's Challengers
    end in " challenger"; tour events carry the plain name ("US Open")."""
    name = (tournament or "").lower().strip()
    path = path or ""
    if name.startswith("futures") or name.startswith("itf") or name.endswith(" itf")             or "-itf/" in path:
        return "itf"
    if "challenger" in name or "challenger" in path:
        return "challenger"
    if name.endswith(" wta") or "-wta/" in path:
        return "125"
    if any(w in name for w in ("utr", "bundesliga", "league", "exhibition", "cup of", "pro tennis series")):
        return "other"
    return "tour" if path else "other"


@dataclass
class TEMatch:
    match_id: str | None
    tournament: str | None
    tournament_path: str | None
    time: str | None
    p1_slug: str
    p1_name: str
    p2_slug: str
    p2_name: str
    p1_sets: int | None
    p2_sets: int | None
    p1_games: list
    p2_games: list
    p1_tiebreaks: list
    p2_tiebreaks: list
    p1_price: float | None
    p2_price: float | None
    winner_marked: int | None      # 1 or 2: whose price carries `coursew`


def _num(s: str):
    s = htmlmod.unescape(re.sub(r"<[^>]+>", "", s)).strip()
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def _games(cell: str) -> tuple:
    """'6<sup>5</sup>' -> (6, 5); '7' -> (7, None); '&nbsp;' -> (None, None)."""
    m = re.match(r"\s*(\d+)\s*(?:<sup>(\d+)</sup>)?", cell)
    if not m:
        return None, None
    return int(m.group(1)), (int(m.group(2)) if m.group(2) else None)


def parse_results_page(page: str) -> list[TEMatch]:
    """Every match on one results page, with the tournament header above it."""
    out: list[TEMatch] = []
    # Walk headers and rows in document order.
    tokens = [(m.start(), "head", m) for m in _HEAD.finditer(page)]
    tokens += [(m.start(), "row", m) for m in _ROW.finditer(page)]
    tokens.sort(key=lambda t: t[0])
    tourney = tpath = None
    pending = None
    for _, kind, m in tokens:
        if kind == "head":
            t = _TOURNEY.search(m.group(1))
            if t:
                tpath, tourney = t.group(1), htmlmod.unescape(t.group(2)).strip()
            else:
                # ITF events sit under one unlinked header ("Futures 2025").
                cell = re.search(r'<td class="t-name"[^>]*>(.*?)</td>', m.group(1), re.S)
                text = htmlmod.unescape(re.sub(r"<[^>]+>", "", cell.group(1))).strip() if cell else ""
                tpath, tourney = None, (text or None)
            continue
        body, second = m.group(3), m.group(2) == "b"
        p = _PLAYER.search(body)
        if not p:
            pending = None
            continue
        cells = _CELL.findall(body)
        sets = next((_num(v) for k, v in cells if k == "result"), None)
        games = [_games(v) for k, v in cells if k == "score"]
        if not second:
            prices = [(k, _num(v)) for k, v in cells if k in ("course", "coursew")]
            time_cell = next((htmlmod.unescape(re.sub(r"<[^>]+>", "", v)).strip()
                              for k, v in cells if k == "first time"), None)
            det = _DETAIL.search(body)
            pending = {"tourney": tourney, "tpath": tpath, "time": time_cell,
                       "slug": p.group(1), "name": htmlmod.unescape(p.group(2)).strip(),
                       "sets": sets, "games": games, "prices": prices,
                       "id": det.group(1) if det else None}
            continue
        if pending is None:
            continue
        a = pending
        pr = a["prices"]
        p1p = pr[0][1] if len(pr) > 0 else None
        p2p = pr[1][1] if len(pr) > 1 else None
        marked = 1 if (pr and pr[0][0] == "coursew") else (2 if len(pr) > 1 and pr[1][0] == "coursew" else None)
        out.append(TEMatch(
            a["id"], a["tourney"], a["tpath"], a["time"], a["slug"], a["name"],
            p.group(1), htmlmod.unescape(p.group(2)).strip(), a["sets"], sets,
            [g for g, _ in a["games"] if g is not None], [g for g, _ in games if g is not None],
            [t for g, t in a["games"] if g is not None], [t for g, t in games if g is not None],
            p1p, p2p, marked))
        pending = None
    return out


# ── store and crawl ──────────────────────────────────────────────────────────

import json
import time
from datetime import date, timedelta

import requests
from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

URL = "https://www.tennisexplorer.com/results/"
SOURCE = "tennisexplorer_results"
PAGE_TYPES = ("atp-single", "wta-single")       # every level of each, ITF included
TOUR_OF = {"atp-single": "ATP", "wta-single": "WTA"}
PAUSE_S = 2.0

TABLE = "tennis_te_matches"
COLS = ("match_id", "page_date", "tour", "level", "tournament", "tournament_path", "local_time",
        "p1_slug", "p1_name", "p2_slug", "p2_name", "p1_sets", "p2_sets", "p1_games",
        "p2_games", "p1_tiebreaks", "p2_tiebreaks", "p1_price", "p2_price", "winner_marked",
        "source")
DDL = """
CREATE TABLE IF NOT EXISTS tennis_te_matches (
    match_id         TEXT PRIMARY KEY,
    page_date        DATE NOT NULL,
    tour             TEXT NOT NULL,
    level            TEXT NOT NULL,
    tournament       TEXT,
    tournament_path  TEXT,
    local_time       TEXT,
    p1_slug          TEXT NOT NULL,
    p1_name          TEXT,
    p2_slug          TEXT NOT NULL,
    p2_name          TEXT,
    p1_sets          INTEGER,
    p2_sets          INTEGER,
    p1_games         INTEGER[],
    p2_games         INTEGER[],
    p1_tiebreaks     INTEGER[],
    p2_tiebreaks     INTEGER[],
    p1_price         DOUBLE PRECISION,
    p2_price         DOUBLE PRECISION,
    winner_marked    INTEGER,
    source           TEXT NOT NULL,
    imported_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
INDEX = "idx_tennis_te_matches_date"
INDEX_DDL = f"CREATE INDEX IF NOT EXISTS {INDEX} ON {TABLE} (tour, page_date)"
_UPSERT = (f"INSERT INTO {TABLE} ({', '.join(COLS)}) VALUES ({', '.join(['%s'] * len(COLS))}) "
           "ON CONFLICT (match_id) DO UPDATE SET level = EXCLUDED.level, "
           "tournament = EXCLUDED.tournament, p1_sets = EXCLUDED.p1_sets, "
           "p2_sets = EXCLUDED.p2_sets, p1_games = EXCLUDED.p1_games, p2_games = EXCLUDED.p2_games, "
           "p1_tiebreaks = EXCLUDED.p1_tiebreaks, p2_tiebreaks = EXCLUDED.p2_tiebreaks, "
           "p1_price = EXCLUDED.p1_price, p2_price = EXCLUDED.p2_price, "
           "winner_marked = EXCLUDED.winner_marked")


def ensure_tables(conn) -> None:
    if not schema_is_current(conn, TABLE, columns=COLS, indexes=(INDEX,), rls=True,
                             revoked_from=API_ROLES):
        conn.execute(DDL)
        conn.execute(INDEX_DDL)
        lock_down(conn, TABLE)
        conn.commit()


def rows_for(page: str, page_type: str, day: date) -> list[tuple]:
    """A page's matches at the three professional levels, keyed on
    TennisExplorer's own match id (a match without one is dropped)."""
    out = []
    for m in parse_results_page(page):
        lvl = level_of(m.tournament, m.tournament_path)
        if lvl == "other" or not m.match_id:
            continue
        out.append((m.match_id, day.isoformat(), TOUR_OF[page_type], lvl, m.tournament,
                    m.tournament_path, m.time, m.p1_slug, m.p1_name, m.p2_slug, m.p2_name,
                    m.p1_sets, m.p2_sets, m.p1_games, m.p2_games,
                    [t for t in m.p1_tiebreaks], [t for t in m.p2_tiebreaks],
                    m.p1_price, m.p2_price, m.winner_marked, SOURCE))
    return out


def held_days(conn) -> set:
    rows = conn.execute(f"SELECT DISTINCT tour, page_date FROM {TABLE} WHERE source = %s",
                        (SOURCE,)).fetchall()
    return {(r[0], r[1]) for r in rows}


def crawl(conn, first: date, last: date, *, resume: bool = True) -> dict:
    """One page a day per tour, newest first, two seconds apart; each page's
    rows stored before the next is asked. A day already held is skipped when
    `resume` (today and yesterday are always re-read: results land late)."""
    ensure_tables(conn)
    held = held_days(conn) if resume else set()
    if not resume:
        logger.info("re-reading every day in the range")
    today = date.today()
    n_pages = n_rows = 0
    d = last
    while d >= first:
        for pt in PAGE_TYPES:
            if resume and (TOUR_OF[pt], d) in held and d < today - timedelta(days=1):
                continue
            r = requests.get(URL, params={"type": pt, "year": d.year, "month": d.month,
                                          "day": d.day}, timeout=60)
            time.sleep(PAUSE_S)
            if r.status_code != 200:
                logger.warning(f"TennisExplorer {pt} {d}: HTTP {r.status_code}; stopping")
                return {"pages": n_pages, "rows": n_rows, "stopped_at": d.isoformat()}
            rows = rows_for(r.text, pt, d)
            if rows:
                conn.executemany(_UPSERT, rows)
            conn.commit()
            n_pages += 1
            n_rows += len(rows)
        if d.day == 1:
            logger.info(f"TennisExplorer through {d}: {n_pages} pages, {n_rows} rows")
        d -= timedelta(days=1)
    return {"pages": n_pages, "rows": n_rows}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="TennisExplorer results -> Supabase")
    ap.add_argument("--from", dest="first", required=True)
    ap.add_argument("--to", dest="last", default=date.today().isoformat())
    ap.add_argument("--reread", action="store_true", help="read days already held again")
    a = ap.parse_args(argv)
    from data.db import get_connection
    conn = get_connection()
    try:
        print(json.dumps(crawl(conn, date.fromisoformat(a.first), date.fromisoformat(a.last),
                               resume=not a.reread)))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
