"""`nfl_wind_totals` does not bet a game whose venue is not established.

WHY THIS FILE EXISTS (mike, 2026-10-20: "The repo/models should look ahead
schedules for all markets and sports and models")

The wind card read where each game is played from a schedule file frozen on
2026-08-15 that gave every 2026 game abroad the home team's US stadium. Two
London BETs were forecast at Jacksonville's coordinates: 3465055 (PHI @ JAX,
Tottenham, WIN) and 3583736 (HOU @ JAX, Wembley, LOSS). The schedule now comes
from the games table and the venue is resolved by name for a game abroad
(nfl/data_ingest/weather.resolve_venue); a game it cannot place carries
stadium_id None. These tests pin what the MODEL does with that row: no bet,
and a board row that says why -- even when a stale reading stored under the
game would clear the wind bar.

Each was watched failing on the model without the gate: the None row bet.
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


def _slate(stadium_id, *, roof="outdoors", note=""):
    """One windy, priced game inside the firing window (the fire-window
    tests' CLE @ JAX row: -105 both ways clears MIN_EDGE)."""
    kick = pd.Timestamp.now("UTC") + pd.Timedelta(days=2)
    return pd.DataFrame([{
        "game_id": "2026_05_PHI_JAX", "matchup": "PHI @ JAX",
        "kick_utc": kick.isoformat(), "stadium_id": stadium_id, "roof": roof,
        "venue_note": note, "lead_days": 2.0, "forecast_wind": 14.0,
        "exp_true_wind": 13.0, "best_book": "draftkings", "best_total": 42.0,
        "best_under_px": -105, "best_over_px": -105,
    }])


def _covered_reads(mph=14.0):
    """A covered 12h window of readings stored under the game."""
    now = pd.Timestamp.now("UTC")
    return {"2026_05_PHI_JAX": [(now - pd.Timedelta(hours=h), mph)
                                for h in (12, 8, 4, 0)]}


def test_a_placed_game_still_bets(wind):
    """The control: the gate removes the unplaced row, nothing else."""
    assert len(wind.select_bets(_slate("LON02"))) == 1


@pytest.mark.parametrize("sid", [None, float("nan"), "NOWHERE00"])
def test_no_venue_no_bet(wind, sid):
    assert wind.select_bets(_slate(sid)).empty


def test_stored_readings_cannot_carry_an_unplaced_game(wind):
    """The live path overrides the forecast with the stored window minimum.
    A window recorded before the venue was known must not bet either."""
    assert len(wind.select_bets(_slate("LON02"), wind_reads=_covered_reads())) == 1
    assert wind.select_bets(_slate(None), wind_reads=_covered_reads()).empty


def test_the_board_says_why(wind):
    note = "neutral site Somewhere Park (nflverse id YY00) is not in the venue table"
    row = wind.evaluate_board(_slate(None, note=note))[0]
    assert not int(row["qualifies"])
    assert row["reason"] == f"venue not established: {note}"


def test_the_board_and_the_card_agree_on_a_placed_game(wind):
    row = wind.evaluate_board(_slate("LON02"))[0]
    assert int(row["qualifies"]), row["reason"]


def test_the_bernabeu_with_no_roof_state_is_held_back(wind):
    """Madrid has a retractable roof and nflverse leaves it blank. Before the
    venue came from the games table this game sat at ATL97, also retractable,
    and was held back; it must still be, now that it is placed in Madrid."""
    assert wind.select_bets(_slate("MAD01", roof="")).empty
    row = wind.evaluate_board(_slate("MAD01", roof=""))[0]
    assert "retractable roof at MAD01" in row["reason"]
    assert len(wind.select_bets(_slate("MAD01", roof="open"))) == 1
