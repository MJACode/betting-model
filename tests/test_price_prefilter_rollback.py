"""A timed-out price pre-filter must not abort the rest of scoring.

Evening refresh run_id 82578720862b4c88990a974ff33ed81d, 2026-09-25 01:59:53Z:

    WARNING  NCAAF price pre-filter failed (canceling statement due to
             statement timeout); scoring all
    WARNING  Look-ahead price pre-filter failed (current transaction is
             aborted, commands ignored until end of transaction block);
             scoring all
    ERROR    Scorer failed: InFailedSqlTransaction(...)

The NCAAF statement_timeout aborted the psycopg2 transaction. The except
logged "scoring all" and kept going on the same connection, so every later
execute — including the look-ahead pre-filter that was supposed to be the
sibling fallback — raised InFailedSqlTransaction, and the scoring step failed.
"""

from __future__ import annotations

from pathlib import Path

import psycopg2
from loguru import logger

import models.scorer as scorer

_SRC = (Path(__file__).parent.parent / "models" / "scorer.py").read_text(
    encoding="utf-8")


_ABORTED = "current transaction is aborted, commands ignored until end of transaction block"


class _PoisonConn:
    """Postgres-shaped: a failed statement aborts the transaction until
    ROLLBACK TO SAVEPOINT or rollback()."""

    def __init__(self, games, *, fail_ncaaf=False, fail_lookahead=False,
                 reject_savepoint_rollback=False):
        self.games = games
        self.fail_ncaaf = fail_ncaaf
        self.fail_lookahead = fail_lookahead
        self.reject_savepoint_rollback = reject_savepoint_rollback
        self.aborted = False
        self.rollbacks = 0
        self.savepoint_rollbacks = 0
        self.closed = False
        self.events: list[tuple] = []
        self.last = ""

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        if self.aborted:
            if text.upper().startswith("ROLLBACK TO SAVEPOINT"):
                self.events.append(("savepoint_rollback_attempt", text))
                if self.reject_savepoint_rollback:
                    raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
                self.aborted = False
                self.savepoint_rollbacks += 1
                self.events.append(("savepoint_rollback", text))
                self.last = text
                return self
            self.events.append(("poisoned", text[:80]))
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        self.events.append(("exec", text[:80]))
        self.last = text
        if self.fail_ncaaf and "g.sport = 'NCAAF'" in text and "EXISTS" in text:
            self.aborted = True
            raise psycopg2.errors.QueryCanceled(
                "canceling statement due to statement timeout")
        if (self.fail_lookahead and "game_id = ANY" in text and "EXISTS" in text):
            self.aborted = True
            raise psycopg2.errors.QueryCanceled(
                "canceling statement due to statement timeout")
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        if "home_team" in self.last:
            return self.games
        return []

    def rollback(self):
        self.rollbacks += 1
        self.aborted = False
        self.events.append(("rollback",))

    def commit(self):
        if self.aborted:
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        self.events.append(("commit",))

    def close(self):
        self.closed = True


def _games():
    # commence_time in the past so the loop skips them before any feature
    # build. Both sports are present so a poisoned NCAAF pre-filter would
    # take down the look-ahead pre-filter, which is the production chain.
    started = "1999-01-01T00:00:00+00:00"
    return [
        ("NCAAF_2026-09-26_A_B", "NCAAF", 2026, "2026-09-26", "B", "A", started),
        ("MLB_2026-09-26_NYY_BOS", "MLB", 2026, "2026-09-26", "BOS", "NYY", started),
    ]


def _run(monkeypatch, conn):
    monkeypatch.setattr(scorer, "get_connection", lambda: conn)
    monkeypatch.setattr(scorer, "_get_postponed_games", lambda _date: set())
    seen: list[str] = []
    sink = logger.add(lambda m: seen.append(str(m)), level="WARNING",
                      format="{message}")
    try:
        result = scorer.run_scorer("2026-09-25", dry_run=False)
    finally:
        logger.remove(sink)
    return result, seen


def _event_index(conn, kind, contains=""):
    for i, ev in enumerate(conn.events):
        if ev[0] == kind and (not contains or contains in ev[-1]):
            return i
    return -1


def test_ncaaf_timeout_rolls_back_and_scoring_continues(monkeypatch):
    conn = _PoisonConn(_games(), fail_ncaaf=True)
    result, logs = _run(monkeypatch, conn)

    assert result["target_date"] == "2026-09-25"
    assert result["games"] == 2
    assert conn.closed
    assert not conn.aborted
    assert conn.savepoint_rollbacks >= 1, (
        "the timed-out pre-filter must ROLLBACK TO SAVEPOINT before scoring all")
    reset_at = _event_index(conn, "savepoint_rollback")
    lookahead = _event_index(conn, "exec", "game_id = ANY")
    assert reset_at != -1 and lookahead != -1 and reset_at < lookahead, (
        "the look-ahead pre-filter ran on the aborted transaction")
    assert any("pipeline_log" in ev[-1] for ev in conn.events if ev[0] == "exec")
    assert not any(ev[0] == "poisoned" for ev in conn.events)
    text = "\n".join(logs)
    assert "NCAAF price pre-filter failed" in text
    assert "scoring all" in text
    assert "Traceback" in text
    assert "QueryCanceled" in text
    assert _ABORTED not in text


def test_lookahead_timeout_rolls_back_and_scoring_continues(monkeypatch):
    conn = _PoisonConn(_games(), fail_lookahead=True)
    result, logs = _run(monkeypatch, conn)

    assert result["games"] == 2
    assert not conn.aborted
    assert conn.savepoint_rollbacks >= 1
    assert any("pipeline_log" in ev[-1] for ev in conn.events if ev[0] == "exec")
    assert not any(ev[0] == "poisoned" for ev in conn.events)
    text = "\n".join(logs)
    assert "Look-ahead price pre-filter failed" in text
    assert "scoring all" in text
    assert "Traceback" in text
    assert _ABORTED not in text


def test_a_failed_savepoint_rollback_falls_back_to_full_rollback(monkeypatch):
    """ROLLBACK TO SAVEPOINT can itself fail once the transaction is aborted.
    conn.rollback() is what clears InFailedSqlTransaction in that case."""
    conn = _PoisonConn(_games(), fail_ncaaf=True, reject_savepoint_rollback=True)
    result, logs = _run(monkeypatch, conn)

    assert result["games"] == 2
    assert conn.rollbacks >= 1, "full rollback was not invoked"
    assert not conn.aborted
    reset_at = _event_index(conn, "rollback")
    lookahead = _event_index(conn, "exec", "game_id = ANY")
    assert reset_at != -1 and lookahead != -1 and reset_at < lookahead
    assert not any(ev[0] == "poisoned" for ev in conn.events)
    assert _ABORTED not in "\n".join(logs)


def test_the_ncaaf_prefilter_does_not_distinct_scan_odds():
    """Pin the measured shape. SELECT DISTINCT on this window read 66,997
    odds rows (2026-09-25); EXISTS returned the same 124 game ids."""
    i = _SRC.index("        ncaaf_unpriced: set = set()")
    block = _SRC[i:_SRC.index("        ahead_unpriced: set = set()", i)]
    assert "EXISTS (" in block
    assert "g.sport = 'NCAAF'" in block
    assert "SELECT DISTINCT" not in block
    assert "_select_isolated" in block


def test_the_lookahead_prefilter_is_isolated_the_same_way():
    i = _SRC.index("        ahead_unpriced: set = set()")
    block = _SRC[i:_SRC.index("        # Check for postponed", i)]
    assert "game_id = ANY(?)" in block
    assert "EXISTS (" in block
    assert "SELECT DISTINCT" not in block
    assert "_select_isolated" in block
    assert "ahead_unpriced = set()" in block.split("except")[1]


def test_both_prefilters_timing_out_still_reaches_the_pipeline_log(monkeypatch):
    conn = _PoisonConn(_games(), fail_ncaaf=True, fail_lookahead=True)
    result, logs = _run(monkeypatch, conn)

    assert result["total_picks"] == 0
    assert conn.savepoint_rollbacks >= 2
    assert not conn.aborted
    assert any("pipeline_log" in ev[-1] for ev in conn.events if ev[0] == "exec")
    text = "\n".join(logs)
    assert "NCAAF price pre-filter failed" in text
    assert "Look-ahead price pre-filter failed" in text
    assert text.count("Traceback") >= 2
    assert _ABORTED not in text
