"""ESPN NBA scoreboard and box parsers (data/ingestors/nba_espn_box.py).

Until 2026-10-15 this file also pinned `rows_for_game`, which left a whole game
unlogged when any box name failed to resolve -- so a rookie's games were never
logged. That rule is gone: every player is logged, an unresolved one under an
`espn:<id>` id. The replacement tests live in tests/test_nba_results_ingestor.py
(test_one_unresolved_player_does_not_drop_the_game,
test_settlements_fill_missing_logs_a_game_with_a_rookie_in_it).
"""
from __future__ import annotations

from data.ingestors.nba_espn_box import parse_nba_box, parse_nba_scoreboard


def _board():
    def event(eid, completed, away="NYK", home="BOS"):
        return {
            "id": eid,
            "status": {"type": {"completed": completed}},
            "competitions": [{
                "competitors": [
                    {"homeAway": "away", "team": {
                        "abbreviation": away, "displayName": "New York Knicks"}},
                    {"homeAway": "home", "team": {
                        "abbreviation": home, "displayName": "Boston Celtics"}},
                ],
            }],
        }
    return {"events": [event("401", True), event("402", False, "LAL", "GSW")]}


def test_the_scoreboard_keeps_completed_games_only():
    games = parse_nba_scoreboard(_board(), "2026-10-13")
    assert [g["game_id"] for g in games] == ["NBA_2026-10-13_NYK_BOS"]
    assert games[0]["event_id"] == "401"


def _summary():
    labels = ["PTS", "MIN", "REB", "OREB", "DREB", "AST", "STL", "BLK", "TO",
              "FG", "3PT", "FT"]
    return {
        "boxscore": {
            "players": [{
                "team": {"abbreviation": "BOS", "displayName": "Boston Celtics"},
                "statistics": [{
                    "labels": labels,
                    "athletes": [
                        {
                            "starter": True,
                            "athlete": {"displayName": "Jayson Tatum"},
                            "stats": ["28", "35:30", "8", "1", "7", "4", "1", "0",
                                      "2", "10-20", "3-8", "5-6"],
                        },
                        {
                            "starter": False,
                            "didNotPlay": True,
                            "athlete": {"displayName": "Out Guy"},
                            "stats": [],
                        },
                        {
                            "starter": False,
                            "athlete": {"displayName": "Someone Else"},
                            "stats": ["4", "12", "2", "0", "2", "1", "0", "0",
                                      "1", "2-4", "0-1", "0-0"],
                        },
                    ],
                }],
            }],
        },
    }


def test_stats_are_read_by_label_and_a_dnp_is_omitted():
    players = parse_nba_box(_summary())
    assert [p["name"] for p in players] == ["Jayson Tatum", "Someone Else"]
    tatum = players[0]
    assert tatum["points"] == 28
    assert tatum["minutes"] == 35.5
    assert tatum["fg_made"] == 10 and tatum["fg_att"] == 20
    assert tatum["starter"] is True
