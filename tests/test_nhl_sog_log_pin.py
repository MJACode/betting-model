"""The NHL prop log load is one player per statement, with one deadline per run.

2026-10-02 and 2026-10-03: dispatch:nhl-prop-scoring cancelled the shots
(and, twice, the assists) read of nhl_skater_game_log at statement_timeout.
pipeline_log has 6 errors on 2026-10-02 and 4 on 2026-10-03, each mentioning
that timeout. From 2026-10-04 through 2026-10-17 the same step, still on the
single ANY() statement, succeeded 697 times (average 6.5s, maximum 23.1s).
One player per statement, and one 120s budget for every uncached read in the
run, is the safety net for the next slow night.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

import models.nhl_prop_blocked_shots as bs
import models.nhl_props as np_
from scripts import nhl_prop_card as blocked
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


class _Clock:
    def __init__(self, t: float = 0.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def test_one_run_stops_at_its_deadline_and_still_returns_a_cached_player():
    """Each statement keeps the server's 120s timeout. The run does not get
    another 120s per player."""
    clock = _Clock()
    cache = np_.PlayerLogCache(deadline_s=120, clock=clock)
    rec = _Rec()
    np_.load_players(rec, "skater", [1], cache=cache)
    clock.t = 119
    np_.load_players(rec, "skater", [2], cache=cache)
    clock.t = 120
    try:
        np_.load_players(rec, "skater", [3], cache=cache)
    except np_.PlayerLogDeadline:
        pass
    else:
        raise AssertionError("a third player started after the run's 120s")
    again = np_.load_players(rec, "skater", [1], cache=cache)
    assert again.empty
    assert [p[0] for _, p in _player_calls(rec)] == [1, 2]


def test_the_card_hands_one_cache_to_every_market(monkeypatch):
    """run_card is executed. Every live market receives the same cache object."""
    seen: list = []

    def fake_score(conn, spec, games, game_date, artifact=None, log_cache=None):
        seen.append(log_cache)
        return {"priced": 0, "mus": [], "rows": [], "skipped": []}

    class Conn:
        def close(self):
            return None

    monkeypatch.setattr(card, "score_market", fake_score)
    monkeypatch.setattr(card, "get_connection", lambda: Conn())
    monkeypatch.setattr(card, "slate", lambda conn, game_date, now: {})
    now = datetime(2026, 10, 17, 16, tzinfo=timezone.utc)
    card.run_card(game_date="2026-10-17", now=now)
    assert len(seen) == len(np_.LIVE)
    assert len({id(c) for c in seen}) == 1
    assert isinstance(seen[0], np_.PlayerLogCache)
    assert seen[0].deadline_s == np_.PLAYER_LOG_DEADLINE_S

    seen.clear()
    shared = np_.PlayerLogCache(deadline_s=120, clock=_Clock())
    card.run_card(game_date="2026-10-17", now=now, log_cache=shared)
    assert seen and all(c is shared for c in seen)


class _CardConn:
    def __init__(self):
        self.calls: list[tuple[str, object]] = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self

    def fetchall(self):
        return []

    def close(self):
        return None


def _blocked_slate(monkeypatch, conn: _CardConn):
    monkeypatch.setattr(blocked, "get_connection", lambda: conn)
    monkeypatch.setattr(blocked, "slate", lambda conn, game_date, now: {
        "G1": {"home": "BOS", "away": "NYR", "commence_time": "2026-10-17T23:00:00Z"},
    })
    monkeypatch.setattr(blocked, "latest_quotes", lambda conn, games: pd.DataFrame([{
        "game_id": "G1", "player": "A Player", "line": 1.5,
        "over": -110, "under": -110,
    }]))
    monkeypatch.setattr(blocked, "candidates", lambda conn, teams, seasons: pd.DataFrame([{
        "player_id": 10, "player_name": "A Player", "pkey": bs.name_key("A Player"),
    }]))


def test_the_blocked_shots_card_passes_the_shared_cache(monkeypatch):
    """A player already in the cache is not read again. Without the cache
    argument the card would issue the one-player statement."""
    conn = _CardConn()
    _blocked_slate(monkeypatch, conn)
    cache = np_.PlayerLogCache(deadline_s=120, clock=_Clock())
    cache[("blocked", 10)] = []
    blocked.run_card(
        game_date="2026-10-17", do_publish=False, artifact={"model": object()},
        log_cache=cache, now=datetime(2026, 10, 17, 16, tzinfo=timezone.utc))
    assert conn.calls == []

    conn2 = _CardConn()
    _blocked_slate(monkeypatch, conn2)
    blocked.run_card(
        game_date="2026-10-17", do_publish=False, artifact={"model": object()},
        now=datetime(2026, 10, 17, 16, tzinfo=timezone.utc))
    player = [(sql, params) for sql, params in conn2.calls if "player_id = %s" in sql]
    assert len(player) == 1
    assert player[0][1] == (10,)


def test_the_scoring_step_shares_one_cache_across_both_cards(monkeypatch):
    import run_pipeline
    seen: list = []

    def fake_blocked(*_a, **k):
        seen.append(k["log_cache"])
        return {}

    def fake_props(*_a, **k):
        seen.append(k["log_cache"])
        return {"date": "2026-10-17"}

    monkeypatch.setattr("scripts.nhl_prop_card.run_card", fake_blocked)
    monkeypatch.setattr("scripts.nhl_props_card.run_card", fake_props)
    assert run_pipeline.step_nhl_prop_scoring(dry_run=True) is True
    assert len(seen) == 2 and seen[0] is seen[1]
    assert isinstance(seen[0], np_.PlayerLogCache)
    assert seen[0].deadline_s == np_.PLAYER_LOG_DEADLINE_S
