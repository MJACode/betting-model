"""Where can the Scoreboard's % bets / % money come from reliably?

Matt, 2026-11-03: the Scoreboard should carry DraftKings' own handle % and
bet % (his screenshot of DK Network's splits page) where that can be pulled
reliably. Today's scoreboard_splits rows are Action Network's CONSENSUS
pseudo-book (id 15), which on NFL_2026_08_CHI_SEA read Chicago +3.5 58% bets /
64% money against DraftKings' own +3 48% / 39%: a different population at a
different line.

This sandbox cannot reach either host, so the worker (open egress) runs this.
It writes nothing and makes no Odds API call. It prints two things:

1. DK Network's splits page: HTTP status, size, how many tables / rows /
   percent cells the HTML carries, every iframe and script source, every
   link that names splits, and a text window around the first "Handle". That
   says whether the numbers are in the HTML or loaded from somewhere else.
2. Action Network's v2 scoreboard with no bookIds filter: for each sport and
   day, which book ids appear under `markets` and which of them carry a
   bet_info split. Plus /web/v1/books, so an id can be named from the
   response rather than from memory.

    python -m scripts.splits_source_probe
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
from html import unescape
from zoneinfo import ZoneInfo

import requests

SUMMARY_MARK = "== SUMMARY =="
DK_URL = "https://dknetwork.draftkings.com/draftkings-sportsbook-betting-splits/"
AN_SCOREBOARD = "https://api.actionnetwork.com/web/v2/scoreboard/{slug}"
AN_BOOKS = "https://api.actionnetwork.com/web/v1/books"
SPORTS = ("nfl", "ncaaf", "nba", "nhl")
DAYS = 4
TIMEOUT = 25
_ET = ZoneInfo("America/New_York")
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _install() -> None:
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("splits-source-probe")
    except Exception:  # noqa: BLE001
        pass


def _get(url: str, **kw):
    try:
        resp = requests.get(url, timeout=TIMEOUT,
                            headers={"User-Agent": _UA, **kw.pop("headers", {})}, **kw)
        return resp.status_code, resp.text, None
    except requests.RequestException as exc:
        return None, "", f"{type(exc).__name__}: {exc}"


def describe_dk_html(body: str) -> dict:
    """What the page's HTML holds. Pure, so a test can feed it a fixture."""
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.S | re.I)
    text = unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text)
    at = text.lower().find("handle")
    return {
        "tables": len(re.findall(r"<table\b", body, re.I)),
        "rows": len(re.findall(r"<tr\b", body, re.I)),
        "percent_cells": len(re.findall(r">\s*\d{1,3}%\s*<", body)),
        "iframes": sorted(set(re.findall(r"<iframe[^>]+src=[\"']([^\"']+)", body, re.I)))[:20],
        "scripts": sorted(set(re.findall(r"<script[^>]+src=[\"']([^\"']+)", body, re.I)))[:40],
        "split_links": sorted(set(
            u for u in re.findall(r"href=[\"']([^\"']+)", body, re.I)
            if "split" in u.lower() or "tb_" in u.lower()))[:40],
        "handle_window": text[max(0, at - 300): at + 1500] if at >= 0 else "",
    }


def describe_an_games(payload: dict) -> dict:
    """Book ids under `markets`, and which carry a bet_info split. Pure."""
    games = payload.get("games") or []
    seen: dict[str, int] = {}
    with_split: dict[str, int] = {}
    for g in games:
        for book_id, book in (g.get("markets") or {}).items():
            seen[book_id] = seen.get(book_id, 0) + 1
            event = (book or {}).get("event") or book or {}
            has = any(
                isinstance(e, dict) and (e.get("bet_info") or {}).get("tickets", {}).get("percent")
                for arr in event.values() if isinstance(arr, list) for e in arr)
            if has:
                with_split[book_id] = with_split.get(book_id, 0) + 1
    return {"games": len(games), "books": seen, "books_with_split": with_split}


def probe(get=_get, today: str | None = None) -> int:
    summary: list[str] = []
    failed = False

    status, body, err = get(DK_URL)
    print(f"--- DK Network {DK_URL}")
    if err or status != 200:
        why = err or f"HTTP {status}"
        print(f"dk: {why}")
        summary.append(f"dk: {why}")
        failed = True
    else:
        d = describe_dk_html(body)
        print(f"dk: HTTP {status}, {len(body):,} bytes")
        print(json.dumps(d, indent=1)[:12_000])
        summary.append(f"dk: HTTP 200 {len(body):,}B tables={d['tables']} rows={d['rows']} "
                       f"pct_cells={d['percent_cells']} iframes={len(d['iframes'])}")

    status, body, err = get(AN_BOOKS, headers={"Accept": "application/json"})
    print(f"--- Action Network books {AN_BOOKS}")
    if err or status != 200:
        print(f"an books: {err or f'HTTP {status}'}")
        summary.append(f"an books: {err or f'HTTP {status}'}")
    else:
        try:
            books = json.loads(body).get("books") or []
            named = [f"{b.get('id')}={b.get('display_name') or b.get('name')}" for b in books]
            print("an books: " + ", ".join(named))
            dk = [n for n in named if "draftkings" in n.lower()]
            summary.append(f"an books: {len(books)} listed; DraftKings ids: {dk or 'none'}")
        except ValueError:
            print(f"an books: not JSON, first 300: {body[:300]!r}")
            summary.append("an books: not JSON")

    start = datetime.strptime(today, "%Y-%m-%d") if today else datetime.now(_ET)
    for slug in SPORTS:
        for offset in range(DAYS):
            day = (start + timedelta(days=offset)).strftime("%Y%m%d")
            status, body, err = get(AN_SCOREBOARD.format(slug=slug),
                                    params={"date": day, "periods": "event"},
                                    headers={"Accept": "application/json",
                                             "Referer": f"https://www.actionnetwork.com/{slug}/public-betting"})
            if err or status != 200:
                line = f"an {slug} {day}: {err or f'HTTP {status}'}"
                print(line)
                summary.append(line)
                continue
            try:
                d = describe_an_games(json.loads(body))
            except ValueError:
                print(f"an {slug} {day}: not JSON")
                continue
            line = (f"an {slug} {day}: games={d['games']} books={d['books']} "
                    f"with_split={d['books_with_split']}")
            print(line)
            if d["games"]:
                summary.append(line)
                break

    print(SUMMARY_MARK)
    for line in summary:
        print(line)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    _install()
    return probe()


if __name__ == "__main__":
    sys.exit(main())
