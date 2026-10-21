"""NHL game-center box → the columns the prop settler reads.

The morning stats top-up still owns the full row. This insert must not
replace it.
"""
from __future__ import annotations

from pathlib import Path

from data.ingestors.nhl_boxscore import (
    BOX_SOURCE, parse_boxscore, store_boxscore, toi_seconds,
)

_SRC = Path(__file__).resolve().parents[1].joinpath(
    "data", "ingestors", "nhl_boxscore.py").read_text(encoding="utf-8")

GAME = "NHL_2026-10-13_NJD_DET"


def test_toi_is_minutes_and_seconds():
    assert toi_seconds("11:44") == 704
    assert toi_seconds("61:05") == 3665
    assert toi_seconds("1:01:05") == 3665
    assert toi_seconds(None) is None
    assert toi_seconds("nope") is None


def _box():
    return {
        "id": 2026020090,
        "season": 20262027,
        "gameType": 2,
        "homeTeam": {"abbrev": "DET", "score": 4, "sog": 27},
        "awayTeam": {"abbrev": "NJD", "score": 3, "sog": 37},
        "playerByGameStats": {
            "awayTeam": {
                "forwards": [{
                    "playerId": 8476474,
                    "name": {"default": "S. Noesen"},
                    "position": "R",
                    "sog": 1,
                    "assists": 1,
                    "blockedShots": 0,
                    "toi": "11:44",
                    "goals": 0,
                    "points": 1,
                    "plusMinus": 0,
                    "pim": 0,
                    "hits": 2,
                    "shifts": 14,
                    "powerPlayGoals": 0,
                }],
                "defense": [],
                "goalies": [{
                    "playerId": 8477970,
                    "name": {"default": "J. Allen"},
                    "starter": True,
                    "decision": "W",
                    "saves": 23,
                    "shotsAgainst": 27,
                    "goalsAgainst": 4,
                    "toi": "60:00",
                }],
            },
            "homeTeam": {
                "forwards": [],
                "defense": [],
                "goalies": [
                    {
                        "playerId": 8476434,
                        "name": {"default": "J. Gibson"},
                        "starter": True,
                        "decision": "O",
                        "saves": 32,
                        "shotsAgainst": 37,
                        "goalsAgainst": 3,
                        "toi": "65:00",
                    },
                    {
                        "playerId": 8482076,
                        "name": {"default": "N. Daws"},
                        "starter": False,
                        "decision": None,
                        "saves": 0,
                        "shotsAgainst": 0,
                        "goalsAgainst": 0,
                        "toi": "0:00",
                    },
                ],
            },
        },
    }


def test_parse_keeps_the_stats_the_settler_reads():
    parsed = parse_boxscore(_box(), GAME, "2026-10-13")
    noesen = next(s for s in parsed["skater"] if s["player_id"] == 8476474)
    assert noesen["shots"] == 1
    assert noesen["assists"] == 1
    assert noesen["blocked_shots"] == 0
    assert noesen["toi_seconds"] == 704
    assert noesen["game_id"] == GAME
    assert noesen["team"] == "NJD"
    assert noesen["season"] == 2027
    assert noesen["source"] == BOX_SOURCE

    allen = next(g for g in parsed["goalie"] if g["player_id"] == 8477970)
    assert allen["started"] == 1
    assert allen["saves"] == 23
    assert allen["decision"] == "W"
    assert type(allen["started"]) is int

    gibson = next(g for g in parsed["goalie"] if g["player_id"] == 8476434)
    assert gibson["decision"] == "OTL"
    assert gibson["started"] == 1

    daws = next(g for g in parsed["goalie"] if g["player_id"] == 8482076)
    assert daws["started"] == 0

    away = next(t for t in parsed["team"] if t["team"] == "NJD")
    home = next(t for t in parsed["team"] if t["team"] == "DET")
    assert away["shots_for"] == 37
    assert home["shots_for"] == 27
    assert away["game_id"] == GAME


def test_an_unposted_box_is_not_a_logged_game():
    payload = _box()
    payload["playerByGameStats"] = {}
    parsed = parse_boxscore(payload, GAME, "2026-10-13")
    assert parsed == {"team": [], "skater": [], "goalie": []}


def test_the_insert_does_not_overwrite_and_one_game_is_a_savepoint():
    assert "ON CONFLICT" in _SRC and "DO NOTHING" in _SRC
    assert "DO UPDATE" not in _SRC
    assert 'call_in_savepoint(conn, "nhl_box_game"' in _SRC

    class Conn:
        def __init__(self):
            self.sql = []

        def execute(self, sql, params=None):
            self.sql.append(" ".join(sql.split()))
            return self

        def executemany(self, sql, rows):
            self.sql.append(" ".join(sql.split()))
            self.rows = rows

    conn = Conn()
    parsed = parse_boxscore(_box(), GAME, "2026-10-13")
    store_boxscore(conn, parsed)
    text = "\n".join(conn.sql)
    assert "SAVEPOINT nhl_box_game" in text
    assert "RELEASE SAVEPOINT nhl_box_game" in text
    assert "ON CONFLICT (nhl_game_id, player_id) DO NOTHING" in text
    assert "DO UPDATE" not in text


def test_an_empty_box_writes_nothing():
    class Conn:
        def execute(self, sql, params=None):
            raise AssertionError(sql)

    assert store_boxscore(Conn(), {"team": [], "skater": [], "goalie": []}) == {
        "team": 0, "skater": 0, "goalie": 0,
    }
