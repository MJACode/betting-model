"""The NHL shots-on-goal log load stays one player per statement.

2026-10-02 dispatch:nhl-prop-scoring cancelled this statement at
statement_timeout (pipeline_log 117003 at 16:27:37Z and 117073 at 17:23:45Z,
SQLSTATE 57014). Saves and assists on the same card finished:

    SELECT ... FROM nhl_skater_game_log
    WHERE game_type = 2 AND player_id IS NOT NULL
      AND player_id = ANY(ARRAY[11 ids])

Index Scan on idx_nhl_skater_game_log_player_date, planner cost 3085 for an
estimated 3,153 rows. The same shape for assists' 14 ids completed in
70,351 ms one minute later (cost 3580, estimated 3,742 rows). Eleven ids did
not finish inside 120s. One player is one index range on the index that
exists; the rows are the same rows.
"""
from __future__ import annotations

import inspect

import models.nhl_prop_blocked_shots as bs
import models.nhl_props as np_
from scripts import nhl_props_card as card


class _Rec:
    def __init__(self, rows_for=None):
        self.calls: list[tuple[str, object]] = []
        self.rows_for = rows_for or {}

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        self._params = params
        self._sql = sql
        return self

    def fetchall(self):
        if self.rows_for and self._params is not None:
            pid = self._params[0] if not isinstance(self._params[0], list) else None
            return list(self.rows_for.get(pid, []))
        return []


def _player_calls(rec: _Rec) -> list[tuple[str, object]]:
    return [(sql, params) for sql, params in rec.calls if "nhl_skater_game_log" in sql
            or "nhl_goalie_game_log" in sql]


def test_a_shots_slate_is_one_statement_per_player_not_one_array():
    """The statement Postgres cancelled bound eleven ids in one ANY()."""
    rec = _Rec()
    ids = [8471214, 8473533, 8475791, 8476880, 8476906, 8477940, 8478427,
           8479345, 8480830, 8482702, 8482809]
    out = np_.load_players(rec, "skater", ids)
    calls = _player_calls(rec)
    assert len(calls) == len(ids)
    assert out.empty
    for sql, params in calls:
        assert "player_id = %s" in sql, sql
        assert "player_id = ANY" not in sql, sql
        assert isinstance(params, tuple) and len(params) == 1
        assert isinstance(params[0], int)
        assert "game_type = 2" in sql
    assert [p[0] for _, p in calls] == ids


def test_batched_loads_return_every_players_rows_once():
    """Splitting the statement does not drop a row or duplicate one."""
    rows_for = {
        1: [(10, 1, "A", "C", 2026, "2026-01-01", "BOS", "NYR", 1, 3, 5, 1, 1, 1000, 100)],
        2: [
            (11, 2, "B", "D", 2026, "2026-01-02", "NYR", "BOS", 0, 1, 2, 0, 0, 900, 0),
            (12, 2, "B", "D", 2026, "2026-01-04", "NYR", "BOS", 1, 4, 6, 0, 1, 1100, 80),
        ],
        3: [],
    }
    rec = _Rec(rows_for)
    out = np_.load_players(rec, "skater", [1, 2, 3, 2])
    assert list(out.player_id) == [1, 2, 2]
    assert len(_player_calls(rec)) == 3


def test_a_second_market_does_not_reread_a_player_already_loaded():
    """Shots and assists price overlapping skaters. The second market reads
    only the ids the first did not."""
    rec = _Rec()
    cache: dict = {}
    np_.load_players(rec, "skater", [1, 2], cache=cache)
    np_.load_players(rec, "skater", [2, 3], cache=cache)
    assert [p[0] for _, p in _player_calls(rec)] == [1, 2, 3]


def test_training_still_reads_the_log_in_one_statement():
    """A backtest asks for every skater. That is one statement, not one per
    player in the league."""
    rec = _Rec()
    np_.load_players(rec, "skater", None)
    calls = _player_calls(rec)
    assert len(calls) == 1
    sql, params = calls[0]
    assert "player_id = %s" not in sql and "ANY" not in sql
    assert params is None


def test_an_empty_id_list_does_not_touch_the_log():
    rec = _Rec()
    out = np_.load_players(rec, "skater", [])
    assert out.empty and rec.calls == []


def test_blocked_shots_uses_the_same_one_player_statement():
    """Same table, same index, same timeout. The blocked-shots card must not
    keep the ANY() array the shots card just stopped sending."""
    rec = _Rec()
    bs.load_skaters(rec, [10, 11])
    calls = _player_calls(rec)
    assert len(calls) == 2
    for sql, params in calls:
        assert "player_id = %s" in sql and "player_id = ANY" not in sql
        assert isinstance(params, tuple) and len(params) == 1


def test_the_card_hands_one_cache_to_every_market():
    src = inspect.getsource(card.run_card)
    assert "log_cache: dict = {}" in src or "log_cache = {}" in src
    assert "log_cache=log_cache" in src
    body = inspect.getsource(card.score_market)
    assert "cache=log_cache" in body or "log_cache" in body
