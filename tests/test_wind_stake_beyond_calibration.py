"""A wind pick past the 7-day calibration is SIZED, not zeroed.

THE BUG. `model_under_prob` has always CLIPPED a forecast lead to
`MAX_CALIBRATED_LEAD` (7) -- Open-Meteo's `previous_dayN` stops there, so a
longer lead reuses the lead-7 error distribution. `stake_units` did not clip; it
returned 0.0. So the two halves of one model disagreed about the same bet: a
real probability, a real edge, and no stake.

That would be harmless if nothing downstream published it, but
`scripts/nfl_wind_publisher.build_rows` mirrors EVERY card row into `picks` with
a hardcoded `signal_type='BET'`, and the publisher is insert-once. Both Week 1
picks of 2026-09-05 -- CLE @ JAX Under 40.5 (-105) and BUF @ HOU Under 44.5
(-105), a 8.7-day lead -- were written as permanently locked BETs labelled
`0.00u`, cleared every action threshold, and reached the app carrying the
1-unit default that `units_for` publishes for a zero Kelly.

Matt, 2026-09-05: "we should return stakes 7 days for signal picks." So the
stake clips exactly as the probability always has.

UPDATE 2026-09-06 (mike). The clipping above is UNCHANGED and still pinned
here. What changed is that such a row no longer reaches the card at all: the
zero stake had been the de-facto firing gate, and removing it let every bet
lock outside the calibration. Firing is now gated explicitly by
`MAX_FIRE_LEAD`, so the two tests that went end-to-end through `select_bets`
pass `max_fire_lead` to isolate the stake question from the firing question --
and then assert the default gate holds. See
tests/test_nfl_wind_fire_window.py.

Run in a SUBPROCESS with cwd=nfl/, the way the scheduler runs the card:
`nfl/models/` and the platform's `models/` are different packages with the same
name, and importing the NFL one in-process shadows the platform's for the rest
of the suite (tests/test_nfl_model_imports.py exists about this).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
NFL = ROOT / "nfl"


def _probe(expr_lines: str) -> list[str]:
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(NFL)!r})\n"
        "from _nfl_models import load_nfl_model\n"
        "w = load_nfl_model('wind_totals')\n"
        + expr_lines
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=str(NFL),
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()


def test_the_stake_clips_to_lead_seven_instead_of_returning_zero():
    """The regression, at the real numbers off the 2026-09-05 picks.

    Asserted as EQUALITY with the lead-7 stake, not merely "> 0": clipping is
    the requirement, and a test for non-zero would also pass against some other
    invented number for an uncalibrated lead.
    """
    out = _probe(
        "p7 = w.model_under_prob(7.0, 11.0)\n"
        "p871 = w.model_under_prob(8.71, 11.0)\n"
        "print(w.stake_units(p7, -105, 7.0))\n"
        "print(w.stake_units(p871, -105, 8.71))\n"
    )
    at_seven, beyond = float(out[0]), float(out[1])
    assert at_seven > 0, "the lead-7 reference stake must be non-zero"
    assert beyond == at_seven, (
        f"a lead-8.71 bet staked {beyond}, not the lead-7 stake {at_seven} -- "
        "the stake must clip exactly as model_under_prob does")


def test_the_probability_was_already_clipping():
    """Why the old behaviour was an inconsistency rather than a policy.

    The stored `model_probability` on both 2026-09-05 picks is 0.5489, which IS
    the lead-7 number -- the model was already treating them as lead-7 bets.
    Only the stake disagreed.
    """
    out = _probe(
        "print(w.model_under_prob(7.0, 11.0))\n"
        "print(w.model_under_prob(8.71, 11.0))\n"
        "print(w.model_under_prob(30.0, 11.0))\n"
    )
    assert out[0] == out[1] == out[2], out
    assert float(out[0]) == 0.5489, (
        f"lead-7 P(under) is {out[0]}; the two picks written on 2026-09-05 "
        "carry 0.5489, so a change here changes what those bets meant")


_CLE_JAX = (
    "import pandas as pd\n"
    "g = pd.DataFrame([{'game_id': '2026_01_CLE_JAX', 'matchup': 'CLE @ JAX',\n"
    "  'kick_utc': '2026-09-13 17:00:00+00:00', 'stadium_id': 'JAX00',\n"
    "  'roof': 'outdoors', 'lead_days': 8.71, 'forecast_wind': 14.0,\n"
    "  'exp_true_wind': 12.0, 'best_book': 'onexbet', 'best_total': 40.5,\n"
    "  'best_under_px': -105, 'best_over_px': -115}])\n"
)


def test_an_uncalibrated_lead_is_sized_rather_than_zeroed_on_the_card():
    """End to end through select_bets: the row that used to arrive at 0.00u.

    `max_fire_lead` is widened here ON PURPOSE. Since 2026-09-06 the default
    gate stops this lead-8.71 row before sizing ever happens, so at the default
    the test would pass for the wrong reason -- an empty card is not evidence
    that a clipped stake is non-zero. Widening isolates the stake question;
    the test below re-asserts the gate.
    """
    out = _probe(
        _CLE_JAX +
        "b = w.select_bets(g, threshold=11.0, bankroll=1.0, max_fire_lead=99)\n"
        "print(len(b))\n"
        "print(float(b.units.iloc[0]))\n"
        "print(bool(b.calibrated_lead.iloc[0]))\n"
    )
    assert int(out[0]) == 1, "the game must still make the card"
    assert float(out[1]) > 0, (
        f"the card row is sized at {out[1]} units -- this is the 0.00u bet")
    assert out[2] == "False", (
        "the row must still be FLAGGED uncalibrated; clipping the stake is an "
        "assumption and the card has to keep saying so")


def test_at_the_default_gate_that_same_row_does_not_fire_at_all():
    """The 2026-09-06 change, stated against the pick that motivated both.

    CLE @ JAX at a 8.71-day lead is the bet from the docstring above. Sizing it
    was right; LOCKING it eight days out was not, and the publisher is
    insert-once, so the two decisions could not be separated once it fired.
    """
    out = _probe(_CLE_JAX +
                 "print(len(w.select_bets(g, threshold=11.0, bankroll=1.0)))\n"
                 "print(w.MAX_FIRE_LEAD)\n")
    assert int(out[0]) == 0, (
        f"a lead-8.71 bet fired at the default gate (MAX_FIRE_LEAD={out[1]})")


def test_the_eval_board_agrees_with_the_card():
    """They used to disagree about the same game.

    `evaluate_board` disqualified an uncalibrated lead outright while
    `select_bets` -- which had no lead gate at all -- carried the same row onto
    the card. The eval board feeds the locked-pick history, so the record said
    "does not qualify" about a bet that was live.

    Checked at BOTH gate settings, because the 2026-09-06 gate is a second
    chance to reintroduce exactly this bug: it has to be applied to both halves
    or the board and the card part company again.
    """
    out = _probe(
        _CLE_JAX +
        "wide = w.evaluate_board(g, threshold=11.0, max_fire_lead=99)[0]\n"
        "tight = w.evaluate_board(g, threshold=11.0)[0]\n"
        # `qualifies` is the STRING "1"/"0" (pick_eval.eval_row), so bool() of
        # it is True either way and the assertion below could never have failed.
        # int() first. Found 2026-09-06 by writing a case that should fail it.
        "print(bool(int(wide['qualifies'])))\n"
        "print(wide['reason'])\n"
        "print(bool(int(tight['qualifies'])))\n"
        "print(tight['reason'])\n"
    )
    assert out[0] == "True", (
        f"the eval board still disqualifies the card's own bet: {out[1]}")
    assert "clipped" in out[1], (
        f"the caveat must survive into the reason string, got: {out[1]}")
    assert out[2] == "False", (
        f"the board fired a row the card will not: {out[3]}")
    assert "firing window" in out[3], (
        f"the board must say WHY it is waiting, got: {out[3]}")
