"""NBA prop settlement reads every stat a market can settle on.

The bug this guards (measured 2026-10-15): _load_nba_prop_actuals selected
points, rebounds, assists, fg3_made, steals and blocks only. The settlement map
already routes nba_prop_player_turnovers to the `turnovers` column, so a
turnovers bet found no value, the game WAS logged, and the settler voided it as
a did-not-play -- NO_ACTION on a player who played.

The combo markets (points+rebounds, points+assists, rebounds+assists,
blocks+steals, triple-double) must be computable from the same row. The helper
exists so the lead can register models against it; no model id is registered
here.
"""
from __future__ import annotations

import re

from tracking import paper_tracker as pt

GID = "NBA_2026-10-21_GSW_LAL"
PID = "201939"

FULL_ROW = {
    "player_id": PID, "player_name": "Stephen Curry", "game_id": GID,
    "team": "GSW", "minutes": 34.0,
    "points": 31, "rebounds": 6, "offensive_reb": 1, "defensive_reb": 5,
    "assists": 10, "steals": 2, "blocks": 1, "turnovers": 5,
    "fg_made": 10, "fg_att": 20, "fg3_made": 6, "fg3_att": 12,
    "ft_made": 5, "ft_att": 5,
}


class _SelectConn:
    """Answers a SELECT with FULL_ROW projected onto the columns it names, so
    the test checks what the loader asked for, not a hand-built tuple."""

    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table
        self.updates = []
        self._rows = []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.upper().startswith("UPDATE"):
            self.updates.append((s, params))
            self._rows = []
            return self
        m = re.search(r"SELECT (.*?) FROM (\w+)", s, re.I)
        table = m.group(2) if m else ""
        full_rows = self.rows_by_table.get(table, [])
        if table == "picks" or table.startswith("picks"):
            self._rows = full_rows
            return self
        cols = [c.strip().split()[-1].split(".")[-1] for c in m.group(1).split(",")] if m else []
        self._rows = [tuple(r.get(c) for c in cols) for r in full_rows]
        return self

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


def test_the_loader_selects_turnovers():
    conn = _SelectConn({"nba_player_game_log": [FULL_ROW]})
    got = pt._load_nba_prop_actuals(conn, "2026-10-21")
    assert got[(PID, GID)]["turnovers"] == 5


def test_the_loader_carries_every_stat_a_market_settles_on():
    conn = _SelectConn({"nba_player_game_log": [FULL_ROW]})
    row = pt._load_nba_prop_actuals(conn, "2026-10-21")[(PID, GID)]
    for col in ("points", "rebounds", "assists", "fg3_made", "steals", "blocks",
                "turnovers", "offensive_reb", "defensive_reb", "fg_made", "fg_att",
                "fg3_att", "ft_made", "ft_att", "minutes"):
        assert row[col] == FULL_ROW[col], col


def test_combo_helpers():
    a = pt._nba_prop_actual
    r = FULL_ROW
    assert a(r, "COMPUTE_PRA") == 31 + 6 + 10
    assert a(r, "COMPUTE_PR") == 37
    assert a(r, "COMPUTE_PA") == 41
    assert a(r, "COMPUTE_RA") == 16
    assert a(r, "COMPUTE_BS") == 3
    assert a(r, "COMPUTE_DD") == 1             # points and assists
    assert a(r, "COMPUTE_TD") == 0             # rebounds 6
    assert a({**r, "rebounds": 10}, "COMPUTE_TD") == 1
    assert a(r, "turnovers") == 5
    assert a(r, "fg3_made") == 6


def test_double_double_matches_the_rule_it_replaced():
    """The inline rule was: >= 10 in at least two of pts/reb/ast/stl/blk,
    a missing value counting as 0. The helper must grade every row the same."""
    def old(row):
        cats = [row.get("points"), row.get("rebounds"), row.get("assists"),
                row.get("steals"), row.get("blocks")]
        return int(sum(1 for c in cats if (c or 0) >= 10) >= 2)

    rows = [
        FULL_ROW,
        {**FULL_ROW, "assists": 9},
        {**FULL_ROW, "points": None, "assists": 12, "rebounds": 10},
        {**FULL_ROW, "steals": 10, "blocks": 10, "points": 2, "assists": 1},
        {"points": None, "rebounds": None, "assists": None, "steals": None, "blocks": None},
    ]
    for row in rows:
        assert pt._nba_prop_actual(row, "COMPUTE_DD") == old(row)


def test_a_missing_stat_is_none_not_zero():
    """None is what tells the settler there is nothing to grade; a 0 would
    grade the under as a win."""
    assert pt._nba_prop_actual({"points": 12}, "turnovers") is None


def test_combo_markets_are_mapped_to_helpers_without_registering_a_model():
    m = pt._NBA_MARKET_STAT
    assert m["player_turnovers"] == "turnovers"
    assert m["player_points_rebounds"] == "COMPUTE_PR"
    assert m["player_points_assists"] == "COMPUTE_PA"
    assert m["player_rebounds_assists"] == "COMPUTE_RA"
    assert m["player_blocks_steals"] == "COMPUTE_BS"
    assert m["player_triple_double"] == "COMPUTE_TD"
    assert m["player_double_double"] == "COMPUTE_DD"
    assert m["player_points_rebounds_assists"] == "COMPUTE_PRA"
    for model_id, stat_map in pt._PROP_MARKET_STAT_BY_MODEL.items():
        assert stat_map is not m, f"{model_id} registered against the NBA map"
    for sentinel in set(m.values()):
        assert pt._nba_prop_actual(FULL_ROW, sentinel) is not None, sentinel


def test_a_turnovers_bet_on_a_player_who_played_settles_win_not_no_action():
    """End to end through _settle_prop_picks: an over 3.5 turnovers bet, five
    turnovers in the box. Before the fix this settled NO_ACTION as a DNP."""
    pick = ("pk1", GID, "nba_prop_player_turnovers", "over", -110, 2.0, 3.5,
            PID, "Stephen Curry Over 3.5 Turnovers", "player_turnovers", None)
    conn = _SelectConn({"picks": [pick], "nba_player_game_log": [FULL_ROW]})
    pt._settle_prop_picks(conn, "2026-10-21", "2026-10-22T05:00:00Z")
    results = [(s, p) for s, p in conn.updates if "SET result" in s]
    assert results, "the pick was not settled at all"
    sql, params = results[-1]
    got = "NO_ACTION" if "'NO_ACTION'" in sql else params[0]
    assert got == "WIN", f"settled {got}, expected WIN"
    assert params[-1] == "pk1"
