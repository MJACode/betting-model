"""A BYOM write must not stay open across the next odds read.

Measured 2026-11-04: worker_jobs 977491 (byom_prop_facts) was claimed at
15:00:13Z and left idle in transaction. Its last statement was the
nfl_odds_history read (`SELECT game_id, bookmaker, market, snapshot_at`),
and that session held RowExclusiveLock on byom_official_legs. The hourly
ALTER waited out lock_timeout behind it. The same shape is build_seasons
(commit only after every season) and refresh (game legs, then prop odds,
one commit).
"""
from __future__ import annotations

from datetime import date


class _Conn:
    def __init__(self):
        self._dirty = False
        self.events: list[tuple] = []

    def execute(self, sql, params=None):
        self.events.append(("execute", self._dirty))
        return self

    def fetchall(self):
        return [("row",)]

    def commit(self):
        self.events.append(("commit", self._dirty))
        self._dirty = False

    def rollback(self):
        self.events.append(("rollback", self._dirty))
        self._dirty = False


def test_a_quote_read_ends_before_the_caller_uses_the_rows():
    from byom.load import _fetch
    from byom.prop_load import _fetch as prop_fetch

    conn = _Conn()
    assert _fetch(conn, "SELECT game_id, bookmaker, market, snapshot_at", ()) == [
        ("row",)]
    assert conn.events == [("execute", False), ("rollback", False)]
    conn._dirty = True
    assert prop_fetch(conn, "SELECT 1", ()) == [("row",)]
    assert conn.events[-1] == ("execute", True)
    assert [e for e in conn.events if e[0] == "rollback"] == [("rollback", False)]


def _season_events(monkeypatch, module, facts):
    events = []

    class Conn:
        def __init__(self):
            self._dirty = False

        def commit(self):
            events.append(("commit", self._dirty))
            self._dirty = False

    def upsert_game(conn, rows):
        events.append(("write",))
        conn._dirty = True
        return 1

    def upsert_prop(conn, rows, keys):
        events.append(("write",))
        conn._dirty = True
        return 1

    def legs(conn, keys, rows, props):
        events.append(("legs", props, conn._dirty))
        conn._dirty = True
        return 1

    monkeypatch.setattr(module, "facts_for_season", facts)
    monkeypatch.setattr(module, "_upsert",
                        upsert_prop if module.__name__.endswith("prop_load") else upsert_game)
    monkeypatch.setattr("byom.load.write_official_legs", legs)
    return events, Conn()


def test_the_next_season_reads_odds_after_the_official_write_commits(monkeypatch):
    import byom.load as load

    def facts(conn, season, game_ids=None, sport="NFL"):
        load_events.append(("read", season, conn._dirty))
        return [{"canonical_key": str(season), "_official": [{"canonical_key": str(season)}]}]

    load_events, conn = _season_events(monkeypatch, load, facts)
    load.build_seasons(conn, [2024, 2025], apply=True, sport="NFL")
    second = load_events.index(("read", 2025, False))
    committed = load_events.index(("commit", True))
    assert committed < second
    assert ("read", 2024, False) in load_events
    assert ("legs", False, True) in load_events


def test_prop_seasons_commit_the_leg_write_before_the_next_odds_read(monkeypatch):
    import byom.prop_load as prop

    def facts(conn, season, game_ids=None, sport="NFL"):
        prop_events.append(("read", season, conn._dirty))
        return ([{"_official": [{"canonical_key": str(season)}]}], [str(season)])

    prop_events, conn = _season_events(monkeypatch, prop, facts)
    prop.build_seasons(conn, [2024, 2025], apply=True, sport="NFL")
    assert prop_events.index(("commit", True)) < prop_events.index(("read", 2025, False))
    assert ("read", 2024, False) in prop_events
    assert ("legs", True, True) in prop_events


def test_refresh_reads_prop_odds_after_the_game_legs_commit(monkeypatch):
    import byom.load as load
    import byom.prop_load as prop
    import byom.refresh as refresh

    events = []

    class Conn:
        def __init__(self):
            self._dirty = False

        def execute(self, sql, params=None):
            events.append(("mark", self._dirty))
            self._dirty = True
            return self

        def commit(self):
            events.append(("commit", self._dirty))
            self._dirty = False

    def game_facts(conn, season, game_ids=None, sport="NFL"):
        events.append(("game-read", conn._dirty))
        return [{"canonical_key": "k", "_official": [{"canonical_key": "k"}]}]

    def game_upsert(conn, rows):
        conn._dirty = True
        return 1

    def legs(conn, keys, rows, props):
        events.append(("legs", props))
        conn._dirty = True
        return 1

    def prop_facts(conn, season, game_ids=None, sport="NFL"):
        events.append(("prop-read", conn._dirty))
        return [], []

    def prop_upsert(conn, rows, keys):
        return 0

    monkeypatch.setattr(refresh, "_fact_rows", lambda *a, **k: {})
    monkeypatch.setattr(refresh, "_prop_keys", lambda *a, **k: set())
    monkeypatch.setattr(refresh, "due_games", lambda *a, **k: [{
        "game_id": "NFL_2026_01_A_B"}])
    monkeypatch.setattr(refresh, "freshness", lambda *a, **k: {
        "season": 2026, "as_of": "2026-11-04", "due": 1, "in_window": 1,
        "missing_game_facts": 0, "incomplete_game_facts": 0,
        "stale_game_facts": 0, "window_missing_prop_facts": 0, "writes": False,
    })
    monkeypatch.setattr(load, "facts_for_season", game_facts)
    monkeypatch.setattr(load, "_upsert", game_upsert)
    monkeypatch.setattr(load, "write_official_legs", legs)
    monkeypatch.setattr(prop, "facts_for_season", prop_facts)
    monkeypatch.setattr(prop, "_upsert", prop_upsert)

    refresh.refresh(Conn(), apply=True, today=date(2026, 11, 4))
    prop_at = events.index(("prop-read", False))
    assert events.index(("commit", True)) < prop_at
    assert ("game-read", False) in events
    assert events[prop_at][1] is False


def test_byom_jobs_open_with_their_own_idle_timeout():
    import inspect

    from tracking.job_queue import (
        _byom_connection,
        _job_byom_game_facts,
        _job_byom_prop_facts,
        _job_byom_refresh,
    )

    for fn in (_job_byom_game_facts, _job_byom_prop_facts, _job_byom_refresh):
        assert "_byom_connection()" in inspect.getsource(fn)
    src = inspect.getsource(_byom_connection)
    assert "idle_in_transaction_ms=POLLER_IDLE_IN_TRANSACTION_MS" in src
