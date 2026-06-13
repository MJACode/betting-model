"""
Unit tests for parse_nhl_game — the NHL API game→games-row parser.

Locks in the regulation/OT encoding that the 3-way model target
(feature_engine._compute_target) and settlement (paper_tracker._compute_result)
depend on:
  went_to_ot   = 1 when the game ended in OT or SO
  home_win_reg = 1 only when home won in regulation (0 for away reg win OR any
                 OT/SO game)
  regulation_tie = went_to_ot
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.nhl_stats_ingestor import parse_nhl_game


def _g(**over):
    base = {
        "gameType": 2,
        "gameDate": "2024-03-15",
        "season": 20232024,
        "gameState": "OFF",
        "gameOutcome": {"lastPeriodType": "REG"},
        "homeTeam": {"abbrev": "BOS", "score": 4},
        "awayTeam": {"abbrev": "TOR", "score": 2},
    }
    base.update(over)
    return base


def test_regulation_home_win():
    r = parse_nhl_game(_g())
    assert r["home_win"] == 1
    assert r["home_win_reg"] == 1
    assert r["went_to_ot"] == 0
    assert r["regulation_tie"] == 0
    assert r["season"] == 2024
    assert r["game_id"] == "NHL_2024-03-15_TOR_BOS"


def test_ot_home_win_is_regulation_draw():
    # Home wins but in OT → regulation was a draw, not a home regulation win.
    r = parse_nhl_game(_g(gameOutcome={"lastPeriodType": "OT"},
                          homeTeam={"abbrev": "NYR", "score": 3},
                          awayTeam={"abbrev": "PIT", "score": 2}))
    assert r["home_win"] == 1
    assert r["home_win_reg"] == 0
    assert r["went_to_ot"] == 1
    assert r["regulation_tie"] == 1


def test_shootout_away_win():
    r = parse_nhl_game(_g(gameState="FINAL", gameOutcome={"lastPeriodType": "SO"},
                          homeTeam={"abbrev": "DET", "score": 2},
                          awayTeam={"abbrev": "FLA", "score": 3}))
    assert r["home_win"] == 0
    assert r["home_win_reg"] == 0
    assert r["went_to_ot"] == 1


def test_scheduled_game_has_no_scores():
    r = parse_nhl_game(_g(gameState="FUT", gameOutcome=None,
                          homeTeam={"abbrev": "EDM"}, awayTeam={"abbrev": "CGY"}))
    assert r is not None
    assert r["home_score"] is None
    assert r["home_win"] is None
    assert r["went_to_ot"] is None


def test_preseason_game_skipped():
    assert parse_nhl_game(_g(gameType=1)) is None


def test_arizona_folds_into_utah():
    # Relocated franchise — historical ARI rows use the canonical UTA id.
    r = parse_nhl_game(_g(season=20212022, gameDate="2022-03-15",
                          homeTeam={"abbrev": "ARI", "score": 5},
                          awayTeam={"abbrev": "VGK", "score": 1}))
    assert r["home_team"] == "UTA"
    assert r["game_id"] == "NHL_2022-03-15_VGK_UTA"


def test_missing_teams_returns_none():
    assert parse_nhl_game(_g(homeTeam={}, awayTeam={})) is None
