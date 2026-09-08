"""
The game scorer commits ONE GAME AT A TIME (2026-09-08).

Until 2026-09-08 `run_scorer` was one transaction from the housekeeping
DELETE to the final commit: a dropped connection or a worker redeploy at game
60 of 70 rolled back sixty games' work (the pass that died at 01:31:00Z that
night left nothing, not even its own failure row), and a second scorer
starting on the :20 waited on the first one's row locks until
statement_timeout — 35 "while deleting tuple in relation picks" failures in
the week to 09-08. Twenty worker redeploys in the two hours before midnight
each killed the pass in flight ("aborted" 23 times in three days).

Source-level pins, same style as test_pick_lock_is_on_picks: the unit of work
is the game (its own non-BET rows cleared, its rows inserted, commit); a lost
connection re-runs that game once and never the pass; the housekeeping DELETE
is a SWEEP after the loop for games the loop did not re-score, in its own
short transaction with a lock_timeout; the outer handler still records.
"""
from __future__ import annotations

from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "models" / "scorer.py").read_text(encoding="utf-8")


def _between(a: str, b: str) -> str:
    i = SRC.index(a)
    return SRC[i:SRC.index(b, i)]


def _run_scorer_body() -> str:
    return _between("def run_scorer(", "def _get_current_bankroll(")


def test_each_game_is_its_own_committed_unit():
    body = _run_scorer_body()
    unit = _between("ONE GAME = ONE TRANSACTION", "        if skipped_postponed:")
    # clear THIS game's non-BET rows, not the window's
    assert "DELETE FROM picks" in unit and "WHERE game_id = %s" in unit
    assert "signal_type != 'BET'" in unit and "is_live IS NOT TRUE" in unit
    # ...score every model, then commit inside the loop
    assert "for model_id in relevant_models:" in unit
    assert unit.index("for model_id in relevant_models:") < unit.index("conn.commit()")
    assert "rescored.add(game_id)" in unit
    # the per-game commit sits INSIDE the games loop, before the pass summary
    assert body.index("conn.commit()\n                    rescored.add(game_id)") < body.index("if skipped_postponed:")


def test_a_lost_connection_re_runs_the_game_once_and_never_the_pass():
    unit = _between("ONE GAME = ONE TRANSACTION", "        if skipped_postponed:")
    assert "for attempt in (1, 2):" in unit
    assert "except ConnectionLost as exc:" in unit
    # the per-model catch must not swallow it — it is the game's unit, not the model's
    assert "except ConnectionLost:\n                            raise" in unit
    assert "if attempt == 2:" in unit and "model_failures.append" in unit
    assert "from data.db import get_connection, DBConnection, ConnectionLost" in SRC


def test_picks_are_only_counted_once_the_game_committed():
    unit = _between("ONE GAME = ONE TRANSACTION", "        if skipped_postponed:")
    assert "game_picks.extend(picks)" in unit
    assert "all_picks.extend(picks)" not in unit, "a retried game would double-count"
    assert unit.index("conn.commit()") < unit.index("all_picks.extend(game_picks)")


def test_the_housekeeping_delete_is_a_sweep_after_the_loop():
    body = _run_scorer_body()
    sweep = _between("# Housekeeping for the pairs the lock deliberately leaves open.",
                     'logger.info(f"Cleared unsettled picks')
    assert body.index("ONE GAME = ONE TRANSACTION") < body.index(
        "# Housekeeping for the pairs the lock deliberately leaves open."), \
        "the sweep runs AFTER the per-game loop, never before it"
    assert "NOT IN" in sweep and "rescored" in sweep, "games this pass re-scored are left alone"
    assert "SET LOCAL lock_timeout" in sweep
    assert "conn.commit()" in sweep, "the sweep is its own transaction"
    assert "conn.rollback()" in sweep, "a sweep that cannot lock yields; it never fails the picks"
    # the window bound and the started-game guard are unchanged
    assert "max(ncaaf_horizon, ufc_horizon, game_horizon)" in sweep
    assert "commence_time > %s" in sweep


def test_no_bulk_delete_of_non_bet_rows_precedes_the_loop():
    body = _run_scorer_body()
    pre = body[:body.index("ONE GAME = ONE TRANSACTION")]
    # The lock-ON path must not clear the whole window up front any more.
    # (The lock-OFF legacy deletes remain, guarded by `if not LOCK_GAME_PICKS_AT_FIRST_RUN`.)
    assert "signal_type != 'BET'" not in pre


def test_the_outer_handler_still_records_the_failure():
    body = _run_scorer_body()
    tail = body[body.index("    except Exception as exc:\n        conn.rollback()"):]
    assert '_log_pipeline(conn, target_date, "error"' in tail
    # rollback() on a dead connection reconnects (data/db.py), so this record
    # lands even when the pass died with the connection.
