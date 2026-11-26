"""Which markets carry % of bets / % of money, beyond the full-game moneyline, spread and total?

Matt, 2026-11-26 ("Yes on 3"): the AI assistant's get_public_splits should cover every market a source splits.
What is already measured (worker_jobs 936774, scripts/splits_source_probe.py, 2026-11-03):
  * DK Network's page says it covers "the Spread, Total, and Moneyline on each game", and its market filter
    (tb_emt) offered exactly Moneyline / Spread / Total, on the NFL page only.
  * Action Network's v2 scoreboard was asked for periods=event (full game) only.

This asks the two questions left open, from the worker (this sandbox cannot resolve either host):
  1. DK Network, every sport the page links: which tb_emt market filters each sport page offers, and which market
     labels appear in its split rows.
  2. Action Network, NBA / NHL / NFL / NCAAB / NCAAF: for each `periods` value, HTTP status, games, and the
     consensus book's period and market keys that carry a non-zero, pre-game split (0/0 is Action Network's
     no-split placeholder).

Writes nothing, no Odds API call.

    python -m scripts.splits_markets_probe
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from html import unescape
from zoneinfo import ZoneInfo

import requests

SUMMARY_MARK = "== SUMMARY =="
DK_URL = "https://dknetwork.draftkings.com/draftkings-sportsbook-betting-splits/"
AN_SCOREBOARD = "https://api.actionnetwork.com/web/v2/scoreboard/{slug}"
AN_SPORTS = ("nba", "nhl", "nfl", "ncaab", "ncaaf")
AN_PERIODS = ("event", "firsthalf", "secondhalf", "firstquarter", "secondquarter", "thirdquarter",
              "fourthquarter", "firstperiod")
# The consensus book only: the request carries bookIds=15, as the ingestor's does, so any other book would just
# be missing from the response, which would read as "no splits" (PR #1638 review).
AN_BOOKS = ("15",)
DK_LABELS = ("Moneyline", "Spread", "Total", "1st Half", "2nd Half", "1st Quarter", "1st Period",
             "Team Total", "Player", "Props", "Alternate")
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


def dk_sport_links(body: str) -> dict[str, str]:
    """{event group id: the sport name in the link's itm_content} from the page's links. Pure."""
    out = {}
    for href in re.findall(r"href=[\"']([^\"']+)", body, re.I):
        href = unescape(href)
        eg = re.search(r"[?&]tb_eg=(\d+)", href)
        if eg and "betting-splits" in href:
            name = re.search(r"itm_content=([^&]+)", href)
            out.setdefault(eg.group(1), name.group(1) if name else "?")
    return out


def dk_markets(body: str) -> dict:
    """The market filters (tb_emt values) a DK page offers and the market labels its split rows show. Pure."""
    emt = sorted({unescape(v) for v in re.findall(r"tb_emt=([^&\"'#]+)", unescape(body))})
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.S | re.I)
    text = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text)))
    rows = text.split("Selection Odds Handle Bets")[1:]
    labels = {lab: sum(f" {r} ".count(f" {lab} ") for r in rows) for lab in DK_LABELS}
    return {"filters": emt, "games": len(rows), "labels": {k: v for k, v in labels.items() if v}}


def _share(v) -> bool:
    """A non-zero share, whether sent as a number or a string ("0" is no split). Pure."""
    try:
        return float(v) != 0
    except (TypeError, ValueError):
        return False


def an_split_markets(payload: dict, books=AN_BOOKS) -> dict:
    """{book: {period key: {market key: games with a bet_info split}}}. Pure."""
    out: dict[str, dict[str, dict[str, int]]] = {}
    for g in payload.get("games") or []:
        for book_id, book in (g.get("markets") or {}).items():
            if book_id not in books or not isinstance(book, dict):
                continue
            for period, mkts in book.items():
                if not isinstance(mkts, dict):
                    continue
                for market, arr in mkts.items():
                    if not isinstance(arr, list):
                        continue
                    # A real split has a non-zero share: 0/0 is Action Network's "no split" placeholder
                    # (the pair rules drop it), which the 2026-11-26 first run counted as a split.
                    has = any(isinstance(e, dict) and not e.get("is_live") and any(
                        _share(((e.get("bet_info") or {}).get(k) or {}).get("percent"))
                        for k in ("tickets", "money")) for e in arr)
                    if has:
                        cell = out.setdefault(book_id, {}).setdefault(period, {})
                        cell[market] = cell.get(market, 0) + 1
    return out


TEAM_SCORE_KEY = "core_bet_type_6_team_score"


def team_score_sample(payload: dict, book: str = "15", limit: int = 4) -> list[dict]:
    """The first game's consensus team-total entries, verbatim but for long fields, so the entry shape (side, team,
    value, bet_info) can be read before a parser is written (Matt 2026-11-26, "yes add splits"). Pure."""
    for g in payload.get("games") or []:
        block = ((g.get("markets") or {}).get(book) or {})
        for period in block.values():
            if isinstance(period, dict) and isinstance(period.get(TEAM_SCORE_KEY), list) and period[TEAM_SCORE_KEY]:
                out = []
                for e in period[TEAM_SCORE_KEY][:limit]:
                    out.append({k: v for k, v in e.items() if k not in ("deeplink", "deeplinks")} if isinstance(e, dict)
                               else e)
                return [{"home_team_id": g.get("home_team_id"), "away_team_id": g.get("away_team_id")}] + out
    return []


def probe(get=_get, today: str | None = None) -> int:
    summary: list[str] = []
    samples: list[str] = []
    failed = False

    status, body, err = get(DK_URL)
    if err or status != 200:
        summary.append(f"dk: {err or f'HTTP {status}'}")
        failed = True
        groups = {}
    else:
        groups = dk_sport_links(body)
        print(f"dk: default page {dk_markets(body)}; sport links {groups}")
    for eg, name in sorted(groups.items()):
        status, page, err = get(DK_URL, params={"tb_eg": eg, "tb_edate": "n7days"})
        line = (f"dk {name} (eg {eg}): {err or f'HTTP {status}'}" if err or status != 200
                else f"dk {name} (eg {eg}): {dk_markets(page)}")
        print(line)
        summary.append(line)

    day = today or datetime.now(_ET).strftime("%Y%m%d")
    for slug in AN_SPORTS:
        for period in AN_PERIODS:
            # Exactly the ingestor's request (bookIds=15), so a filter the endpoint treats differently shows here.
            status, text, err = get(AN_SCOREBOARD.format(slug=slug),
                                    params={"bookIds": "15", "date": day, "periods": period},
                                    headers={"Accept": "application/json",
                                             "Referer": f"https://www.actionnetwork.com/{slug}/public-betting"})
            if err or status != 200:
                line = f"an {slug} {period}: {err or f'HTTP {status}'}"
            else:
                try:
                    payload = json.loads(text)
                except ValueError:
                    line = f"an {slug} {period}: not JSON"
                else:
                    line = (f"an {slug} {period}: games={len(payload.get('games') or [])} "
                            f"splits={an_split_markets(payload)}")
                    if period == "event":
                        sample = team_score_sample(payload)
                        if sample:
                            samples.append(f"team_score sample {slug}: {json.dumps(sample, default=str)[:900]}")
            print(line)
            summary.append(line)

    print(SUMMARY_MARK)
    # Samples first: the job keeps the summary's first 6,000 characters.
    for line in samples + summary:
        print(line)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    try:
        from monitoring.probe import install
        install("splits-markets-probe")
    except Exception:  # noqa: BLE001
        pass
    return probe()


if __name__ == "__main__":
    sys.exit(main())
