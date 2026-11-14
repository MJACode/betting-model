"""The EuroLeague halftime loop's two feeds (models/euroleague_live_loop.py).

EUROLEAGUE'S OWN LIVE API (free, no key). Three answers per game, asked one
at a time (Cloudflare refused four at once, HTTP 429 error 1015, 2026-11-13):

    live.euroleague.net/api/PlayByPlay?gamecode=N&seasoncode=E2026
        quarter arrays (FirstQuarter, SecondQuarter, ThirdQuarter, ForthQuarter,
        ExtraTime) of plays with the game clock only. Read off a played game
        (E2026 game 110, 2026-11-13): a quarter ends with an 'EP' (End Period)
        play; the next quarter's substitutions ('IN'/'OUT' at 10:00) are logged
        DURING the break, numbered before the quarter's 'BP' (Begin Period),
        which is logged at the restart. So "the half is over" is an 'EP' in
        SecondQuarter, and "the third quarter has begun" is a 'BP' in
        ThirdQuarter (or a third-quarter shot), never "ThirdQuarter is not empty".
    live.euroleague.net/api/Points?gamecode=N&seasoncode=E2026
        every shot made or missed (free throws: made only) with its UTC
        wall-clock stamp, the minute and clock, and the running score; A is
        the home club. The half's last shot (MINUTE <= 20) and the game's first
        shot place a quote's stamp, as they did in the grade.
    live.euroleague.net/api/Header?gamecode=N&seasoncode=E2026
        the clubs (CodeTeamA is the home club) and the score after each quarter
        (ScoreQuarter2A/B: cumulative, 33-32 after two of game 110, which
        ended 74-76): a second witness to the half-time score.

THE ODDS API (paid). One bulk call for every EuroLeague game at once:
    GET /v4/sports/basketball_euroleague/odds?regions=us&markets=h2h,spreads,totals
        &bookmakers=<the ten books the history was bought at>
The ten (config.EUROLEAGUE_HISTORY_BOOKMAKERS) are the books the grade's
median line and count of other books were taken over, and ten named books
bill as one region: 3 credits a call for three markets. That number is
derived, not measured live: the history billed 30 credits a snapshot for the
same ten books and three markets (docs/sports/euroleague.md, "The purchase"),
and the historical endpoint bills ten times the live one. The loop logs the
first call's x-requests-last. The model reads the spreads; the moneylines and
totals of the same read are stored beside them for the next re-test. Rows are
parsed by odds_ingestor._process_events onto EuroLeague's games through
euroleague_teams.make_resolver, and stored in_play under LIVE_SOURCE only for
games already under way (a game not yet started is pre-game, never in_play).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from data.ingestors.nba_live_feed import Fetch, LiveOddsFeed  # noqa: F401

log = logging.getLogger(__name__)

SPORT = "EUROLEAGUE"
SPORT_KEY = "basketball_euroleague"
ODDS_URL = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds"
MARKETS = ("h2h", "spreads", "totals")
LIVE_SOURCE = "euroleague_live_loop"
API = "https://live.euroleague.net/api/{endpoint}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Signalbase)", "Accept": "application/json"}
# Between any two calls to EuroLeague's API, from this process.
PAUSE_S = 1.5
BACKOFF_S = 30.0


def feed_books() -> list[str]:
    """The ten books the EuroLeague history was bought at."""
    import config
    return list(config.EUROLEAGUE_HISTORY_BOOKMAKERS)


def odds_feed(call_cap: int, credit_cap: int, session=None) -> LiveOddsFeed:
    return LiveOddsFeed(call_cap, credit_cap, session=session, url=ODDS_URL, markets=MARKETS,
                        books=feed_books, label=SPORT)


class EuroleagueApi:
    """Free reads of EuroLeague's live API, one call at a time, PAUSE_S apart.
    A failed read is None; an HTTP 429 (Cloudflare's rate limit) backs the
    whole client off BACKOFF_S before the next call. Injected sleep/clock so a
    test drives it without waiting."""

    def __init__(self, session=None, sleep=time.sleep, monotonic=time.monotonic):
        self.session = session
        self.sleep, self.monotonic = sleep, monotonic
        self.calls = 0
        self.refused = 0
        self._next_at = 0.0

    def _get(self, endpoint: str, season_code: str, game_code: int) -> dict | None:
        wait = self._next_at - self.monotonic()
        if wait > 0:
            self.sleep(wait)
        if self.session is None:
            import requests
            self.session = requests.Session()
        self.calls += 1
        try:
            r = self.session.get(API.format(endpoint=endpoint), params={"gamecode": int(game_code),
                                                                        "seasoncode": season_code},
                                 headers=HEADERS, timeout=20)
        except Exception as exc:                      # noqa: BLE001
            log.warning("EuroLeague %s %s/%s failed: %s", endpoint, season_code, game_code, exc)
            self._next_at = self.monotonic() + PAUSE_S
            return None
        if r.status_code == 429:
            self.refused += 1
            log.warning("EuroLeague API rate-limited (HTTP 429) on %s; backing off %.0f s", endpoint, BACKOFF_S)
            self._next_at = self.monotonic() + BACKOFF_S
            return None
        self._next_at = self.monotonic() + PAUSE_S
        if r.status_code != 200:
            log.warning("EuroLeague %s %s/%s: HTTP %s", endpoint, season_code, game_code, r.status_code)
            return None
        try:
            return r.json() if (r.text or "").strip() else {}
        except ValueError:
            return None

    def game(self, season_code: str, game_code: int) -> dict | None:
        """{'pbp', 'points', 'header'} for one game, or None when any of the three failed."""
        out = {}
        for key, ep in (("pbp", "PlayByPlay"), ("points", "Points"), ("header", "Header")):
            got = self._get(ep, season_code, game_code)
            if got is None:
                return None
            out[key] = got
        return out


# ── the half, read off the three answers (pure) ─────────────────────────────

def _utc(v) -> pd.Timestamp | None:
    s = str(v or "").strip()
    if len(s) != 14 or not s.isdigit():
        return None
    return pd.Timestamp(datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc))


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _code(v) -> str:
    return str(v or "").strip()


@dataclass
class HalfRead:
    """What EuroLeague's API says about one game's half at one moment.
    status: 'first_half'   the second quarter has not ended (no 'EP' in it)
            'break'        it has, and the third has not begun
            'second_half'  the third quarter has begun ('BP' in it, or a shot of minute 21+)
            'unreadable'   the answers do not carry a half (no shots, clubs differ ...)
    `problem` says why a 'break' cannot be used (the witnesses disagree), else None."""
    status: str
    first_shot: pd.Timestamp | None = None
    last_q2_shot: pd.Timestamp | None = None
    q3_at: pd.Timestamp | None = None
    ht_home: int | None = None
    ht_away: int | None = None
    pbp_score: tuple | None = None
    header_score: tuple | None = None
    problem: str | None = None
    shots: int = 0


def _plays(pbp: dict, quarter: str) -> list:
    return [p for p in ((pbp or {}).get(quarter) or []) if isinstance(p, dict)]


def read_half(answers: dict, home: str, away: str) -> HalfRead:
    """The half of one game from its PlayByPlay, Points and Header answers.
    `home`/`away` are OUR club codes; EuroLeague's A must be our home club
    (it is the local club), else the read is unusable (never flipped here)."""
    pbp, pts, hdr = answers.get("pbp") or {}, answers.get("points") or {}, answers.get("header") or {}
    a, b = _code(hdr.get("CodeTeamA") or pbp.get("CodeTeamA")), _code(hdr.get("CodeTeamB") or pbp.get("CodeTeamB"))
    if (a, b) != (home, away):
        return HalfRead("unreadable", problem=f"EuroLeague lists {a or '?'} v {b or '?'}, the game is {home} v {away}")
    rows = []
    for r in (pts.get("Rows") or []):
        t, m = _utc(r.get("UTC")), _int(r.get("MINUTE"))
        if t is None or m is None:
            continue
        rows.append((t, _int(r.get("NUM_ANOT")) or 0, m, _int(r.get("POINTS_A")), _int(r.get("POINTS_B"))))
    q2 = [p for p in _plays(pbp, "SecondQuarter")]
    q3 = [p for p in _plays(pbp, "ThirdQuarter")]
    half_over = any(str(p.get("PLAYTYPE") or "").strip() == "EP" for p in q2)
    begun_pbp = any(str(p.get("PLAYTYPE") or "").strip() == "BP" for p in q3)
    q3_shots = [t for t, _n, m, _h, _a in rows if m >= 21]
    out = HalfRead("first_half", shots=len(rows))
    if not rows:
        out.status = "unreadable" if half_over else "first_half"
        out.problem = "no shot with a time on EuroLeague's shot chart" if half_over else None
        return out
    out.first_shot = min(t for t, *_ in rows)
    h1 = [x for x in rows if x[2] <= 20]
    if h1:
        out.last_q2_shot = max(t for t, *_ in h1)
        hs = [h for *_x, h, _a in h1 if h is not None]
        as_ = [a_ for *_x, a_ in h1 if a_ is not None]
        out.ht_home, out.ht_away = (max(hs) if hs else 0), (max(as_) if as_ else 0)
    if q3_shots:
        out.q3_at = min(q3_shots)
    if q3_shots or begun_pbp:
        out.status = "second_half"
        return out
    if not half_over:
        return out
    out.status = "break"
    scored = [(p.get("POINTS_A"), p.get("POINTS_B")) for q in ("FirstQuarter", "SecondQuarter")
              for p in _plays(pbp, q) if p.get("POINTS_A") is not None and p.get("POINTS_B") is not None]
    out.pbp_score = (_int(scored[-1][0]), _int(scored[-1][1])) if scored else (0, 0)
    ha, hb = _int(hdr.get("ScoreQuarter2A")), _int(hdr.get("ScoreQuarter2B"))
    out.header_score = None if ha is None or hb is None else (ha, hb)
    shot = (out.ht_home, out.ht_away)
    if out.last_q2_shot is None:
        out.problem = "no shot of the first two quarters on the shot chart"
    elif out.pbp_score != shot:
        out.problem = f"the play-by-play says {out.pbp_score[0]}-{out.pbp_score[1]} at the half, the shot chart {shot[0]}-{shot[1]}"
    elif out.header_score is not None and out.header_score != shot:
        out.problem = (f"the header says {out.header_score[0]}-{out.header_score[1]} after two quarters, "
                       f"the shot chart {shot[0]}-{shot[1]}")
    return out


def rows_from_events(events: list, fetched_at, resolver, started: set) -> list[dict]:
    """`odds` rows (snapshot_type in_play, snapshot_at = each book's market
    last_update) for OUR EuroLeague games already under way (`started`: game
    ids), through odds_ingestor._process_events and euroleague_teams'
    resolver (`resolver`; None resolves nothing). A game not yet started is
    left out: its prices are pre-game and the hourly pass stores those."""
    if resolver is None:
        return []
    from data.ingestors.odds_ingestor import _process_events
    _games, rows = _process_events(events, SPORT, "in_play", fetched_at.isoformat(), resolve_game_id=resolver)
    rows = [r for r in rows if r.get("market") in MARKETS and r.get("game_id") in started]
    for r in rows:
        r["source"] = LIVE_SOURCE
    return rows
