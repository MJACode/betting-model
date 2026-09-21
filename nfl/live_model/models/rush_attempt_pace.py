"""
Live rushing attempts: the under, when the over needs a pace the back has not had.

WHAT REPLACED WHAT. The model this supersedes priced live PASS attempts from a
claimed 2.33-attempt book bias and nothing else. It passed `accrued=None`, read
no clock, and returned the same probability on every quote in every game, which
turned its expected-value threshold into a pure price filter. On 2026-09-20 it
went 4-13; across its whole life it was 6-16 for -10.62 units. Re-measured on
the archive, the bias it was built on is -0.12 attempts with a 95% interval of
(-0.42, +0.18) -- it does not exist, and pass attempts carry no edge in any
season (-2.8% pooled across 2023-25). That market is not fixable by tuning, so
this model changes market rather than threshold.

WHAT IS CLAIMED HERE, AND HOW BIG IT IS. On 874 archived DraftKings quotes
across 546 games and three seasons, betting the UNDER when the over still needed
a pace at least 1.25x what the back had actually been managing returned +11.2%
(+98.4 units), with a bootstrap interval of (+4.9%, +17.6%) resampling GAMES
rather than quotes. Every season was positive on its own -- 2023 +10.0%, 2024
+8.0%, 2025 +16.3% -- and every threshold from 1.0 to 2.0 was positive too, so
this is a plateau rather than a peak.

    the over needed   quotes   over hit   the book charged   gap
    under 0.6x         772      62.2%          52.0%      +10.1pp
    0.6 - 0.8x        1084      54.7%          50.2%       +4.5pp
    0.8 - 1.0x        1151      50.0%          50.1%       -0.1pp
    1.0 - 1.25x       1066      44.5%          49.5%       -5.0pp
    1.25 - 1.6x        925      37.8%          49.1%      -11.3pp
    over 1.6x          971      41.4%          48.8%       -7.4pp

WHY A BOOK WOULD BE WRONG HERE. A live line is re-hung mechanically off the
pregame number and the clock. That prorate cannot know that carries are the
most game-script-dependent counting stat in the sport: a back who is behind his
line at halftime is usually behind it because his team has been throwing, and
the same script that produced the shortfall goes on producing it. The book
marks the line down for time elapsed and not enough for the reason. The effect
is strongest where that reading predicts -- the player's team ahead by more than
a week's touchdown, where the market prices a run-heavy closing script that the
STARTER frequently does not get (235 bets, 66.0% under, +25.7%).

IT IS NOT STALE-LINE CAPTURE, WHICH WAS THE OBVIOUS OBJECTION. The archive
snapshots every five minutes, so these could have been prices the book had
already begun to move. Three tests say no: the edge does not decay when the
SECOND or THIRD qualifying quote is taken instead of the first (+9.7%, +11.7%
against +11.2%), and it is strongest, not weakest, on quotes where the book's
number had NOT moved since the previous snapshot (+23.7%). Nothing here races
anybody.

WHAT IS HONESTLY NOT KNOWN. There is no holdout. The 1.25 threshold predates
the archive -- it came from bucketing the deployed model's own 2026 losses --
but the MARKET and the SIDE were both chosen by reading the pooled table over
all three seasons, so the per-season agreement above is a consistency check and
not an out-of-sample test. 2026 is the first genuine one, and it has not
happened: the worker has only ever bought pass attempts, so no 2026 rushing
quote exists to grade. Treat the deployed size accordingly.

Reproduce every number here with, in order:
    python scripts/nfl_live_prop_state.py
    python scripts/nfl_live_prop_rule.py
    python scripts/nfl_live_prop_staleness.py
"""
from __future__ import annotations

import math
from dataclasses import dataclass

MODEL_ID = "nfl_live_prop"
MARKET = "player_rush_attempts"
SIDE = "under"

# THE EDGE, AS A SHIFT IN LOG ODDS ON THE BOOK'S OWN NUMBER. Fitted as an
# offset logit over all three seasons: logit P(under) = logit(book's de-vigged
# under) + delta. One estimated quantity, deliberately -- inside this gate the
# SIZE of the required surge is not significant (p=0.45) and neither is the
# price (p=0.19), so a six-coefficient model would be fitting noise. The edge
# lives in WHICH quotes are selected, not in a gradient within them.
MEASURED_DELTA = 0.3655
MEASURED_DELTA_CI = (0.2287, 0.5022)      # clustered on game, z = 5.24

# DEPLOYED BELOW THE MEASUREMENT, as the model this replaces should have been.
# 0.25 sits just above the interval's lower bound, so a bet only clears the
# threshold if it would also have cleared on the most pessimistic reading of
# the estimate. At this value the rule still takes 871 of the 874 archived
# quotes at +11.2%, so the haircut costs coverage rather than the finding.
DEPLOY_DELTA = 0.25

# THE GATE THAT IS THE ACTUAL MODEL. The over must need at least this much more
# pace than the back has been managing. Positive across 1.0, 1.1, 1.25, 1.4,
# 1.6 and 2.0 -- a neighbourhood, not a peak -- and 1.25 is where the book's
# error first exceeds its own hold.
RATIO_CUT = 1.25

# A PACE HAS TO EXIST BEFORE IT CAN BE COMPARED TO ONE. With no carries yet the
# ratio is infinite and every line looks unreachable, which is how the old model
# came to bet four quarterbacks before they had thrown a pass. This is also what
# makes an unmatched player SAFE rather than dangerous: a name the feed spells
# differently reads as zero carries and is declined here, never mispriced.
MIN_ACCRUED = 1.0

# Below this the game is nearly over and the remaining carries are a handful.
MIN_SECONDS_REMAINING = 240

# The most juice this model will lay. Mirrors nfl/live_model/config.MIN_PRICE;
# restated because the measurement was taken with it applied.
MIN_UNDER_PRICE = -140.0


@dataclass(frozen=True)
class Read:
    """What the model concluded, and why, whether or not it wants a bet."""
    under_prob: float | None
    reason: str


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def pace_ratio(line: float, accrued: float, seconds_remaining: float) -> float | None:
    """How much more pace the over needs than the back has been managing.

    Returns None when the question is not askable -- no carries yet, no time
    left, or a line he has already passed.
    """
    if seconds_remaining is None or seconds_remaining <= 0:
        return None
    if line is None or accrued is None:
        return None
    slack = line - accrued
    if slack <= 0:
        return None
    elapsed_min = max((3600.0 - seconds_remaining) / 60.0, 1.0)
    pace_so_far = accrued / elapsed_min
    if pace_so_far <= 0:
        return None
    return (slack / (seconds_remaining / 60.0)) / pace_so_far


def under_prob(line: float, accrued: float | None, seconds_remaining: float,
               market_under_prob: float, price: float,
               delta: float | None = None,
               ratio_cut: float | None = None) -> Read:
    """
    Probability the FINAL stays under this line, given what the back has done.

    The constants are read HERE, at call time, and not bound as default
    argument values. Python evaluates a default once at import, so
    `delta: float = DEPLOY_DELTA` would freeze the shipped number into the
    function object and silently ignore any later change to it -- which is
    exactly how the model this replaces kept emitting a bias that had been
    edited away.
    """
    delta = DEPLOY_DELTA if delta is None else delta
    cut = RATIO_CUT if ratio_cut is None else ratio_cut

    if seconds_remaining is None or seconds_remaining < MIN_SECONDS_REMAINING:
        return Read(None, f"too_late:{seconds_remaining}")
    if line is None or line <= 0:
        return Read(None, "no_line")
    # NOT the same as zero. None means the feed did not tell us, and pricing a
    # feasibility model without the accrued count is what produced -10.62 units.
    if accrued is None:
        return Read(None, "no_accrued")
    if accrued < MIN_ACCRUED:
        return Read(None, f"no_pace_yet:{accrued:g}")
    if (line - accrued) <= 0:
        return Read(None, "line_already_passed")
    if price is None or price < MIN_UNDER_PRICE:
        return Read(None, f"price_too_short:{price}")
    if market_under_prob is None or not (0.0 < market_under_prob < 1.0):
        return Read(None, "no_market_price")

    ratio = pace_ratio(line, accrued, seconds_remaining)
    if ratio is None:
        return Read(None, "no_pace_to_compare")
    if ratio < cut:
        # The over is reachable at the pace he has been going. The archive says
        # the book is priced about right here, so no edge is claimed.
        return Read(None, f"over_is_reachable:{ratio:.2f}")

    odds = math.log(market_under_prob / (1.0 - market_under_prob)) + delta
    return Read(_sigmoid(odds), f"pace_surge_required:{ratio:.2f}")
