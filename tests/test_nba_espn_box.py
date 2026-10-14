"""ESPN NBA box rows are written only when every needed player resolves."""
from __future__ import annotations

from data.ingestors.nba_espn_box import (
    _name_map, parse_nba_box, parse_nba_scoreboard, rows_for_game,
)

GAME = {
    "game_id": "NBA_2026-10-13_NYK_BOS",
    "game_date": "2026-10-13",
    "home": "BOS",
    "away": "NYK",
}


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


def test_an_unresolved_name_blocks_the_write_when_a_needed_id_is_missing():
    """The unmatched box name might be the bet. Writing the others would
    make the settler void that bet as a DNP."""
    names = {"jayson tatum": "1628369"}
    rows, unmatched = rows_for_game(
        parse_nba_box(_summary()), names, {"not-on-this-box"}, GAME)
    assert "Someone Else" in unmatched
    assert rows == []


def test_matched_needed_players_are_written_when_a_teammate_did_not_play():
    """Out Guy is DNP and is not in the box. Tatum is the only needed id,
    and he resolved, so the game can be logged."""
    summary = _summary()
    athletes = summary["boxscore"]["players"][0]["statistics"][0]["athletes"]
    summary["boxscore"]["players"][0]["statistics"][0]["athletes"] = athletes[:2]
    names = {"jayson tatum": "1628369"}
    rows, unmatched = rows_for_game(
        parse_nba_box(summary), names, {"1628369"}, GAME)
    assert unmatched == []
    assert len(rows) == 1
    assert rows[0]["player_id"] == "1628369"
    assert rows[0]["is_starter"] == 1
    assert type(rows[0]["is_starter"]) is int
    assert rows[0]["season"] == 2027
    assert rows[0]["game_id"] == GAME["game_id"]


def test_a_bench_player_is_stored_as_zero():
    names = {"someone else": "9"}
    players = [p for p in parse_nba_box(_summary()) if p["name"] == "Someone Else"]
    rows, unmatched = rows_for_game(players, names, {"9"}, GAME)
    assert unmatched == []
    assert rows[0]["is_starter"] == 0
    assert type(rows[0]["is_starter"]) is int


class _NameConn:
    def __init__(self, rows):
        self.rows = rows
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append(sql)
        self._rows = self.rows if "nba_player_game_log" in sql else []
        return self

    def fetchall(self):
        return self._rows


def test_a_name_worn_by_two_ids_is_dropped():
    conn = _NameConn([
        ("1", "Jayson Tatum"),
        ("2", "Jayson Tatum"),
        ("3", "Jaylen Brown"),
    ])
    names = _name_map(conn, "2025-09-08")
    assert "jayson tatum" not in names
    assert names["jaylen brown"] == "3"
    assert any("SAVEPOINT nba_box_names" in s for s in conn.sql)
