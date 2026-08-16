"""
Tests for the nflverse games.csv finals parser (session 119).

Pure-function tests only — the fetch + UPDATE path runs in the daily pipeline
(Step 0f) against Postgres.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.nfl_results_ingestor import parse_nflverse_scores

CSV = """game_id,season,week,gameday,away_team,away_score,home_team,home_score,roof
2026_01_NE_SEA,2026,1,2026-09-09,NE,17,SEA,24,outdoors
2026_01_NYJ_MIA,2026,1,2026-09-13,NYJ,20,MIA,20,outdoors
2026_02_DEN_KC,2026,2,2026-09-20,DEN,,KC,,outdoors
1999_01_MIN_ATL,1999,1,1999-09-12,MIN,17,ATL,14,dome
"""


class TestParseNflverseScores:
    def test_completed_wanted_games_parsed(self):
        out = parse_nflverse_scores(CSV, {"2026_01_NE_SEA", "2026_01_NYJ_MIA"})
        assert out == {
            "2026_01_NE_SEA": (17.0, 24.0),   # (away, home)
            "2026_01_NYJ_MIA": (20.0, 20.0),  # ties parse too
        }

    def test_unfinished_game_skipped(self):
        out = parse_nflverse_scores(CSV, {"2026_02_DEN_KC"})
        assert out == {}

    def test_unwanted_games_ignored(self):
        out = parse_nflverse_scores(CSV, {"2026_01_NE_SEA"})
        assert "1999_01_MIN_ATL" not in out and len(out) == 1

    def test_empty_wanted_set(self):
        assert parse_nflverse_scores(CSV, set()) == {}
