"""DraftKings' own player-prop handle and bet shares, from DK Network's prop-split articles.

mike, 2026-11-26 ("Do all the outstanding tasks now"). DK Network's splits table covers moneyline / spread /
total only, for every event group (worker_jobs 1722475). Player-prop splits are published as articles for featured
NFL games: 34 found through the site's WordPress posts API, 2026-09-14 to 2026-11-23, every TNF / SNF / MNF game
and some Sunday slates (worker_jobs 1723195). The search stopped at its 1,000-post cap and a 2025-02-09 Super Bowl
article exists outside that list, so 34 is a floor.

Two table layouts were measured (worker_jobs 1723195, the bodies of posts 481849 and 443922):

* ``side_line`` (November): Player | Market | Line | Handle split | Bet split, the line cell naming the side
  ("Under 20.5"), the two shares that side's.
* ``leaders`` (September): Player prop | Line | Handle leader | Bet leader, each leader cell a side and its share
  ("Over (99.1%)"); the handle and bet leaders can be different sides.

Any other table (the anytime-touchdown rank lists carry no percentages) is counted as skipped, never guessed at.
Every table, parsed or not, is kept as printed in ``dk_prop_split_tables`` (header and body cells), so a layout no
parser reads yet can be parsed later from the database: the first import (worker_jobs 1724494) parsed 4 of 35
versions, and 31 from 2026-09-17 to 2026-11-16 use a layout that had not been seen.

WRITES. ``dk_prop_split_articles`` (one row per article version read: post id and WordPress's modified time) and
``dk_prop_splits`` (one row per table row of that version), both worker-only. A version already in the ledger is
not fetched again, and an edited article is a new version: nothing is updated or deleted. No API key, no Odds API
credits. Each row's ``prop_text`` is the player and market as printed; ``game_id`` is set only when the title
names exactly one NFL game on our schedule.

    python -m data.ingestors.dk_prop_splits            # newest page of search results
    python -m data.ingestors.dk_prop_splits --pages 50 # backfill
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from html import unescape
from typing import Callable
from zoneinfo import ZoneInfo

from loguru import logger

SOURCE = "dk_network_article"
WP_POSTS = "https://dknetwork.draftkings.com/wp-json/wp/v2/posts"
SEARCH = "prop splits"
PER_PAGE = 100
REQUEST_TIMEOUT = 25
_ET = ZoneInfo("America/New_York")
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

_BLOCK = re.compile(r"<h[23][^>]*>(?P<h>.*?)</h[23]>|(?P<t><table\b.*?</table>)", re.S | re.I)
_ROW = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<t([hd])\b[^>]*>(.*?)</t[hd]>", re.S | re.I)
_SIDE_LINE = re.compile(r"^(?P<side>[A-Za-z]+)\s+(?P<line>[+\-]?\d+(?:\.\d+)?)$")
_LEADER = re.compile(r"^(?P<side>[A-Za-z]+)\s*\(\s*(?P<pct>\d{1,3}(?:\.\d+)?)\s*%\s*\)$")
_PCT = re.compile(r"^(?P<pct>\d{1,3}(?:\.\d+)?)\s*%$")
# "Updated Monday, Nov. 23 at 6:04 p.m. ET." / "Updated September 14, 2026." (the two bodies measured).
_UPDATED = re.compile(r"Updated\b.{0,90}?(?:\bET\b\.?|\d{4}\.)|Updated\b.{0,60}", re.I)
_TITLE_GAME = re.compile(r"^(?P<a>\w[\w.' ]*?) vs\.? (?P<b>\w[\w.' ]*?) player\b", re.I)


def text_of(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html or "", flags=re.S | re.I)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def is_prop_split_title(title: str) -> bool:
    t = (title or "").lower()
    return "prop" in t and "split" in t


def _num(s: str) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _table(html: str) -> tuple[list[str], list[list[str]]]:
    """(header cells, body rows) of one <table>, as visible text."""
    header: list[str] = []
    rows: list[list[str]] = []
    for tr in _ROW.findall(html):
        cells = _CELL.findall(tr)
        if not cells:
            continue
        texts = [text_of(c) for _, c in cells]
        if all(kind.lower() == "h" for kind, _ in cells) and not header:
            header = [t.lower() for t in texts]
        else:
            rows.append(texts)
    return header, rows


def _col(header: list[str], *needles: str, exclude: str = "") -> int | None:
    for i, h in enumerate(header):
        if all(n in h for n in needles) and not (exclude and exclude in h):
            return i
    return None


def parse_row(layout: str, cols: dict, cells: list[str]) -> dict | None:
    """One table row -> the stored fields, or None when a cell does not read. Pure."""
    def cell(k):
        i = cols.get(k)
        return cells[i].strip() if i is not None and i < len(cells) else ""

    if layout == "side_line":
        m = _SIDE_LINE.match(cell("line"))
        h, b = _PCT.match(cell("handle")), _PCT.match(cell("bets"))
        if not (m and (h or b) and cell("player")):
            return None
        side = m.group("side").lower()
        return {"prop_text": f"{cell('player')} {cell('market')}".strip(), "player": cell("player"),
                "market": cell("market") or None, "line_value": _num(m.group("line")),
                "handle_side": side if h else None, "handle_pct": _num(h.group("pct")) if h else None,
                "bets_side": side if b else None, "bets_pct": _num(b.group("pct")) if b else None}
    h, b = _LEADER.match(cell("handle")), _LEADER.match(cell("bets"))
    if not ((h or b) and cell("prop")):
        return None
    return {"prop_text": cell("prop"), "player": None, "market": None, "line_value": _num(cell("line")),
            "handle_side": h.group("side").lower() if h else None, "handle_pct": _num(h.group("pct")) if h else None,
            "bets_side": b.group("side").lower() if b else None, "bets_pct": _num(b.group("pct")) if b else None}


def parse_article(html: str) -> tuple[list[dict], int]:
    """(rows, tables skipped) for one article body. Each row carries table_no, row_no, section, layout. Pure."""
    rows, skipped, _ = parse_article_tables(html)
    return rows, skipped


def parse_article_tables(html: str) -> tuple[list[dict], int, list[dict]]:
    """(rows, tables skipped, every table as printed: {table_no, section, header, body, layout}). Pure."""
    out: list[dict] = []
    tables: list[dict] = []
    skipped = 0
    section = None
    table_no = 0
    for m in _BLOCK.finditer(html or ""):
        if m.group("h") is not None:
            section = text_of(m.group("h")) or section
            continue
        table_no += 1
        header, rows = _table(m.group("t"))
        printed = {"table_no": table_no, "section": section, "header": header, "body": rows, "layout": None}
        tables.append(printed)
        handle = _col(header, "handle")
        bets = _col(header, "bet", exclude="handle")
        line = _col(header, "line")
        if _col(header, "player prop") is not None and handle is not None:
            layout = "leaders"
            cols = {"prop": _col(header, "player prop"), "line": line, "handle": handle, "bets": bets}
        elif _col(header, "player") is not None and _col(header, "market") is not None and handle is not None:
            layout = "side_line"
            cols = {"player": _col(header, "player"), "market": _col(header, "market"), "line": line,
                    "handle": handle, "bets": bets}
        else:
            skipped += 1
            continue
        kept = 0
        for row_no, cells in enumerate(rows, start=1):
            r = parse_row(layout, cols, cells)
            if r is None:
                continue
            kept += 1
            out.append({"table_no": table_no, "row_no": row_no, "section": section, "layout": layout, **r})
        if not kept:
            skipped += 1
        else:
            printed["layout"] = layout
    return out, skipped, tables


def updated_text(html: str) -> str | None:
    m = _UPDATED.search(text_of(html))
    return m.group(0).strip() if m else None


def _ts(v) -> datetime | None:
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def title_game(title: str, posted: datetime | None, games: list[dict]) -> str | None:
    """The one NFL game a title names ("Bengals vs. Commanders Player Prop ..."), within a day before and three
    after the post's ET date, or None. Multi-game titles ("NFL Week 4 Sunday ...") name none. Pure."""
    m = _TITLE_GAME.match(title or "")
    if not m or posted is None:
        return None
    from config import NFL_ODDS_API_MAP
    def ids(nick: str) -> set[str]:
        n = " " + nick.strip().lower()
        return {abbr for full, abbr in NFL_ODDS_API_MAP.items() if full.lower().endswith(n)}
    a, b = ids(m.group("a")), ids(m.group("b"))
    if not a or not b:
        return None
    day = posted.astimezone(_ET).date()
    hits = {g["game_id"] for g in games
            if {g["home_team"], g["away_team"]} & a and {g["home_team"], g["away_team"]} & b
            and g["home_team"] != g["away_team"]
            and -1 <= (date.fromisoformat(g["game_date"]) - day).days <= 3}
    return next(iter(hits)) if len(hits) == 1 else None


def _default_get(url: str, params: dict) -> tuple[int | None, str, dict]:
    import requests
    try:
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT,
                         headers={"User-Agent": _UA, "Accept": "application/json"})
    except Exception as exc:                                  # noqa: BLE001
        logger.warning(f"dk_prop_splits {url}: fetch failed: {exc}")
        return None, "", {}
    return r.status_code, r.text, dict(r.headers)


def find_posts(get, pages: int) -> list[dict]:
    """Prop-split posts from the newest `pages` pages of the search, newest first."""
    out: list[dict] = []
    for page in range(1, pages + 1):
        status, text, headers = get(WP_POSTS, {"search": SEARCH, "orderby": "date", "order": "desc",
                                               "per_page": PER_PAGE, "page": page,
                                               "_fields": "id,date_gmt,modified_gmt,link,title"})
        if status != 200:
            break
        try:
            posts = json.loads(text)
        except ValueError:
            break
        if not isinstance(posts, list) or not posts:
            break
        for p in posts:
            title = text_of((p.get("title") or {}).get("rendered") or "")
            if is_prop_split_title(title):
                out.append({"id": int(p["id"]), "title": title, "link": p.get("link"),
                            "date": _ts(p.get("date_gmt")), "modified": _ts(p.get("modified_gmt"))})
        total = headers.get("X-WP-TotalPages") or headers.get("x-wp-totalpages")
        if total and page >= int(total):
            break
        time.sleep(0.5)
    return out


# A version read again because its tables were not kept yet keeps its first ledger row, except that a row
# recording nothing stored takes the new counts (the counts describe what is in dk_prop_splits).
ARTICLE_SQL = """
INSERT INTO public.dk_prop_split_articles
    (post_id, post_modified, post_date, title, link, updated_text, game_id, rows_stored, tables_skipped, source)
VALUES (%(post_id)s, %(post_modified)s, %(post_date)s, %(title)s, %(link)s, %(updated_text)s, %(game_id)s,
        %(rows_stored)s, %(tables_skipped)s, %(source)s)
ON CONFLICT (post_id, post_modified) DO UPDATE SET
    rows_stored = EXCLUDED.rows_stored, tables_skipped = EXCLUDED.tables_skipped
WHERE public.dk_prop_split_articles.rows_stored = 0 AND EXCLUDED.rows_stored > 0
"""
TABLE_SQL = """
INSERT INTO public.dk_prop_split_tables (post_id, post_modified, table_no, section, header, body, layout, source)
VALUES (%(post_id)s, %(post_modified)s, %(table_no)s, %(section)s, %(header)s, %(body)s, %(layout)s, %(source)s)
ON CONFLICT (post_id, post_modified, table_no) DO NOTHING
"""
ROW_SQL = """
INSERT INTO public.dk_prop_splits
    (post_id, post_modified, game_id, table_no, row_no, section, layout, prop_text, player, market, line_value,
     handle_side, handle_pct, bets_side, bets_pct, source)
VALUES (%(post_id)s, %(post_modified)s, %(game_id)s, %(table_no)s, %(row_no)s, %(section)s, %(layout)s,
        %(prop_text)s, %(player)s, %(market)s, %(line_value)s, %(handle_side)s, %(handle_pct)s, %(bets_side)s,
        %(bets_pct)s, %(source)s)
ON CONFLICT (post_id, post_modified, table_no, row_no) DO NOTHING
"""


def run(conn=None, *, pages: int = 1, get: Callable | None = None) -> dict:
    """One pass: read every prop-split article version not yet in the ledger. Returns counts."""
    get = get or _default_get
    own = conn is None
    if own:
        from data.db import get_connection
        conn = get_connection()
    try:
        if conn.execute("SELECT to_regclass('public.dk_prop_splits') IS NOT NULL "
                        "AND to_regclass('public.dk_prop_split_tables') IS NOT NULL").fetchone()[0] is not True:
            logger.info("dk_prop_splits: tables not created yet; nothing written")
            return {}
        posts = find_posts(get, pages)
        ids = {"ids": [p["id"] for p in posts]}
        # Done: a version whose tables are kept, or one the ledger shows had no table at all.
        seen = ({(int(r[0]), _ts(r[1])) for r in conn.execute(
                    "SELECT DISTINCT post_id, post_modified FROM public.dk_prop_split_tables "
                    "WHERE post_id = ANY(%(ids)s)", ids).fetchall()}
                | {(int(r[0]), _ts(r[1])) for r in conn.execute(
                    "SELECT post_id, post_modified FROM public.dk_prop_split_articles WHERE post_id = ANY(%(ids)s) "
                    "AND rows_stored = 0 AND tables_skipped = 0", ids).fetchall()}) if posts else set()
        cols = ("game_id", "game_date", "home_team", "away_team")
        out = {"posts": len(posts), "new_versions": 0, "rows": 0, "tables_skipped": 0, "with_game": 0}
        for p in posts:
            if p["modified"] is None or (p["id"], p["modified"]) in seen:
                continue
            status, text, _ = get(f"{WP_POSTS}/{p['id']}", {"_fields": "id,modified_gmt,content"})
            if status != 200:
                continue
            try:
                body = json.loads(text)
            except ValueError:
                continue
            modified = _ts(body.get("modified_gmt")) or p["modified"]
            html = (body.get("content") or {}).get("rendered") or ""
            rows, skipped, tables = parse_article_tables(html)
            game_id = None
            if p["date"] is not None:
                d = p["date"].astimezone(_ET).date()
                games = [dict(zip(cols, r)) for r in conn.execute(
                    "SELECT game_id, game_date::text, home_team, away_team FROM public.games "
                    "WHERE sport = 'NFL' AND game_date::date BETWEEN %(lo)s AND %(hi)s",
                    {"lo": d - timedelta(days=1), "hi": d + timedelta(days=3)}).fetchall()]
                game_id = title_game(p["title"], p["date"], games)
            common = {"post_id": p["id"], "post_modified": modified, "game_id": game_id, "source": SOURCE}
            if tables:
                conn.executemany(TABLE_SQL, [{**common, **t, "header": json.dumps(t["header"]),
                                              "body": json.dumps(t["body"])} for t in tables])
            if rows:
                conn.executemany(ROW_SQL, [{**common, **r} for r in rows])
            conn.execute(ARTICLE_SQL, {**common, "post_date": p["date"], "title": p["title"], "link": p["link"],
                                       "updated_text": updated_text(html), "rows_stored": len(rows),
                                       "tables_skipped": skipped})
            conn.commit()
            out["new_versions"] += 1
            out["rows"] += len(rows)
            out["tables_skipped"] += skipped
            out["with_game"] += 1 if game_id else 0
            time.sleep(0.5)
        logger.info(f"dk_prop_splits: {out}")
        return out
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pages", type=int, default=1)
    print(run(pages=ap.parse_args().pages))
