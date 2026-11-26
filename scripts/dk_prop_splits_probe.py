"""DK Network's player-prop split articles: how many, how far back, and how the numbers are laid out.

mike, 2026-11-26 ("do all the outstanding tasks"): build the prop-splits scraper. DK Network's splits table offers
Moneyline / Spread / Total only (worker_jobs 1722475); prop splits appear only as articles ("Super Bowl Player Prop
& Novelty Prop Splits", 2025-02-09; "Colts vs. Chiefs Player Prop Bet Splits for Sunday", 2026-09-20). Before a
parser is written, this measures, from the worker (this sandbox's proxy refuses the host):

1. WordPress's public posts API (`/wp-json/wp/v2/posts`, the site serves `wp-json`): for several searches, how
   many posts, their date range, and every title, so the history and the cadence are counts, not a guess.
2. Two articles' bodies: whether the numbers sit in a <table>, and the text around each "%".
3. Tennis on Action Network, which the coverage probe skipped (no past date with 3 games): `atp`, `wta`, `tennis`
   on the last date with any ATP / WTA game.

Writes nothing, no Odds API call.

    python -m scripts.dk_prop_splits_probe
"""
from __future__ import annotations

import json
import re
import sys
from html import unescape

import requests

SUMMARY_MARK = "== SUMMARY =="
WP_POSTS = "https://dknetwork.draftkings.com/wp-json/wp/v2/posts"
SEARCHES = ("prop bet splits", "prop splits", "player prop splits", "betting splits props")
AN_SCOREBOARD = "https://api.actionnetwork.com/web/v2/scoreboard/{slug}"
TENNIS_SLUGS = {"atp": "ATP", "wta": "WTA", "tennis": "ATP"}
TIMEOUT = 25
MAX_PAGES = 10
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _get(url: str, **kw):
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": _UA, **kw.pop("headers", {})}, **kw)
        return resp.status_code, resp.text, dict(resp.headers), None
    except requests.RequestException as exc:
        return None, "", {}, f"{type(exc).__name__}: {exc}"


def text_of(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html or "", flags=re.S | re.I)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def is_prop_split_title(title: str) -> bool:
    """A post whose title names prop splits. Pure."""
    t = (title or "").lower()
    return "prop" in t and "split" in t


def describe_body(html: str, width: int = 90, limit: int = 8) -> dict:
    """Tables, percent cells and the text around the first `limit` percents of an article body. Pure."""
    text = text_of(html)
    hits = [m.start() for m in re.finditer(r"\d{1,3}%", text)]
    return {
        "tables": len(re.findall(r"<table\b", html or "", re.I)),
        "rows": len(re.findall(r"<tr\b", html or "", re.I)),
        "percents": len(hits),
        "windows": [text[max(0, i - width): i + width] for i in hits[:limit]],
    }


def search_posts(get, query: str) -> tuple[list[dict], str | None]:
    """Every post the search returns, newest first: [{id, date, link, title}]."""
    out: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        status, text, headers, err = get(WP_POSTS, params={"search": query, "per_page": 100, "page": page,
                                                           "_fields": "id,date,link,title"})
        if err or status != 200:
            return out, (None if out else (err or f"HTTP {status}"))
        try:
            posts = json.loads(text)
        except ValueError:
            return out, "not JSON"
        if not isinstance(posts, list) or not posts:
            break
        for p in posts:
            out.append({"id": p.get("id"), "date": p.get("date"), "link": p.get("link"),
                        "title": text_of(((p.get("title") or {}).get("rendered")) or "")})
        total_pages = headers.get("X-WP-TotalPages") or headers.get("x-wp-totalpages")
        if total_pages and page >= int(total_pages):
            break
    return out, None


def _tennis_day(conn, sport: str) -> str | None:
    if conn is None:
        return None
    row = conn.execute("SELECT max(game_date::text) FROM games WHERE sport = %s AND game_date::date < current_date",
                       (sport,)).fetchone()
    return row[0].replace("-", "") if row and row[0] else None


def probe(get=_get, conn=None) -> int:
    summary: list[str] = []
    failed = False

    def say(line: str) -> None:
        print(line)
        summary.append(line)

    found: dict[int, dict] = {}
    for q in SEARCHES:
        posts, err = search_posts(get, q)
        if err:
            say(f"wp search '{q}': {err}")
            failed = True
            continue
        props = [p for p in posts if is_prop_split_title(p["title"])]
        dates = sorted(p["date"] for p in props if p.get("date"))
        say(f"wp search '{q}': {len(posts)} posts, {len(props)} titled prop splits"
            + (f", {dates[0][:10]} to {dates[-1][:10]}" if dates else ""))
        for p in props:
            found.setdefault(p["id"], p)
    by_year: dict[str, int] = {}
    for p in found.values():
        by_year[(p.get("date") or "?")[:4]] = by_year.get((p.get("date") or "?")[:4], 0) + 1
    say(f"prop-split posts, distinct: {len(found)}; by year {dict(sorted(by_year.items()))}")
    listed = sorted(found.values(), key=lambda p: p.get("date") or "", reverse=True)
    for p in listed[:60]:
        say(f"  {(p.get('date') or '')[:10]} {p['id']} {p['title'][:110]}")

    for p in listed[:1] + listed[-1:]:
        status, text, _, err = get(f"{WP_POSTS}/{p['id']}", params={"_fields": "id,date,content"})
        if err or status != 200:
            say(f"body {p['id']}: {err or f'HTTP {status}'}")
            continue
        try:
            html = (json.loads(text).get("content") or {}).get("rendered") or ""
        except ValueError:
            say(f"body {p['id']}: not JSON")
            continue
        say(f"body {p['id']} ({(p.get('date') or '')[:10]}): {json.dumps(describe_body(html))[:2200]}")
        i = html.find("%")
        print(f"html {p['id']} around the first percent: {html[max(0, i - 1500): i + 1500]!r}")

    for slug, sport in TENNIS_SLUGS.items():
        day = _tennis_day(conn, sport)
        if not day:
            say(f"an {slug}: no past {sport} date in games")
            continue
        status, text, _, err = get(AN_SCOREBOARD.format(slug=slug), params={"date": day, "periods": "event"},
                                   headers={"Accept": "application/json",
                                            "Referer": f"https://www.actionnetwork.com/{slug}/public-betting"})
        if err or status != 200:
            say(f"an {slug} {day}: {err or f'HTTP {status}'}")
            continue
        try:
            games = json.loads(text).get("games") or []
        except (ValueError, AttributeError):
            say(f"an {slug} {day}: not JSON")
            continue
        with_split = sum(1 for g in games if any(
            ((e.get("bet_info") or {}).get("tickets") or {}).get("percent")
            for book in ((g.get("markets") or {}).values()) if isinstance(book, dict)
            for mk in (book.get("event") or {}).values() if isinstance(mk, list)
            for e in mk if isinstance(e, dict)))
        say(f"an {slug} {day}: games={len(games)} with a non-zero split={with_split}")

    print(SUMMARY_MARK)
    for line in summary:
        print(line)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    try:
        from monitoring.probe import install
        install("dk-prop-splits-probe")
    except Exception:  # noqa: BLE001
        pass
    conn = None
    try:
        from data.db import get_connection
        conn = get_connection()
    except Exception as exc:  # noqa: BLE001
        print(f"no database connection ({type(exc).__name__}); tennis dates cannot be chosen")
    try:
        return probe(conn=conn)
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
