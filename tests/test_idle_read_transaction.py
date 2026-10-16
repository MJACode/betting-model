"""Read-only polls must not sit idle in a transaction.

Measured 2026-10-16 on vvprgnrmzeekokzkrkfu. Two sessions were idle in
transaction and holding AccessShareLock:

  * pregame poller, xact_start 2026-10-15 22:32:58Z, last query the credit
    SUM on api_call_log. Still open at 01:10Z. A quiet tick never committed,
    so every later tick reused that one transaction.
  * nfl_live_leader, xact_start 2026-10-16 00:20:00Z, last query the standing
    BET dates on picks. The loop keeps one connection and does not touch the
    database again until a 4th-quarter window, so the lock lived for the game.

add_clv_method ran ALTER TABLE on picks every pass. That lock is
AccessExclusive even when the column already exists, so it waited out
statement_timeout behind the leader's AccessShareLock, and while it waited
every other lock request on picks queued behind it. pipeline_runs from
00:20Z through 01:00Z are 37 steps, failed_steps exactly
apply-view-migrations. The 00:10Z pass, before that transaction, succeeded.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import data.db as db
from data.ingestors.pregame_line_poller import _credits_used_today, poll_once
from data.view_migrations import MIGRATION_LOCK_TIMEOUT, apply_view_migrations
from nfl_live_leader import gameday as G
from nfl_live_leader.state import EventMeta


class _Rec:
    def __init__(self, dirty: bool = False):
        self._dirty = dirty
        self.rolls = 0
        self.commits = 0
        self.sql: list[str] = []

    def execute(self, sql, params=None):
        self.sql.append(sql)
        if "BOOM" in sql:
            raise RuntimeError("canceling statement due to lock timeout")
        return self

    def fetchall(self):
        return []

    def fetchone(self):
        return None

    def commit(self):
        self.commits += 1
        self._dirty = False

    def rollback(self):
        self.rolls += 1
        self._dirty = False

    def close(self):
        pass


def test_release_read_ends_a_clean_transaction_and_leaves_a_dirty_one():
    clean = _Rec()
    db.release_read(clean)
    assert clean.rolls == 1
    dirty = _Rec(dirty=True)
    db.release_read(dirty)
    assert dirty.rolls == 0


def test_a_poller_session_sets_the_idle_timeout_and_only_then(monkeypatch):
    monkeypatch.delenv("DB_IDLE_IN_TRANSACTION_TIMEOUT_MS", raising=False)
    monkeypatch.delenv("DB_STATEMENT_TIMEOUT_MS", raising=False)
    assert db._session_options() is None
    db.use_poller_session()
    opts = db._session_options()
    assert f"idle_in_transaction_session_timeout={db.POLLER_IDLE_IN_TRANSACTION_MS}" in opts
    assert db.POLLER_IDLE_IN_TRANSACTION_MS <= 60_000
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "120000")
    both = db._session_options()
    assert "statement_timeout=120000" in both
    assert "idle_in_transaction_session_timeout=" in both


def test_standing_bets_release_the_picks_read():
    conn = _Rec()
    conn.fetchall = lambda: [("2026-10-08",)]
    # execute returns self, and unsettled_bet_dates calls .fetchall() on that.
    class Rows:
        def fetchall(self_inner):
            return [("2026-10-08",)]

    conn.execute = lambda sql, params=None: Rows()
    assert G.unsettled_bet_dates(conn) == {"2026-10-08"}
    assert conn.rolls == 1


def test_a_locked_bet_releases_the_lock_check(monkeypatch):
    import models.scorer as sc
    monkeypatch.setattr(sc, "_locked_live_lanes", lambda conn, gid, mids: {G.MODEL_ID})
    monkeypatch.setattr(sc, "_insert_picks", lambda conn, picks: (_ for _ in ()).throw(
        AssertionError("a locked lane must not insert")))
    conn = _Rec()
    assert G.write_bet(conn, {"game_id": "g", "pick_label": "TB ML (live)"}) is False
    assert conn.rolls == 1 and conn.commits == 0


def test_an_unresolved_game_releases_the_context_read(monkeypatch):
    monkeypatch.setattr(G, "resolve_game", lambda *a, **k: None)
    meta = EventMeta(event_id="E1", date="2026-10-09T00:15Z", home_id="6",
                     away_id="27", home_abbr="DAL", away_abbr="TB",
                     status_ref=None, situation_ref=None, plays_ref=None,
                     season_type=2)
    conn = _Rec()
    assert G.load_context(conn, meta) is None
    assert conn.rolls == 1


def test_is_locked_releases_the_read(monkeypatch):
    import models.scorer as sc
    monkeypatch.setattr(sc, "_locked_live_lanes", lambda conn, gid, mids: set())
    conn = _Rec()
    assert G.is_locked(conn, "g") is False
    assert conn.rolls == 1


def test_the_credit_read_ends_before_the_caller_can_block_on_the_network():
    src = inspect.getsource(_credits_used_today)
    assert src.index("api_call_log") < src.index("finally")
    assert "release_read" in src[src.index("finally"):]
    tick = inspect.getsource(poll_once)
    # The docstring names the fetch. The call order is what holds the lock
    # across the network, so match the calls.
    assert tick.index("used = _credits_used_today") < tick.index("fetched = fetch_pregame_rows")


def test_a_quiet_tick_rolls_the_read_back(monkeypatch):
    import data.ingestors.odds_ingestor as oi
    monkeypatch.setattr(oi, "fetch_pregame_rows", lambda sports: [], raising=False)
    conn = _Rec()

    class Rows:
        def fetchone(self_inner):
            return (0,)

        def fetchall(self_inner):
            return []

    conn.execute = lambda sql, params=None: Rows()
    out = poll_once(conn, sports=["MLB"], score=False, known={})
    assert out["written"] == 0
    assert conn.rolls >= 1


def test_a_tick_that_writes_does_not_roll_the_insert_back(monkeypatch):
    import config
    import data.ingestors.odds_ingestor as oi
    from data.ingestors.pregame_line_poller import PRICE_COLS
    row = {"game_id": "g1", "market": "h2h",
           "bookmaker": config.ODDS_API_BOOKMAKER, "snapshot_type": "open"}
    row.update({c: None for c in PRICE_COLS})
    events = []
    monkeypatch.setattr(oi, "fetch_pregame_rows",
                        lambda sports: [row], raising=False)
    monkeypatch.setattr(oi, "_insert_odds", lambda conn, rows: events.append("insert"),
                        raising=False)
    conn = _Rec()

    class Rows:
        def fetchone(self_inner):
            return (0,)

        def fetchall(self_inner):
            return []

    conn.execute = lambda sql, params=None: Rows()
    conn.commit = lambda: events.append("commit")
    conn.rollback = lambda: events.append("rollback")
    out = poll_once(conn, sports=["MLB"], score=False, known={})
    assert out["written"] == 1
    assert "insert" in events and "commit" in events
    assert events.index("rollback") < events.index("commit")
    assert events[-1] == "commit"


def test_the_other_long_lived_feeds_release_a_quiet_tick():
    import data.ingestors.bovada_direct_feed as bovada
    import data.ingestors.dk_direct_feed as dk
    for fn in (dk.poll_once, bovada.poll_once, dk._ensure_schema):
        src = inspect.getsource(fn)
        assert "release_read" in src
    for fn in (dk.run, bovada.run, G.main):
        assert "use_poller_session" in inspect.getsource(fn)


def test_migration_lock_timeout_is_short_and_local():
    """SET, not SET LOCAL, would leak onto the CLV backfill that shares
    the connection. 120s is statement_timeout, which is the wait that
    queued the writers."""
    assert MIGRATION_LOCK_TIMEOUT == "5s"
    src = inspect.getsource(apply_view_migrations)
    assert "SET LOCAL lock_timeout" in src
    assert src.index("SET LOCAL lock_timeout") < src.index("path.read_text")


def test_a_lock_timeout_fails_that_file_and_the_next_still_runs(tmp_path, monkeypatch):
    (tmp_path / "a.sql").write_text("SELECT BOOM", encoding="utf-8")
    (tmp_path / "b.sql").write_text("SELECT 2", encoding="utf-8")
    import data.view_migrations as vm
    monkeypatch.setattr(vm, "MIGRATIONS_DIR", tmp_path)
    monkeypatch.setattr(vm, "ACTIVE_MIGRATIONS", ["a.sql", "b.sql"])
    conn = _Rec()
    n = apply_view_migrations(conn)
    assert n == 1
    assert conn.rolls >= 1
    assert conn.commits == 1
    assert any("lock_timeout" in s for s in conn.sql)
    assert any("SELECT 2" in s for s in conn.sql)
    # The timeout is inside the file's own transaction, ahead of the file.
    boom_at = next(i for i, s in enumerate(conn.sql) if "BOOM" in s)
    assert "lock_timeout" in conn.sql[boom_at - 1]


def test_clv_method_migration_is_still_one_statement():
    sql = (Path(__file__).parent.parent / "data" / "migrations"
           / "add_clv_method_2026_09_14.sql").read_text(encoding="utf-8")
    assert sql.count("$$") == 2
    assert sql.strip().endswith(";")
