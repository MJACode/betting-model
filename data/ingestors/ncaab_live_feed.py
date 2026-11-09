"""The NCAAB in-play loop's two feeds (models/ncaab_live_loop.py).

ESPN (free). The scoreboard (Division I, one ET date a call) says which games
are in progress; each game's summary carries its play-by-play with ESPN's
wallclock, parsed by data.ingestors.ncaab_pbp.summary_rows, the parser that
wrote the play-by-play the model was graded on. Every event is mapped to our
game by ESPN's event id (ncaab_events), never by team names.

Measured on the 2026-11-07 afternoon slate (17 games polled every 5 s for 90
minutes, 2,587 plays first seen live, 433 of them scoring): ESPN served a
scoring play a median 37 s after its wallclock, 55 s at the 99th percentile,
58 s at the longest; two non-scoring plays of 2,587 came later than 120 s (a
dead-ball team rebound at 725 s, a coach's challenge at 148 s).

THE ODDS API (paid). One bulk call for every NCAAB game at once:
    GET /v4/sports/basketball_ncaab/odds?regions=us&markets=spreads,totals
        &bookmakers=<the ten books the in-play history was bought at>
The ten books are config.LINE_SHOP_BOOKMAKERS[:10], the purchase's own list
(data/ingestors/ncaab_odds_history.BOOKS), so a fetch's outlier reference and
the deciding books are the ones the grade had. Ten names bill as one region:
2 markets, 2 credits a call (measured on the first call; logged). Rows are
parsed by odds_ingestor._process_events onto ESPN's games through
ncaab_teams.make_resolver, stored in_play under LIVE_SOURCE.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from data.ingestors.nba_live_feed import (Fetch, LiveOddsFeed, clock_running,  # noqa: F401
                                          late_plays, score_mismatch)

log = logging.getLogger(__name__)

SPORT = "NCAAB"
SPORT_KEY = "basketball_ncaab"
ODDS_URL = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds"
MARKETS = ("spreads", "totals")
LIVE_SOURCE = "ncaab_live_loop"
SCOREBOARD_URL = ("https://site.api.espn.com/apis/site/v2/sports/basketball/"
                  "mens-college-basketball/scoreboard")


def feed_books() -> list[str]:
    """The ten books the in-play history was bought at (one region group)."""
    import config
    books = list(config.LINE_SHOP_BOOKMAKERS[:10])
    if len(books) > 10:
        raise ValueError(f"{len(books)} books would bill a second region")
    return books


def odds_feed(call_cap: int, credit_cap: int, session=None) -> LiveOddsFeed:
    return LiveOddsFeed(call_cap, credit_cap, session=session, url=ODDS_URL, markets=MARKETS,
                        books=feed_books, label="NCAAB")


@dataclass(frozen=True)
class EspnGame:
    event_id: int
    state: str                    # 'pre' | 'in' | 'post'
    status: str                   # STATUS_IN_PROGRESS, STATUS_HALFTIME, ...
    period: int | None
    clock: str | None
    commence: str | None
    season_type: int | None


def parse_scoreboard(data: dict) -> list[EspnGame]:
    out = []
    for ev in (data or {}).get("events") or []:
        st = ev.get("status") or {}
        t = st.get("type") or {}
        try:
            eid = int(ev.get("id"))
        except (TypeError, ValueError):
            continue
        per = st.get("period")
        out.append(EspnGame(event_id=eid, state=str(t.get("state") or ""),
                            status=str(t.get("name") or ""),
                            period=int(per) if isinstance(per, (int, float)) else None,
                            clock=st.get("displayClock"), commence=ev.get("date"),
                            season_type=(ev.get("season") or {}).get("type")))
    return out


class Espn:
    """Free ESPN reads; a failed read is None and the caller decides."""

    def __init__(self, get=None):
        self._get = get
        self.calls = 0

    def _json(self, url: str, params: dict) -> dict | None:
        self.calls += 1
        try:
            if self._get is not None:
                return self._get(url, params)
            import requests
            from data.ingestors.injury_ingestor import ESPN_HEADERS
            r = requests.get(url, params=params, headers=ESPN_HEADERS, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            log.warning("ESPN read failed %s %s: %s", url.rsplit("/", 1)[-1], params, exc)
            return None

    def scoreboard(self, game_date: str) -> list[EspnGame] | None:
        d = self._json(SCOREBOARD_URL, {"dates": game_date.replace("-", ""), "groups": 50,
                                        "limit": 500})
        return None if d is None else parse_scoreboard(d)

    def summary(self, event_id: int) -> dict | None:
        from data.ingestors.ncaab_pbp import SUMMARY_URL
        return self._json(SUMMARY_URL, {"event": str(event_id)})


def rows_from_events(events: list, fetched_at, resolver) -> list[dict]:
    """`odds` rows (snapshot_type in_play, snapshot_at = each book's market
    last_update) for our NCAAB games, through odds_ingestor._process_events and
    ncaab_teams.make_resolver (`resolver`; None resolves nothing)."""
    if resolver is None:
        return []
    from data.ingestors.odds_ingestor import _process_events
    _games, rows = _process_events(events, SPORT, "in_play", fetched_at.isoformat(),
                                   resolve_game_id=resolver)
    rows = [r for r in rows if r.get("market") in MARKETS]
    for r in rows:
        r["source"] = LIVE_SOURCE
    return rows
