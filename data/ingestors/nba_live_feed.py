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
# The loop's own in-play rows in `odds` carry this source, so a restarted loop
# can tell them from the refresh pass's (also in_play for NBA after the tip,
# also from the bulk endpoint) and seed its earlier-fetch dedupe from them.
LIVE_SOURCE = "nba_live_loop"


def _install_api_call_log() -> None:
    """Every Odds API call is logged to api_call_log (monitoring/probe.py)."""
    try:
        from monitoring.probe import install
        install()
    except Exception:  # noqa: BLE001
        pass


_install_api_call_log()


def feed_books() -> list[str]:
    """The deciding books plus Pinnacle, at most ten (one region group).

    Plus the state-limited books (betparx, mike 2026-11-06): they left the
    deciding list, not the data, and this pull is the only in-play NBA source.
    A book stays here only while it is still fetched pre-game."""
    import config
    kept = [b for b in sorted(config.STATE_LIMITED_BOOKMAKERS)
            if b in config.LINE_SHOP_BOOKMAKERS]
    books = list(dict.fromkeys([*config.BEST_LINE_BOOKMAKERS, *kept, SHARP]))
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


def plays_logged_by(data: dict | None, at: datetime) -> set[str]:
    """Ids of the plays in one ESPN summary whose wallclock is at or before
    `at`."""
    out = set()
    for p in (data or {}).get("plays") or []:
        w = p.get("wallclock")
        if not w:
            continue
        try:
            t = datetime.fromisoformat(str(w).replace("Z", "+00:00"))
        except ValueError:
            continue
        if t <= at:
            out.add(str(p.get("id")))
    return out


def late_plays(first: dict | None, second: dict | None, served_at: datetime) -> list[str]:
    """Plays logged at or before the served time that the SECOND read of the
    summary carries and the first did not: ESPN published them late. When
    there is one, the first read's picture of the served time was incomplete,
    so it cannot be trusted that the second is complete either; the loop does
    not decide on that fetch (fail closed)."""
    return sorted(plays_logged_by(second, served_at) - plays_logged_by(first, served_at))


def header_score(data: dict | None) -> tuple[int, int] | None:
    """(home, away) as ESPN's summary header states them, ESPN's own sides."""
    comp = (((data or {}).get("header") or {}).get("competitions") or [{}])[0]
    sc = {}
    for c in comp.get("competitors") or []:
        try:
            sc[c.get("homeAway")] = int(float(c.get("score")))
        except (TypeError, ValueError):
            return None
    if "home" not in sc or "away" not in sc:
        return None
    return sc["home"], sc["away"]


def newest_play_score(data: dict | None) -> tuple[int, int] | None:
    """(home, away) ESPN's play list carries on its newest play (ESPN's own
    running score and sides), in play order: the last play of the highest
    period by clock, then sequence."""
    best, key = None, None
    for p in (data or {}).get("plays") or []:
        try:
            per = int((p.get("period") or {}).get("number") or 0)
            seq = int(p.get("sequenceNumber") or 0)
            hs, as_ = int(p.get("homeScore")), int(p.get("awayScore"))
        except (TypeError, ValueError):
            continue
        k = (per, seq)
        if key is None or k > key:
            key, best = k, (hs, as_)
    return best


def score_mismatch(data: dict | None) -> str | None:
    """Why ESPN's play list is behind its own header score, or None when they
    agree. Measured on 2026-11-04: in 2 of 6 reads the header was ahead (ATL @
    WSH 8-9 at 9:06 while the plays stopped at 9:24, 8-6), a play list that
    has stopped while the game has not."""
    h, p = header_score(data), newest_play_score(data)
    if h is None or p is None:
        return None
    if h != p:
        return f"ESPN's header score is {h[0]}-{h[1]} but its newest play is {p[0]}-{p[1]} (home-away)"
    return None


def clock_running(first: dict | None, second: dict | None) -> bool:
    """True when ESPN's header shows the game in progress in both reads and
    its clock moved between them (period or clock seconds changed)."""
    def st(d):
        comp = (((d or {}).get("header") or {}).get("competitions") or [{}])[0]
        s_ = comp.get("status") or {}
        t = (s_.get("type") or {})
        try:
            clock = float(s_.get("clock")) if s_.get("clock") is not None else None
        except (TypeError, ValueError):
            clock = None
        return t.get("state"), s_.get("period"), clock
    a, b = st(first), st(second)
    if a[0] != "in" or b[0] != "in" or a[2] is None or b[2] is None:
        return False
    return (a[1], a[2]) != (b[1], b[2])


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


# The account balance below which the loop stops fetching: 1,000 credits, the
# line just above zero (the September 2026 outage hit zero and stopped every
# feed). There is no share-of-plan floor (mike, 2026-11-07: "I dont care about
# the odds api balance"): the 15%-of-plan rule it had stopped the model after
# its first fetch of each night once the balance fell under 750,000 of
# 5,000,000, while the loop spends 12-28 credits a night.
QUOTA_FLOOR_CREDITS = 1000


def below_floor(remaining: int | None, used: int | None = None) -> bool:
    """True only when the balance is under QUOTA_FLOOR_CREDITS. `used` is kept
    for the callers' signature and no longer read."""
    if remaining is None:
        return False
    return remaining < QUOTA_FLOOR_CREDITS


class LiveOddsFeed:
    """One bulk call per decision instant. Never returns a cached payload.

    The URL, markets, books and log label default to the NBA loop's; the
    NCAAB in-play loop passes its own (data/ingestors/ncaab_live_feed.py), so
    both loops share one fetch, one credit accounting and one quota floor."""

    def __init__(self, call_cap: int, credit_cap: int, session=None, *, url: str | None = None,
                 markets: tuple | None = None, books=None, label: str = "NBA"):
        self.url = url or ODDS_URL
        self.markets = tuple(markets or MARKETS)
        self._books = books
        self.label = label
        self.call_cap, self.credit_cap = int(call_cap), int(credit_cap)
        self.calls = 0
        self.credits_used = 0
        self.first_credits: int | None = None
        self.remaining: int | None = None
        self.used: int | None = None
        self._session = session

    def books(self) -> list[str]:
        return list(self._books() if callable(self._books) else (self._books or feed_books()))

    def fetch(self) -> Fetch | None:
        lab = self.label
        if below_floor(self.remaining, self.used):
            log.error("%s live odds: %s credits left of %s - under the quota floor, not fetching",
                      lab, self.remaining, (self.used or 0) + (self.remaining or 0))
            return None
        if self.calls >= self.call_cap:
            log.error("%s live odds: call cap %d reached - not fetching", lab, self.call_cap)
            return None
        if self.credits_used >= self.credit_cap:
            log.error("%s live odds: credit cap %d reached (%d used) - not fetching",
                      lab, self.credit_cap, self.credits_used)
            return None
        key = _api_key()
        if not key:
            log.error("%s live odds: no ODDS_API_KEY set", lab)
            return None
        import requests
        s = self._session or requests
        self.calls += 1
        try:
            r = s.get(self.url, params={"apiKey": key, "regions": "us", "markets": ",".join(self.markets),
                                        "bookmakers": ",".join(self.books()), "oddsFormat": "american",
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
            used_h = r.headers.get("x-requests-used")
            credits = int(float(last)) if last is not None else None
            remaining = int(float(rem)) if rem is not None else None
            self.remaining = remaining
            self.used = int(float(used_h)) if used_h is not None else self.used
            if credits is not None:
                self.credits_used += credits
                if self.first_credits is None:
                    self.first_credits = credits
                    log.info("%s live odds: FIRST CALL COST x-requests-last=%s (markets %s, %d books); "
                             "x-requests-remaining=%s", lab, credits, ",".join(self.markets),
                             len(self.books()), remaining)
            r.raise_for_status()
            payload = r.json()
            log.info("%s live odds: %d events, x-requests-last=%s, remaining=%s (process %d credits, %d calls)",
                     lab, len(payload) if isinstance(payload, list) else -1, last, rem, self.credits_used,
                     self.calls)
            if not isinstance(payload, list):
                return None
            return Fetch(payload, fetched_at, credits, remaining)
        except Exception as exc:  # noqa: BLE001
            log.warning("%s live odds fetch failed: %s", lab, exc)
            return None


def rows_from_events(events: list, fetched_at: datetime) -> list[dict]:
    """`odds` rows (snapshot_type in_play, snapshot_at = each book's market
    last_update) through odds_ingestor._process_events, the parser that wrote
    the rows the 2026-27 search graded. game_id is built from the feed's
    teams and the tip's Eastern date; the caller keeps only its own games."""
    from data.ingestors.odds_ingestor import _process_events
    _games, rows = _process_events(events, "NBA", "in_play", fetched_at.isoformat())
    rows = [r for r in rows if r.get("market") in MARKETS]
    for r in rows:
        r["source"] = LIVE_SOURCE
    return rows
