"""
NFL live game state from ESPN sports.core, built to the model's TRAINING
definitions -- not to what a scoreboard shows.

WHY CORE. site.api.espn.com answers 403 to the Railway worker (the platform's
own health probe records it every day since early August); sports.core
answers. nfl/live_model/feeds/espn_core.py is the precedent; this is a port of
its shape, not an import (nfl/ runs as its own package root).

WHAT THE MODEL NEEDS, AND WHERE EACH FIELD COMES FROM.

    score  the LAST COMPLETED PLAY's homeScore / awayScore (post-play)
    secs   that play's clock.value at the SNAP, as game seconds remaining:
           (4 - period) * 900 + clock.value
    ball   the team with the ball AFTER that play: situation.team (the live
           core shape; see possession_team_id), cross-checked against the
           play's end.team
    band   the pregame spread (gameday.py reads it from the platform)

VERIFIED, NOT ASSUMED. Against 17 finished 2026 games (weeks 4-5, every game in
the local nflverse 2026 play-by-play; the week-5 one is TB @ DAL, core event
401872980), matching each core play document to the same nflverse play by its
text:
  * play.clock.value == nflverse quarter_seconds_remaining (the SNAP clock) on
    2,190 of 2,191 non-scoring plays (the one miss is a punt, 2 s off);
  * play.homeScore / awayScore == nflverse total_home_score / total_away_score
    (POST-play) on 2,191 of 2,191;
  * play.end.team == the backtest's post_ball_team on 2,188 of 2,191; the three
    misses are a muffed punt, a punt fumble and a kickoff penalty, where ESPN
    is right and the training rule is not;
  * SCORING plays break both rules: their clock is the END of the play (0 of
    65 equal the snap, all 65 lower) and their score already includes the
    PAT, which ESPN folds into the touchdown play (there is no separate PAT
    document). So a scoring play is never the state we evaluate.
  * administrative rows -- Timeout (type 21), Official Timeout (74),
    Two-minute warning (75), End Period (2), End of Half (65), End of Game
    (66), Coin Toss (70) -- carry the clock at the stoppage, not a snap. The
    training data has no such rows (nflverse timeouts have no posteam and
    there is no two-minute-warning row), so they are skipped when choosing
    "the last play".

THE GATE. A state is evaluable only when the game is in progress in the 4th
quarter, the last real play was not a scoring play or a conversion, the
situation shows a scrimmage down (1-4) and a possession team we can identify,
and that team agrees with the last play's end.team. Everything else is a
transitional state -- the touchdown-to-kickoff window above all, where the
training rule says the receiving team has the ball and ESPN may not -- and is
skipped, never guessed.

POSSESSION: TWO BUGS IN THE OLD CORE PARSER, BOTH FIXED HERE.
  1. espn_core.py matched `home_id in poss_ref`, a SUBSTRING test against the
     whole URL. Team id "1" is inside ".../teams/12", and the URL also carries
     the SEASON (".../seasons/2026/teams/27"), so a home team whose id is a
     substring of "2026" -- Dallas is 6 -- read as having the ball on every
     play of every game (tests/test_nfl_live_leader_state.py reproduces it on
     TB @ DAL). Here the id is parsed out of '/teams/(\\d+)' and compared whole.
  2. it read situation.possession, which the live core document does not
     carry: measured on a live core football payload (college-football event
     401871067, 2026-10-13), the possessing team is situation.team, and in 2
     of the first 5 in-progress reads (around the opening kickoff) neither key
     was present -- which is exactly when this module refuses.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

CORE_ROOT = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
ADMIN_TYPE_IDS = frozenset({"2", "21", "65", "66", "70", "74", "75"})
ADMIN_TYPE_TEXTS = frozenset({"end period", "timeout", "official timeout", "two-minute warning",
                              "end of half", "end of game", "coin toss", "end of regulation"})
CONVERSION_HINTS = ("extra point", "two-point", "two point", "2pt", "2-pt", "conversion", "pat")
SCRIMMAGE_DOWNS = (1, 2, 3, 4)
END_TYPE_IDS = frozenset({"2", "66"})    # End Period, End of Game
_TEAM_IN_REF = re.compile(r"/teams/(\d+)")


# ─── small parsers ────────────────────────────────────────────────────────────

def https(url: str | None) -> str | None:
    if isinstance(url, str) and url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def ref_of(x) -> str | None:
    if isinstance(x, dict):
        return x.get("$ref")
    return x if isinstance(x, str) else None


def team_id(x) -> str | None:
    """The ESPN team id in a team reference: {'$ref': '.../teams/12?...'}, the
    URL itself, or a bare id. Parsed WHOLE -- '/teams/12' is 12, never 1."""
    if isinstance(x, dict) and "$ref" not in x and x.get("id") is not None:
        return str(x["id"])
    s = ref_of(x)
    if s is None:
        return str(x) if isinstance(x, int) else None
    m = _TEAM_IN_REF.search(s)
    if m:
        return m.group(1)
    return s if s.isdigit() else None


def _num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def _int(x) -> int | None:
    v = _num(x)
    return None if v is None else int(v)


def play_type_id(play: dict) -> str:
    return str(((play or {}).get("type") or {}).get("id") or "")


def play_type_text(play: dict) -> str:
    return str(((play or {}).get("type") or {}).get("text") or "").strip().lower()


def is_admin_play(play: dict) -> bool:
    return play_type_id(play) in ADMIN_TYPE_IDS or play_type_text(play) in ADMIN_TYPE_TEXTS


def is_conversion_play(play: dict) -> bool:
    t = play_type_text(play)
    return any(h in t for h in CONVERSION_HINTS)


def is_scoring_play(play: dict) -> bool:
    return bool((play or {}).get("scoringPlay")) or (_num((play or {}).get("scoreValue")) or 0) > 0


def play_seq(play: dict) -> int:
    return _int((play or {}).get("sequenceNumber")) or -1


def possession_team_id(situation: dict | None) -> str | None:
    """The team with the ball in a core situation document.

    MEASURED ON A LIVE CORE PAYLOAD (college-football event 401871067,
    2026-10-13 23:03Z, the same football schema): the live situation carries
    the possessing team as `team` ({'$ref': '.../teams/48'}) beside
    `possessionText` ("DEL 41"), and has NO `possession` key at all -- so the
    old core parser, which read situation.possession, could never have found a
    possession on this host. `possession` is still read as a fallback for the
    site.api shape (a bare team id)."""
    s = situation or {}
    for key in ("team", "possession"):
        tid = team_id(s.get(key))
        if tid:
            return tid
    return None


def game_seconds(period, clock) -> float | None:
    """Game seconds remaining in regulation: (4 - period) * 900 + clock."""
    p, c = _int(period), _num(clock)
    if p is None or c is None or p < 1 or p > 4:
        return None
    return (4 - p) * 900.0 + c


def last_real_play(plays: list[dict]) -> dict | None:
    """The completed play with the highest sequence number that is not an
    administrative row. Sorted by sequence because the core plays LIST is not
    in sequence order: a scoring play is re-listed after the play that follows
    it once ESPN folds its PAT in (6 of 184 rows out of order on event
    401872980)."""
    real = [p for p in plays or [] if isinstance(p, dict) and not is_admin_play(p)]
    return max(real, key=play_seq) if real else None


# ─── the state ────────────────────────────────────────────────────────────────

@dataclass
class EventMeta:
    event_id: str
    date: str | None                  # the event's ISO kickoff (UTC)
    home_id: str
    away_id: str
    home_abbr: str | None             # ESPN abbreviations (teams.abbrev maps them)
    away_abbr: str | None
    status_ref: str | None
    situation_ref: str | None
    plays_ref: str | None
    season_type: int | None = None    # 1 pre, 2 regular, 3 post


@dataclass
class LiveState:
    event_id: str
    status_state: str | None          # 'pre' | 'in' | 'post'
    status_name: str | None
    period: int | None                # status.period
    running_clock: float | None       # status.clock (the running clock, NOT used for secs)
    final: bool = False
    home_score: float | None = None   # after the last real play
    away_score: float | None = None
    secs: float | None = None         # game seconds at the last real play's snap
    play_period: int | None = None
    possession: str | None = None     # 'home' | 'away' | None, after the last real play
    down: int | None = None
    last_play_id: str | None = None
    last_play_seq: int | None = None
    last_play_type: str | None = None
    evaluable: bool = False
    reason: str = ""
    notes: list = field(default_factory=list)

    @property
    def lead(self) -> int | None:
        if self.home_score is None or self.away_score is None:
            return None
        return int(abs(self.home_score - self.away_score))

    @property
    def score(self) -> tuple | None:
        if self.home_score is None or self.away_score is None:
            return None
        return (self.home_score, self.away_score)

    @property
    def score_diff(self) -> float | None:
        if self.home_score is None or self.away_score is None:
            return None
        return self.home_score - self.away_score


def in_window(st: LiveState, secs_max: float = 600, lead_min: int = 4,
              lead_max: int = 16) -> bool:
    """The model's window on the TRAINING clock: 4th quarter in progress, the
    last real play's snap at <= 10:00, a 4-16 point lead."""
    return (st.status_state == "in" and st.period == 4 and st.secs is not None
            and st.secs <= secs_max and st.lead is not None
            and lead_min <= st.lead <= lead_max)


def state_from_docs(meta: EventMeta, status: dict | None, situation: dict | None,
                    plays: list[dict] | None) -> LiveState:
    """One LiveState from the core documents. Pure. `plays` is the recent tail
    (or just situation.lastPlay when that is a real play)."""
    status = status or {}
    stype = status.get("type") or {}
    st = LiveState(event_id=meta.event_id, status_state=stype.get("state"),
                   status_name=stype.get("name"), period=_int(status.get("period")),
                   running_clock=_num(status.get("clock")))
    st.final = st.status_state == "post" or bool(stype.get("completed"))
    if st.final:
        st.reason = "game over"
        return st
    if st.status_state != "in":
        st.reason = f"not in progress ({st.status_state})"
        return st
    if st.period is None:
        st.reason = "period unknown"
        return st
    if st.period > 4:
        st.reason = "overtime"
        return st

    play = last_real_play(plays or [])
    if play is not None:
        st.last_play_id = str(play.get("id") or "")
        st.last_play_seq = play_seq(play)
        st.last_play_type = play_type_text(play)
        st.play_period = _int((play.get("period") or {}).get("number"))
        st.home_score = _num(play.get("homeScore"))
        st.away_score = _num(play.get("awayScore"))
        st.secs = game_seconds(st.play_period, (play.get("clock") or {}).get("value"))
    situation = situation or {}
    st.down = _int(situation.get("down"))
    pid = possession_team_id(situation)
    st.possession = ("home" if pid == meta.home_id else
                     "away" if pid == meta.away_id else None)

    if st.period != 4:
        st.reason = f"period {st.period}"
        return st
    if play is None:
        st.reason = "no completed play"
        return st
    if st.play_period != st.period:
        st.reason = f"last play is from period {st.play_period}"
        return st
    # THE GAME IS OVER BEFORE THE STATUS SAYS SO. Between the final snap and
    # ESPN flipping the status to 'post', the last real play still reads as a
    # live state. The study never bet at or after the final play, so an
    # end-of-period / end-of-game row after it, or a 4th-quarter running
    # clock at 0:00, is a refusal.
    if any(play_type_id(x) in END_TYPE_IDS and play_seq(x) > play_seq(play)
           for x in plays or [] if isinstance(x, dict)):
        st.reason = "the 4th quarter has ended"
        return st
    if st.running_clock is not None and st.running_clock <= 0:
        st.reason = "4th-quarter clock at 0:00"
        return st
    if is_scoring_play(play):
        st.reason = "last play was a scoring play (clock is its end, score includes the PAT)"
        return st
    if is_conversion_play(play):
        st.reason = "last play was a conversion try"
        return st
    if st.secs is None or st.home_score is None or st.away_score is None:
        st.reason = "last play has no clock or score"
        return st
    if st.down not in SCRIMMAGE_DOWNS:
        st.reason = f"no scrimmage down (down={st.down}): transitional"
        return st
    if st.possession is None:
        st.reason = f"possession unknown (situation team {pid!r})"
        return st
    end_id = team_id(((play.get("end") or {}).get("team")))
    end_side = ("home" if end_id == meta.home_id else
                "away" if end_id == meta.away_id else None)
    if end_side is not None and end_side != st.possession:
        st.reason = (f"possession {st.possession} disagrees with the last play's end team "
                     f"{end_side}: transitional")
        return st
    st.evaluable = True
    st.reason = "ok"
    return st


# ─── the client ───────────────────────────────────────────────────────────────

class CoreClient:
    """Small ESPN core client. Dynamic documents (status, situation, plays) are
    fetched fresh every call -- a cache there would freeze the game. Team and
    event documents are static for a run and are cached."""

    def __init__(self, session=None, timeout: float = 10.0):
        import requests
        self.s = session or requests.Session()
        self.timeout = timeout
        self._static: dict[str, dict] = {}
        self.calls = 0

    def get(self, url: str | None) -> dict | None:
        url = https(url)
        if not url:
            return None
        self.calls += 1
        try:
            r = self.s.get(url, timeout=self.timeout)
            if r.status_code != 200:
                log.warning("core %s for %s", r.status_code, url[:140])
                return None
            d = r.json()
            return d if isinstance(d, dict) else None
        except Exception as exc:                      # noqa: BLE001
            log.warning("core fetch failed %s: %s", url[:140], exc)
            return None

    def get_static(self, url: str | None) -> dict | None:
        url = https(url)
        if not url:
            return None
        if url not in self._static:
            d = self.get(url)
            if d is None:
                return None
            self._static[url] = d
        return self._static[url]

    def list_event_refs(self, now: datetime | None = None) -> list[str] | None:
        """Event refs for yesterday-today (UTC): a Sunday or Monday night
        kickoff carries the next UTC date. None when the feed did not answer."""
        now = now or datetime.now(timezone.utc)
        a = (now - timedelta(days=1)).strftime("%Y%m%d")
        b = now.strftime("%Y%m%d")
        d = self.get(f"{CORE_ROOT}/events?dates={a}-{b}&limit=100")
        if d is None:
            return None
        return [ref_of(i) for i in d.get("items") or [] if ref_of(i)]

    def event_meta(self, ref: str) -> EventMeta | None:
        ev = self.get_static(ref)
        comps = (ev or {}).get("competitions") or []
        if not comps:
            return None
        comp = comps[0]
        home = away = None
        for c in comp.get("competitors") or []:
            if c.get("homeAway") == "home":
                home = c
            elif c.get("homeAway") == "away":
                away = c
        if home is None or away is None:
            return None

        def _abbr(c):
            doc = self.get_static(ref_of(c.get("team"))) or {}
            return doc.get("abbreviation")

        st = None
        m = re.search(r"/types/(\d+)", str(ref_of(ev.get("seasonType")) or ref_of(ev.get("season"))
                                          or ""))
        if m:
            st = int(m.group(1))
        return EventMeta(
            event_id=str(ev.get("id") or comp.get("id") or ""), date=ev.get("date"),
            home_id=str(home.get("id") or team_id(home.get("team")) or ""),
            away_id=str(away.get("id") or team_id(away.get("team")) or ""),
            home_abbr=_abbr(home), away_abbr=_abbr(away),
            status_ref=ref_of(comp.get("status")), situation_ref=ref_of(comp.get("situation")),
            plays_ref=ref_of(comp.get("details")), season_type=st)

    def status(self, meta: EventMeta) -> dict | None:
        return self.get(meta.status_ref)

    def plays_tail(self, meta: EventMeta, n: int = 10) -> list[dict]:
        """The last ~n..2n plays. The list is paged in listing order, so the
        last two pages of size n are fetched and the caller sorts by
        sequence."""
        if not meta.plays_ref:
            return []
        base = https(meta.plays_ref).split("?")[0]
        head = self.get(f"{base}?limit=1")
        count = _int((head or {}).get("count")) or 0
        if count <= 0:
            return []
        last = -(-count // n)
        out: list[dict] = []
        for page in sorted({max(1, last - 1), last}):
            d = self.get(f"{base}?limit={n}&page={page}")
            out.extend(i for i in (d or {}).get("items") or [] if isinstance(i, dict))
        return out

    def poll(self, meta: EventMeta, detail: bool = True) -> LiveState:
        """The state of one game. `detail=False` reads the status only (games
        outside the 4th quarter do not need the play documents)."""
        status = self.status(meta)
        if status is None:
            st = LiveState(event_id=meta.event_id, status_state=None, status_name=None,
                           period=None, running_clock=None, reason="status unavailable")
            return st
        stype = status.get("type") or {}
        if not detail or stype.get("state") != "in" or (_int(status.get("period")) or 0) < 4:
            return state_from_docs(meta, status, None, None)
        situation = self.get(meta.situation_ref) or {}
        plays: list[dict] = []
        lp = self.get(ref_of(situation.get("lastPlay")))
        if lp is not None:
            plays.append(lp)
        if lp is None or is_admin_play(lp):
            plays.extend(self.plays_tail(meta))
        return state_from_docs(meta, status, situation, plays)
