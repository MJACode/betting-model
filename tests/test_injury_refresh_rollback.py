"""A timed-out statement in injuries-refresh must not become
"current transaction is aborted".

Hourly runs on 2026-10-01, pipeline_log log_id 115154 (20:21:07Z) and
115196 (21:02:06Z), step=injury, status=error, error_msg exactly:

    current transaction is aborted, commands ignored until end of transaction block

Postgres cancelled the statement for statement_timeout first. The ingestor
caught that (the name seed, or the return-ramp read on the shared
connection), did not roll back, and the next command raised the follow-on.
That follow-on is what pipeline_log stored.
"""
from __future__ import annotations

from pathlib import Path

import psycopg2
import pytest

import data.ingestors.injury_ingestor as inj
import run_pipeline as rp

_ABORTED = "current transaction is aborted, commands ignored until end of transaction block"
_TIMEOUT = "canceling statement due to statement timeout"


class _TimeoutConn:
    """execute() aborts the transaction the way statement_timeout does.
    close() refuses to run while the transaction is still aborted."""

    def __init__(self):
        self.aborted = False
        self.rollbacks = 0
        self.closed = False
        self.commits = 0

    def execute(self, sql, params=None):
        self.aborted = True
        raise psycopg2.errors.QueryCanceled(_TIMEOUT)

    def rollback(self):
        self.rollbacks += 1
        self.aborted = False

    def commit(self):
        if self.aborted:
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        self.commits += 1

    def close(self):
        assert not self.aborted, "closed an aborted transaction without ROLLBACK"
        self.closed = True


class _RampConn:
    """The return-ramp SELECT times out. Every later statement on this
    connection raises InFailedSqlTransaction until rollback()."""

    def __init__(self, *, fail_ramp=True, fail_names=False):
        self.aborted = False
        self.fail_ramp = fail_ramp
        self.fail_names = fail_names
        self.events: list[tuple] = []

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        # ROLLBACK TO SAVEPOINT is legal in an aborted transaction and is
        # what clears it. Every other command is not.
        if self.aborted and not text.upper().startswith("ROLLBACK TO SAVEPOINT"):
            self.events.append(("poisoned", text[:80], params))
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        if text.upper().startswith("ROLLBACK TO SAVEPOINT"):
            self.aborted = False
            self.events.append(("savepoint_rollback", text, params))
            return self
        if (self.fail_ramp and "activation_date" in text
                and "FROM injuries" in text):
            self.aborted = True
            self.events.append(("timeout", text[:80], params))
            raise psycopg2.errors.QueryCanceled(_TIMEOUT)
        self.events.append(("exec", text, params))
        return self

    def executemany(self, sql, rows):
        text = " ".join(sql.split())
        if self.aborted:
            self.events.append(("poisoned", text[:80], rows))
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        if self.fail_names and "injury_player_names" in text:
            self.aborted = True
            self.events.append(("names_missing", text[:80], rows))
            raise psycopg2.errors.UndefinedTable(
                'relation "injury_player_names" does not exist')
        self.events.append(("executemany", text, rows))

    def fetchall(self):
        return []

    def fetchone(self):
        return None

    def rollback(self):
        self.events.append(("rollback", "", None))
        self.aborted = False

    def commit(self):
        if self.aborted:
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        self.events.append(("commit", "", None))

    def close(self):
        self.events.append(("close", "", None))


def _injury(sport="NHL"):
    return {
        "sport": sport,
        "team": "SEA",
        "player_name": "Julio Rodriguez",
        "player_id": "9",
        "status": "Out",
        "injury_type": "oblique",
        "scenario": "A",
        "severity_weight": 0.7,
        "return_ramp_factor": None,
        "games_since_return": None,
        "activation_date": None,
        "report_date": "2026-10-01",
        "status_ts": None,
    }


def _kind_index(conn, kind):
    for i, ev in enumerate(conn.events):
        if ev[0] == kind:
            return i
    return -1


def _error_msgs(conn):
    msgs = []
    for ev in conn.events:
        if ev[0] != "exec" or "pipeline_log" not in ev[1] or not ev[2]:
            continue
        if ev[2][1] == "error":
            msgs.append(ev[2][5])
    return msgs


@pytest.fixture(autouse=True)
def _clear_seed_state():
    inj._ATHLETE_NAME_CACHE = {}
    inj._SEED_DB_ERROR = None
    inj._SEED_ATTEMPTED = False
    yield
    inj._ATHLETE_NAME_CACHE = {}
    inj._SEED_DB_ERROR = None
    inj._SEED_ATTEMPTED = False


def test_a_ramp_timeout_rolls_back_and_the_logged_error_is_the_timeout(monkeypatch):
    conn = _RampConn()
    monkeypatch.setattr(inj, "get_connection", lambda: conn)
    monkeypatch.setattr(inj, "fetch_espn_injuries", lambda sport, report_date: [_injury(sport)])
    monkeypatch.setattr(inj, "fetch_mlb_transactions", lambda report_date: [])

    with pytest.raises(psycopg2.errors.QueryCanceled):
        inj.run_injury_ingestor(sport="NHL", report_date="2026-10-01")

    assert not any(ev[0] == "poisoned" for ev in conn.events), (
        "a later statement ran on the aborted transaction"
    )
    rolled = _kind_index(conn, "rollback")
    inserted = _kind_index(conn, "executemany")
    assert rolled != -1 and inserted != -1 and rolled < inserted, (
        "the injury insert ran before the timed-out statement was rolled back"
    )
    msgs = _error_msgs(conn)
    assert msgs, "pipeline_log did not record the failure"
    assert "QueryCanceled" in msgs[-1]
    assert "statement timeout" in msgs[-1]
    assert _ABORTED not in msgs[-1]


def test_a_timed_out_name_seed_is_rolled_back_and_is_the_step_error(monkeypatch):
    main = _RampConn(fail_ramp=False)
    seed = _TimeoutConn()
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return main if calls["n"] == 1 else seed

    monkeypatch.setattr(inj, "get_connection", factory)
    import data.db as db
    monkeypatch.setattr(db, "get_connection", factory)

    def fetch(sport, report_date):
        inj._seed_athlete_cache()
        return [_injury(sport)]

    monkeypatch.setattr(inj, "fetch_espn_injuries", fetch)

    with pytest.raises(psycopg2.errors.QueryCanceled):
        inj.run_injury_ingestor(sport="NHL", report_date="2026-10-01")

    assert seed.rollbacks >= 1
    assert seed.closed
    assert not seed.aborted
    assert not any(ev[0] == "poisoned" for ev in main.events)
    msgs = _error_msgs(main)
    assert msgs and "statement timeout" in msgs[-1]
    assert _ABORTED not in msgs[-1]
    assert _kind_index(main, "executemany") != -1


def test_an_empty_name_table_is_backfilled_and_the_fill_is_committed(monkeypatch):
    class _Conn:
        def __init__(self):
            self.fetches = 0
            self.committed = False
            self.sqls: list[str] = []
            self.closed = False

        def execute(self, sql, params=None):
            self.sqls.append(" ".join(sql.split()))
            return self

        def fetchall(self):
            self.fetches += 1
            if self.fetches == 1:
                return []
            return [("9", "Julio Rodriguez")]

        def executemany(self, sql, rows):
            assert rows == [{"player_id": "9", "player_name": "Julio Rodriguez"}]
            self.sqls.append("INSERT injury_player_names")

        def commit(self):
            self.committed = True

        def rollback(self):
            assert self.committed, "rollback discarded the name backfill"

        def close(self):
            self.closed = True

    conn = _Conn()
    import data.db as db
    monkeypatch.setattr(db, "get_connection", lambda *a, **k: conn)
    assert inj._seed_athlete_cache() == 1
    assert inj._ATHLETE_NAME_CACHE["9"] == "Julio Rodriguez"
    assert conn.committed and conn.closed
    assert any("DISTINCT ON (player_id)" in s for s in conn.sqls)
    assert any("injury_player_names" in s for s in conn.sqls)


def test_a_seed_timeout_rolls_back_before_close(monkeypatch):
    conn = _TimeoutConn()
    import data.db as db
    monkeypatch.setattr(db, "get_connection", lambda *a, **k: conn)
    assert inj._seed_athlete_cache() == 0
    assert conn.rollbacks >= 1
    assert conn.closed
    assert isinstance(inj._SEED_DB_ERROR, psycopg2.errors.QueryCanceled)
    # a second sport in the same process must not scan again
    assert inj._seed_athlete_cache() == 0
    assert conn.rollbacks == 1


def test_a_failed_name_upsert_does_not_drop_the_injury_insert(monkeypatch):
    """The names table is new. Until the migration has run, that INSERT
    raises and aborts the transaction. The injury rows must still commit."""
    conn = _RampConn(fail_ramp=False, fail_names=True)
    monkeypatch.setattr(inj, "get_connection", lambda: conn)
    monkeypatch.setattr(inj, "fetch_espn_injuries",
                        lambda sport, report_date: [_injury(sport)])

    result = inj.run_injury_ingestor(sport="NHL", report_date="2026-10-01")
    assert result["rows_inserted"] == 1
    assert _kind_index(conn, "savepoint_rollback") != -1
    assert not any(ev[0] == "poisoned" for ev in conn.events)
    injury_insert = next(
        i for i, ev in enumerate(conn.events)
        if ev[0] == "executemany" and "INTO injuries" in ev[1]
    )
    committed = _kind_index(conn, "commit")
    assert injury_insert < committed
    assert _error_msgs(conn) == []


def test_a_missing_name_table_stays_a_cold_cache_and_the_ingest_succeeds(monkeypatch):
    """UndefinedTable is not a statement timeout. The seed rolls back and the
    injuries still insert; failing the step here would red every pass until
    the migration landed."""
    main = _RampConn(fail_ramp=False)

    class _Missing(_TimeoutConn):
        def execute(self, sql, params=None):
            self.aborted = True
            raise psycopg2.errors.UndefinedTable(
                'relation "injury_player_names" does not exist')

    seed = _Missing()
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return main if calls["n"] == 1 else seed

    monkeypatch.setattr(inj, "get_connection", factory)
    import data.db as db
    monkeypatch.setattr(db, "get_connection", factory)
    def fetch(sport, report_date):
        inj._seed_athlete_cache()
        return [_injury(sport)]

    monkeypatch.setattr(inj, "fetch_espn_injuries", fetch)

    result = inj.run_injury_ingestor(sport="NHL", report_date="2026-10-01")
    assert result["rows_inserted"] == 1
    assert seed.rollbacks >= 1 and seed.closed and not seed.aborted
    assert _error_msgs(main) == []
    assert not any(ev[0] == "poisoned" for ev in main.events)


def test_freshness_probe_rolls_back_a_timeout_before_close(monkeypatch):
    conn = _TimeoutConn()
    import data.db as db
    monkeypatch.setattr(db, "get_connection", lambda *a, **k: conn)
    assert rp._minutes_since("SELECT created_at FROM injuries ORDER BY injury_id DESC LIMIT 1") is None
    assert conn.rollbacks >= 1
    assert conn.closed


def test_injury_freshness_uses_the_primary_key():
    src = (Path(__file__).parent.parent / "run_pipeline.py").read_text(encoding="utf-8")
    block = src[src.index("def step_injuries"):src.index("\ndef step_player_news")]
    call = block[block.index("_is_fresh"):]
    assert "ORDER BY injury_id DESC LIMIT 1" in call
    assert "MAX(created_at)" not in call
