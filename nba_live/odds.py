"""The NBA in-play odds: ONE bulk call per hourly tick, credits measured.

    GET /v4/sports/basketball_nba/odds?regions=us&markets=h2h,spreads
        &bookmakers=<the 8 deciding books>,pinnacle&includeLinks=true&includeSids=true

The bulk endpoint returns every NBA event the books list, in play or not, in
one response, so a tick that decides ten games costs what one does. Nine named
books are one group of ten, which the feed bills as one region (config.py,
LINE_SHOP_BOOKMAKERS, measured 2026-09-20), so a call is markets x 1.

MEASURED, NOT ASSUMED: 2026-10-18 00:22Z, this exact call against the
pre-game NBA board (no game was in play) answered x-requests-last = 2, with 46
events and all nine books. The cost is markets x regions whether or not an event
is in play. Every response's x-requests-last is added to the process total;
the loop records each fetch in live_credit_telemetry and refuses to fetch
  * past NBA_LIVE_INGAME_CREDIT_CAP credits in this process (default 400),
  * past NBA_LIVE_INGAME_CALL_CAP calls in this process (default 200: a call
    that fails before its header is read moves no meter),
  * past NBA_LIVE_INGAME_DAILY_CREDIT_CAP credits today, by the telemetry
    (default 1,000), and
  * when the account's x-requests-remaining is under NBA_LIVE_INGAME_MIN_REMAINING
    (default 50,000; the latest reading, seeded at start from odds_api_quota),
    so this loop can never be the one that takes the balance to zero (the
    September 2026 outage, CLAUDE.md global section 5).
At one call an hour while games are in play, a full night is about 7 ticks, 14
credits. The caps are a runaway guard, not a budget.

`last_update` is kept PER MARKET (data/ingestors/odds_ingestor._process_events
stores it as snapshot_at): the book's own publish clock, the lab's `stamp`.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import config

log = logging.getLogger(__name__)

SPORT_KEY = "basketball_nba"
ODDS_URL = f"{config.ODDS_API_BASE}/sports/{SPORT_KEY}/odds"
MARKETS = ("h2h", "spreads")
BOOKS = tuple(dict.fromkeys((*config.BEST_LINE_BOOKMAKERS, "pinnacle")))
MEASURED_CREDITS_PER_CALL = 2
TELEMETRY_PURPOSE = "nba_live_ingame:h2h,spreads"
SESSION_CREDIT_CAP = int(os.environ.get("NBA_LIVE_INGAME_CREDIT_CAP", "400"))
SESSION_CALL_CAP = int(os.environ.get("NBA_LIVE_INGAME_CALL_CAP", "200"))
DAILY_CREDIT_CAP = int(os.environ.get("NBA_LIVE_INGAME_DAILY_CREDIT_CAP", "1000"))
MIN_REMAINING = int(os.environ.get("NBA_LIVE_INGAME_MIN_REMAINING", "50000"))


def _api_key() -> str:
    return os.environ.get("ODDS_API_KEY", "")


class LiveOddsFeed:
    def __init__(self, session=None, cap: int = SESSION_CREDIT_CAP, call_cap: int = SESSION_CALL_CAP,
                 min_remaining: int = MIN_REMAINING, remaining: float | None = None, now=None):
        self._session = session
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.cap, self.call_cap, self.min_remaining = int(cap), int(call_cap), int(min_remaining)
        self.remaining = remaining
        self.credits_used = 0
        self.calls = 0
        self.last_credits: int | None = None

    def refusal(self, used_today: int | None = None) -> str | None:
        """Why this feed will not fetch now, or None."""
        if not _api_key():
            return "no ODDS_API_KEY"
        if self.credits_used >= self.cap:
            return f"session credit cap {self.cap} reached ({self.credits_used} used)"
        if self.calls >= self.call_cap:
            return f"session call cap {self.call_cap} reached"
        if used_today is not None and used_today + MEASURED_CREDITS_PER_CALL > DAILY_CREDIT_CAP:
            return f"daily credit cap {DAILY_CREDIT_CAP} reached ({used_today} used today)"
        if self.remaining is not None and self.remaining < self.min_remaining:
            return (f"account balance {self.remaining:,.0f} is under the "
                    f"{self.min_remaining:,} floor")
        return None

    def fetch(self) -> tuple[list | None, datetime | None]:
        """(events, served_at): the payload and the moment it arrived, or
        (None, None) on any failure. Never a cached payload."""
        import requests
        from data.ingestors.odds_quota import record_quota_headers
        s = self._session or requests
        self.calls += 1
        try:
            r = s.get(ODDS_URL, params={"apiKey": _api_key(), "regions": "us",
                                        "markets": ",".join(MARKETS), "bookmakers": ",".join(BOOKS),
                                        "oddsFormat": "american", "includeLinks": "true",
                                        "includeSids": "true"}, timeout=30)
            served_at = self._now()
            record_quota_headers(r)
            used = r.headers.get("x-requests-last")
            left = r.headers.get("x-requests-remaining")
            if used not in (None, ""):
                self.last_credits = int(float(used))
                self.credits_used += self.last_credits
            if left not in (None, ""):
                self.remaining = float(left)
            r.raise_for_status()
            payload = r.json()
            log.info("live odds: %d events, x-requests-last=%s, remaining=%s (session %d of %d)",
                     len(payload) if isinstance(payload, list) else -1, used, left,
                     self.credits_used, self.cap)
            return (payload if isinstance(payload, list) else None), served_at
        except Exception as exc:                      # noqa: BLE001
            # Never the URL: it carries the key.
            log.warning("live odds fetch failed: %s", type(exc).__name__)
            return None, None


def used_today(conn, today: str | None = None) -> int:
    """This loop's credits today (UTC), from live_credit_telemetry."""
    today = today or datetime.now(timezone.utc).date().isoformat()
    row = conn.execute("""
        SELECT COALESCE(SUM(credits), 0) FROM live_credit_telemetry
        WHERE date = %s AND market = %s
    """, (today, TELEMETRY_PURPOSE)).fetchone()
    return int(row[0]) if row else 0


def record_fetch(conn, credits: int, fired_at: datetime) -> None:
    from data.ingestors.live_odds_ingestor import record_credits
    record_credits(conn, TELEMETRY_PURPOSE, int(credits), fired_at=fired_at.isoformat())


def latest_remaining(conn) -> float | None:
    """The account balance on record (odds_api_quota), to seed the floor."""
    try:
        from data.ingestors.odds_quota import latest_remaining as _lr
        v = _lr(conn)
        return None if v is None else float(v)
    except Exception:                                 # noqa: BLE001
        return None


def parse_events(events: list, served_at: datetime, known: set[str] | None = None) -> list[dict]:
    """The payload as `odds` rows (snapshot_type 'in_play', the book's own
    last_update as snapshot_at) through the pre-game ingestor's own parser, so
    game ids and team codes are the ones the `games` table holds."""
    from data.ingestors.odds_ingestor import _process_events
    _, rows = _process_events(events or [], "NBA", "in_play", served_at.isoformat())
    rows = [r for r in rows if r.get("market") in MARKETS and r.get("bookmaker") in BOOKS]
    if known is not None:
        rows = [r for r in rows if r["game_id"] in known]
    for r in rows:
        r["source"] = "nba_live_ingame"
    return rows
