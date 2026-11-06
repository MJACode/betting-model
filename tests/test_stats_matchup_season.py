"""The Stats tab's matchup column grades on the season the Teams board reads.

2026-11-06: it called fetchTeamStats(sport, yearET()). NBA seasons are labelled
by their ENDING year, so in November that asked for last season and every NBA
row graded off 2025-26 defences, while the Teams board showed 2026-27.
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "mobile" / "src" / "screens" / "StatsScreen.tsx"


def test_matchup_defence_read_uses_sport_aware_season():
    text = SRC.read_text(encoding="utf-8")
    calls = re.findall(r"fetchTeamStats\(\s*sport\s*,\s*([^)]+?)\s*\)", text)
    assert calls, "StatsScreen no longer reads team stats; update this test"
    for arg in calls:
        assert arg.startswith("teamBoardSeason(sport"), (
            f"fetchTeamStats(sport, {arg}) - use teamBoardSeason(sport), "
            "the season the Teams board reads"
        )
