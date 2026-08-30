"""One failed game must not silently void the rest of a backfill.

Postgres poisons a connection after a failed statement — every later command
returns "current transaction is aborted, commands ignored until end of
transaction block" until someone rolls back. `backfill_pbp` caught per-game
exceptions and carried on WITHOUT rolling back, so a single conflict early in a
multi-hour run turned every remaining game into the same error while the run
ended on a SUCCESS line.

Observed 2026-08-30: a unique-key conflict around game 600 of 1,818 left the
remaining ~2,200 schedule entries "processed" and nothing written, reported as
`PBP backfill 2026-2026 complete: 0/2869 games, 0 plays`. Exit code 0. The only
evidence anything was wrong was a row count that had stopped climbing.
"""
from __future__ import annotations

import io
import re
from pathlib import Path

SRC = (Path(__file__).parent.parent
       / "data/ingestors/mlb_pbp_ingestor.py").read_text(encoding="utf-8")


def _backfill_body() -> str:
    start = SRC.index("def backfill_pbp")
    return SRC[start:]


def test_a_failed_game_rolls_the_connection_back():
    """Without this the next game gets 'current transaction is aborted'."""
    body = _backfill_body()
    handler = body[body.index("ingest error"):]
    window = body[max(0, body.index("ingest error") - 900):body.index("ingest error")]
    assert "conn.rollback()" in window, (
        "the per-game exception handler must roll back — otherwise one failure "
        "silently voids every game after it")
    assert handler  # keep the slice meaningful


def test_the_rollback_cannot_itself_raise():
    """A rollback on an already-dead connection must not end the run."""
    body = _backfill_body()
    i = body.index("conn.rollback()")
    guard = body[i - 120:i + 160]
    assert "try:" in guard and "except" in guard, (
        "conn.rollback() needs its own try/except — a dead connection would "
        "otherwise turn a skippable game into a crashed backfill")


def test_errors_are_counted_not_just_logged():
    """A count is what lets the summary tell success from silent failure."""
    body = _backfill_body()
    assert 'totals["errors"] += 1' in body
    assert '"errors": 0' in SRC, "totals must initialise the errors counter"


def test_a_run_that_wrote_nothing_reports_an_error_not_a_success():
    """The failure mode was a SUCCESS line over a run that wrote zero rows."""
    body = _backfill_body()
    assert re.search(r'if totals\["errors"\] and not totals\["games_loaded"\]', body), (
        "the summary must distinguish 'nothing to do' from 'everything failed'")
    tail = body[body.index('if totals["errors"] and not totals["games_loaded"]'):]
    assert "logger.error" in tail[:600], (
        "a run that errored on every game must log at ERROR, not SUCCESS")


def test_partial_failures_are_surfaced_too():
    body = _backfill_body()
    i = body.index('if totals["errors"] and not totals["games_loaded"]')
    assert "logger.warning" in body[i:i + 900], (
        "a run that wrote some games and errored on others must say so — "
        "the backfill is idempotent, so the fix is simply to re-run")
