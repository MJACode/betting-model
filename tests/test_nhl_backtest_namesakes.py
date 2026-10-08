"""The prop backtests refuse a shared name, as the live card does.

Prices find their player by name (models.nhl_props.name_key). Elias Pettersson
is two Vancouver players and Sebastian Aho two players on two teams, so a
price attached by name alone lands on both. The backtest then graded the
forward's shots-on-goal under on the defenceman's count: 124 bets, +89.8 units
at a 90% win rate, which the card can never place (scripts/nhl_props_card.py
upcoming_rows skips a name matching more than one player on either team).
"""
from __future__ import annotations

import pandas as pd

import models.nhl_props as P
from scripts.nhl_prop_backtest import namesakes


def _frame(rows):
    f = pd.DataFrame(rows, columns=["game_id", "season", "team", "opponent", "player_id", "player_name"])
    f["pkey"] = f.player_name.map(P.name_key)
    f["upcoming"] = False
    return f


def test_two_teammates_with_one_name_are_both_refused():
    f = _frame([("g1", 2026, "VAN", "DET", 8480012, "Elias Pettersson"),
                ("g1", 2026, "VAN", "DET", 8483678, "Elias Pettersson"),
                ("g1", 2026, "VAN", "DET", 8477000, "Quinn Hughes")])
    assert list(namesakes(f, f, 2026)) == [True, True, False]


def test_a_namesake_who_played_for_the_team_last_season_still_counts():
    # the card's roster is everyone who played for either team this season or last
    f = _frame([("g0", 2025, "VAN", "SEA", 8483678, "Elias Pettersson"),
                ("g1", 2026, "VAN", "DET", 8480012, "Elias Pettersson")])
    te = f[f.season == 2026]
    assert namesakes(te, f, 2026).tolist() == [True]


def test_namesakes_on_two_teams_collide_only_when_those_teams_meet():
    f = _frame([("g1", 2026, "CAR", "NYI", 8478427, "Sebastian Aho"),
                ("g1", 2026, "NYI", "CAR", 8480222, "Sebastián Aho"),
                ("g2", 2026, "CAR", "BOS", 8478427, "Sebastian Aho")])
    assert namesakes(f, f, 2026).tolist() == [True, True, False]


def test_a_unique_name_is_kept():
    f = _frame([("g1", 2026, "COL", "WPG", 8480069, "Cale Makar")])
    assert namesakes(f, f, 2026).tolist() == [False]
