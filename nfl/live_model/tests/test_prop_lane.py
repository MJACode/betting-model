"""
Guards on the one lane that survived validation.

The measured edge is the BOOK's centring, not the model's accuracy, so the
lane must price the bias and must refuse the states where the bias has no room
to express itself. It must also never price a game off a defaulted pregame
number, which is the shortcut that produced three wrong answers in the session
that built this.
"""
from __future__ import annotations

import pytest

from live_model.models import pass_attempt_bias as pab
from live_model.workers.gameday import GamedayWorker, GameTracker


def test_prices_the_haircut_not_the_measured_bias():
    """Deploying the full measured bias leaves no room for it to tighten."""
    r = pab.over_prob(32.5, 17.0, 1800)
    full = pab.over_prob(32.5, 17.0, 1800, bias=pab.MEASURED_BIAS)
    assert pab.DEPLOY_BIAS < pab.MEASURED_BIAS
    assert r.over_prob < full.over_prob
    # Still a real edge over a -115 breakeven of about 0.535.
    assert 0.57 < r.over_prob < 0.63


def test_refuses_the_end_of_the_game():
    assert pab.over_prob(32.5, 30.0, 60).over_prob is None
    assert pab.over_prob(32.5, 30.0, 239).over_prob is None
    assert pab.over_prob(32.5, 30.0, 241).over_prob is not None


def test_refuses_a_line_already_beaten():
    """A number below what the player has thrown is a pulled market."""
    assert pab.over_prob(30.0, 31.0, 1800).over_prob is None
    assert pab.over_prob(30.0, 30.0, 1800).over_prob is None


def test_missing_accrued_does_not_block_the_read():
    """ESPN state carries no per player accrual; the guard degrades, not fails."""
    assert pab.over_prob(32.5, None, 1800).over_prob is not None


def test_blind_arm_is_the_measured_over_rate():
    assert pab.blind_over_prob() == pytest.approx(0.642, abs=1e-3)


class _Q:
    def __init__(self, market, side, line):
        self.game_id, self.market, self.side = "g1", market, side
        self.line, self.price, self.player = line, -115.0, "Some QB"
        self.bookmaker, self.ts = "draftkings", None


def test_state_is_never_built_from_a_defaulted_anchor():
    """
    No anchor means no prop decision, not a decision priced off a default.

    from_espn's own docstring forbids defaults, and a lane that quietly
    invents a pregame total prices every game off it.
    """
    w = GamedayWorker(dry_run=True)
    tr = GameTracker("e1", "SEA", "NE")
    tr.payload = {"anything": True}
    assert w._state_from(tr, "e1") is None          # no anchor quotes at all

    w._anchor_quotes = [_Q("spreads", "home", -3.5)]
    assert w._state_from(tr, "e1") is None          # spread but no total


def test_no_payload_means_no_state():
    w = GamedayWorker(dry_run=True)
    assert w._state_from(GameTracker("e1", "SEA", "NE"), "e1") is None


def test_pricing_skips_when_there_is_no_state():
    """A tick without a usable state records nothing rather than guessing."""
    w = GamedayWorker(dry_run=True)
    tr = GameTracker("e1", "SEA", "NE")
    summary = {}
    w._price_props([_Q(pab.MARKET, "over", 32.5)], tr, summary)
    assert summary == {}
    assert w.executor.decisions == []


def test_pricing_ignores_other_markets_and_the_under():
    w = GamedayWorker(dry_run=True)
    tr = GameTracker("e1", "SEA", "NE")
    tr.state = object()
    summary = {}
    w._price_props([_Q("player_rush_yds", "over", 40.5),
                    _Q(pab.MARKET, "under", 32.5)], tr, summary)
    assert w.executor.decisions == []
