"""Which betting splits exist, per book, per market, per sport: the measurement behind "splits for every market".

mike, 2026-11-26 ("1) yes 2) yes"): build every remaining splits source. Four questions were open, and each
decides whether anything should be stored. This answers all four in one write-free pass, from the worker (this
sandbox's proxy refuses both hosts):

1. Action Network per book. The 2026-11-03 probe (worker_jobs 936774) measured non-zero full-game ticket splits
   under books 15 (consensus), 49, 68 (DK NJ), 69, 71 (BetRivers NJ) and 75. It did not measure whether a book's
   numbers DIFFER from consensus, which is the only thing that would make storing them worth anything. Here, per
   book, period and market: games with a non-zero split, how many sides equal consensus exactly, the median gap to
   consensus in tickets %, and the median |money % - tickets %| (since 2024-25 consensus money % is close to a copy
   of tickets %, docs/nba_data_sources_and_handle_2026_11.md A4, on the festive-gauss branch).
2. Periods and team totals. The 2026-11-26 01:10 and 13:35 probe runs counted Action Network's 0/0 placeholder as a
   split; the 15:15 run, counting only non-zero shares at consensus, found no period or team-total split, and the
   hourly period passes since have stored 0 rows. Here every book is asked, not only consensus.
3. Other sports: WNBA and MLB on their last played date (the archive serves the closing split), and candidate
   Action Network slugs for UFC, tennis, EuroLeague and women's college basketball. Each prints its HTTP status,
   so a slug that does not exist shows as such rather than as "no splits".
4. Player props on DK Network: each known event group's market filters, and the text around every "Player" /
   "Prop" on the page, plus the two DK Network article pages a web search said show prop handle and bets.

Writes nothing, no Odds API call. Reads `games` only to choose dates.

    python -m scripts.splits_coverage_probe
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from datetime import datetime, timedelta
from html import unescape
from zoneinfo import ZoneInfo

import requests

SUMMARY_MARK = "== SUMMARY =="
CONSENSUS = "15"
AN_SCOREBOARD = "https://api.actionnetwork.com/web/v2/scoreboard/{slug}"
AN_BOOKS = "https://api.actionnetwork.com/web/v1/books"
DK_URL = "https://dknetwork.draftkings.com/draftkings-sportsbook-betting-splits/"
# Measured: NFL 88808 (worker_jobs 936774); NBA 42648, NHL 42133, NCAAF 87637, NCAAB 92483 (probe dk2 on the
# festive-gauss branch, 2026-11-26).
DK_EVENT_GROUPS = {"NFL": "88808", "NBA": "42648", "NHL": "42133", "NCAAF": "87637", "NCAAB": "92483"}
# The two DK Network pages a 2026-11-26 web search said show player-prop handle and bets. Not yet seen by anyone.
DK_ARTICLES = ("https://dknetwork.draftkings.com/?p=194999", "https://dknetwork.draftkings.com/?p=447024")
PERIODS = ("event", "firsthalf", "secondhalf", "firstquarter", "secondquarter", "thirdquarter", "fourthquarter",
           "firstperiod")
# In-season sports: the next date with games. Every period is asked.
LIVE_SLUGS = {"nba": "NBA", "nhl": "NHL", "nfl": "NFL", "ncaaf": "NCAAF", "ncaab": "NCAAB"}
# Off-season sports with a slug we know exists: their last played date, full game only.
PAST_SLUGS = {"wnba": "WNBA", "mlb": "MLB"}
# Slugs never asked: candidates only, each reported with its HTTP status. Sport is ours, for choosing a date.
CANDIDATE_SLUGS = {"ufc": "UFC", "mma": "UFC", "atp": "ATP", "wta": "WTA", "tennis": "ATP",
                   "euroleague": "EUROLEAGUE", "ncaaw": "NCAABW", "wcbb": "NCAABW"}
MARKETS = {"moneyline": "ml", "spread": "sp", "total": "tot", "core_bet_type_6_team_score": "tt"}
TIMEOUT = 25
_ET = ZoneInfo("America/New_York")
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _get(url: str, **kw):
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": _UA, **kw.pop("headers", {})}, **kw)
        return resp.status_code, resp.text, None
    except requests.RequestException as exc:
        return None, "", f"{type(exc).__name__}: {exc}"


def _pct(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def book_entries(game: dict, book: str, period: str) -> dict:
    """{(market, side, team_id): (tickets %, money %)} for one book and period, pre-game entries with a non-zero
    share only. 0/0 is Action Network's "no split" placeholder; a None share is missing. Pure."""
    block = ((game.get("markets") or {}).get(book) or {})
    mkts = block.get(period) if isinstance(block.get(period), dict) else {}
    out: dict = {}
    for market in MARKETS:
        for e in (mkts or {}).get(market) or []:
            if not isinstance(e, dict) or e.get("is_live"):
                continue
            bi = e.get("bet_info") or {}
            t = _pct((bi.get("tickets") or {}).get("percent"))
            m = _pct((bi.get("money") or {}).get("percent"))
            if not t and not m:
                continue
            key = (market, e.get("side"), e.get("team_id") if market == "core_bet_type_6_team_score" else None)
            out.setdefault(key, (t, m))
    return out


def compare_books(payload: dict, period: str) -> dict:
    """Per book: {market: {games, sides, same, tk_gap_med, mt_gap_med}}. `same` counts sides whose tickets and money
    both equal consensus's; `tk_gap_med` is the median |tickets - consensus tickets| over sides both carry;
    `mt_gap_med` the median |money - tickets| on the book's own sides. Pure."""
    acc: dict = {}
    for g in (payload or {}).get("games") or []:
        if not isinstance(g, dict):
            continue
        cons = book_entries(g, CONSENSUS, period)
        for book in sorted((g.get("markets") or {}).keys()):
            ents = book_entries(g, str(book), period)
            seen_markets = set()
            for (market, side, team), (t, m) in ents.items():
                a = acc.setdefault(str(book), {}).setdefault(
                    MARKETS[market], {"games": 0, "sides": 0, "same": 0, "compared": 0, "tk": [], "mt": []})
                if market not in seen_markets:
                    a["games"] += 1
                    seen_markets.add(market)
                a["sides"] += 1
                if t is not None and m is not None:
                    a["mt"].append(abs(m - t))
                c = cons.get((market, side, team))
                if str(book) != CONSENSUS and c is not None:
                    a["compared"] += 1
                    if c == (t, m):
                        a["same"] += 1
                    if t is not None and c[0] is not None:
                        a["tk"].append(abs(t - c[0]))
    out: dict = {}
    for book, mk in acc.items():
        for market, a in mk.items():
            out.setdefault(book, {})[market] = {
                "games": a["games"], "sides": a["sides"], "same": a["same"], "compared": a["compared"],
                "tk_gap_med": statistics.median(a["tk"]) if a["tk"] else None,
                "mt_gap_med": statistics.median(a["mt"]) if a["mt"] else None,
            }
    return out


def first_split_entry(payload: dict, market: str, period: str = "event", skip_book: str = "") -> dict | None:
    """One pre-game entry of `market` with a non-zero share, any book but `skip_book`, verbatim but for links. Pure."""
    for g in (payload or {}).get("games") or []:
        for book, block in sorted(((g or {}).get("markets") or {}).items()):
            if str(book) == skip_book or not isinstance(block, dict):
                continue
            for e in (block.get(period) or {}).get(market) or [] if isinstance(block.get(period), dict) else []:
                bi = (e or {}).get("bet_info") or {}
                if not (e or {}).get("is_live") and any(((bi.get(k) or {}).get("percent") or 0) for k in
                                                       ("tickets", "money")):
                    return {"book": book, **{k: v for k, v in e.items() if "deeplink" not in k}}
    return None


def _strip(body: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body or "", flags=re.S | re.I)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text)))


def dk_page_facts(body: str, words=("Player", "Prop"), width: int = 110, limit: int = 4) -> dict:
    """A DK Network page: its title, its market filters (tb_emt), links naming props, the number of split rows,
    and the text around each of `words` (first `limit` each). Pure."""
    title = re.search(r"<title[^>]*>(.*?)</title>", body or "", re.S | re.I)
    text = _strip(body)
    windows = {}
    for w in words:
        hits = [m.start() for m in re.finditer(re.escape(w), text)][:limit]
        windows[w] = [text[max(0, i - width): i + width] for i in hits]
    hrefs = [unescape(h) for h in re.findall(r"href=[\"']([^\"']+)", body or "", re.I)]
    return {
        "title": unescape(title.group(1)).strip()[:150] if title else None,
        "filters": sorted({unescape(v) for v in re.findall(r"tb_emt=([^&\"'#]+)", unescape(body or ""))}),
        "split_rows": max(0, len(text.split("Selection Odds Handle Bets")) - 1),
        "prop_links": sorted({h for h in hrefs if "prop" in h.lower()})[:12],
        "handle_windows": [text[max(0, i - width): i + width]
                           for i in [m.start() for m in re.finditer("Handle", text)][:2]],
        "windows": windows,
    }


def _fmt_compare(cmp: dict) -> str:
    parts = []
    for book in sorted(cmp, key=lambda b: (b != CONSENSUS, int(b) if b.isdigit() else 0)):
        cells = []
        for market, a in sorted(cmp[book].items()):
            cell = f"{market}:{a['games']}g"
            if book != CONSENSUS:
                cell += f",same {a['same']}/{a['compared']},tk {a['tk_gap_med']}"
            cell += f",mt {a['mt_gap_med']}"
            cells.append(cell)
        parts.append(f"{book}[{' '.join(cells)}]")
    return " ".join(parts) or "none"


def match_counts(sport: str, payload: dict, games: list[dict]) -> dict:
    """How many of the payload's games the Scoreboard ingestor would parse (a non-zero consensus split) and match to
    a `games` row, with its own parser and matcher (data/ingestors/scoreboard_splits). Pure but for that import."""
    from data.ingestors.scoreboard_splits import match, parse_game
    out = {"listed": 0, "with_split": 0, "matched": 0}
    for g in (payload or {}).get("games") or []:
        if not isinstance(g, dict):
            continue
        out["listed"] += 1
        parsed = parse_game(sport, g)
        if parsed is None:
            continue
        out["with_split"] += 1
        if match(parsed, games) is not None:
            out["matched"] += 1
    return out


def _games(conn, sport: str, day: str) -> list[dict]:
    if conn is None:
        return []
    cols = ("game_id", "sport", "game_date", "home_team", "away_team", "commence_time")
    iso = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    return [dict(zip(cols, r)) for r in conn.execute(
        "SELECT game_id, sport, game_date::text, home_team, away_team, commence_time::text FROM games "
        "WHERE sport = %s AND game_date::text = %s", (sport, iso)).fetchall()]


def _dates(conn, sport: str, past: bool) -> list[str]:
    """YYYYMMDD: the last past date with 3+ games, or the next two dates with games, from `games`."""
    if conn is None:
        return []
    if past:
        sql = ("SELECT game_date::text FROM games WHERE sport = %s AND game_date::date < current_date "
               "GROUP BY 1 HAVING count(*) >= 3 ORDER BY 1 DESC LIMIT 1")
    else:
        sql = ("SELECT game_date::text FROM games WHERE sport = %s AND game_date::date >= current_date "
               "GROUP BY 1 ORDER BY 1 LIMIT 2")
    return [r[0].replace("-", "") for r in conn.execute(sql, (sport,)).fetchall()]


def _an(get, slug: str, day: str, period: str):
    status, text, err = get(AN_SCOREBOARD.format(slug=slug), params={"date": day, "periods": period},
                            headers={"Accept": "application/json",
                                     "Referer": f"https://www.actionnetwork.com/{slug}/public-betting"})
    if err or status != 200:
        return None, (err or f"HTTP {status}")
    try:
        return json.loads(text), None
    except ValueError:
        return None, "not JSON"


def probe(get=_get, conn=None) -> int:
    summary: list[str] = []
    samples: list[str] = []
    failed = False

    def say(line: str) -> None:
        print(line)
        summary.append(line)

    status, text, err = get(AN_BOOKS)
    names = {}
    if not err and status == 200:
        try:
            for b in json.loads(text).get("books") or []:
                names[str(b.get("id"))] = b.get("display_name") or b.get("name")
        except (ValueError, AttributeError):
            pass
    say(f"an books: {len(names)} named; " + ", ".join(f"{i}={names.get(i)}" for i in
                                                    ("15", "30", "49", "68", "69", "71", "75")))

    for slug, sport in {**LIVE_SLUGS, **PAST_SLUGS, **CANDIDATE_SLUGS}.items():
        past = slug in PAST_SLUGS or (slug in CANDIDATE_SLUGS and not _dates(conn, sport, False))
        days = _dates(conn, sport, past)
        if not days:
            say(f"an {slug}: no {('past' if past else 'upcoming')} {sport} date in games")
            continue
        periods = PERIODS if slug in LIVE_SLUGS else ("event",)
        for day in days:
            for period in periods:
                payload, why = _an(get, slug, day, period)
                if payload is None:
                    say(f"an {slug} {day} {period}: {why}")
                    if slug in LIVE_SLUGS:
                        failed = True
                    break
                games = len(payload.get("games") or [])
                say(f"an {slug} {day} {period}: games={games} {_fmt_compare(compare_books(payload, period))}")
                if period == "event" and slug not in LIVE_SLUGS and games:
                    say(f"an {slug} {day} match: {match_counts(sport, payload, _games(conn, sport, day))}")
                if period == "event":
                    for market in ("core_bet_type_6_team_score", "spread"):
                        e = first_split_entry(payload, market, skip_book=CONSENSUS)
                        if e:
                            samples.append(f"sample {slug} {market}: {json.dumps(e, default=str)[:500]}")

    for sport, eg in DK_EVENT_GROUPS.items():
        status, page, err = get(DK_URL, params={"tb_eg": eg, "tb_edate": "n7days"})
        if err or status != 200:
            say(f"dk {sport} (eg {eg}): {err or f'HTTP {status}'}")
            failed = True
            continue
        say(f"dk {sport} (eg {eg}): {json.dumps(dk_page_facts(page))[:1400]}")
    for url in DK_ARTICLES:
        status, page, err = get(url)
        line = (f"dk article {url}: {err or f'HTTP {status}'}" if err or status != 200
                else f"dk article {url}: {json.dumps(dk_page_facts(page, words=('Prop', 'Over', 'Handle')))[:1400]}")
        say(line)

    print(SUMMARY_MARK)
    # Summary first: the job keeps its first 6,000 characters; the samples follow in stdout.
    for line in summary + samples:
        print(line)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    try:
        from monitoring.probe import install
        install("splits-coverage-probe")
    except Exception:  # noqa: BLE001
        pass
    conn = None
    try:
        from data.db import get_connection
        conn = get_connection()
    except Exception as exc:  # noqa: BLE001
        print(f"no database connection ({type(exc).__name__}); dates cannot be chosen")
    try:
        return probe(conn=conn)
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
