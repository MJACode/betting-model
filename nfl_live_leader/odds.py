"""
DraftKings' live NFL moneyline: ONE bulk call per evaluation pass.

    GET /v4/sports/americanfootball_nfl/odds?regions=us&markets=h2h&bookmakers=draftkings

The bulk endpoint returns every NFL event in one response, so a pass that
evaluates three games costs the same as one. It is only called when at least
one in-window game is due (gameday.py), never on the 20-second state tick.

CREDITS ARE MEASURED, NOT ASSUMED: every response's `x-requests-last` header is
added to the session total, and the feed refuses to fetch past
NFL_LIVE_LEADER_CREDIT_CAP (default 2000) for the life of the process.

`last_update` is kept PER QUOTE -- the DraftKings outcome's market timestamp,
else the bookmaker's. It is the book's own publish clock, which is what
data/live_quote_guard.quote_predates_score compares against the moment we saw
the score change.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

log = logging.getLogger(__name__)

SPORT_KEY = "americanfootball_nfl"
ODDS_URL = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds"
BOOK = "draftkings"
SESSION_CREDIT_CAP = int(os.environ.get("NFL_LIVE_LEADER_CREDIT_CAP", "2000"))


def _api_key() -> str:
    return os.environ.get("THE_ODDS_API_KEY") or os.environ.get("ODDS_API_KEY", "")


@dataclass(frozen=True)
class Quote:
    home_team: str            # The Odds API's full names
    away_team: str
    commence_time: str | None
    home_price: float | None  # DraftKings American
    away_price: float | None
    last_update: str | None   # DraftKings' own publish time for this market


SESSION_CALL_CAP = int(os.environ.get("NFL_LIVE_LEADER_CALL_CAP", "400"))


def parse_h2h(events: list) -> dict[tuple[str, str, str], Quote]:
    """{(home_team, away_team, commence_time): Quote} for every event DraftKings
    prices. Keyed on the KICKOFF as well as the teams: the bulk feed lists every
    upcoming event, and a later meeting of the same two teams (a divisional
    rematch) must not overwrite the game in progress (review of the build,
    2026-10-13)."""
    out: dict[tuple[str, str, str], Quote] = {}
    for ev in events or []:
        home, away = ev.get("home_team"), ev.get("away_team")
        if not home or not away:
            continue
        for bk in ev.get("bookmakers") or []:
            if (bk.get("key") or "").strip().lower() != BOOK:
                continue
            for m in bk.get("markets") or []:
                if m.get("key") != "h2h":
                    continue
                prices = {}
                for o in m.get("outcomes") or []:
                    if o.get("name") == home:
                        prices["home"] = o.get("price")
                    elif o.get("name") == away:
                        prices["away"] = o.get("price")
                out[(home, away, ev.get("commence_time") or "")] = Quote(home, away, ev.get("commence_time"),
                                          prices.get("home"), prices.get("away"),
                                          m.get("last_update") or bk.get("last_update"))
    return out


class LiveOddsFeed:
    def __init__(self, cap: int = SESSION_CREDIT_CAP, session=None):
        self.cap = int(cap)
        self.credits_used = 0
        self.calls = 0
        self.last_credits: int | None = None
        self._session = session

    def fetch(self) -> list | None:
        """One bulk call, or None (cap reached, no key, or the call failed).
        Never returns a cached payload: a pass prices on this pass's quote."""
        if self.credits_used >= self.cap:
            log.error("live odds: session credit cap %d reached (%d used) - not fetching",
                      self.cap, self.credits_used)
            return None
        if self.calls >= SESSION_CALL_CAP:
            # A call that fails before the header is read moves no credit
            # meter, so the call count is capped too.
            log.error("live odds: session call cap %d reached - not fetching", SESSION_CALL_CAP)
            return None
        key = _api_key()
        if not key:
            log.error("live odds: no ODDS_API_KEY / THE_ODDS_API_KEY set")
            return None
        import requests
        s = self._session or requests
        self.calls += 1
        try:
            r = s.get(ODDS_URL, params={"apiKey": key, "regions": "us", "markets": "h2h",
                                        "bookmakers": BOOK, "oddsFormat": "american"},
                      timeout=30)
            used = r.headers.get("x-requests-last")
            if used is not None:
                self.last_credits = int(float(used))
                self.credits_used += self.last_credits
            r.raise_for_status()
            payload = r.json()
            log.info("live odds: %d events, x-requests-last=%s (session %d of %d)",
                     len(payload), used, self.credits_used, self.cap)
            return payload if isinstance(payload, list) else None
        except Exception as exc:                      # noqa: BLE001
            log.warning("live odds fetch failed: %s", exc)
            return None
