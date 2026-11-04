"""The NBA in-play loop's two feeds (models/nba_live_loop.py).

ESPN (free). `nba_pbp` is NOT a live table: data/ingestors/nba_pbp.fill_gaps
loads a game only once it has a final score, in the 6am pipeline (step
nba-quarters). So the loop reads ESPN's own summary endpoint during the game
and turns it into nba_pbp rows through the SAME code that wrote every 2026-27
row the in-play search graded: nba_pbp.summary_records (ESPN's JSON in the
release's column names), nba_pbp.espn_game_meta, nba_pbp.slim_plays (play
order, our running score, our home/away). The scoreboard says which games are
in progress. Both hosts are site.api.espn.com, which answered 200 to the
worker's NBA scoreboard and summary calls on 2026-11-02/03 (api_call_log).

THE ODDS API (paid). One bulk call for every NBA game at once:
    GET /v4/sports/basketball_nba/odds?regions=us&markets=h2h,spreads
        &bookmakers=<config.BEST_LINE_BOOKMAKERS + pinnacle>&oddsFormat=american
Pinnacle is in the call because the freshness rule pairs every deciding quote
with Pinnacle's quote in the same fetch. Nine named books stay inside the
feed's one-region group of ten, so the bill is markets x 1 = 2 credits (the
same NBA call with totals bills 3 in api_call_log, 2026-11-02..04). The cost
is MEASURED, not assumed: every response's x-requests-last is added to the
process total and logged, and the first call's figure is logged on its own
line. Rows are parsed by odds_ingestor._process_events, the parser that wrote
the 2026-27 rows the search graded, with snapshot_type 'in_play'.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

log = logging.getLogger(__name__)

SPORT_KEY = "basketball_nba"
ODDS_URL = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds"
MARKETS = ("h2h", "spreads")
SHARP = "pinnacle"


def _install_api_call_log() -> None:
    """Every Odds API call is logged to api_call_log (monitoring/probe.py)."""
    try:
        from monitoring.probe import install
        install()
    except Exception:  # noqa: BLE001
        pass


_install_api_call_log()


def feed_books() -> list[str]:
    """The deciding books plus Pinnacle, at most ten (one region group)."""
    import config
    books = list(dict.fromkeys([*config.BEST_LINE_BOOKMAKERS, SHARP]))
    if len(books) > 10:
        raise ValueError(f"{len(books)} books would bill a second region: {books}")
    return books


# ─── ESPN ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EspnGame:
    event_id: int
    home: str | None              # our team codes (nba_espn_box.nba_team)
    away: str | None
    state: str                    # 'pre' | 'in' | 'post'
    status: str                   # STATUS_IN_PROGRESS, STATUS_HALFTIME, ...
    period: int | None
    clock: str | None
    commence: str | None
    season_type: int | None


def parse_scoreboard(data: dict) -> list[EspnGame]:
    """Every event on an ESPN NBA scoreboard, any state."""
    from data.ingestors.nba_espn_box import nba_team
    out = []
    for ev in (data or {}).get("events") or []:
        comp = (ev.get("competitions") or [{}])[0]
        st = ev.get("status") or {}
        t = st.get("type") or {}
        teams = {}
        for c in comp.get("competitors") or []:
            tm = c.get("team") or {}
            teams[c.get("homeAway")] = nba_team(tm.get("abbreviation"), tm.get("displayName"))
        try:
            eid = int(ev.get("id"))
        except (TypeError, ValueError):
            continue
        per = st.get("period")
        out.append(EspnGame(event_id=eid, home=teams.get("home"), away=teams.get("away"),
                            state=str(t.get("state") or ""), status=str(t.get("name") or ""),
                            period=int(per) if isinstance(per, (int, float)) else None,
                            clock=st.get("displayClock"), commence=ev.get("date"),
                            season_type=(ev.get("season") or {}).get("type")))
    return out


class Espn:
    """Free ESPN reads with the repo's browser headers; never raises past a
    caller -- a failed read is None and the caller decides."""

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
        from data.ingestors.nba_espn_box import ESPN_NBA_SCOREBOARD_URL
        d = self._json(ESPN_NBA_SCOREBOARD_URL, {"dates": game_date.replace("-", "")})
        return None if d is None else parse_scoreboard(d)

    def summary(self, event_id: int) -> dict | None:
        from data.ingestors.nba_espn_box import ESPN_NBA_SUMMARY_URL
        return self._json(ESPN_NBA_SUMMARY_URL, {"event": str(event_id)})


def summary_final(data: dict) -> bool:
    comp = (((data or {}).get("header") or {}).get("competitions") or [{}])[0]
    return bool((((comp.get("status") or {}).get("type")) or {}).get("completed"))


def plays_from_summary(data: dict, event_id: int, game_id: str, season: int, game_date: str,
                       home: str, away: str) -> tuple[list[dict], bool] | None:
    """(nba_pbp rows, swapped) for one game in progress, or None when the
    summary has no plays or its teams are not this game's two teams.

    `swapped`: ESPN lists our away team as home (a neutral court); slim_plays
    then flips the sides so 'H' is always our `games` row's home team."""
    from data.ingestors import nba_pbp as P
    recs, _box = P.summary_records(data, int(event_id), int(season), 2, game_date)
    if not recs:
        return None
    meta = P.espn_game_meta(int(event_id), recs)
    if meta is None:
        return None
    if (meta["home"], meta["away"]) == (home, away):
        swapped = False
    elif (meta["home"], meta["away"]) == (away, home):
        swapped = True
    else:
        log.warning("%s: ESPN event %s is %s @ %s, not %s @ %s - refused",
                    game_id, event_id, meta["away"], meta["home"], away, home)
        return None
    rows = P.slim_plays(recs, espn_game_id=int(event_id), game_id=game_id, season=int(season),
                        season_type=2, swapped=swapped)
    return rows, swapped


def starters_from_summary(data: dict, espn_home: str | None, swapped: bool) -> pd.DataFrame:
    """(espn_id, side H/A, starter) for every athlete ESPN flags a starter in
    the live box, whatever his minutes so far (nba_espn_box.parse_nba_box
    leaves out a player with no minutes yet, which every starter is at tip).
    `espn_home`: our code for the team ESPN lists at home."""
    from data.ingestors.nba_espn_box import _team_blocks
    rows = []
    for team, _idx, block in _team_blocks(data):
        is_home = team == espn_home
        side = ("A" if is_home else "H") if swapped else ("H" if is_home else "A")
        for ath in block.get("athletes") or []:
            if not ath.get("starter"):
                continue
            a = ath.get("athlete") or {}
            try:
                aid = int(a.get("id"))
            except (TypeError, ValueError):
                continue
            rows.append({"espn_id": aid, "side": side, "starter": True})
    return pd.DataFrame(rows, columns=["espn_id", "side", "starter"])


# ─── the Odds API ──────────────────────────────────────────────────────────────

def _api_key() -> str:
    return os.environ.get("ODDS_API_KEY") or os.environ.get("THE_ODDS_API_KEY", "")


@dataclass
class Fetch:
    events: list
    fetched_at: datetime          # when the response arrived: the fetch's served time
    credits: int | None           # x-requests-last
    remaining: int | None         # x-requests-remaining


class LiveOddsFeed:
    """One bulk call per decision instant. Never returns a cached payload."""

    def __init__(self, call_cap: int, credit_cap: int, session=None):
        self.call_cap, self.credit_cap = int(call_cap), int(credit_cap)
        self.calls = 0
        self.credits_used = 0
        self.first_credits: int | None = None
        self._session = session

    def fetch(self) -> Fetch | None:
        if self.calls >= self.call_cap:
            log.error("NBA live odds: call cap %d reached - not fetching", self.call_cap)
            return None
        if self.credits_used >= self.credit_cap:
            log.error("NBA live odds: credit cap %d reached (%d used) - not fetching",
                      self.credit_cap, self.credits_used)
            return None
        key = _api_key()
        if not key:
            log.error("NBA live odds: no ODDS_API_KEY set")
            return None
        import requests
        s = self._session or requests
        self.calls += 1
        try:
            r = s.get(ODDS_URL, params={"apiKey": key, "regions": "us", "markets": ",".join(MARKETS),
                                        "bookmakers": ",".join(feed_books()), "oddsFormat": "american",
                                        "includeLinks": "true", "includeSids": "true"},
                      timeout=30)
            fetched_at = datetime.now(timezone.utc)
            try:
                from data.ingestors.odds_quota import record_quota_headers
                record_quota_headers(r)
            except Exception:  # noqa: BLE001
                pass
            last = r.headers.get("x-requests-last")
            rem = r.headers.get("x-requests-remaining")
            credits = int(float(last)) if last is not None else None
            remaining = int(float(rem)) if rem is not None else None
            if credits is not None:
                self.credits_used += credits
                if self.first_credits is None:
                    self.first_credits = credits
                    log.info("NBA live odds: FIRST CALL COST x-requests-last=%s (markets %s, %d books); "
                             "x-requests-remaining=%s", credits, ",".join(MARKETS), len(feed_books()), remaining)
            r.raise_for_status()
            payload = r.json()
            log.info("NBA live odds: %d events, x-requests-last=%s, remaining=%s (process %d credits, %d calls)",
                     len(payload) if isinstance(payload, list) else -1, last, rem, self.credits_used, self.calls)
            if not isinstance(payload, list):
                return None
            return Fetch(payload, fetched_at, credits, remaining)
        except Exception as exc:  # noqa: BLE001
            log.warning("NBA live odds fetch failed: %s", exc)
            return None


def rows_from_events(events: list, fetched_at: datetime) -> list[dict]:
    """`odds` rows (snapshot_type in_play, snapshot_at = each book's market
    last_update) through odds_ingestor._process_events, the parser that wrote
    the rows the 2026-27 search graded. game_id is built from the feed's
    teams and the tip's Eastern date; the caller keeps only its own games."""
    from data.ingestors.odds_ingestor import _process_events
    _games, rows = _process_events(events, "NBA", "in_play", fetched_at.isoformat())
    return [r for r in rows if r.get("market") in MARKETS]
