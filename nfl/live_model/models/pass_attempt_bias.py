"""
The pass-attempt bias this lane was built to price DOES NOT EXIST.

Re-measured 2026-09-21 on the same archive the original claim came from, after
mike: *"when the ev threshold was tightened there were no picks, when it's
slightly loosened you literally pick the over on pass attempts for every game --
this tells me the model is shit."* He was reading the symptom correctly and the
cause is worse than a threshold.

WHAT THIS MODULE USED TO CLAIM. That DK's live full-game pass-attempt line sat
2.33 attempts BELOW the eventual final across 2023-25, and that 64.2% of 2025
quotes went over. It deployed a haircut 1.50 and priced every quote at
Phi(1.50/5.90) = 0.6003.

THREE THINGS WERE WRONG, in increasing order of severity.

1. THE OUTPUT WAS A CONSTANT. `z = bias / sigma` reads neither the line, the
   accrued total nor the clock. Every quote in every game got 0.6003 (or 0.642
   on the blind arm). With a constant probability the EV test reduces to a pure
   PRICE filter -- fair odds -150.2, so EV>=0.06 means "any over priced better
   than -130.6". That is exactly the behaviour reported: tighten it and nothing
   qualifies, loosen it and every game qualifies, always the over.

2. THE BIAS IS NOT THERE. Re-derived from the 5,333 archived snapshots joined
   to nfl_player_game_log finals (4,071 two-sided DK pass-attempt quotes, 776
   games), clustered on game:

       bias (line - final)   -0.12    95% CI (-0.42, +0.18)   t = -0.8
       by season   2023 -0.33 | 2024 +0.12 | 2025 -0.16   (none significant)
       over rate   2023 50.5% | 2024 48.2% | 2025 45.7%   (not 64.2%)

   The reconstruction reproduces the original's DISPERSION (MAE 4.41 against
   the 4.72-4.97 reported) while contradicting its CENTRE, and corr(line,
   final) = 0.70 with mean line 32.3 against mean final 32.4. Same spread,
   different middle: the original's `actual_final` was offset, not its sample.
   Quote-level standard errors also understate by ~1.7x here, because five
   minute snapshots of one game are not independent draws -- but that is a
   footnote, since the point estimate itself is ~0 rather than -2.33.

3. GRADED AT REAL PRICES IT LOSES, AND TIGHTENING MAKES IT WORSE. Every
   archived DK quote, bet at the posted over price with the -140 floor:

       EV >= 0.00   4,048 bets   -330.7u   -8.17%   90% CI (-12.1, -4.4)
       EV >= 0.06   3,794 bets   -321.4u   -8.47%   90% CI (-12.4, -4.6)
       EV >= 0.10   2,916 bets   -272.5u   -9.34%   90% CI (-13.6, -5.1)
       by season    2023 -4.41% | 2024 -10.71% | 2025 -15.29%

   THE REASON TIGHTENING HURTS is adverse selection, and it is measurable. The
   book's price is informative: regressing the outcome on the de-vigged over
   probability gives a slope of +1.22 (1.0 = perfectly calibrated). So the
   cheapest overs are the ones least likely to land. The cut keeps quotes whose
   de-vigged probability averages 0.496 and which go over 48.5% of the time,
   and discards quotes averaging 0.543 which go over 54.9%. A constant
   probability plus a price filter is an adverse-selection machine.

WHAT WAS TRIED BEFORE GIVING UP. Game state was joined to every quote from
nflverse play-by-play (score margin for the passer's team, game seconds
remaining, accrued attempts, slack, pace, and the margin x sqrt(time)
interaction). In sample the state block IS significant over and above the
book's price (chi2 = 16.13, df 6, p = 0.013) with the deficit term carrying the
sign the hurry-up story predicts, and the book's own price turns out to encode
almost no state at all (R^2 = 0.010). That is the most promising thing in this
file. It does not survive: trained on 2023-24 and tested on 2025 the model ties
the market exactly on log loss (0.6917 vs 0.6917) and on Brier (0.2493 vs
0.2493), its calibration is non-monotone, and the single cut that produced
bets returned -18.9% on 18 of them.

SO THIS MODULE DECLINES TO PRICE. Not a pause and not a retirement -- both are
mike's call and the settled record is untouched either way (CLAUDE.md 1c). The
model simply no longer asserts a number that measurement says is false, and the
caller already treats a None read as "no opinion, no bet"
(workers/gameday.py). Restoring the old behaviour is one constant: set
DEPLOY_BIAS back to a non-zero value.

Full assessment, every table and how to reproduce it:
`docs/nfl_live_prop_assessment.md`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Re-measured 2026-09-21 on 4,071 two-sided DraftKings quotes over 776 games,
# standard error clustered on the game. The interval spans zero, so the honest
# deployable bias is zero and there is nothing here to price.
MEASURED_BIAS = -0.12
MEASURED_BIAS_CI = (-0.42, 0.18)
DEPLOY_BIAS = 0.0

# Dispersion of (final - line), re-measured: sd 5.78, MAE 4.41. Unchanged in
# spirit from the original 5.90 -- the spread was never the problem.
SIGMA = 5.78

# Below this the game is nearly over, the remaining attempts are a handful, and
# any bias would have no room left to express itself.
MIN_SECONDS_REMAINING = 240

# NOTE: production calls over_prob(line, accrued=None, ...), so this gate has
# never once fired live. Left in place because the signature is public and the
# replay harness does pass an accrued figure.
MIN_SLACK = 0.0

MODEL_ID = "nfl_live_prop"
MARKET = "player_pass_attempts"


@dataclass(frozen=True)
class Read:
    """What the lane concluded, and why, whether or not it wants a bet."""
    over_prob: float | None
    reason: str


def over_prob(line: float, accrued: float, seconds_remaining: float,
              bias: float | None = None, sigma: float | None = None) -> Read:
    """
    Probability the FINAL clears this line.

    `bias` and `sigma` default to the module constants AT CALL TIME, not at
    import time. That matters: the old signature bound `bias=DEPLOY_BIAS` as a
    default value, so rebinding the constant -- in a test, a replay or a
    hotfix -- changed nothing and the function went on using the value captured
    when the module was first imported.

    Returns None while `bias` is zero, which is the measured value. This is
    deliberate and is the whole point of the 2026-09-21 re-measurement: with no
    bias there is no edge, and asserting 0.50 into a priced market would simply
    donate the hold. A caller that gets None writes no pick.

    The sanity gates still run first, so a caller can tell "no opinion" from
    "this quote was unusable" by the reason string.
    """
    bias = DEPLOY_BIAS if bias is None else bias
    sigma = SIGMA if sigma is None else sigma
    if seconds_remaining is None or seconds_remaining < MIN_SECONDS_REMAINING:
        return Read(None, f"too_late:{seconds_remaining}")
    if line is None or line <= 0:
        return Read(None, "no_line")
    if accrued is not None and (line - accrued) <= MIN_SLACK:
        return Read(None, "line_at_or_below_accrued")
    if sigma <= 0:
        return Read(None, "degenerate_sigma")
    if bias == 0.0:
        # The measured state. See the module docstring for the tables.
        return Read(None, "no_measured_bias")
    # P(final > line) = P(final - line > 0), centred on the book's bias.
    z = bias / sigma
    return Read(0.5 * (1.0 + math.erf(z / math.sqrt(2.0))), "measured_bias")


def blind_over_prob() -> float | None:
    """
    The rate at which finals cleared the line, with no gate at all.

    Carried so the paper trade could run this arm alongside the priced one, on
    the reasoning that the honest question was whether anything beats betting
    every over. That question now HAS an answer, measured on 4,071 real quotes
    at real prices: betting every over returns -8.23%, 90% CI (-12.1, -4.4).
    The 0.642 this used to return was the 2025 over rate from the same
    reconstruction that produced the phantom -2.33; re-derived, 2025 went over
    45.7% of the time.

    So this arm returns None too, and for the same reason as over_prob.
    """
    return None
