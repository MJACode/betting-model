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


def test_an_uncalibrated_lead_still_reaches_the_card_with_units():
    """End to end through select_bets: the row that used to arrive at 0.00u."""
    out = _probe(
        "import pandas as pd\n"
        "g = pd.DataFrame([{'game_id': '2026_01_CLE_JAX', 'matchup': 'CLE @ JAX',\n"
        "  'kick_utc': '2026-09-13 17:00:00+00:00', 'stadium_id': 'JAX00',\n"
        "  'roof': 'outdoors', 'lead_days': 8.71, 'forecast_wind': 14.0,\n"
        "  'exp_true_wind': 12.0, 'best_book': 'onexbet', 'best_total': 40.5,\n"
        "  'best_under_px': -105, 'best_over_px': -115}])\n"
        "b = w.select_bets(g, threshold=11.0, bankroll=1.0)\n"
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


def test_the_eval_board_agrees_with_the_card():
    """They used to disagree about the same game.

    `evaluate_board` disqualified an uncalibrated lead outright while
    `select_bets` -- which has no lead gate at all -- carried the same row onto
    the card. The eval board feeds the locked-pick history, so the record said
    "does not qualify" about a bet that was live.
    """
    out = _probe(
        "import pandas as pd\n"
        "g = pd.DataFrame([{'game_id': '2026_01_CLE_JAX', 'matchup': 'CLE @ JAX',\n"
        "  'kick_utc': '2026-09-13 17:00:00+00:00', 'stadium_id': 'JAX00',\n"
        "  'roof': 'outdoors', 'lead_days': 8.71, 'forecast_wind': 14.0,\n"
        "  'exp_true_wind': 12.0, 'best_book': 'onexbet', 'best_total': 40.5,\n"
        "  'best_under_px': -105, 'best_over_px': -115}])\n"
        "rows = w.evaluate_board(g, threshold=11.0)\n"
        "print(bool(rows[0]['qualifies']))\n"
        "print(rows[0]['reason'])\n"
    )
    assert out[0] == "True", (
        f"the eval board still disqualifies the card's own bet: {out[1]}")
    assert "clipped" in out[1], (
        f"the caveat must survive into the reason string, got: {out[1]}")
