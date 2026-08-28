"""
Executor guards and sizing.

Most of this file tests REFUSALS, which is the correct emphasis: the executor's
job is mostly to decline, and a guard that silently stops firing is how a live
model starts betting stale numbers without anyone noticing.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from live_model.config import (  # noqa: E402
    EV_THRESHOLDS, MAX_DAILY_EXPOSURE_FRACTION, MAX_STAKE_FRACTION,
)
from live_model.executor import (  # noqa: E402
    Executor, derivative_lag, expected_value, is_hunt_state, kelly_stake,
    script_trigger_fired,
)
from live_model.feeds.odds_live import Quote  # noqa: E402
from live_model.state import GameState  # noqa: E402

NOW = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)


def state(period=3, clock=600, home=21, away=17, ts=None, dome=True):
    return GameState("g", ts or NOW, period, clock, home, away, "home", 1, 10,
                     50, 3, 3, -3.0, 46.0, None, dome, 80, 0.6, 0.55)


def quote(price=-110, ts=None, market="totals_h2", side="over", line=23.5):
    return Quote("g", market, "draftkings", side, price, line, ts or NOW)


# --------------------------------------------------------------------- math
def test_expected_value_is_on_the_quoted_price():
    assert expected_value(0.55, -110) == pytest.approx(0.05, abs=1e-3)
    assert expected_value(0.5, 100) == pytest.approx(0.0, abs=1e-9)
    assert expected_value(0.4, -110) < 0


def test_kelly_is_quartered_haircut_and_capped():
    """A huge edge must still respect the per bet cap. The cap, not the Kelly
    term, is what bounds the worst case here."""
    assert kelly_stake(0.95, 200) == pytest.approx(MAX_STAKE_FRACTION)
    assert kelly_stake(0.40, -110) == 0.0        # no edge, no stake
    small = kelly_stake(0.53, -110)
    assert 0 < small <= MAX_STAKE_FRACTION


# ------------------------------------------------------------------ guards
def test_a_stale_quote_is_never_acted_on():
    ex = Executor()
    d = ex.evaluate(state=state(), quote=quote(ts=NOW - timedelta(seconds=200)),
                    model_prob=0.9, model_id="nfl_live_deriv", now=NOW)
    assert not d.bet and d.reason.startswith("stale_quote")


def test_a_stale_state_is_never_acted_on():
    ex = Executor()
    d = ex.evaluate(state=state(ts=NOW - timedelta(seconds=120)), quote=quote(),
                    model_prob=0.9, model_id="nfl_live_deriv", now=NOW)
    assert not d.bet and d.reason.startswith("stale_state")


def test_overtime_is_declined_rather_than_guessed():
    """The engine models regulation. Overtime is sudden death shaped and
    pricing it with a regulation distribution would be wrong, not approximate."""
    ex = Executor()
    d = ex.evaluate(state=state(period=5), quote=quote(), model_prob=0.9,
                    model_id="nfl_live_deriv", now=NOW)
    assert not d.bet and d.reason == "overtime_not_modelled"


def test_the_dying_seconds_are_declined():
    ex = Executor()
    d = ex.evaluate(state=state(period=4, clock=10), quote=quote(),
                    model_prob=0.9, model_id="nfl_live_deriv", now=NOW)
    assert not d.bet and d.reason == "too_little_time"


def test_halftime_is_priceable_even_with_no_clock_left():
    """Halftime has zero seconds on the quarter clock and is the single most
    valuable window in the system. The too-little-time guard must not eat it."""
    ex = Executor()
    d = ex.evaluate(state=state(period=2, clock=0), quote=quote(),
                    model_prob=0.62, model_id="nfl_live_halftime", now=NOW)
    assert d.bet


def test_an_unknown_model_id_cannot_bet():
    ex = Executor()
    d = ex.evaluate(state=state(), quote=quote(), model_prob=0.9,
                    model_id="nfl_live_nonsense", now=NOW)
    assert not d.bet and d.reason.startswith("unknown_model")


@pytest.mark.parametrize("model_id", sorted(EV_THRESHOLDS))
def test_each_lane_enforces_its_own_threshold(model_id):
    ex = Executor()
    thresh = EV_THRESHOLDS[model_id]
    # Just under the lane's threshold at even money.
    p_under = (1.0 + thresh) / 2.0 - 0.005
    d = ex.evaluate(state=state(), quote=quote(price=100), model_prob=p_under,
                    model_id=model_id, now=NOW)
    assert not d.bet and d.reason.startswith("below_threshold")
    d = ex.evaluate(state=state(), quote=quote(price=100),
                    model_prob=p_under + 0.02, model_id=model_id, now=NOW)
    assert d.bet


def test_daily_exposure_is_capped_and_the_last_bet_is_clipped():
    ex = Executor()
    for _ in range(20):
        ex.evaluate(state=state(), quote=quote(), model_prob=0.75,
                    model_id="nfl_live_deriv", now=NOW)
    assert ex.exposure <= MAX_DAILY_EXPOSURE_FRACTION + 1e-12
    assert ex.decisions[-1].reason == "daily_exposure_cap"


# ------------------------------------------------------------- record trail
def test_every_pass_is_recorded_not_only_every_bet():
    """
    Without the passes there is no way to tell later whether a lane produced no
    bets because there was no edge or because a guard was eating everything.
    That distinction is not recoverable after the fact.
    """
    rows = []
    ex = Executor(recorder=rows.append)
    ex.evaluate(state=state(), quote=quote(), model_prob=0.30,
                model_id="nfl_live_deriv", now=NOW)
    ex.evaluate(state=state(), quote=quote(), model_prob=0.62,
                model_id="nfl_live_deriv", now=NOW)
    assert len(rows) == 2
    assert [r.bet for r in rows] == [False, True]
    assert all(r.state_ref and r.quote_ref for r in rows)


def test_a_recorder_that_raises_cannot_break_the_loop():
    def boom(_):
        raise RuntimeError("postgres is down")
    ex = Executor(recorder=boom)
    d = ex.evaluate(state=state(), quote=quote(), model_prob=0.62,
                    model_id="nfl_live_deriv", now=NOW)
    assert d.bet


def test_an_alerter_that_raises_cannot_unmake_the_bet():
    def boom(_):
        raise RuntimeError("discord is down")
    rows = []
    ex = Executor(recorder=rows.append, alerter=boom)
    d = ex.evaluate(state=state(), quote=quote(), model_prob=0.62,
                    model_id="nfl_live_deriv", now=NOW)
    assert d.bet and rows[-1].bet


def test_the_decision_row_round_trips():
    ex = Executor()
    d = ex.evaluate(state=state(), quote=quote(), model_prob=0.62,
                    model_id="nfl_live_deriv", now=NOW)
    row = d.to_row()
    assert row["bet"] is True
    assert row["market"] == "totals_h2"
    assert row["state_ref"] and row["quote_ref"]


# -------------------------------------------------------------- hunt states
def test_halftime_always_opens_the_hunt():
    assert is_hunt_state(state(period=2, clock=0))[0]


def test_a_lagging_derivative_opens_the_hunt_and_a_keeping_up_one_does_not():
    assert is_hunt_state(state(), deriv_lag=0.2)[0]
    assert not is_hunt_state(state(), deriv_lag=0.9)[0]


def test_derivative_lag_is_a_ratio_of_moves():
    assert derivative_lag(0.10, 0.02) == pytest.approx(0.2)
    assert derivative_lag(0.10, 0.10) == pytest.approx(1.0)
    assert derivative_lag(0.0, 0.05) == 1.0       # no main move, nothing to lag


def test_two_scores_in_the_second_half_fires_the_script_trigger():
    assert script_trigger_fired(state(period=3, home=7, away=21))
    assert not script_trigger_fired(state(period=1, home=7, away=21))
    assert not script_trigger_fired(state(period=3, home=21, away=17))
