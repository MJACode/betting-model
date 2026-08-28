"""
Game and player state, and the two builders that produce it.

THE CONTRACT THAT MATTERS: `from_pbp_row` (backtest) and `from_espn` (live)
must emit field-for-field identical schemas. If they drift, the model is
trained on one thing and served another and every backtest number is a lie.
tests/test_state_parity.py asserts it.

Score convention, verified against nflverse 2024:
  total_home_score / total_away_score are POST-play running totals.
  posteam_score / defteam_score / score_differential are PRE-play.
The state a bettor faces is the PRE-play one, so the pbp builder shifts the
running totals rather than reading them off the row.

Spread convention: GameState.pregame_spread is stored in STANDARD form
(negative = home laying points), matching odds.spread_home everywhere else in
this repo. nflverse `spread_line` is the reverse (positive = home favored), so
the pbp builder negates it. Session 128 established that the league-wide ATS
split cannot discriminate between the two conventions, which is exactly why
this is written down rather than inferred.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict, fields
from datetime import datetime, timezone

PERIOD_SECONDS = 900
REGULATION_PERIODS = 4


@dataclass(frozen=True)
class GameState:
    game_id: str
    ts: datetime                # feed timestamp, UTC
    period: int                 # 1-4, 5 = OT
    clock_seconds: int          # remaining in period
    home_score: int
    away_score: int
    possession: str | None      # 'home' | 'away' | None between plays or at half
    down: int | None
    distance: int | None
    yardline_100: int | None    # yards to the opponent end zone for the possessor
    home_timeouts: int
    away_timeouts: int
    pregame_spread: float       # home line, standard form (negative = home favored)
    pregame_total: float
    wind_mph: float | None
    is_dome: bool
    plays_run: int
    home_pass_rate: float       # in-game, smoothed toward a league prior
    away_pass_rate: float

    # ---------------------------------------------------------- derived
    @property
    def seconds_remaining(self) -> int:
        """Regulation seconds left. OT states report 0 and are priced separately."""
        if self.period > REGULATION_PERIODS:
            return 0
        full_periods_left = REGULATION_PERIODS - self.period
        return int(self.clock_seconds + full_periods_left * PERIOD_SECONDS)

    @property
    def half_seconds_remaining(self) -> int:
        if self.period > REGULATION_PERIODS:
            return 0
        in_first_half = self.period <= 2
        last_of_half = 2 if in_first_half else 4
        return int(self.clock_seconds + (last_of_half - self.period) * PERIOD_SECONDS)

    @property
    def score_diff(self) -> int:
        return self.home_score - self.away_score

    @property
    def is_halftime(self) -> bool:
        """
        End of the second quarter with the clock expired. This is the single
        most valuable window in the whole system: the market is open, no plays
        are being run, and nothing can suspend on us mid-decision.
        """
        return self.period == 2 and self.clock_seconds <= 0

    def to_json(self) -> dict:
        d = asdict(self)
        d["ts"] = self.ts.isoformat()
        return d


@dataclass(frozen=True)
class PlayerState:
    player_id: str
    game_id: str
    ts: datetime
    team_side: str              # 'home' | 'away'
    position: str
    pass_att: int
    pass_cmp: int
    pass_yds: int
    pass_tds: int
    rush_att: int
    rush_yds: int
    targets: int
    receptions: int
    rec_yds: int
    snap_share_prior: float
    active: bool

    def to_json(self) -> dict:
        d = asdict(self)
        d["ts"] = self.ts.isoformat()
        return d


GAME_STATE_FIELDS = tuple(f.name for f in fields(GameState))
PLAYER_STATE_FIELDS = tuple(f.name for f in fields(PlayerState))

# League-average pass rate, used to shrink an in-game rate computed off a
# handful of snaps. Without this the first drive of a game reports a 100% or 0%
# pass rate and the props engine happily extrapolates it over three quarters.
LEAGUE_PASS_RATE = 0.575
PASS_RATE_PRIOR_PLAYS = 20.0


def smooth_pass_rate(pass_plays: float, total_plays: float) -> float:
    """Beta-shrunk in-game pass rate. Never returns 0 or 1 on a small sample."""
    if total_plays is None or not math.isfinite(total_plays) or total_plays < 0:
        return LEAGUE_PASS_RATE
    prior = LEAGUE_PASS_RATE * PASS_RATE_PRIOR_PLAYS
    return float((pass_plays + prior) / (total_plays + PASS_RATE_PRIOR_PLAYS))


def _as_int(v, default=0):
    try:
        if v is None:
            return default
        f = float(v)
        if not math.isfinite(f):
            return default
        return int(round(f))
    except (TypeError, ValueError):
        return default


def _as_opt_int(v):
    try:
        if v is None:
            return None
        f = float(v)
        if not math.isfinite(f):
            return None
        return int(round(f))
    except (TypeError, ValueError):
        return None


def _as_float(v, default=0.0):
    try:
        if v is None:
            return default
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _as_opt_float(v):
    try:
        if v is None:
            return None
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ backtest
def from_pbp_row(row, ts: datetime | None = None) -> GameState:
    """
    Build a GameState from one nflverse play-by-play row.

    `row` carries the PRE-play columns that live_model.backtest.states adds
    (home_score_pre, away_score_pre, plays_run, home_pass_rate, away_pass_rate);
    everything else comes straight off nflverse.
    """
    posteam = row.get("posteam")
    home = row.get("home_team")
    possession = None
    if posteam is not None and isinstance(posteam, str) and posteam:
        possession = "home" if posteam == home else "away"

    home_to = _as_int(row.get("home_timeouts_remaining"), 3)
    away_to = _as_int(row.get("away_timeouts_remaining"), 3)

    roof = row.get("roof")
    is_dome = isinstance(roof, str) and roof in ("dome", "closed")

    # nflverse spread_line is positive when the HOME team is favored. Our
    # standard form is negative when home is laying, so negate.
    spread_line = _as_float(row.get("spread_line"), 0.0)

    return GameState(
        game_id=str(row.get("game_id")),
        ts=ts or datetime.now(timezone.utc),
        period=_as_int(row.get("qtr"), 1),
        clock_seconds=_as_int(row.get("quarter_seconds_remaining"), 0),
        home_score=_as_int(row.get("home_score_pre")),
        away_score=_as_int(row.get("away_score_pre")),
        possession=possession,
        down=_as_opt_int(row.get("down")),
        distance=_as_opt_int(row.get("ydstogo")),
        yardline_100=_as_opt_int(row.get("yardline_100")),
        home_timeouts=home_to,
        away_timeouts=away_to,
        pregame_spread=-spread_line,
        pregame_total=_as_float(row.get("total_line"), 44.0),
        wind_mph=None if is_dome else _as_opt_float(row.get("wind")),
        is_dome=is_dome,
        plays_run=_as_int(row.get("plays_run")),
        home_pass_rate=_as_float(row.get("home_pass_rate"), LEAGUE_PASS_RATE),
        away_pass_rate=_as_float(row.get("away_pass_rate"), LEAGUE_PASS_RATE),
    )


# ---------------------------------------------------------------------- live
def from_espn(
    summary: dict,
    *,
    game_id: str,
    pregame_spread: float,
    pregame_total: float,
    wind_mph: float | None,
    is_dome: bool,
    ts: datetime | None = None,
) -> GameState | None:
    """
    Build a GameState from an ESPN `summary?event=` payload.

    ESPN is an undocumented endpoint and its shape changes without notice, so
    every field is extracted defensively and a missing REQUIRED field returns
    None rather than a half-built state. The caller alerts on None; it must
    never silently price a game off defaults.
    """
    from .feeds.espn import extract_summary_state  # local import, avoids a cycle

    parsed = extract_summary_state(summary)
    if parsed is None:
        return None

    return GameState(
        game_id=game_id,
        ts=ts or datetime.now(timezone.utc),
        period=parsed["period"],
        clock_seconds=parsed["clock_seconds"],
        home_score=parsed["home_score"],
        away_score=parsed["away_score"],
        possession=parsed["possession"],
        down=parsed["down"],
        distance=parsed["distance"],
        yardline_100=parsed["yardline_100"],
        home_timeouts=parsed["home_timeouts"],
        away_timeouts=parsed["away_timeouts"],
        pregame_spread=float(pregame_spread),
        pregame_total=float(pregame_total),
        wind_mph=None if is_dome else wind_mph,
        is_dome=bool(is_dome),
        plays_run=parsed["plays_run"],
        home_pass_rate=smooth_pass_rate(
            parsed["home_pass_plays"], parsed["home_plays"]
        ),
        away_pass_rate=smooth_pass_rate(
            parsed["away_pass_plays"], parsed["away_plays"]
        ),
    )
