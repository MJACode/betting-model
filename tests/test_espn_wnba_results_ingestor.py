"""
test_espn_wnba_results_ingestor.py — Pure-function tests for the ESPN WNBA
final-score self-heal ingestor.

Exercises team-name resolution and scoreboard parsing against synthetic
payloads shaped like ESPN's site.api scoreboard contract (no network, no DB).
"""

from data.ingestors.espn_wnba_results_ingestor import (
    _build_game_id,
    _espn_team_to_abbrev,
    parse_scoreboard,
)


def _competitor(home_away, display_name, score):
    return {
        "homeAway": home_away,
        "score": score,
        "team": {"displayName": display_name, "location": display_name.rsplit(" ", 1)[0],
                  "name": display_name.rsplit(" ", 1)[1]},
    }


def _event(home_name, home_score, away_name, away_score, completed=True):
    return {
        "competitions": [
            {
                "status": {"type": {"completed": completed}},
                "competitors": [
                    _competitor("home", home_name, home_score),
                    _competitor("away", away_name, away_score),
                ],
            }
        ]
    }


def test_build_game_id_matches_canonical_format():
    assert _build_game_id("2026-07-05", "NY", "LV") == "WNBA_2026-07-05_NY_LV"


def test_espn_team_to_abbrev_resolves_known_franchise():
    team = {"displayName": "Las Vegas Aces", "location": "Las Vegas", "name": "Aces"}
    assert _espn_team_to_abbrev(team) == "LV"


def test_espn_team_to_abbrev_returns_none_for_unknown_team():
    team = {"displayName": "Some Unknown Club", "location": "Some", "name": "Unknown Club"}
    assert _espn_team_to_abbrev(team) is None


def test_parse_scoreboard_extracts_completed_game():
    data = {"events": [_event("Las Vegas Aces", "88", "New York Liberty", "82")]}
    rows = parse_scoreboard(data, "2026-07-05")
    assert len(rows) == 1
    row = rows[0]
    assert row["game_id"] == "WNBA_2026-07-05_NY_LV"
    assert row["home_team"] == "LV"
    assert row["away_team"] == "NY"
    assert row["home_score"] == 88
    assert row["away_score"] == 82
    assert row["home_win"] == 1


def test_parse_scoreboard_skips_incomplete_games():
    data = {"events": [_event("Las Vegas Aces", "40", "New York Liberty", "38", completed=False)]}
    assert parse_scoreboard(data, "2026-07-05") == []


def test_parse_scoreboard_skips_unknown_team_without_raising():
    data = {"events": [_event("Some Unknown Club", "80", "New York Liberty", "70")]}
    assert parse_scoreboard(data, "2026-07-05") == []


def test_parse_scoreboard_skips_missing_score():
    data = {"events": [_event("Las Vegas Aces", None, "New York Liberty", "70")]}
    assert parse_scoreboard(data, "2026-07-05") == []


def test_parse_scoreboard_handles_malformed_event_without_raising():
    data = {"events": [{"competitions": [{"status": {"type": {"completed": True}}}]}]}
    assert parse_scoreboard(data, "2026-07-05") == []


def test_parse_scoreboard_handles_empty_or_missing_events():
    assert parse_scoreboard({}, "2026-07-05") == []
    assert parse_scoreboard({"events": []}, "2026-07-05") == []


def test_parse_scoreboard_away_win():
    data = {"events": [_event("Las Vegas Aces", "70", "New York Liberty", "91")]}
    rows = parse_scoreboard(data, "2026-07-05")
    assert rows[0]["home_win"] == 0
