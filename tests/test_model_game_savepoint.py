"""One model-game SQL failure must not abort the rest of the game.

Daily run 51e965f8023c4b0e86e03fe075af1f9c, 2026-09-28 10:36:24Z. Postgres
cancelled a statement at statement_timeout, then logged six
"current transaction is aborted" errors. The scorer recorded only the cascade:

    NHL_2026-09-29_VAN_EDM/nhl_moneyline FAILED: InFailedSqlTransaction(...)
    NHL_2026-09-29_VAN_EDM/nhl_moneyline_regulation FAILED: InFailedSqlTransaction(...)

psycopg2 commit() on an aborted transaction rolls the game back and returns,
so the next game still ran and the original error never reached pipeline_log.
"""

from __future__ import annotations

import psycopg2
import pytest
from loguru import logger

import models.scorer as scorer

_ABORTED = "current transaction is aborted, commands ignored until end of transaction block"
_TIMEOUT = "canceling statement due to statement timeout"


class _PoisonConn:
    """A failed statement aborts the transaction until ROLLBACK TO SAVEPOINT."""

    def __init__(self, games):
        self.games = games
        self.aborted = False
        self.closed = False
        self.events: list[tuple] = []
        self.last = ""
        self._conn = self

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        if self.aborted:
            if text.upper().startswith("ROLLBACK TO SAVEPOINT"):
                self.aborted = False
                self.events.append(("savepoint_rollback", text))
                self.last = text
                return self
            self.events.append(("poisoned", text[:80]))
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        self.events.append(("exec", text[:120]))
        self.last = text
        upper = text.upper()
        if upper.startswith("SAVEPOINT") or upper.startswith("RELEASE SAVEPOINT"):
            return self
        if "fail_moneyline" in text or "best_price_timeout" in text:
            self.aborted = True
            raise psycopg2.errors.QueryCanceled(_TIMEOUT)
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        if "home_team" in self.last:
            return self.games
        return []

    def rollback(self):
        self.aborted = False
        self.events.append(("rollback",))

    def commit(self):
        if self.aborted:
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        self.events.append(("commit",))

    def close(self):
        self.closed = True


def _games():
    return [(
        "NHL_2026-09-29_VAN_EDM", "NHL", 2026, "2026-09-28",
        "EDM", "VAN", "2099-01-01T00:00:00+00:00",
    )]


def test_a_model_sql_error_does_not_poison_the_next_model(monkeypatch):
    conn = _PoisonConn(_games())
    seen: list[str] = []
    scored: list[str] = []

    def fake_score(conn, game_id, model_id, *args, **kwargs):
        scored.append(model_id)
        if model_id == "nhl_moneyline":
            conn.execute("SELECT fail_moneyline")
        else:
            conn.execute(f"SELECT ok_{model_id}")
        return []

    monkeypatch.setattr(scorer, "get_connection", lambda: conn)
    monkeypatch.setattr(scorer, "_get_postponed_games", lambda _date: set())
    monkeypatch.setattr(scorer, "build_nhl_game_features", lambda *a, **k: {"x": 1})
    monkeypatch.setattr(scorer, "_get_dk_odds", lambda *a, **k: None)
    monkeypatch.setattr(scorer, "score_game", fake_score)
    sink = logger.add(lambda m: seen.append(str(m)), level="ERROR", format="{message}")
    try:
        with pytest.raises(RuntimeError, match="nhl_moneyline") as raised:
            scorer.run_scorer("2026-09-28", dry_run=False)
    finally:
        logger.remove(sink)

    assert scored[0] == "nhl_moneyline"
    assert "nhl_moneyline_regulation" in scored
    # nhl_over_under is a rule card since 2026-10-08; the generic loop
    # must not score it.
    assert "nhl_over_under" not in scored
    assert "nhl_puckline" in scored
    assert any(ev[0] == "savepoint_rollback" for ev in conn.events)
    reset_at = next(i for i, ev in enumerate(conn.events) if ev[0] == "savepoint_rollback")
    next_ok = next(i for i, ev in enumerate(conn.events)
                   if ev[0] == "exec" and "ok_nhl_moneyline_regulation" in ev[1])
    assert reset_at < next_ok
    assert not any(ev[0] == "poisoned" for ev in conn.events)
    assert not conn.aborted
    assert any(ev[0] == "commit" for ev in conn.events)
    text = "\n".join(seen) + "\n" + str(raised.value)
    assert "QueryCanceled" in text
    assert _TIMEOUT in text
    assert _ABORTED not in text
    assert "Traceback" in text


def test_a_best_price_timeout_is_the_logged_error_and_the_next_lookup_runs():
    conn = _PoisonConn([])
    calls = {"n": 0}

    def lookup():
        calls["n"] += 1
        conn.execute("SELECT best_price_timeout" if calls["n"] == 1 else "SELECT best_price_ok")
        return {"book": "draftkings", "odds": -110}

    seen: list[str] = []
    sink = logger.add(lambda m: seen.append(str(m)), level="WARNING", format="{message}")
    try:
        first = scorer._fail_open(conn, "sp_best_price", lookup, None, "best-price lookup")
        second = scorer._fail_open(conn, "sp_best_price", lookup, None, "best-price lookup")
    finally:
        logger.remove(sink)

    assert first is None
    assert second == {"book": "draftkings", "odds": -110}
    assert not conn.aborted
    assert not any(ev[0] == "poisoned" for ev in conn.events)
    text = "\n".join(seen)
    assert "QueryCanceled" in text
    assert _TIMEOUT in text
    assert "Traceback" in text
    assert _ABORTED not in text
