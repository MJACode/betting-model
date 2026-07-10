"""
Tests for the ESPN-based WNBA results ingestor — pure parsers only
(no network, no DB), same convention as test_ufc_csv_loader / test_datagolf.
Fixtures mirror ESPN's site.api.espn.com v2 scoreboard/summary shapes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.wnba_results_ingestor import (
    parse_scoreboard, parse_summary_boxscore, norm_player_name,
    _split_made_att, _min_to_float,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _scoreboard_fixture():
    def competitor(home_away, name, abbrev, score):
        return {"homeAway": home_away, "score": score,
                "team": {"displayName": name, "abbreviation": abbrev}}
    return {
        "events": [
            {   # completed game — LVA @ NYL (ESPN abbrevs differ from ours)
                "id": "401736123",
                "date": "2026-07-05T23:00Z",
                "status": {"type": {"completed": True, "name": "STATUS_FINAL"}},
                "competitions": [{
                    "competitors": [
                        competitor("home", "New York Liberty", "NYL", "88"),
                        competitor("away", "Las Vegas Aces", "LVA", "79"),
                    ],
                }],
            },
            {   # in-progress game — must not produce scores
                "id": "401736124",
                "date": "2026-07-06T01:00Z",
                "status": {"type": {"completed": False, "name": "STATUS_IN_PROGRESS"}},
                "competitions": [{
                    "competitors": [
                        competitor("home", "Phoenix Mercury", "PHX", "41"),
                        competitor("away", "Chicago Sky", "CHI", "39"),
                    ],
                }],
            },
        ],
    }


def _summary_fixture():
    labels = ["MIN", "FG", "3PT", "FT", "OREB", "DREB", "REB", "AST",
              "STL", "BLK", "TO", "PF", "+/-", "PTS"]

    def athlete(espn_id, name, starter, stats, dnp=False):
        return {"athlete": {"id": espn_id, "displayName": name},
                "starter": starter, "didNotPlay": dnp, "stats": stats}

    return {
        "boxscore": {
            "players": [
                {
                    "team": {"displayName": "New York Liberty", "abbreviation": "NYL"},
                    "statistics": [{
                        "labels": labels,
                        "athletes": [
                            athlete("3149391", "Breanna Stewart", True,
                                    ["34", "9-17", "2-5", "4-4", "1", "7", "8",
                                     "3", "1", "2", "2", "1", "+11", "24"]),
                            athlete("4398911", "Marine Johannès", False,
                                    ["18", "3-7", "2-4", "0-0", "0", "2", "2",
                                     "5", "0", "0", "1", "2", "-3", "8"]),
                            athlete("9999999", "Bench Player", False, [], dnp=False),
                            athlete("8888888", "Dnp Player", False,
                                    ["0", "0-0", "0-0", "0-0", "0", "0", "0",
                                     "0", "0", "0", "0", "0", "0", "0"], dnp=True),
                        ],
                    }],
                },
                {
                    "team": {"displayName": "Las Vegas Aces", "abbreviation": "LVA"},
                    "statistics": [{
                        "labels": labels,
                        "athletes": [
                            athlete("2998938", "A'ja Wilson", True,
                                    ["36", "11-20", "0-1", "6-7", "3", "8", "11",
                                     "2", "2", "3", "4", "3", "-9", "28"]),
                        ],
                    }],
                },
            ],
        },
    }


# ── Scoreboard parsing ────────────────────────────────────────────────────────

def test_scoreboard_completed_game():
    games = parse_scoreboard(_scoreboard_fixture(), "2026-07-05")
    final = next(g for g in games if g["completed"])
    assert final["game_id"] == "WNBA_2026-07-05_LV_NY"   # ESPN LVA/NYL → our LV/NY
    assert final["home"] == "NY" and final["away"] == "LV"
    assert final["home_score"] == 88 and final["away_score"] == 79
    assert final["home_win"] == 1
    assert final["season"] == 2026
    assert final["event_id"] == "401736123"
    assert final["commence_time"] == "2026-07-05T23:00Z"


def test_scoreboard_in_progress_game_has_no_scores():
    games = parse_scoreboard(_scoreboard_fixture(), "2026-07-05")
    live = next(g for g in games if not g["completed"])
    assert live["home_score"] is None and live["away_score"] is None
    assert live["home_win"] is None
    assert live["game_id"] == "WNBA_2026-07-05_CHI_PHX"


def test_scoreboard_empty_payload():
    assert parse_scoreboard({}, "2026-07-05") == []
    assert parse_scoreboard({"events": []}, "2026-07-05") == []


# ── Box-score parsing ─────────────────────────────────────────────────────────

def test_boxscore_stats_parsed_by_label():
    rows = parse_summary_boxscore(_summary_fixture())
    stew = next(r for r in rows if r["name"] == "Breanna Stewart")
    assert stew["team"] == "NY"
    assert stew["starter"] is True
    assert stew["minutes"] == 34.0
    assert stew["points"] == 24
    assert stew["rebounds"] == 8
    assert stew["offensive_reb"] == 1 and stew["defensive_reb"] == 7
    assert stew["assists"] == 3 and stew["steals"] == 1 and stew["blocks"] == 2
    assert stew["turnovers"] == 2
    assert (stew["fg_made"], stew["fg_att"]) == (9, 17)
    assert (stew["fg3_made"], stew["fg3_att"]) == (2, 5)
    assert (stew["ft_made"], stew["ft_att"]) == (4, 4)


def test_boxscore_skips_dnp_and_empty_stats():
    rows = parse_summary_boxscore(_summary_fixture())
    names = {r["name"] for r in rows}
    assert "Dnp Player" not in names      # didNotPlay
    assert "Bench Player" not in names    # empty stats row
    assert len(rows) == 3


def test_boxscore_both_teams_and_espn_abbrev_normalized():
    rows = parse_summary_boxscore(_summary_fixture())
    wilson = next(r for r in rows if "Wilson" in r["name"])
    assert wilson["team"] == "LV"          # ESPN LVA → our LV
    assert wilson["points"] == 28


def test_boxscore_empty_payload():
    assert parse_summary_boxscore({}) == []
    assert parse_summary_boxscore({"boxscore": {}}) == []


# ── Helpers ───────────────────────────────────────────────────────────────────

def test_split_made_att():
    assert _split_made_att("5-11") == (5, 11)
    assert _split_made_att(" 0-0 ") == (0, 0)
    assert _split_made_att("") == (None, None)
    assert _split_made_att(None) == (None, None)
    assert _split_made_att("abc") == (None, None)


def test_min_to_float():
    assert _min_to_float("32") == 32.0
    assert _min_to_float("32:30") == 32.5
    assert _min_to_float("--") is None
    assert _min_to_float("") is None
    assert _min_to_float(None) is None


def test_norm_player_name_matches_across_sources():
    # accents / punctuation / suffixes must not break the ESPN ↔ nba_api join
    assert norm_player_name("Marine Johannès") == norm_player_name("Marine Johannes")
    assert norm_player_name("A'ja Wilson") == norm_player_name("Aja Wilson")
    assert norm_player_name("Kelsey Plum Jr.") == norm_player_name("Kelsey Plum")
    assert norm_player_name("Skylar Diggins-Smith") == norm_player_name("Skylar Diggins Smith")
    assert norm_player_name("  Napheesa   Collier ") == "napheesa collier"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"{len(fns)} tests passed")
