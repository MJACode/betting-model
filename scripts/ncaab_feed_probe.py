"""Is the NCAAB odds feed up, does it resolve onto ESPN's schedule, and what does
College Basketball Data serve?

WHY. Men's college basketball goes live for 2026-27 (first game 2026-11-01).
Before the history purchase and the live poll spend anything, three things are
measured where the keys are (the worker; mike, 2026-10-26):

  (a) The Odds API, FREE calls only: /v4/sports (is basketball_ncaab active?)
      and /v4/sports/basketball_ncaab/events (how many events, the earliest
      tip, and every team name ncaab_teams.resolve_team_name cannot place,
      plus how many events land on an ESPN game through make_resolver).
      x-requests-last is printed for each and must read 0.
  (b) Up to --market-events N events (default 5, at most 10):
      /events/{id}/markets, 1 credit each, the market keys each book offers.
  (c) College Basketball Data (api.collegebasketballdata.com), the CFBD key as
      a Bearer token: teams, one team's games and lines, and the line
      providers, with status, size and any rate-limit header.

Writes nothing but the Odds API quota reading (odds_api_quota, as every Odds API
caller does). Never prints a key: an exception is reported by its type only,
because a requests error message carries the URL and the URL carries apiKey.
The compact summary is printed LAST, after a marker the worker job reads, so
the job card shows it and worker_jobs.result keeps the whole printout.

    python -m scripts.ncaab_feed_probe --market-events 5
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date

import requests

import config
from data.ingestors.ncaab_teams import (ODDS_API_SPORT_KEY, eastern_game_date,
                                        load_registry, make_resolver, reset_registry_cache,
                                        resolve_team_name)
from data.ingestors.odds_quota import persist_quota, record_quota_headers

ODDS = "https://api.the-odds-api.com/v4"
CBBD = "https://api.collegebasketballdata.com"
BOOKS = ",".join(config.LINE_SHOP_BOOKMAKERS[:10])
MAX_MARKET_EVENTS = 10
SUMMARY_MARK = "== SUMMARY =="


class Report:
    """Every line printed goes through here, so no key can reach the output."""

    def __init__(self, secrets: tuple[str, ...]):
        self.secrets = tuple(s for s in secrets if s)
        self.summary: list[str] = []

    def clean(self, text) -> str:
        text = str(text)
        for s in self.secrets:
            text = text.replace(s, "***")
        return text

    def line(self, text) -> None:
        print(self.clean(text))

    def sum(self, text) -> None:
        self.summary.append(self.clean(text))


def _get(url: str, params: dict | None = None, headers: dict | None = None):
    """(response, None) or (None, the exception's TYPE). Never the message: a
    requests error quotes the URL, and an Odds API URL carries the key."""
    try:
        return requests.get(url, params=params, headers=headers, timeout=30), None
    except requests.RequestException as exc:
        return None, type(exc).__name__


def _json(r):
    try:
        return r.json()
    except ValueError:
        return None


def _hdr(r, name: str) -> str:
    return (r.headers.get(name) if r is not None else None) or "?"


def _free_verdict(*billed: str) -> str:
    """"ok" when every free call read x-requests-last 0, "NOT ZERO" when any
    billed, "NOT READ" when a header is missing (a failed call or no header is
    not evidence of a charge, and not evidence it was free either)."""
    vals = []
    for b in billed:
        try:
            vals.append(float(b))
        except (TypeError, ValueError):
            vals.append(None)
    if any(v is not None and v > 0 for v in vals):
        return "NOT ZERO"
    return "ok" if all(v == 0 for v in vals) else "NOT READ"


# ── (a) and (b): The Odds API ────────────────────────────────────────────────

def probe_odds(conn, rep: Report, market_events: int) -> None:
    key = config.ODDS_API_KEY
    if not key:
        rep.line("odds: ODDS_API_KEY is not set here")
        rep.sum("odds: no ODDS_API_KEY on this machine; nothing called")
        return
    r, err = _get(f"{ODDS}/sports", {"apiKey": key, "all": "true"})
    if r is not None:
        record_quota_headers(r)
    sports = _json(r) if r is not None and r.status_code == 200 else None
    entry = next((s for s in (sports or []) if s.get("key") == ODDS_API_SPORT_KEY), None)
    active = entry.get("active") if entry else None
    rep.line(f"odds /sports: HTTP {getattr(r, 'status_code', err)}, x-requests-last "
             f"{_hdr(r, 'x-requests-last')}, remaining {_hdr(r, 'x-requests-remaining')}; "
             f"{ODDS_API_SPORT_KEY} {'listed' if entry else 'NOT listed'}, active={active}")
    sports_last = _hdr(r, "x-requests-last")

    r, err = _get(f"{ODDS}/sports/{ODDS_API_SPORT_KEY}/events", {"apiKey": key})
    if r is not None:
        record_quota_headers(r)
    events = _json(r) if r is not None and r.status_code == 200 else None
    events = events if isinstance(events, list) else []
    events_last, remaining = _hdr(r, "x-requests-last"), _hdr(r, "x-requests-remaining")
    tips = sorted(e.get("commence_time") or "" for e in events if e.get("commence_time"))
    rep.line(f"odds /events: HTTP {getattr(r, 'status_code', err)}, x-requests-last "
             f"{events_last}, remaining {remaining}; {len(events)} events, earliest "
             f"{tips[0] if tips else 'none'}, latest {tips[-1] if tips else 'none'}")
    free = _free_verdict(sports_last, events_last)
    rep.sum(f"odds: {ODDS_API_SPORT_KEY} active={active}; {len(events)} events, earliest "
            f"{tips[0] if tips else 'none'}; x-requests-last sports={sports_last} "
            f"events={events_last} ({free}); remaining {remaining}")

    _resolve_report(conn, rep, events, tips)
    if market_events > 0 and events:
        _markets_report(rep, key, sorted(events, key=lambda e: e.get("commence_time") or "")
                        [:market_events])


def _resolve_report(conn, rep: Report, events: list[dict], tips: list[str]) -> None:
    """Every feed name the ESPN registry cannot place, and how many events land
    on an ESPN game. Unplaced names are what config.NCAAB_ODDS_API_MAP fixes."""
    if conn is None:
        rep.line("names: no database connection here, registry not read")
        rep.sum("names: not checked (no database connection)")
        return
    # The worker runs every job in one process and load_registry caches what it
    # read first, an empty list included. This probe is declared to run BEFORE
    # the ESPN backfill creates ncaab_teams, so it reads fresh and leaves no
    # cache behind: an empty one would make every later NCAAB job in the same
    # process resolve nothing (2026-10-26 review).
    reset_registry_cache()
    try:
        _resolve_names(conn, rep, events, tips)
    finally:
        reset_registry_cache()


def _resolve_names(conn, rep: Report, events: list[dict], tips: list[str]) -> None:
    registry = load_registry(conn)
    names = sorted({n for e in events for n in (e.get("home_team"), e.get("away_team")) if n})
    unresolved = [n for n in names if resolve_team_name(n, registry) is None]
    rep.line(f"names: {len(names)} distinct feed names, registry {len(registry)} teams, "
             f"{len(unresolved)} unresolved: {unresolved}")
    on_game = flipped = 0
    if tips:
        first = date.fromisoformat(eastern_game_date(tips[0]))
        last = date.fromisoformat(eastern_game_date(tips[-1]))
        resolve = make_resolver(conn, first.isoformat(), days_back=2,
                                days_fwd=(last - first).days + 2)
        for e in events:
            hit = resolve(e.get("home_team") or "", e.get("away_team") or "",
                          e.get("commence_time") or "") if resolve else None
            if hit:
                on_game += 1
                flipped += int(hit[1])
    rep.line(f"resolve: {on_game} of {len(events)} events land on an ESPN game "
             f"({flipped} with the feed's home and away reversed)")
    shown = ", ".join(unresolved[:15]) + (" ..." if len(unresolved) > 15 else "")
    rep.sum(f"names: {len(unresolved)} of {len(names)} unresolved [{shown or 'none'}]; "
            f"{on_game} of {len(events)} events on an ESPN game ({flipped} reversed)")


def _markets_report(rep: Report, key: str, events: list[dict]) -> None:
    """Which market keys each book offers, over the soonest events (1 credit each)."""
    offered: dict[str, Counter] = defaultdict(Counter)
    billed = []
    for e in events:
        r, err = _get(f"{ODDS}/sports/{ODDS_API_SPORT_KEY}/events/{e.get('id')}/markets",
                      {"apiKey": key, "bookmakers": BOOKS})
        if r is not None:
            record_quota_headers(r)
        billed.append(_hdr(r, "x-requests-last"))
        body = _json(r) if r is not None and r.status_code == 200 else None
        books = (body or {}).get("bookmakers", []) if isinstance(body, dict) else []
        rep.line(f"markets {e.get('away_team')} @ {e.get('home_team')} "
                 f"({e.get('commence_time')}): HTTP {getattr(r, 'status_code', err)}, "
                 f"x-requests-last {billed[-1]}, {len(books)} books")
        for b in books:
            for m in b.get("markets", []):
                offered[b.get("key")][m.get("key")] += 1
    for book in sorted(offered):
        rep.line(f"  {book}: " + ", ".join(f"{m} ({n}/{len(events)})"
                                            for m, n in sorted(offered[book].items())))
    every = sorted(set.intersection(*(set(c) for c in offered.values()))) if offered else []
    rep.sum(f"markets: {len(events)} events, x-requests-last {billed}; {len(offered)} books; "
            f"keys every book offers: {every or 'none'}")


# ── (c): College Basketball Data ─────────────────────────────────────────────

CBBD_CALLS = (("teams", "/teams", {"season": 2027}),
              ("games", "/games", {"season": 2026, "team": "Duke"}),
              ("lines", "/lines", {"season": 2026, "team": "Duke"}),
              ("providers", "/lines/providers", None))


def probe_cbbd(rep: Report) -> None:
    key = config.CFBD_API_KEY
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    else:
        rep.line("cbbd: CFBD_API_KEY is not set here; calling without it to read the status")
    parts = []
    for name, path, params in CBBD_CALLS:
        r, err = _get(f"{CBBD}{path}", params, headers)
        if r is None:
            rep.line(f"cbbd {path}: {err}")
            parts.append(f"{name} {err}")
            continue
        body = _json(r)
        size = len(r.content or b"")
        count = len(body) if isinstance(body, list) else None
        limits = {k: v for k, v in r.headers.items()
                  if "limit" in k.lower() or "remaining" in k.lower()}
        rep.line(f"cbbd {path} {params or ''}: HTTP {r.status_code}, {size:,} bytes"
                 + (f", {count} records" if count is not None else "")
                 + (f", rate headers {limits}" if limits else ""))
        if name == "providers" and isinstance(body, list):
            provs = [p.get("name") or p.get("provider") or p for p in body
                     if isinstance(p, (dict, str))]
            rep.line(f"cbbd providers: {provs}")
            parts.append(f"providers {provs}")
        elif name == "lines" and isinstance(body, list):
            seen = Counter(ln.get("provider") for g in body if isinstance(g, dict)
                           for ln in (g.get("lines") or []) if isinstance(ln, dict))
            rep.line(f"cbbd lines by provider: {dict(seen)}")
        parts.append(f"{name} {r.status_code}/{size:,}B")
        if limits:
            parts.append(f"limits {limits}")
    rep.sum("cbbd: " + "; ".join(parts))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--market-events", type=int, default=5,
                    help=f"events whose market list is read (1 credit each, 0..{MAX_MARKET_EVENTS})")
    a = ap.parse_args(argv)
    if not 0 <= a.market_events <= MAX_MARKET_EVENTS:
        ap.error(f"--market-events must be 0..{MAX_MARKET_EVENTS}")
    rep = Report((config.ODDS_API_KEY, config.CFBD_API_KEY))
    conn = None
    try:
        from data.db import get_connection
        conn = get_connection()
    except Exception as exc:                                    # noqa: BLE001
        rep.line(f"database: not reachable ({type(exc).__name__}); names are not checked")
    try:
        probe_odds(conn, rep, a.market_events)
        probe_cbbd(rep)
    finally:
        if conn is not None:
            try:
                persist_quota(conn)
            finally:
                conn.close()
    print(SUMMARY_MARK)
    for s in rep.summary:
        print(s)


if __name__ == "__main__":
    main()
