"""
The one lane that survived validation: DK's live pass attempt line runs low.

WHAT WAS MEASURED, and what it is not. Across 2023, 2024 and 2025, on real
in play quotes at the prices actually posted, DK's live full game pass attempt
line sat about 2.33 attempts BELOW the eventual final. The other three prop
markets pulled in the same exercise sat within 0.25 of zero. The bias is one
sign, one magnitude, one market, three seasons.

    season(s)   quotes   bias   median   mae    went over
    2023-24      3,794   -2.33   -2.50   4.97      -
    2025           377   -2.33   -1.50   4.72     64.2%

This is NOT the flow model. The flow model ties the book on absolute error
(MAE 4.99 against 4.97) and beats it only on centring. Everything the flow
features add sits on top of this bias rather than underneath it, and a model
free rule, take the over, captured most of it. So this lane prices the BIAS,
and does not pretend a game script model is doing the work.

WHY THE MECHANISM IS CREDIBLE. Late passing volume arrives at a low completion
rate: hurry up, sideline throws to stop the clock, spikes, which are an attempt
and an incompletion by definition, and desperation deep balls. A book prorating
off its opener and the clock therefore lands low on ATTEMPTS while landing
right on COMPLETIONS, which is exactly the pattern in all three seasons. A bias
with a mechanism is worth more than one without, because it says when it should
be absent: a game with no late deficit has no hurry up to under forecast.

WHY THE EDGE IS NOT SPEED. The bias stands all game and never corrects, which
is why pseudo CLV came back near zero while ROI did not. Nothing here races a
book. A quote read sixty seconds late is worth what a quote read instantly is.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Measured on 2023 to 2025. Deliberately HAIRCUT below the measured 2.33: the
# spec's own rule is that backtest ROI is an upper bound, snapshots are five
# minutes apart in the archive, and a bet that needs the full measured bias to
# clear its threshold is a bet that fails the first time the market tightens.
MEASURED_BIAS = 2.33
DEPLOY_BIAS = 1.50

# Dispersion of (final - line). Measured MAE is 4.72 to 4.97; for a roughly
# normal error the standard deviation runs about 1.25x the mean absolute error.
SIGMA = 5.90

# Below this the game is nearly over, the remaining attempts are a handful, and
# the bias has no room left to express itself.
MIN_SECONDS_REMAINING = 240

# A line already below what the player has thrown is a stale or pulled market,
# not an edge. Fewer than 0.2% of measured quotes looked like this.
MIN_SLACK = 0.0

MODEL_ID = "nfl_live_prop"
MARKET = "player_pass_attempts"


@dataclass(frozen=True)
class Read:
    """What the lane concluded, and why, whether or not it wants a bet."""
    over_prob: float | None
    reason: str


def over_prob(line: float, accrued: float, seconds_remaining: float,
              bias: float = DEPLOY_BIAS, sigma: float = SIGMA) -> Read:
    """
    Probability the FINAL clears this line, from the measured book bias alone.

    No game state beyond the sanity gates enters this. That is the point: the
    edge measured over three seasons was the book's centring, not our forecast,
    and pricing it with a model we know ties the book on error would dress up
    the same number as something it is not.
    """
    if seconds_remaining is None or seconds_remaining < MIN_SECONDS_REMAINING:
        return Read(None, f"too_late:{seconds_remaining}")
    if line is None or line <= 0:
        return Read(None, "no_line")
    if accrued is not None and (line - accrued) <= MIN_SLACK:
        return Read(None, "line_at_or_below_accrued")
    if sigma <= 0:
        return Read(None, "degenerate_sigma")
    # P(final > line) = P(final - line > 0), with (final - line) centred on the
    # book's bias. Positive bias means the book posts low, so the over is live.
    z = bias / sigma
    return Read(0.5 * (1.0 + math.erf(z / math.sqrt(2.0))), "measured_bias")


def blind_over_prob() -> float:
    """
    The rate at which finals cleared the line in 2025, with no gate at all.

    Carried so the paper trade can run this arm ALONGSIDE the priced one. The
    honest question about this lane is whether anything beats betting every
    over, and that is only answerable if both are recorded from the start.
    """
    return 0.642
