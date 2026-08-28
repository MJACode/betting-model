"""
Live player props: distributions over a player's REMAINING production.

    remaining_stat = remaining_team_plays
                   x play mix (pass/rush split implied by the game script)
                   x player usage share
                   x per-opportunity efficiency

GAME SCRIPT IS THE WHOLE POINT. A book that re-derives its live rushing prop
off pregame usage is quoting a number that the score has already invalidated:
a team down 14 entering the fourth quarter throws on nearly every snap, so the
running back's rush-yards over is dead and the slot receiver's reception over
is live. The books do move these, but they move them slowly and last, which is
why this lane exists at all.

WHAT THIS MODEL DOES NOT DO
It does not predict who gets hot. It predicts OPPORTUNITY, which is the part
of a live prop that is actually forecastable from the state. Efficiency per
opportunity is modelled as a stable player-level rate with heavy shrinkage
toward positional priors, because a live model that thinks it can call yards
per carry off six carries will bet noise all afternoon.

INJURY HANDLING IS A HARD GATE, NOT A FEATURE. A player whose snaps have
stopped is marked inactive and NEVER gets an over bet. The failure mode being
prevented is specific and expensive: a book leaves a quarterback's pass-yards
line up for ninety seconds after he walks off, our model sees a huge gap
between the line and his projected remaining yards, and we bet the over on a
man who is in the blue tent.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..state import GameState, PlayerState

# Positional priors for per-opportunity efficiency. Used as the shrinkage
# target so a player with three carries is priced off the position, not off
# three carries.
EFFICIENCY_PRIORS = {
    "rush_ypc": {"RB": 4.3, "QB": 5.0, "WR": 7.5, "FB": 3.6, "_": 4.2},
    "rec_ypr": {"WR": 11.8, "TE": 10.4, "RB": 7.6, "_": 10.5},
    "pass_ypa": {"QB": 7.1, "_": 7.1},
    "comp_pct": {"QB": 0.655, "_": 0.655},
    "catch_rate": {"WR": 0.64, "TE": 0.69, "RB": 0.76, "_": 0.66},
}
# Opportunities of a player's own evidence needed before it outweighs the prior.
SHRINK_OPPS = {"rush_ypc": 25.0, "rec_ypr": 18.0, "pass_ypa": 60.0,
               "comp_pct": 50.0, "catch_rate": 30.0}

# Plays per remaining minute, by score state. A trailing team runs more plays
# per minute (hurry-up, out of bounds, timeouts); a leading team runs fewer.
BASE_PLAYS_PER_MIN = 2.30
PACE_TRAILING_BOOST = 0.22          # per 7 points trailing, capped
PACE_MAX_BOOST = 0.55

# Pass rate as a function of score state. This curve is the game-script model.
# Down two scores late, a team's pass rate approaches but never reaches 1.
SCRIPT_SLOPE = 0.022                # pass rate per point trailing
SCRIPT_TIME_GAIN = 2.4              # the slope steepens as the clock runs out


@dataclass(frozen=True)
class PropProjection:
    player_id: str
    market: str
    accrued: float
    mu_remaining: float
    var_remaining: float
    active: bool
    note: str = ""


def script_pass_rate(state: GameState, side: str) -> float:
    """
    Pass rate a team should be expected to run from here.

    Blends the team's own in-game rate with what the score and clock demand.
    The demand term dominates late: a team down 10 with four minutes left will
    throw regardless of what it has done for three quarters.
    """
    own = state.home_pass_rate if side == "home" else state.away_pass_rate
    diff = state.score_diff if side == "home" else -state.score_diff   # own margin

    frac_left = np.clip(state.seconds_remaining / 3600.0, 0.0, 1.0)
    urgency = SCRIPT_SLOPE * (1.0 + SCRIPT_TIME_GAIN * (1.0 - frac_left))
    demanded = 0.575 - urgency * diff

    # Weight the demand term up as the clock runs down. Early, a team's own
    # tendency is most of the story; late, the scoreboard is all of it.
    w_demand = float(np.clip(1.0 - frac_left, 0.15, 0.9))
    rate = (1 - w_demand) * own + w_demand * demanded
    return float(np.clip(rate, 0.15, 0.92))


def remaining_team_plays(state: GameState, side: str) -> float:
    """Expected remaining scrimmage plays for one team."""
    minutes = max(state.seconds_remaining, 0) / 60.0
    diff = state.score_diff if side == "home" else -state.score_diff
    boost = 0.0
    if diff < 0:
        boost = min(PACE_TRAILING_BOOST * (-diff / 7.0), PACE_MAX_BOOST)
    elif diff > 0:
        boost = -min(PACE_TRAILING_BOOST * (diff / 7.0) * 0.6, PACE_MAX_BOOST * 0.6)
    # Each team gets roughly half the snaps.
    return float(max(minutes * (BASE_PLAYS_PER_MIN + boost) / 2.0, 0.0))


def _shrink(observed_rate: float | None, opportunities: float,
            key: str, position: str) -> float:
    prior_map = EFFICIENCY_PRIORS[key]
    prior = prior_map.get(position, prior_map["_"])
    if observed_rate is None or not np.isfinite(observed_rate) or opportunities <= 0:
        return prior
    k = SHRINK_OPPS[key]
    w = opportunities / (opportunities + k)
    return float(w * observed_rate + (1 - w) * prior)


def _usage_share(player: PlayerState, team_plays_so_far: float,
                 kind: str) -> float:
    """
    Share of the team's remaining opportunities this player takes.

    Blended with the pregame snap-share prior, heavily so early in a game.
    Without the prior a receiver targeted twice on the opening drive projects
    to a 40% target share for the rest of the afternoon.
    """
    if kind == "pass":
        # One quarterback takes essentially every dropback.
        return 1.0 if player.position == "QB" and player.pass_att >= 1 else 0.0

    used = player.rush_att if kind == "rush" else player.targets
    denom = max(team_plays_so_far, 1.0)
    observed = used / denom
    w = float(np.clip(denom / (denom + 25.0), 0.0, 0.85))
    prior = max(player.snap_share_prior, 0.0)
    return float(np.clip(w * observed + (1 - w) * prior, 0.0, 1.0))


def project(player: PlayerState, state: GameState, market: str,
            team_plays_so_far: float) -> PropProjection:
    """
    Mean and variance of a player's REMAINING production in `market`.

    Variance is modelled explicitly rather than assumed, because the price of a
    prop is entirely a tail question: with 8 minutes left, the difference
    between a 55% and a 45% over is almost all in the spread of the
    distribution, not in its mean.
    """
    side = player.team_side
    if not player.active:
        return PropProjection(player.player_id, market,
                              _accrued(player, market), 0.0, 0.0, False,
                              "inactive: snaps stopped")

    plays = remaining_team_plays(state, side)
    pass_rate = script_pass_rate(state, side)
    dropbacks = plays * pass_rate
    carries_team = plays * (1.0 - pass_rate)
    pos = player.position or "_"

    if market in ("player_pass_yds", "player_pass_attempts",
                  "player_pass_completions", "player_pass_tds"):
        share = _usage_share(player, team_plays_so_far, "pass")
        att = dropbacks * share
        if market == "player_pass_attempts":
            return _count(player, market, att, dispersion=1.15)
        if market == "player_pass_completions":
            cp = _shrink(_rate(player.pass_cmp, player.pass_att),
                         player.pass_att, "comp_pct", pos)
            return _count(player, market, att * cp, dispersion=1.10)
        if market == "player_pass_tds":
            # TD rate per attempt, tightly shrunk: nobody has a meaningful
            # personal TD rate inside one game.
            td_rate = 0.045
            return _count(player, market, att * td_rate, dispersion=1.0)
        ypa = _shrink(_rate(player.pass_yds, player.pass_att),
                      player.pass_att, "pass_ypa", pos)
        return _yards(player, market, att, ypa, per_opp_sd=9.5)

    if market in ("player_rush_yds", "player_rush_attempts"):
        share = _usage_share(player, team_plays_so_far, "rush")
        att = carries_team * share
        if market == "player_rush_attempts":
            return _count(player, market, att, dispersion=1.20)
        ypc = _shrink(_rate(player.rush_yds, player.rush_att),
                      player.rush_att, "rush_ypc", pos)
        return _yards(player, market, att, ypc, per_opp_sd=6.0)

    if market in ("player_reception_yds", "player_receptions"):
        share = _usage_share(player, team_plays_so_far, "target")
        tgt = dropbacks * share
        cr = _shrink(_rate(player.receptions, player.targets),
                     player.targets, "catch_rate", pos)
        if market == "player_receptions":
            return _count(player, market, tgt * cr, dispersion=1.05)
        ypr = _shrink(_rate(player.rec_yds, player.receptions),
                      player.receptions, "rec_ypr", pos)
        return _yards(player, market, tgt * cr, ypr, per_opp_sd=9.0)

    raise ValueError(f"unsupported prop market: {market}")


def _rate(num, den):
    return None if not den else float(num) / float(den)


def _accrued(player: PlayerState, market: str) -> float:
    return {
        "player_pass_yds": player.pass_yds,
        "player_pass_attempts": player.pass_att,
        "player_pass_completions": player.pass_cmp,
        "player_pass_tds": player.pass_tds,
        "player_rush_yds": player.rush_yds,
        "player_rush_attempts": player.rush_att,
        "player_reception_yds": player.rec_yds,
        "player_receptions": player.receptions,
    }.get(market, 0.0)


def _count(player: PlayerState, market: str, mu: float,
           dispersion: float) -> PropProjection:
    """
    Negative binomial shaped count. `dispersion` > 1 means overdispersed
    relative to Poisson, which every football count is: opportunities arrive in
    drives, not independently.
    """
    mu = float(max(mu, 0.0))
    return PropProjection(player.player_id, market, _accrued(player, market),
                          mu, mu * dispersion, True)


def _yards(player: PlayerState, market: str, opportunities: float,
           per_opp: float, per_opp_sd: float) -> PropProjection:
    """
    Compound distribution: a random number of opportunities, each with random
    yardage. Variance follows the standard compound formula, which is what
    keeps the tails honest when there are few opportunities left.

        Var = E[N] Var(Y) + Var(N) E[Y]^2
    """
    n = float(max(opportunities, 0.0))
    var_n = n * 1.15
    mu = n * per_opp
    var = n * per_opp_sd ** 2 + var_n * per_opp ** 2
    return PropProjection(player.player_id, market, _accrued(player, market),
                          mu, float(max(var, 1e-6)), True)


def price_over(proj: PropProjection, line: float) -> dict:
    """
    P(accrued + remaining > line).

    Normal approximation with a continuity correction for counts. Deliberately
    NOT used when the projection is degenerate: with almost no time left the
    remaining distribution collapses and a normal approximation would quote
    absurd certainty on a line the game can still cross with one play.
    """
    need = float(line) - float(proj.accrued)
    if not proj.active:
        # Already settled in practice: nothing more is coming.
        return {"over": 0.0 if need >= 0 else 1.0, "under": 1.0 if need >= 0 else 0.0,
                "degenerate": True}

    sd = float(np.sqrt(max(proj.var_remaining, 1e-9)))
    if sd < 1e-6:
        return {"over": float(proj.mu_remaining > need),
                "under": float(proj.mu_remaining <= need), "degenerate": True}

    from scipy.stats import norm
    cc = 0.5 if proj.market.endswith(("attempts", "completions", "receptions",
                                      "tds")) else 0.0
    z = (need + cc - proj.mu_remaining) / sd
    over = float(1.0 - norm.cdf(z))
    return {"over": over, "under": 1.0 - over, "degenerate": False}


def detect_inactive(prev: PlayerState | None, cur: PlayerState,
                    team_plays_since: float,
                    threshold_plays: float = 12.0) -> bool:
    """
    A player is treated as inactive when his team has run a meaningful number
    of plays and he has taken no part in any of them.

    Deliberately crude and deliberately conservative. It will occasionally
    stand a healthy player down, which costs a bet we do not make. The opposite
    error costs a bet we should not have made, on a player who is hurt, into a
    line the book has not pulled yet. Those are not symmetric.
    """
    if prev is None:
        return False
    touched = (
        cur.pass_att > prev.pass_att
        or cur.rush_att > prev.rush_att
        or cur.targets > prev.targets
    )
    return (not touched) and team_plays_since >= threshold_plays
