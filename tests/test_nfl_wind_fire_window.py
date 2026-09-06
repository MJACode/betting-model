"""`nfl_wind_totals` must not fire outside its firing window.

WHY THIS FILE EXISTS

Between 2026-09-05 and 2026-09-06 nothing gated how far out a wind bet could
fire. `MAX_CALIBRATED_LEAD` bounds the PROBABILITY table, and on 2026-09-05 the
stake was changed to clip to lead 7 rather than return zero -- correct on its
own terms, but the zero stake had been the only thing keeping leads 8-10 off the
board, and `scheduler.run_nfl_poll` hands the card `--days 10`.

MEASURED on Week 1, 2026-09-06: all five live picks fired at leads 7.2 / 7.5 /
8.0 / 8.2 / 8.7 days, every one of them carrying model_probability 0.5489 --
the (7, 11) clip value -- so not one published probability was a measurement.
Five of eleven outdoor games qualified.

The gate is `MAX_FIRE_LEAD`, in the model rather than in a caller's argument.
These tests pin the two properties that were violated:

  * a game past the window does not fire, however windy;
  * `select_bets` and `evaluate_board` agree about that game.

The second is the one worth keeping. The two halves of this model have come
apart before over exactly this -- the uncalibrated-lead note used to make
`evaluate_board` say `qualifies=False` while `select_bets` carried the same row
onto the card anyway -- and the comment in `evaluate_board` records it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

NFL_ROOT = Path(__file__).resolve().parents[1] / "nfl"


@pytest.fixture(scope="module")
def wind():
    sys.path.insert(0, str(NFL_ROOT))
    try:
        from _nfl_models import load_nfl_model
        yield load_nfl_model("wind_totals")
    finally:
        sys.path.remove(str(NFL_ROOT))


def _slate(lead_days: float) -> pd.DataFrame:
    """One outdoor game, windy enough to qualify, at the given forecast lead.

    The price is the Week 1 CLE @ JAX pick's: -105 both ways, which de-vigs to
    0.50 and therefore clears MIN_EDGE on the constant model probability. That
    is the real shape of this model's edge -- the wind bar is the only selector
    -- so a lead gate is the only thing that can stop this row.
    """
    kick = pd.Timestamp.now("UTC") + pd.Timedelta(days=lead_days)
    return pd.DataFrame([{
        "game_id": "2026_01_CLE_JAX", "matchup": "CLE @ JAX",
        "kick_utc": kick.isoformat(), "stadium_id": "JAX00", "roof": "outdoors",
        "lead_days": lead_days, "forecast_wind": 14.0, "exp_true_wind": 13.0,
        "best_book": "onexbet", "best_total": 40.5,
        "best_under_px": -105, "best_over_px": -105,
    }])


@pytest.mark.parametrize("lead", [7.2, 7.5, 8.0, 8.2, 8.7])
def test_the_five_week1_leads_would_not_fire_today(wind, lead):
    """The exact leads the five Week 1 picks locked at. None may fire now."""
    assert wind.select_bets(_slate(lead)).empty, (
        f"a 14 mph game at lead {lead}d fired; MAX_FIRE_LEAD is "
        f"{wind.MAX_FIRE_LEAD}")


def test_the_same_game_fires_once_it_is_inside_the_window(wind):
    """The gate must DELAY the bet, not cancel it. Nothing is given up here."""
    bets = wind.select_bets(_slate(wind.MAX_FIRE_LEAD - 0.5))
    assert len(bets) == 1
    assert bets.iloc[0].units > 0, "inside the window and sized at zero"


def test_waiting_is_worth_more_than_firing_early(wind):
    """Why the gate costs nothing: the calibrated rate RISES as the lead falls.

    If this ever inverts, the whole argument for waiting is gone and the gate
    should be revisited rather than quietly kept.
    """
    early = wind.model_under_prob(wind.MAX_CALIBRATED_LEAD)
    late = wind.model_under_prob(wind.MAX_FIRE_LEAD)
    assert late > early, f"lead {wind.MAX_FIRE_LEAD} ({late}) <= lead 7 ({early})"


@pytest.mark.parametrize("lead", [2.0, 4.5, 8.7])
def test_the_card_and_the_eval_board_never_disagree(wind, lead):
    """One game, both halves of the model, same verdict. Regression-prone."""
    slate = _slate(lead)
    fired = not wind.select_bets(slate).empty
    board = wind.evaluate_board(slate)
    assert len(board) == 1
    assert bool(int(board[0]["qualifies"])) == fired, (
        f"lead {lead}d: select_bets fired={fired} but the board said "
        f"{board[0]['qualifies']} — {board[0]['reason']}")


def test_a_waiting_game_is_not_reported_as_a_collapsed_premise(wind):
    """`nfl_pick_monitor` reads the reason string; wording is load-bearing.

    "beyond the" in a reason means GONE -- the premise itself has failed. A game
    waiting on the firing window still has its wind, so it must not trip that.
    """
    from scripts.nfl_pick_monitor import classify

    row = wind.evaluate_board(_slate(8.7))[0]
    still, status, _ = classify({"qualifies": row["qualifies"],
                                 "reason": row["reason"]})
    assert not still
    assert status != "GONE", f"waiting read as a collapsed premise: {row['reason']}"


def test_every_offline_caller_of_select_bets_opts_out_of_the_live_gate(wind):
    """A backtest that silently inherits a deployment policy reports a lie.

    `MAX_FIRE_LEAD` is where we are willing to commit MONEY, not a property of
    the rule. `replay_wind_card.py --lead 5` builds a frame at lead 5 and is how
    leads 5/6/7 in CALIBRATED_UNDER_RATE were checked; with the default gate it
    would print "no qualifying bets", which is indistinguishable from a calm
    week. Caught 2026-09-06 by reading the callers rather than the suite --
    nothing under `nfl/scripts/` is otherwise exercised here.

    Static, deliberately: these scripts need the odds cache and the weather
    cache (108 MB, gitignored) to run at all. The property is cheap to state and
    the failure mode is silence, which is the combination that earns a tripwire.
    """
    live = {"weekly_wind_card.py"}          # the one caller the gate is FOR
    offenders = []
    for path in sorted((NFL_ROOT / "scripts").glob("*.py")):
        src = path.read_text(encoding="utf-8")      # cp1252 default would raise here
        if "select_bets(" not in src or path.name in live:
            continue
        for line in src.splitlines():
            if "select_bets(" in line and "def " not in line and "=" != line.strip()[:1]:
                if "max_fire_lead" not in line:
                    offenders.append(f"{path.name}: {line.strip()}")
    assert not offenders, (
        "offline caller(s) of select_bets inherit the live firing gate and will "
        "silently report zero bets past lead "
        f"{wind.MAX_FIRE_LEAD}: " + "; ".join(offenders))


def test_a_waiting_row_keeps_its_line_price_and_edge(wind):
    """The board's job is the locked-pick record, so a waiting row is not blank.

    A pick locked before the gate existed sits in the waiting branch for the
    days between `MAX_FIRE_LEAD` and its own lock. Gating before pricing would
    blank the line, the price and the edge for exactly that window.

    Concrete case, measured 2026-09-06: CLE @ JAX locked at a 14.0 mph forecast
    on 09-05 and read 4.3 mph the next day, still 7 days from kickoff.
    """
    row = wind.evaluate_board(_slate(8.7))[0]
    assert not int(row["qualifies"])
    assert "waiting" in row["reason"]
    assert row["current_line"] == 40.5, row
    assert row["current_price"] == -105, row
    assert row["edge"] not in (None, ""), "the waiting row lost its edge"
