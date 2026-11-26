"""One-off research probe, 2026-11-26 (mike: "More and deeper research on data sources",
"why can't we get historical data somewhere", and yes to the earlier NBA prop snapshots).

WHY IT RUNS ON THE WORKER. The dev sandbox's egress refuses every host this needs
(api.elections.kalshi.com, data-api.polymarket.com, web.archive.org, data.vsin.com,
historicdata.betfair.com and others: agent-proxy HTTP 403, measured 2026-11-26), and the
request to widen it was rejected. The Railway `prop-probe` service has open egress and holds
ODDS_API_KEY and DATABASE_URL (CLAUDE.md §1b, route 2).

WHAT IT DOES. Prints measurements to stdout (Railway deploy logs), one `RP|section|...` line
each. WRITES NOTHING to the database. Sections, each in its own try:

  props     When NBA player props first post at The Odds API's historical endpoint: six
            past games, player_points at 30..1 hours before tip, then the five markets the
            live models bet most at 10 and 6 hours. Capped by the shared credit meter
            (ceiling 1,500, floor 500,000). Part of the purchase mike approved 2026-11-26.
  kalshi    Which NBA series Kalshi lists, how far back its settled NBA events go, and
            whether a settled game's trades come back with timestamps and taker side.
  poly      The same for Polymarket: the earliest NBA events, volume by month, and one
            game's trade prints.
  wayback   Capture counts of the public-splits pages (DraftKings Network, VSiN's DraftKings
            and Circa views, Action Network and others) in the Wayback Machine, and the text
            of one archived VSiN page.
  dk        DraftKings Network's sport links, to see why only NFL is discovered.
  pages     Text of vendor pages (prices, coverage, terms) that the sandbox cannot open.

    python -m scripts.research_probe_2026_11_26                 # every section
    python -m scripts.research_probe_2026_11_26 kalshi wayback   # some
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from html import unescape
from zoneinfo import ZoneInfo

import requests

ET = ZoneInfo("America/New_York")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
H = {"User-Agent": UA, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"}


def say(section: str, *parts) -> None:
    """One log line, cut to 1,800 characters so Railway keeps it whole."""
    text = " ".join(p if isinstance(p, str) else json.dumps(p, default=str) for p in parts)
    for i in range(0, max(len(text), 1), 1800):
        print(f"RP|{section}|{text[i:i + 1800]}", flush=True)


def get(url: str, params: dict | None = None, timeout: int = 30, headers: dict | None = None):
    for attempt in range(3):
        try:
            return requests.get(url, params=params, timeout=timeout, headers=headers or H)
        except requests.RequestException as exc:
            if attempt == 2:
                return exc
            time.sleep(2 * (attempt + 1))
    return None


def page_text(html: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    text = unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


# ── props: when do NBA props post ────────────────────────────────────────────

PROP_DATES = ["2023-11-08", "2024-01-17", "2024-11-13", "2025-01-15", "2025-11-12", "2026-01-14"]
POINTS_OFFSETS_H = [30, 24, 18, 14, 10, 8, 6, 4, 2, 1]
FIVE = ["player_threes", "player_rebounds", "player_blocks", "player_steals", "player_points"]
FIVE_OFFSETS_H = [10, 6]


def _summarise(body: dict) -> dict:
    out = {}
    for book in (body.get("data") or {}).get("bookmakers", []) or []:
        per = {}
        for m in book.get("markets", []) or []:
            players = {o.get("description") for o in m.get("outcomes", []) or []}
            per[m.get("key")] = len(players)
        out[book.get("key")] = per
    return out


def probe_props() -> None:
    from data.db import get_connection
    from data.ingestors.nba_odds_history import BASE, BOOKS, Meter
    meter = Meter(ceiling=1_500, floor=500_000)
    conn = get_connection()
    try:
        for d in PROP_DATES:
            rows = conn.execute(
                "SELECT game_id, home_team, away_team, commence_time FROM games "
                "WHERE sport = 'NBA' AND game_date = %s AND commence_time IS NOT NULL "
                "ORDER BY commence_time DESC LIMIT 1", (d,)).fetchall()
            if not rows:
                say("props", d, "no game with a start in games")
                continue
            gid, home, away, _ = rows[0]
            noon = datetime.fromisoformat(f"{d}T12:00:00").replace(tzinfo=ET)
            r = meter.get(f"{BASE}/events", {"date": noon.astimezone(timezone.utc)
                                             .strftime("%Y-%m-%dT%H:%M:%SZ")})
            if r is None or r.status_code != 200:
                say("props", d, "event list HTTP", getattr(r, "status_code", "network"))
                continue
            evs = [e for e in (r.json().get("data") or [])
                   if datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
                   .astimezone(ET).date().isoformat() == d]
            if not evs:
                say("props", d, "no events listed")
                continue
            ev = max(evs, key=lambda e: e["commence_time"])
            start = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
            say("props", d, gid, ev.get("away_team"), "@", ev.get("home_team"),
                "tip", start.isoformat())
            plan = [(h, ["player_points"]) for h in POINTS_OFFSETS_H] + \
                   [(h, FIVE) for h in FIVE_OFFSETS_H]
            for hours, markets in plan:
                why = meter.stop_reason(10 * len(markets))
                if why:
                    say("props", "STOP", why)
                    return
                snap = (start - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
                before = meter.spent
                resp = meter.get(f"{BASE}/events/{ev['id']}/odds", {
                    "date": snap, "markets": ",".join(markets), "bookmakers": BOOKS,
                    "oddsFormat": "american"})
                code = getattr(resp, "status_code", "network")
                if code != 200:
                    say("props", d, f"-{hours}h", markets[0] if len(markets) == 1 else "five",
                        "HTTP", code, getattr(resp, "text", "")[:200])
                    continue
                body = resp.json()
                say("props", d, f"-{hours}h", "points" if len(markets) == 1 else "five",
                    "snapshot", body.get("timestamp"), "cost", meter.spent - before,
                    "books", _summarise(body))
        say("props", "TOTAL spent", meter.spent, "balance", meter.remaining)
    finally:
        conn.close()


# ── kalshi ───────────────────────────────────────────────────────────────────

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
_KDATE = re.compile(r"-(\d{2})([A-Z]{3})(\d{2})")
_MON = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def _kdate(ticker: str) -> str | None:
    m = _KDATE.search(ticker or "")
    if not m or m.group(2) not in _MON:
        return None
    return f"20{m.group(1)}-{_MON[m.group(2)]:02d}-{m.group(3)}"


def _kpages(path: str, params: dict, key: str, pages: int = 60) -> list[dict]:
    out, cursor = [], None
    for _ in range(pages):
        p = dict(params)
        if cursor:
            p["cursor"] = cursor
        r = get(f"{KALSHI}{path}", p, timeout=60)
        if not isinstance(r, requests.Response) or r.status_code != 200:
            say("kalshi", path, "HTTP", getattr(r, "status_code", repr(r)),
                getattr(r, "text", "")[:200])
            break
        body = r.json()
        out += body.get(key) or []
        cursor = body.get("cursor")
        if not cursor:
            break
        time.sleep(0.15)
    return out


def probe_kalshi() -> None:
    r = get(f"{KALSHI}/series", {"category": "Sports"}, timeout=60)
    series = []
    if isinstance(r, requests.Response) and r.status_code == 200:
        series = r.json().get("series") or []
    say("kalshi", "sports series", len(series))
    nba = [s for s in series if "NBA" in (s.get("ticker") or "").upper()
           or "pro basketball" in (s.get("title") or "").lower()]
    say("kalshi", "NBA series", [(s.get("ticker"), s.get("title")) for s in nba][:80])
    cut = get(f"{KALSHI}/historical/cutoff", timeout=30)
    say("kalshi", "historical cutoff", getattr(cut, "status_code", None),
        getattr(cut, "text", "")[:300])
    wanted = [s["ticker"] for s in nba if re.search(r"GAME|TOTAL|SPREAD", s.get("ticker", ""))][:6]
    wanted += [s["ticker"] for s in nba if re.search(r"PTS|REB|AST|3PT|THREE", s.get("ticker", ""))][:4]
    for tk in wanted:
        evs = _kpages("/events", {"series_ticker": tk, "status": "settled", "limit": 200}, "events")
        months = Counter((_kdate(e.get("event_ticker")) or "?")[:7] for e in evs)
        dated = sorted(e for e in (_kdate(e.get("event_ticker")) for e in evs) if e)
        say("kalshi", tk, "settled events", len(evs), "first", dated[:1], "last", dated[-1:],
            "by month", dict(sorted(months.items())))
        if not evs or not re.search(r"GAME", tk):
            continue
        picks = sorted(evs, key=lambda e: _kdate(e.get("event_ticker")) or "9")
        sample = [picks[0], picks[len(picks) // 2]]
        for ev in sample:
            et = ev.get("event_ticker")
            mk = _kpages("/markets", {"event_ticker": et, "limit": 100}, "markets", pages=2)
            say("kalshi", et, "markets", [(m.get("ticker"), m.get("volume"), m.get("open_time"),
                                           m.get("close_time"), m.get("result")) for m in mk])
            if not mk:
                continue
            m0 = mk[0]["ticker"]
            tr = _kpages("/markets/trades", {"ticker": m0, "limit": 1000}, "trades", pages=20)
            src = "live"
            if not tr:
                tr = _kpages("/historical/trades", {"ticker": m0, "limit": 1000}, "trades", pages=20)
                src = "historical"
            times = sorted(t.get("created_time") for t in tr if t.get("created_time"))
            sides = Counter(t.get("taker_side") for t in tr)
            say("kalshi", m0, src, "trades", len(tr), "first", times[:1], "last", times[-1:],
                "taker sides", dict(sides), "keys", sorted(tr[0].keys()) if tr else [],
                "sample", tr[:1])


# ── polymarket ───────────────────────────────────────────────────────────────

GAMMA = "https://gamma-api.polymarket.com"
PDATA = "https://data-api.polymarket.com"


def probe_poly() -> None:
    r = get(f"{GAMMA}/tags/slug/nba", timeout=30)
    tag = r.json() if isinstance(r, requests.Response) and r.status_code == 200 else {}
    say("poly", "tag", getattr(r, "status_code", None), {k: tag.get(k) for k in ("id", "label", "slug")})
    if not tag.get("id"):
        return
    events, offset = [], 0
    for _ in range(40):
        rr = get(f"{GAMMA}/events", {"tag_id": tag["id"], "closed": "true", "limit": 500,
                                     "offset": offset, "order": "startDate", "ascending": "true"},
                 timeout=60)
        if not isinstance(rr, requests.Response) or rr.status_code != 200:
            say("poly", "events HTTP", getattr(rr, "status_code", repr(rr)), getattr(rr, "text", "")[:200])
            break
        batch = rr.json() or []
        if not isinstance(batch, list) or not batch:
            break
        events += batch
        offset += len(batch)
        time.sleep(0.2)
    games = [e for e in events if re.search(r" vs\.? | @ ", e.get("title") or "")]
    by_month = defaultdict(lambda: [0, 0.0])
    for e in games:
        m = (e.get("startDate") or "?")[:7]
        by_month[m][0] += 1
        try:
            by_month[m][1] += float(e.get("volume") or 0)
        except (TypeError, ValueError):
            pass
    say("poly", "closed NBA events", len(events), "game-like", len(games))
    say("poly", "games and volume by month", {k: [v[0], round(v[1])] for k, v in sorted(by_month.items())})
    say("poly", "earliest game events", [(e.get("title"), e.get("startDate"), e.get("volume"))
                                         for e in games[:8]])
    mid = [e for e in games if (e.get("startDate") or "").startswith("2025-01")]
    for e in (mid[:1] or games[len(games) // 2: len(games) // 2 + 1]):
        mkts = e.get("markets") or []
        say("poly", "sample event", e.get("title"), e.get("startDate"),
            [(m.get("question"), m.get("conditionId"), m.get("volume")) for m in mkts][:6])
        if not mkts:
            continue
        cid = mkts[0].get("conditionId")
        trades, off = [], 0
        for _ in range(10):
            tr = get(f"{PDATA}/trades", {"market": cid, "limit": 500, "offset": off}, timeout=60)
            if not isinstance(tr, requests.Response) or tr.status_code != 200:
                say("poly", "trades HTTP", getattr(tr, "status_code", repr(tr)), getattr(tr, "text", "")[:200])
                break
            b = tr.json() or []
            if not b:
                break
            trades += b
            off += len(b)
        ts = sorted(t.get("timestamp") for t in trades if t.get("timestamp"))
        sample = {k: v for k, v in (trades[0] if trades else {}).items()
                  if k not in ("proxyWallet", "name", "pseudonym", "bio", "profileImage",
                               "profileImageOptimized")}
        say("poly", "trades", len(trades), "first", ts[:1], "last", ts[-1:],
            "sides", dict(Counter(t.get("side") for t in trades)), "sample", sample)


# ── wayback ──────────────────────────────────────────────────────────────────

WAYBACK = [
    "dknetwork.draftkings.com/draftkings-sportsbook-betting-splits",
    "data.vsin.com/betting-splits",
    "data.vsin.com/nba/betting-splits",
    "data.vsin.com/circa",
    "vsin.com/betting-splits",
    "www.actionnetwork.com/nba/public-betting",
    "www.sportsbettingdime.com/nba/public-betting-trends",
    "www.scoresandodds.com/nba/consensus-picks",
    "pregame.com/sportsbook-spy",
    "www.covers.com/sports/nba/consensus",
]


def probe_wayback() -> None:
    caps = {}
    for u in WAYBACK:
        r = get("https://web.archive.org/cdx/search/cdx",
                {"url": u, "matchType": "prefix", "output": "json",
                 "fl": "timestamp,original", "filter": "statuscode:200", "limit": 100000},
                timeout=120)
        if not isinstance(r, requests.Response) or r.status_code != 200:
            say("wayback", u, "HTTP", getattr(r, "status_code", repr(r)))
            continue
        try:
            rows = (r.json() or [])[1:]
        except ValueError:
            say("wayback", u, "not json", r.text[:200])
            continue
        caps[u] = rows
        years = Counter(t[:4] for t, _ in rows)
        days = Counter(t[:8] for t, _ in rows)
        per_day = Counter(days.values())
        variants = Counter(o.split("?")[0] for _, o in rows).most_common(5)
        say("wayback", u, "captures", len(rows), "days", len(days), "by year", dict(sorted(years.items())),
            "captures per day histogram", dict(sorted(per_day.items())[:8]), "url variants", variants)
        time.sleep(1)
    # One archived VSiN page, to see what it carries.
    for u in ("data.vsin.com/betting-splits", "vsin.com/betting-splits", "data.vsin.com/nba/betting-splits"):
        rows = [x for x in caps.get(u, []) if x[0].startswith(("202501", "202412", "202502"))]
        if not rows:
            continue
        ts, orig = rows[len(rows) // 2]
        r = get(f"https://web.archive.org/web/{ts}id_/{orig}", timeout=90)
        if isinstance(r, requests.Response) and r.status_code == 200:
            t = page_text(r.text)
            i = max(t.find("Handle"), 0)
            say("wayback", "sample", ts, orig, "len", len(t), "text", t[max(i - 600, 0): i + 2400])
        break


# ── DraftKings Network ───────────────────────────────────────────────────────

def probe_dk() -> None:
    from data.ingestors import dk_splits
    r = get(dk_splits.DK_URL, timeout=60, headers={"User-Agent": UA, "Accept": "text/html"})
    if not isinstance(r, requests.Response) or r.status_code != 200:
        say("dk", "HTTP", getattr(r, "status_code", repr(r)))
        return
    html = r.text
    say("dk", "discover_event_groups", dk_splits.discover_event_groups(html))
    links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.S | re.I)
    eg = [(h, page_text(t)[:40]) for h, t in links if re.search(r"tb_eg|eventgroup|event_group", h, re.I)]
    say("dk", "event-group links", eg[:60])
    t = page_text(html)
    i = t.find("Sports")
    say("dk", "text near Sports", t[max(i - 100, 0): i + 700])
    say("dk", "every eg id in html", sorted(set(re.findall(r"tb_eg=(\d+)", html)))[:40])


# ── vendor pages ─────────────────────────────────────────────────────────────

PAGES = [
    "https://dunksandthrees.com/about/epm",
    "https://dunksandthrees.com/premium",
    "https://dunksandthrees.com/api",
    "https://www.darko.app/about",
    "https://thedailyaverage.com/historical-projections",
    "https://www.sportsinsights.com/sports-betting-systems/historical-betting-odds-sports-data/",
    "https://www.actionnetwork.com/pro",
    "https://vsin.com/subscribe/",
    "https://data.vsin.com/betting-splits/?bookid=circa&view=nba",
    "https://data.vsin.com/betting-splits/?bookid=dk&view=nba",
    "https://support.developer.betfair.com/hc/en-us/articles/8085210924957-Which-Sports-Are-Included-in-the-Other-Sports-package",
    "https://historicdata.betfair.com/",
    "https://sportsdata.io/developers/api-documentation/nba",
    "https://www.pikkit.com/",
    "https://arxiv.org/abs/2609.06739",
    "https://docs.kalshi.com/api-reference/historical/get-historical-trades",
]


def probe_pages() -> None:
    for u in PAGES:
        r = get(u, timeout=45)
        if not isinstance(r, requests.Response):
            say("pages", u, "network", repr(r)[:160])
            continue
        t = page_text(r.text)
        money = sorted(set(re.findall(r"[^.]{0,80}\$\s?\d[\d,.]*[^.]{0,60}", t)))[:12]
        links = sorted({h for h in re.findall(r'href="([^"]+)"', r.text)
                        if re.search(r"pric|subscri|premium|api|plan|historic", h, re.I)})[:20]
        say("pages", u, "HTTP", r.status_code, "len", len(t))
        say("pages", u, "text", t[:1600])
        say("pages", u, "dollar mentions", money, "links", links)
        time.sleep(0.5)


SECTIONS = {"props": probe_props, "kalshi": probe_kalshi, "poly": probe_poly,
            "wayback": probe_wayback, "dk": probe_dk, "pages": probe_pages}


def main(argv: list[str]) -> None:
    names = argv or list(SECTIONS)
    say("main", "start", datetime.now(timezone.utc).isoformat(), names)
    for n in names:
        try:
            SECTIONS[n]()
        except Exception as exc:  # noqa: BLE001 — one section's failure must not hide the rest
            say(n, "FAILED", f"{type(exc).__name__}: {exc}"[:600])
    say("main", "done", datetime.now(timezone.utc).isoformat())


if __name__ == "__main__":
    main(sys.argv[1:])
