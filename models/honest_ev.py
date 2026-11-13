"""One gate for every BET writer: the honest probability, the EV it implies at
the deciding price, and whether that clears the floor.

Phase 3 (2026-09-19, mike): a pick is a BET only if its CALIBRATED probability
(models/probability_calibration.py, the promoted map) times the decimal of the
price it is decided at, minus one, is at least `config.min_ev_for(model_id)`.
The pre-game scorer, the MLB and NCAAF live loops and the NFL live executor
each already had a decision function and gained the gate inline; the rule
cards (nfl_prop_market, wnba_prop_market, mlb_game_market,
mlb_total_public_fade, nfl wind/opener, nhl_over_under) had no decision
function at all --
a rule's selection WAS the bet -- so they call this. Same arithmetic, same
map, same floor, or a surface would disagree silently.

`gate` never raises: a calibration lookup that fails leaves the raw number
(models.scorer._calibrated's contract), and a missing price yields ev None,
which the caller treats as "no floor can apply" exactly as the live scorer
does.
"""
from __future__ import annotations

from dataclasses import dataclass

import config
from models.market_relative import implied as _implied


@dataclass(frozen=True)
class Gate:
    model_id: str
    raw_prob: float
    cal_prob: float
    odds: float | None
    ev: float | None
    floor: float

    @property
    def clears(self) -> bool:
        """True when the EV is at or above the floor, or no price exists."""
        return self.ev is None or self.ev >= self.floor

    @property
    def reason(self) -> str | None:
        if self.clears:
            return None
        return (f"ev_below_floor:{self.ev:.3f}<{self.floor:.2f} "
                f"(p {self.raw_prob:.3f}->{self.cal_prob:.3f} at {self.odds:+.0f})")


def honest_probability(model_id: str, prob: float) -> float:
    """The promoted map applied; identity when there is none or it fails.

    The two NFL rules in config.MODELS_ON_OWN_PROBABILITY decide on their own
    number (mike, 2026-09-20): their map is the pooled offset borrowed from
    other models, and it puts every bet they make under water.
    """
    if model_id in config.MODELS_ON_OWN_PROBABILITY:
        return float(prob)
    from models.scorer import _calibrated
    cal = _calibrated(model_id, prob)
    return float(prob) if cal is None else float(cal)


def shrink_factor(model_id: str, game_date) -> float | None:
    """k for a row of this model and game date (config.MODEL_PROB_SHRINK), or None when that
    row stores the number the bet was decided on: a model with no shrink, a game before the
    model's "from" date, or no date at all."""
    s = config.MODEL_PROB_SHRINK.get(model_id)
    if s is None or game_date is None:
        return None
    return float(s["k"]) if str(game_date)[:10] >= str(s["from"]) else None


def shown_probability(model_id: str, prob: float, odds, game_date) -> float:
    """The probability a picks row STORES and the app SHOWS, from the one the bet was decided on.

    Where shrink_factor gives k: implied + k (prob - implied), implied from `odds`, the price
    the pick was decided at, so the shown EV is k x the decided EV and the shown edge at that
    price is k x the decided edge. Otherwise `prob` unchanged. Display only: nothing that
    decides, floors or ranks a bet may read this (config.MODEL_PROB_SHRINK says why).
    `implied` is models.market_relative.implied, the one the card's edges use, so the stored
    decision_edge is k x the decided one exactly."""
    k = shrink_factor(model_id, game_date)
    implied = _implied(odds)
    if k is None or implied is None:
        return float(prob)
    return implied + k * (float(prob) - implied)


def decision_probability(model_id: str, shown: float, odds, game_date) -> float | None:
    """The inverse of shown_probability: the number the bet was decided on, from the stored one,
    the decision price and the game date. The stored number itself for a model with no shrink or
    a game before its "from" date. None for a shrunk model's row with no date or no price,
    because the stored number alone cannot say what was decided."""
    if model_id not in config.MODEL_PROB_SHRINK:
        return float(shown)
    if game_date is None:
        return None
    k = shrink_factor(model_id, game_date)
    if k is None:
        return float(shown)
    implied = _implied(odds)
    if implied is None:
        return None
    # To 10 decimals: the inverse leaves ~1e-16 of float noise, and the "good to" price breaks
    # exact half-point ties on it. Every decided number this recovers has far fewer decimals
    # (the projection card's has 4), so this returns it bit for bit.
    return round(implied + (float(shown) - implied) / k, 10)


def gate(model_id: str, prob: float, odds) -> Gate:
    cal = honest_probability(model_id, prob)
    return Gate(model_id=model_id, raw_prob=float(prob), cal_prob=cal,
                odds=None if odds is None else float(odds),
                ev=config.expected_value(cal, odds),
                floor=config.min_ev_for(model_id))
