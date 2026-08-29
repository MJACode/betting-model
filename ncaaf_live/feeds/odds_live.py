"""
In-play NCAAF odds: one metered bulk fetch covering every live game.

The Odds API's bulk /odds endpoint returns all events for the sport in a
single call, so live coverage of a 20-game Saturday window costs the same
credits as one game - which is why the cadence can be raised without the bill
scaling in the number of live games. Credits are read off the RESPONSE HEADERS
every call (the platform's odds_quota lesson: measure, never trust the
documented formula) and the loop stops fetching at the session cap.
"""

from __future__ import annotations

import logging
import time

import requests

from ..config import (LIVE_ODDS_MAX_AGE_SEC, LIVE_ODDS_SESSION_CREDIT_CAP,
                      ODDS_API_KEY, ODDS_SPORT_KEY, POLL_ODDS_SEC,
                      SNAPSHOT_BOOK)

log = logging.getLogger(__name__)

ODDS_URL = f"https://api.the-odds-api.com/v4/sports/{ODDS_SPORT_KEY}/odds"

# Sized in config against the CURRENT cadence. This was a flat 5000, which
# quietly fit the old 60s debounce (~720 fetches a Saturday) and would have
# been exhausted by mid-afternoon at 15s - after which the old code returned
# the cached payload forever, i.e. the loop would have gone on pricing against
# a line frozen hours earlier. The age bound below is what makes that safe.
SESSION_CREDIT_CAP = LIVE_ODDS_SESSION_CREDIT_CAP


class LiveOddsFeed:
    def __init__(self):
        self.credits_used = 0
        self.last_fetch_ts = 0.0
        self.last_payload: list | None = None

    def _cached(self) -> list | None:
        """The cached payload, but only while it is still young enough to be a
        price you could actually take. Past LIVE_ODDS_MAX_AGE_SEC we report NO
        odds, which makes the engine decline rather than bet into a line that
        stopped refreshing (credit cap hit, key revoked, feed down)."""
        if self.last_payload is None:
            return None
        age = time.time() - self.last_fetch_ts
        if age > LIVE_ODDS_MAX_AGE_SEC:
            log.error("live odds: cached payload is %.0fs old (> %ds) - "
                      "reporting no odds rather than pricing a stale line",
                      age, LIVE_ODDS_MAX_AGE_SEC)
            return None
        return self.last_payload

    def fetch(self, min_interval: float = POLL_ODDS_SEC) -> list | None:
        """
        Debounced bulk fetch. Returns the cached payload inside the debounce
        window, and None whenever we have nothing fresh enough to price on.
        """
        now = time.time()
        if self.last_payload is not None and now - self.last_fetch_ts < min_interval:
            return self.last_payload
        if self.credits_used >= SESSION_CREDIT_CAP:
            log.error("live odds: session credit cap %s reached - not fetching",
                      SESSION_CREDIT_CAP)
            return self._cached()
        if not ODDS_API_KEY:
            log.error("live odds: no ODDS_API_KEY / THE_ODDS_API_KEY set")
            return None
        try:
            r = requests.get(ODDS_URL, params={
                "apiKey": ODDS_API_KEY, "regions": "us",
                "markets": "h2h,totals", "oddsFormat": "american",
                "bookmakers": SNAPSHOT_BOOK,
            }, timeout=30)
            r.raise_for_status()
            used = r.headers.get("x-requests-last")
            if used is not None:
                self.credits_used += int(float(used))
            self.last_fetch_ts = now
            self.last_payload = r.json()
            log.info("live odds: %d events, +%s credits (session %d)",
                     len(self.last_payload), used, self.credits_used)
            return self.last_payload
        except Exception as exc:                    # noqa: BLE001
            log.warning("live odds fetch failed: %s", exc)
            return self._cached()


def parse_event_odds(events: list) -> dict:
    """
    {(home_team, away_team): {h2h: {home, away}, total: {line, over, under},
     commence_time}} - keys are The Odds API's own team names; the caller
    maps them to school identity.
    """
    out = {}
    for ev in events or []:
        home, away = ev.get("home_team"), ev.get("away_team")
        if not home or not away:
            continue
        rec = {"commence_time": ev.get("commence_time"),
               "h2h": None, "total": None}
        for bk in ev.get("bookmakers", []) or []:
            for m in bk.get("markets", []) or []:
                if m.get("key") == "h2h":
                    prices = {}
                    for o in m.get("outcomes", []) or []:
                        if o.get("name") == home:
                            prices["home"] = o.get("price")
                        elif o.get("name") == away:
                            prices["away"] = o.get("price")
                    if len(prices) == 2:
                        rec["h2h"] = prices
                elif m.get("key") == "totals":
                    line = over = under = None
                    for o in m.get("outcomes", []) or []:
                        if o.get("name") == "Over":
                            line, over = o.get("point"), o.get("price")
                        elif o.get("name") == "Under":
                            under = o.get("price")
                    if line is not None:
                        rec["total"] = {"line": line, "over": over,
                                        "under": under}
        out[(home, away)] = rec
    return out
