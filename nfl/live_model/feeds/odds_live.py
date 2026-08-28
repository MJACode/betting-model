"""
In-play odds from The Odds API, metered.

COST MODEL. The live endpoint is 1 credit per market per region per call, and
the per-event endpoint is the same per event. A naive "poll everything every
minute" Sunday is five figures of credits, so every call in here goes through
a budget that refuses to spend past the daily cap. The cap is a hard stop, not
a warning: an unmetered poller is the single easiest way to turn a research
project into a bill.

WHAT WE POLL AND WHY
  anchor markets   every game that is live. This is the number we recalibrate
                   onto, so it has to be fresh or nothing downstream is valid.
  derivative       only games in a hunt state. Polling the 2H total of a game
                   whose main line has not moved buys nothing.
  props            per EVENT, not per slate, so a game with no bettable prop
                   state costs nothing.

NOTHING IS CACHED. A cached live line is a wrong line. The historical fetcher
in data_ingest/odds_api.py caches aggressively and correctly; this one must not.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

from ..config import (
    ANCHOR_MARKETS, EXECUTION_REGIONS, LIVE_DAILY_CREDIT_CAP, SPORT_KEY,
)

log = logging.getLogger(__name__)

API_ROOT = "https://api.the-odds-api.com/v4"


class CreditBudgetExceeded(RuntimeError):
    pass


@dataclass
class CreditMeter:
    """
    Spend tracker with a hard daily cap.

    `remaining_reported` is whatever the API last told us in the
    x-requests-remaining header, which is the authoritative number; our own
    count is the guard that stops us before we get there.
    """
    cap: int = LIVE_DAILY_CREDIT_CAP
    spent: int = 0
    calls: int = 0
    remaining_reported: int | None = None
    day: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    def _roll(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self.day:
            self.day, self.spent, self.calls = today, 0, 0

    def can_spend(self, cost: int) -> bool:
        self._roll()
        return self.cap <= 0 or (self.spent + cost) <= self.cap

    def charge(self, cost: int, remaining=None) -> None:
        self._roll()
        self.spent += cost
        self.calls += 1
        if remaining is not None:
            try:
                self.remaining_reported = int(float(remaining))
            except (TypeError, ValueError):
                pass


@dataclass
class Quote:
    """One priced side at one book."""
    game_id: str
    market: str
    bookmaker: str
    side: str                   # 'home' | 'away' | 'over' | 'under' | player name
    price: float                # American
    line: float | None          # point / total / handicap, None for h2h
    ts: datetime
    player: str | None = None
    # The BOOK's team names. Kept because the book's event id and ESPN's event
    # id are unrelated strings, so the only thing the two feeds share is who is
    # playing. Without these a live quote cannot be matched to the game on the
    # scoreboard at all.
    home_team: str | None = None
    away_team: str | None = None

    def age_seconds(self, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        return (now - self.ts).total_seconds()


class LiveOddsClient:
    def __init__(self, api_key: str | None = None, meter: CreditMeter | None = None):
        self.api_key = api_key or os.getenv("THE_ODDS_API_KEY") or os.getenv("ODDS_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "No Odds API key. Set THE_ODDS_API_KEY (the nfl package's own "
                "variable) or ODDS_API_KEY."
            )
        self.meter = meter or CreditMeter()

    # ---------------------------------------------------------------- calls
    def _get(self, url: str, params: dict, cost: int, max_retries: int = 3) -> list | dict:
        if not self.meter.can_spend(cost):
            raise CreditBudgetExceeded(
                f"daily live cap {self.meter.cap} would be exceeded "
                f"(spent {self.meter.spent}, this call {cost})"
            )
        params = dict(params, apiKey=self.api_key)
        last = None
        for attempt in range(max_retries):
            try:
                r = requests.get(url, params=params, timeout=20)
                if r.status_code == 200:
                    self.meter.charge(cost, r.headers.get("x-requests-remaining"))
                    return r.json()
                if r.status_code == 422:
                    # A market this book does not offer for this event. Costs
                    # nothing and is not an error: NFL quarter markets in
                    # particular come and go.
                    log.info("odds 422 (market unavailable): %s", r.text[:160])
                    return []
                if r.status_code in (429, 500, 502, 503, 504):
                    last = f"{r.status_code}"
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"Odds API {r.status_code}: {r.text[:200]}")
            except requests.RequestException as e:
                last = str(e)
                time.sleep(2 ** attempt)
        raise RuntimeError(f"odds fetch failed after {max_retries}: {last}")

    def fetch_markets(self, markets, regions: str = EXECUTION_REGIONS) -> list[Quote]:
        """Slate-wide fetch for featured and derivative markets."""
        markets = tuple(markets)
        cost = len(markets) * len(regions.split(","))
        payload = self._get(
            f"{API_ROOT}/sports/{SPORT_KEY}/odds",
            {"regions": regions, "markets": ",".join(markets),
             "oddsFormat": "american"},
            cost,
        )
        return parse_events(payload)

    def fetch_event_markets(self, event_id: str, markets,
                            regions: str = EXECUTION_REGIONS) -> list[Quote]:
        """
        Per-event fetch. Props live here, and so do quarter markets at most
        books. Charged per market per region for the one event, which is why a
        game with no bettable prop state costs nothing.
        """
        markets = tuple(markets)
        cost = len(markets) * len(regions.split(","))
        payload = self._get(
            f"{API_ROOT}/sports/{SPORT_KEY}/events/{event_id}/odds",
            {"regions": regions, "markets": ",".join(markets),
             "oddsFormat": "american"},
            cost,
        )
        return parse_events([payload] if isinstance(payload, dict) else payload)

    def fetch_anchor(self, regions: str = EXECUTION_REGIONS) -> list[Quote]:
        return self.fetch_markets(ANCHOR_MARKETS, regions=regions)


# ---------------------------------------------------------------- parsing
def parse_events(payload) -> list[Quote]:
    """
    Flatten an Odds API payload into Quote rows.

    Side naming is normalised here so nothing downstream has to know the API's
    conventions: h2h and spread outcomes carry the team NAME, totals carry
    Over/Under, and props carry the player in `description`. Getting this wrong
    silently is how a model ends up betting the wrong side of a total, so
    anything that cannot be classified is dropped rather than guessed.
    """
    out: list[Quote] = []
    if not payload:
        return out
    events = payload if isinstance(payload, list) else [payload]

    for ev in events:
        if not isinstance(ev, dict):
            continue
        gid = str(ev.get("id") or "")
        home = ev.get("home_team")
        away = ev.get("away_team")
        if not gid:
            continue
        for bk in ev.get("bookmakers") or []:
            book = bk.get("key") or ""
            for mk in bk.get("markets") or []:
                key = mk.get("key") or ""
                ts = _parse_ts(mk.get("last_update") or bk.get("last_update"))
                for oc in mk.get("outcomes") or []:
                    name = oc.get("name")
                    price = oc.get("price")
                    point = oc.get("point")
                    desc = oc.get("description")
                    if price is None:
                        continue
                    side = _side_of(key, name, home, away)
                    if side is None:
                        continue
                    out.append(Quote(
                        game_id=gid, market=key, bookmaker=book, side=side,
                        home_team=home, away_team=away,
                        price=float(price),
                        line=None if point is None else float(point),
                        ts=ts, player=desc,
                    ))
    return out


def _side_of(market: str, name, home, away) -> str | None:
    if not isinstance(name, str):
        return None
    low = name.strip().lower()
    if low in ("over", "yes"):
        return "over"
    if low in ("under", "no"):
        return "under"
    if low == "draw":
        return "draw"
    if home and name == home:
        return "home"
    if away and name == away:
        return "away"
    # Team totals name the team; alt lines do too. Unrecognised names are
    # dropped rather than mapped by guesswork.
    return None


def _parse_ts(raw) -> datetime:
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def best_price(quotes, market: str, side: str, line=None,
               books=None) -> Quote | None:
    """
    Best available price for one side, across books.

    Best means the highest payout, which for American odds is simply the
    largest number: +150 beats +100 beats -110 beats -200. That ordering holds
    across the sign flip, which is why this is a plain max and not a decimal
    conversion.
    """
    cands = [
        q for q in quotes
        if q.market == market and q.side == side
        and (line is None or (q.line is not None and abs(q.line - line) < 1e-9))
        and (books is None or q.bookmaker in books)
    ]
    return max(cands, key=lambda q: q.price) if cands else None


def two_way(quotes, market: str, line=None, book: str | None = None):
    """The two sides of a two-way market at one book, for de-vigging."""
    sides = ("home", "away") if not market.startswith("totals") and "total" not in market \
        else ("over", "under")
    picked = {}
    for s in sides:
        cands = [q for q in quotes
                 if q.market == market and q.side == s
                 and (line is None or (q.line is not None and abs(q.line - line) < 1e-9))
                 and (book is None or q.bookmaker == book)]
        if not cands:
            return None
        picked[s] = max(cands, key=lambda q: q.ts)
    return picked[sides[0]], picked[sides[1]]
