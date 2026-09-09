"""The tackles stat the model grades must be the one the book grades.

A book settles "tackles + assists" on the box-score TOTAL, and the box-score
total is solo + tackles-with-assist + assists: against ESPN's TOT column on
193 player-games (2024 week 10) that sum matches 94.8% of rows, while solo +
assists -- what the game log held until 2026-09-09 -- matches 77.7% and runs
0.26 a game low. That gap is why the tackles model read 41% overs against the
book's 50% and bet the under on everything.

Three things pin the fix: the ingestor reads the column the feed already
carries, the feature engine builds the target from all three components, and
it refuses to build tackles features on a game log that never got the column.
"""
from __future__ import annotations

import pandas as pd
import pytest

from data.ingestors.nfl_props_data_ingestor import parse_player_rows

SCHEDULE = {"2025_01_KC_BUF": {"gameday": "2025-09-07", "home_team": "KC",
                               "away_team": "BUF", "spread_line": "-2.5",
                               "total_line": "48.5", "roof": "outdoors"}}

CSV = (
    "player_id,player_display_name,position,season,week,season_type,game_id,team,"
    "opponent_team,def_tackles_solo,def_tackles_with_assist,def_tackle_assists,def_sacks\n"
    "00-009,Nick Bolton,LB,2025,1,REG,2025_01_KC_BUF,KC,BUF,6,2,3,0.5\n"
)


def test_the_ingestor_carries_tackles_with_assist():
    rows = {r["player_name"]: r for r in parse_player_rows(CSV, SCHEDULE)}
    lb = rows["Nick Bolton"]
    assert lb["def_tackles_solo"] == pytest.approx(6.0)
    assert lb["def_tackles_with_assist"] == pytest.approx(2.0)
    assert lb["def_tackle_assists"] == pytest.approx(3.0)


def _frame(with_assist):
    return pd.DataFrame({
        "def_tackles_solo": [6.0, 4.0],
        "def_tackles_with_assist": with_assist,
        "def_tackle_assists": [3.0, 1.0],
        "rushing_yards": [0.0, 0.0], "receiving_yards": [0.0, 0.0],
        "rushing_tds": [0, 0], "receiving_tds": [0, 0],
    })


def _derive(df):
    from features.nfl_prop_feature_engine import derived_targets
    return derived_targets(df)


def test_the_target_is_the_box_score_total():
    df = _derive(_frame([2.0, 0.0]))
    assert list(df["tackles_assists"]) == [11.0, 5.0]


def test_a_game_log_without_the_column_cannot_build_tackles():
    """A frame from before the backfill would silently fall back to the short
    stat, which is the bug this file exists for."""
    with pytest.raises(ValueError, match="def_tackles_with_assist is empty"):
        _derive(_frame([None, None]))
