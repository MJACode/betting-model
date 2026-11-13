"""The women's college basketball halftime loop's two feeds
(models/ncaabw_live_loop.py).

ESPN (free). The women's scoreboard (Division I, one ET date a call) says
which games are near their halftime break; each game's summary carries its
play-by-play with ESPN's wallclock, parsed by data.ingestors.ncaabw_pbp.
summary_rows, the parser the model was fitted through. Every event is mapped
to our game by ESPN's event id (ncaabw_events), never by team names.

THE ODDS API (paid). One bulk call for every women's game at once:
    GET /v4/sports/basketball_wncaab/odds?regions=us&markets=h2h,spreads,totals
        &bookmakers=<the seventeen books the women's history was bought at>
The books are odds_ingestor.sport_bookmakers_param("NCAABW"), the purchase's
own list, so a read's median total and its count of other books are over the
books the grade had. Seventeen names bill as two regions: three markets, 6
credits a call (config.NCAABW_EXTRA_BOOKMAKERS; the first call's cost is
logged). The model reads the totals; the spreads and moneylines of the same
read are stored beside them for the halftime spread's re-test
(docs/sports/ncaabw.md). Rows are parsed by odds_ingestor._process_events onto
ESPN's games through ncaabw_teams.make_resolver, stored in_play under
LIVE_SOURCE.
"""
from __future__ import annotations

import logging

from data.ingestors.nba_live_feed import (Fetch, LiveOddsFeed, header_score,  # noqa: F401
                                          late_plays, score_mismatch)
from data.ingestors.ncaab_live_feed import Espn as _Espn
from data.ingestors.ncaab_live_feed import EspnGame, parse_scoreboard  # noqa: F401

log = logging.getLogger(__name__)

SPORT = "NCAABW"
SPORT_KEY = "basketball_wncaab"
ODDS_URL = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds"
MARKETS = ("h2h", "spreads", "totals")
LIVE_SOURCE = "ncaabw_live_loop"
SCOREBOARD_URL = ("https://site.api.espn.com/apis/site/v2/sports/basketball/"
                  "womens-college-basketball/scoreboard")
HALFTIME = "STATUS_HALFTIME"


def feed_books() -> list[str]:
    """The books the women's history was bought at."""
    from data.ingestors.odds_ingestor import sport_bookmakers_param
    return sport_bookmakers_param(SPORT).split(",")


def odds_feed(call_cap: int, credit_cap: int, session=None) -> LiveOddsFeed:
    return LiveOddsFeed(call_cap, credit_cap, session=session, url=ODDS_URL, markets=MARKETS,
                        books=feed_books, label=SPORT)


class Espn(_Espn):
    """Free ESPN reads of the women's game; a failed read is None."""

    def scoreboard(self, game_date: str) -> list[EspnGame] | None:
        d = self._json(SCOREBOARD_URL, {"dates": game_date.replace("-", ""), "groups": 50,
                                        "limit": 500})
        return None if d is None else parse_scoreboard(d)

    def summary(self, event_id: int) -> dict | None:
        from data.ingestors.ncaabw_pbp import SUMMARY_URL
        return self._json(SUMMARY_URL, {"event": str(event_id)})


def near_half(g: EspnGame) -> bool:
    """ESPN's scoreboard has this game at or about its halftime break: in the
    second quarter, at halftime, or in the third. It only says when a price
    read is worth making; the decision reads the play list
    (models.ncaabw_live_ht.read_break)."""
    return g.state == "in" and (g.status == HALFTIME or g.period in (2, 3))


def header_state(summary: dict | None) -> dict | None:
    """ESPN's own header for a game: its status, period and score as ESPN lists
    the sides (home, away). None when the header cannot be read."""
    comp = (((summary or {}).get("header") or {}).get("competitions") or [{}])[0]
    st = comp.get("status") or {}
    sc = header_score(summary)
    if sc is None:
        return None
    per = st.get("period")
    return {"status": str((st.get("type") or {}).get("name") or ""),
            "period": int(per) if isinstance(per, (int, float)) else None,
            "home": sc[0], "away": sc[1]}


def rows_from_events(events: list, fetched_at, resolver) -> list[dict]:
    """`odds` rows (snapshot_type in_play, snapshot_at = each book's market
    last_update) for our women's games, through odds_ingestor._process_events
    and ncaabw_teams.make_resolver (`resolver`; None resolves nothing)."""
    if resolver is None:
        return []
    from data.ingestors.odds_ingestor import _process_events
    _games, rows = _process_events(events, SPORT, "in_play", fetched_at.isoformat(),
                                   resolve_game_id=resolver)
    rows = [r for r in rows if r.get("market") in MARKETS]
    for r in rows:
        r["source"] = LIVE_SOURCE
    return rows
