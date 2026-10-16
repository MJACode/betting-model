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


def _flat(sql: str) -> str:
    return " ".join(sql.split())


# pg_stat_activity at 2026-10-16 01:33Z, after the 01:30Z (9:30 PM ET)
# pollers restart. Both backends were idle in transaction from xact_start
# 01:30:00Z. Whitespace in the live query matched the deployed source;
# these are that statement with the bind parameters left in.
_LEADER_DATES_SQL = """
    SELECT DISTINCT game_date FROM picks
    WHERE model_id = %s AND is_live = TRUE
      AND signal_type = 'BET' AND result IS NULL
      AND game_date >= %s
"""
_CREDIT_SQL = """
    SELECT COALESCE(SUM(credits), 0) FROM api_call_log
    WHERE host = 'api.the-odds-api.com'
      AND source = 'pregame_poller'
      AND ts >= date_trunc('day', now() AT TIME ZONE 'America/New_York')
"""


def test_standing_bets_release_the_picks_read():
    conn = _Rec()
    seen = {}

    class Rows:
        def fetchall(self_inner):
            return [("2026-10-08",)]

    def execute(sql, params=None):
        seen["sql"] = sql
        seen["params"] = params
        return Rows()

    conn.execute = execute
    assert G.unsettled_bet_dates(conn) == {"2026-10-08"}
    assert conn.rolls == 1
    # The 01:30Z leader session's last query, pid 1627157.
    assert _flat(seen["sql"]) == _flat(_LEADER_DATES_SQL)
    assert seen["params"][0] == "nfl_live_leader_ml"
    src = inspect.getsource(G.unsettled_bet_dates)
    assert src.index("execute") < src.index("finally")
    assert "release_read" in src[src.index("finally"):]


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

    conn = _Rec()
    seen = {}

    class Rows:
        def fetchone(self_inner):
            return (0,)

    def execute(sql, params=None):
        seen["sql"] = sql
        return Rows()

    conn.execute = execute
    assert _credits_used_today(conn) == 0.0
    assert conn.rolls == 1
    # The 01:30Z pregame session's last query, pid 1627156. query_start had
    # moved to 01:33:30Z inside the transaction opened at 01:30:00Z.
    assert _flat(seen["sql"]) == _flat(_CREDIT_SQL)


def test_the_credit_tick_is_shorter_than_the_idle_backstop():
    """A quiet pregame tick re-runs the credit SUM every interval. At 30s
    that session is never idle for the 60s backstop, so the timeout does
    not end the transaction the 01:30Z restart reopened. The rollback in
    _credits_used_today does."""
    import config
    assert config.PREGAME_POLL_INTERVAL_SEC * 1000 < db.POLLER_IDLE_IN_TRANSACTION_MS


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
    from data.ingestors.pregame_line_poller import run_forever
    for fn in (dk.poll_once, bovada.poll_once, dk._ensure_schema):
        src = inspect.getsource(fn)
        assert "release_read" in src
    for fn in (dk.run, bovada.run, G.main, run_forever):
        src = inspect.getsource(fn)
        assert src.index("use_poller_session()") < src.index("get_connection()")


def test_migration_lock_timeout_is_short_and_local():
    """SET, not SET LOCAL, would leak onto the CLV backfill that shares
    the connection. A separate execute would mark the transaction dirty
    (data.db counts SET as a write), so the timeout travels in the same
    statement as the file and a pooler drop replays both. 120s is
    statement_timeout, which is the wait that queued the writers."""
    import data.view_migrations as vm
    assert MIGRATION_LOCK_TIMEOUT == "5s"
    assert vm.LOCK_TIMEOUT == MIGRATION_LOCK_TIMEOUT
    src = inspect.getsource(vm._with_lock_timeout)
    assert "SET LOCAL lock_timeout" in src
    assert "SET lock_timeout" not in src.replace("SET LOCAL lock_timeout", "")
    apply_src = inspect.getsource(apply_view_migrations)
    # The file text is an argument of _apply_one, which prefixes SET LOCAL
    # in the same execute. Source order on that line is the call, then the read.
    line = next(ln for ln in apply_src.splitlines() if "path.read_text" in ln)
    assert "_apply_one" in line and "path.read_text" in line


def test_a_lock_timeout_fails_that_file_and_the_next_still_runs(tmp_path, monkeypatch):
    (tmp_path / "a.sql").write_text("SELECT BOOM", encoding="utf-8")
    (tmp_path / "b.sql").write_text("SELECT 2", encoding="utf-8")
    import data.view_migrations as vm
    monkeypatch.setattr(vm.time, "sleep", lambda _s: None)
    monkeypatch.setattr(vm, "MIGRATIONS_DIR", tmp_path)
    monkeypatch.setattr(vm, "ACTIVE_MIGRATIONS", ["a.sql", "b.sql"])
    conn = _Rec()
    result = apply_view_migrations(conn)
    assert result.applied == 1
    assert result.failed_names == ("a.sql",)
    assert conn.rolls == vm.LOCK_ATTEMPTS
    assert conn.commits == 1
    assert any("SELECT 2" in s for s in conn.sql)
    # The timeout is in the same statement as the file, so a reconnect
    # replays both. "lock timeout" in the error is retried; three misses
    # fail the file and the next file still runs.
    booms = [s for s in conn.sql if "BOOM" in s]
    assert len(booms) == vm.LOCK_ATTEMPTS
    for sent in booms:
        assert sent.startswith(
            f"SET LOCAL lock_timeout = '{MIGRATION_LOCK_TIMEOUT}';")
        assert "SELECT BOOM" in sent


def test_clv_method_migration_is_still_one_statement():
    sql = (Path(__file__).parent.parent / "data" / "migrations"
           / "add_clv_method_2026_09_14.sql").read_text(encoding="utf-8")
    assert sql.count("$$") == 2
    assert sql.strip().endswith(";")
