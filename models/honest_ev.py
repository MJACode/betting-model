"""One gate for every BET writer: the honest probability, the EV it implies at
the deciding price, and whether that clears the floor.

Phase 3 (2026-09-19, mike): a pick is a BET only if its CALIBRATED probability
(models/probability_calibration.py, the promoted map) times the decimal of the
price it is decided at, minus one, is at least `config.min_ev_for(model_id)`.
The pre-game scorer, the MLB and NCAAF live loops and the NFL live executor
each already had a decision function and gained the gate inline; the five
rule cards (nfl_prop_market, wnba_prop_market, mlb_game_market,
mlb_total_public_fade, nfl wind/opener) had no decision function at all --
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
    """The promoted map applied; identity when there is none or it fails."""
    from models.scorer import _calibrated
    cal = _calibrated(model_id, prob)
    return float(prob) if cal is None else float(cal)


def gate(model_id: str, prob: float, odds) -> Gate:
    cal = honest_probability(model_id, prob)
    return Gate(model_id=model_id, raw_prob=float(prob), cal_prob=cal,
                odds=None if odds is None else float(odds),
                ev=config.expected_value(cal, odds),
                floor=config.min_ev_for(model_id))
