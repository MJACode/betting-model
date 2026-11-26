"""DraftKings' own player-prop handle and bet shares, from DK Network's prop-split articles.

mike, 2026-11-26 ("Do all the outstanding tasks now"). DK Network's splits table covers moneyline / spread /
total only, for every event group (worker_jobs 1722475). Player-prop splits are published as articles for featured
NFL games: 34 found through the site's WordPress posts API, 2026-09-14 to 2026-11-23, every TNF / SNF / MNF game
and some Sunday slates (worker_jobs 1723195). The search stopped at its 1,000-post cap and a 2025-02-09 Super Bowl
article exists outside that list, so 34 is a floor.

Seven table headers are kept in ``dk_prop_split_tables`` (2026-11-26): Player | Market | Line | Handle split | Bet
split; Player prop | Line | Handle leader | Bet leader; Player prop | Line | Handle % | Bet %; Player prop |
Handle % | Bet % (the line is the prop text's last number); and the multi-game Game | Player prop | (Line) |
Handle % | Bet %. A share cell prints as "66%", "Over 67%", "Over (99.1%)", "Over: 99.3% Under: 0.7%",
"Over 60% / Under 40%" or "50% each" (`shares`). Each stored row records one side and its share for handle and for
bets: ``side_line`` when the line cell names the side the bare shares belong to ("Under 20.5" / "66%"),
``leaders`` when each share names its own side, storing the larger (the leader; the other side is the rest of
100, and the printed cell is kept). A bare share with no side named anywhere is not stored.

Rank lists (the anytime-touchdown tables) carry no percentages and are counted as skipped, never guessed at.
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
_SIDE_LINE = re.compile(r"^(?P<side>over|under|yes|no)\s+(?P<line>[+\-]?\d+(?:\.\d+)?)$", re.I)
_LINE = re.compile(r"^[+\-]?\d+(?:\.\d+)?$")
_TRAILING_LINE = re.compile(r"\s(?P<line>\d+(?:\.\d+)?)$")
# One share, in each way a cell has printed it: "Over 67%", "Over (99.1%)", "Over: 99.3%".
_SHARE = re.compile(r"\b(?P<side>over|under|yes|no)\b\s*[:(]?\s*(?P<pct>\d{1,3}(?:\.\d+)?)\s*%", re.I)
_PCT = re.compile(r"^(?P<pct>\d{1,3}(?:\.\d+)?)\s*%$")
_EACH = re.compile(r"^(?P<pct>\d{1,3}(?:\.\d+)?)\s*%\s+each$", re.I)      # "50% each": an even split
# "Updated Monday, Nov. 23 at 6:04 p.m. ET." / "Updated September 14, 2026." (the two bodies measured).
_UPDATED = re.compile(r"Updated\b.{0,90}?(?:\bET\b\.?|\d{4}\.)|Updated\b.{0,60}", re.I)
_TITLE_GAME = re.compile(r"^(?P<a>\w[\w.' ]*?) vs\.? (?P<b>\w[\w.' ]*?) player\b", re.I)
_CELL_GAME = re.compile(r"^(?P<a>.+?) (?:vs\.?|@|at) (?P<b>.+)$", re.I)


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


def shares(cell: str) -> dict:
    """{side: share} a cell prints: {'over': 99.3, 'under': 0.7}, {'over': 67.0}, {None: 66.0} for a bare
    "66%", both sides for "50% each". "N/A", a dash and an empty cell give {}. Every shape in the kept tables
    (2026-11-26, 3,162 rows) is one of these. Pure."""
    each = _EACH.match((cell or "").strip())
    if each:
        return {"over": float(each.group("pct")), "under": float(each.group("pct"))}
    found: dict = {}
    for m in _SHARE.finditer(cell or ""):
        found.setdefault(m.group("side").lower(), float(m.group("pct")))
    if found:
        return found
    m = _PCT.match((cell or "").strip())
    return {None: float(m.group("pct"))} if m else {}


def _lead(sh: dict, named: str | None) -> tuple[str | None, float | None]:
    """(side, share) to store: the side the line names when the cell is a bare share, else the cell's larger
    share (the leader; a tie keeps the side printed first). A share with no side and no named side is
    unreadable."""
    if not sh:
        return None, None
    if None in sh:
        return (named, sh[None]) if named else (None, None)
    side = max(sh, key=lambda k: sh[k])
    return side, sh[side]


def table_columns(header: list[str]) -> dict | None:
    """The columns of a prop-split table, or None when it is not one (rank lists, anything else). Pure."""
    cols = {"handle": _col(header, "handle"), "bets": _col(header, "bet", exclude="handle"),
            "line": _col(header, "line"), "game": _col(header, "game"),
            "prop": _col(header, "player prop"), "player": _col(header, "player", exclude="prop"),
            "market": _col(header, "market")}
    if cols["handle"] is None and cols["bets"] is None:
        return None
    if cols["prop"] is None and (cols["player"] is None or cols["market"] is None):
        return None
    return cols


def parse_row(cols: dict, cells: list[str]) -> dict | None:
    """One table row -> the stored fields, or None when it does not read. `layout` is 'side_line' when the line
    cell names the side the bare shares belong to, 'leaders' when each share names its own side. Pure."""
    def cell(k):
        i = cols.get(k)
        return cells[i].strip() if i is not None and i < len(cells) else ""

    if cols.get("prop") is not None:
        prop, player, market = cell("prop"), None, None
    else:
        player, market = cell("player"), cell("market")
        prop = f"{player} {market}".strip()
    if not prop:
        return None
    named, line = None, None
    m = _SIDE_LINE.match(cell("line"))
    if m:
        named, line = m.group("side").lower(), _num(m.group("line"))
    elif _LINE.match(cell("line")):
        line = _num(cell("line"))
    elif cols.get("line") is None:
        t = _TRAILING_LINE.search(prop)            # "Dak Prescott Passing Completions 23.5"
        line = _num(t.group("line")) if t else None
    hs, hp = _lead(shares(cell("handle")), named)
    bs, bp = _lead(shares(cell("bets")), named)
    if hp is None and bp is None:
        return None
    return {"prop_text": prop, "player": player or None, "market": market or None, "line_value": line,
            "handle_side": hs, "handle_pct": hp, "bets_side": bs, "bets_pct": bp,
            "layout": "side_line" if named else "leaders", "game_text": cell("game") or None}


def parse_table(header: list[str], body: list[list[str]]) -> list[dict]:
    """Every readable row of one table, with its row_no (1-based, as printed). Pure."""
    cols = table_columns(header)
    if cols is None:
        return []
    out = []
    for row_no, cells in enumerate(body, start=1):
        r = parse_row(cols, cells)
        if r is not None:
            out.append({"row_no": row_no, **r})
    return out


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
        header, body = _table(m.group("t"))
        rows = parse_table(header, body)
        tables.append({"table_no": table_no, "section": section, "header": header, "body": body,
                       "layout": rows[0]["layout"] if rows else None})
        if not rows:
            skipped += 1
        out.extend({"table_no": table_no, "section": section, **r} for r in rows)
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


def _pair_game(nick_a: str, nick_b: str, posted: datetime | None, games: list[dict]) -> str | None:
    """The one NFL game between the two nicknames, within a day before and three after the post's ET date."""
    if posted is None:
        return None
    from config import NFL_ODDS_API_MAP
    def ids(nick: str) -> set[str]:
        n = " " + nick.strip().lower()
        return {abbr for full, abbr in NFL_ODDS_API_MAP.items() if full.lower().endswith(n)}
    a, b = ids(nick_a), ids(nick_b)
    if not a or not b:
        return None
    day = posted.astimezone(_ET).date()
    hits = {g["game_id"] for g in games
            if {g["home_team"], g["away_team"]} & a and {g["home_team"], g["away_team"]} & b
            and g["home_team"] != g["away_team"]
            and -1 <= (date.fromisoformat(g["game_date"]) - day).days <= 3}
    return next(iter(hits)) if len(hits) == 1 else None


def title_game(title: str, posted: datetime | None, games: list[dict]) -> str | None:
    """The one NFL game a title names ("Bengals vs. Commanders Player Prop ..."), or None. Multi-game titles
    ("NFL Week 4 Sunday ...") name none. Pure."""
    m = _TITLE_GAME.match(title or "")
    return _pair_game(m.group("a"), m.group("b"), posted, games) if m else None


def cell_game(text: str | None, posted: datetime | None, games: list[dict]) -> str | None:
    """The one NFL game a multi-game table's Game cell names ("BAL Ravens vs. ATL Falcons", "Cowboys vs.
    Texans"), by each side's last word, or None. Pure."""
    m = _CELL_GAME.match((text or "").strip())
    if not m:
        return None
    return _pair_game(m.group("a").split()[-1], m.group("b").split()[-1], posted, games)


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


GAMES_SQL = ("SELECT game_id, game_date::text, home_team, away_team FROM public.games "
             "WHERE sport = 'NFL' AND game_date::date BETWEEN %(lo)s AND %(hi)s")


def _games_near(conn, posted: datetime | None) -> list[dict]:
    if posted is None:
        return []
    d = posted.astimezone(_ET).date()
    cols = ("game_id", "game_date", "home_team", "away_team")
    return [dict(zip(cols, r)) for r in conn.execute(
        GAMES_SQL, {"lo": d - timedelta(days=1), "hi": d + timedelta(days=3)}).fetchall()]


def _row_params(common: dict, rows: list[dict], posted: datetime | None, games: list[dict]) -> list[dict]:
    """Insert parameters: a multi-game table's row takes the game its Game cell names, any other row the
    article's."""
    out = []
    for r in rows:
        r = dict(r)
        text = r.pop("game_text", None)
        out.append({**common, **r, "game_id": cell_game(text, posted, games) if text else common["game_id"]})
    return out


def reparse(conn) -> dict:
    """Parse rows from the kept tables of every version the ledger shows stored nothing from tables it had,
    so a layout read by a newer parser is stored without fetching the page again (2026-11-26: 31 versions)."""
    versions = conn.execute(
        "SELECT a.post_id, a.post_modified, a.post_date, a.game_id FROM public.dk_prop_split_articles a "
        "WHERE a.rows_stored = 0 AND a.tables_skipped > 0 AND EXISTS (SELECT 1 FROM public.dk_prop_split_tables t "
        "WHERE t.post_id = a.post_id AND t.post_modified = a.post_modified)").fetchall()
    out = {"versions": 0, "rows": 0}
    for post_id, modified, posted, game_id in versions:
        posted = _ts(posted)
        tables = conn.execute(
            "SELECT table_no, section, header, body FROM public.dk_prop_split_tables "
            "WHERE post_id = %(p)s AND post_modified = %(m)s ORDER BY table_no",
            {"p": post_id, "m": modified}).fetchall()
        rows, skipped, layouts = [], 0, {}
        for table_no, section, header, body in tables:
            header = json.loads(header) if isinstance(header, str) else header
            body = json.loads(body) if isinstance(body, str) else body
            got = parse_table(header, body)
            if not got:
                skipped += 1
                continue
            layouts[table_no] = got[0]["layout"]
            rows.extend({"table_no": table_no, "section": section, **r} for r in got)
        if not rows:
            continue
        common = {"post_id": post_id, "post_modified": modified, "game_id": game_id, "source": SOURCE}
        conn.executemany(ROW_SQL, _row_params(common, rows, posted, _games_near(conn, posted)))
        # The ledger's counts and the kept table's layout describe what is now stored; nothing is removed.
        conn.execute("UPDATE public.dk_prop_split_articles SET rows_stored = %(n)s, tables_skipped = %(k)s "
                     "WHERE post_id = %(p)s AND post_modified = %(m)s AND rows_stored = 0",
                     {"n": len(rows), "k": skipped, "p": post_id, "m": modified})
        conn.executemany("UPDATE public.dk_prop_split_tables SET layout = %(l)s WHERE post_id = %(p)s "
                         "AND post_modified = %(m)s AND table_no = %(t)s AND layout IS NULL",
                         [{"l": l, "p": post_id, "m": modified, "t": t} for t, l in layouts.items()])
        conn.commit()
        out["versions"] += 1
        out["rows"] += len(rows)
    return out


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
            games = _games_near(conn, p["date"])
            game_id = title_game(p["title"], p["date"], games)
            common = {"post_id": p["id"], "post_modified": modified, "game_id": game_id, "source": SOURCE}
            if tables:
                conn.executemany(TABLE_SQL, [{**common, **t, "header": json.dumps(t["header"]),
                                              "body": json.dumps(t["body"])} for t in tables])
            if rows:
                conn.executemany(ROW_SQL, _row_params(common, rows, p["date"], games))
            conn.execute(ARTICLE_SQL, {**common, "post_date": p["date"], "title": p["title"], "link": p["link"],
                                       "updated_text": updated_text(html), "rows_stored": len(rows),
                                       "tables_skipped": skipped})
            conn.commit()
            out["new_versions"] += 1
            out["rows"] += len(rows)
            out["tables_skipped"] += skipped
            out["with_game"] += 1 if game_id else 0
            time.sleep(0.5)
        out["reparsed"] = reparse(conn)
        logger.info(f"dk_prop_splits: {out}")
        return out
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pages", type=int, default=1)
    print(run(pages=ap.parse_args().pages))
