"""What the live model saw is recorded, once per lane, and can never cost a pick.

WHY THIS EXISTS
---------------
A live decision could not be reproduced. `_pregame_features` memoises the
pre-game half of the feature row per (game_date, game_id) in process, so a
running loop freezes one row per game at whatever the stats tables held when it
first saw the game — a moment recorded nowhere.

Measured 2026-09-08 on MLB_2026-09-07_LAA_BOS: the same live state, the same DK
line (7.5) and the same price (−118) give p_over 0.5263 on that day's stats and
0.7199 on the snapshot two days older, against a production record of 0.7268.
Fourteen games could not be reproduced at all, which is what stopped the
inning-gate question being answerable. docs/mlb_volume_efficiency.md §13.

THE TWO PROPERTIES THAT MATTER are not "it writes a row":

  * ONE ROW PER LANE, THE FIRST ONE. The bet of record is the first BET
    (LOCK_LIVE_PICKS_AT_FIRST_SIGNAL), so the row explaining it is the first
    row. A later pass must not overwrite the evidence for a pick it did not
    make — CLAUDE.md §1c applied to the audit trail.
  * A RECORDER MAY NEVER COST A PICK. The connection is not autocommit, so an
    unguarded failure here would poison the transaction and roll back the picks
    just inserted — a recorder that destroys the thing it documents.
"""

from __future__ import annotations

import json

import pytest

from models import live_scorer as ls


class FakeConn:
    """Records statements; optionally raises on the feature INSERT."""

    def __init__(self, fail_on_insert: bool = False):
        self.statements: list[tuple[str, tuple]] = []
        self.fail_on_insert = fail_on_insert

    def execute(self, sql, params=()):
        flat = " ".join(sql.split())
        self.statements.append((flat, tuple(params or ())))
        if self.fail_on_insert and "INSERT INTO live_pick_features" in flat:
            raise RuntimeError("relation does not exist")
        return self

    def sql_of(self, needle: str) -> list[tuple[str, tuple]]:
        return [s for s in self.statements if needle in s[0]]


def _pick(signal="BET", **kw):
    base = {"game_id": "MLB_2026-09-07_LAA_BOS", "model_id": "mlb_live_total_runs",
            "signal_type": signal, "model_probability": 0.7268,
            "_lam": 9.3912, "_state_at": "2026-09-07T17:55:40Z",
            "_features": {"inning": 1, "total_runs": 0, "home_team_era": 3.65}}
    base.update(kw)
    return base


def test_a_live_bet_records_its_feature_row_and_lambda():
    conn = FakeConn()
    assert ls._record_live_features(conn, [_pick()]) == 1
    sql, params = conn.sql_of("INSERT INTO live_pick_features")[0]
    assert params[0] == "MLB_2026-09-07_LAA_BOS"
    assert params[1] == "mlb_live_total_runs"
    assert params[4] == pytest.approx(9.3912)
    assert json.loads(params[6])["home_team_era"] == 3.65


def test_only_BETs_are_recorded():
    """A NONE or AVOID is not a bet of record and has nothing to reproduce."""
    conn = FakeConn()
    assert ls._record_live_features(
        conn, [_pick("NONE"), _pick("AVOID")]) == 0
    assert conn.sql_of("INSERT INTO live_pick_features") == []


def test_a_pick_with_no_feature_row_is_skipped_not_written_empty():
    """The binary branch does not carry one; a NULL features row would look
    like a recorded decision and be worse than an absent one."""
    conn = FakeConn()
    assert ls._record_live_features(conn, [_pick(_features=None)]) == 0
    assert conn.sql_of("INSERT INTO live_pick_features") == []


def test_the_first_row_per_lane_wins():
    """CLAUDE.md §1c on the audit trail: a later pass must not overwrite the
    evidence for a pick it did not make."""
    conn = FakeConn()
    ls._record_live_features(conn, [_pick()])
    sql, _ = conn.sql_of("INSERT INTO live_pick_features")[0]
    assert "ON CONFLICT (game_id, model_id) DO NOTHING" in sql


# ── the recorder may never cost a pick ───────────────────────────────────────

def test_a_recorder_failure_is_swallowed_rather_than_raised():
    conn = FakeConn(fail_on_insert=True)
    assert ls._record_live_features(conn, [_pick()]) == 0


def test_a_recorder_failure_is_rolled_back_to_its_savepoint():
    """THE PROPERTY THAT MATTERS. Without the savepoint the failed INSERT
    poisons the transaction and the picks inserted moments earlier are lost."""
    conn = FakeConn(fail_on_insert=True)
    ls._record_live_features(conn, [_pick()])
    assert conn.sql_of("SAVEPOINT"), "no savepoint was taken"
    assert conn.sql_of("ROLLBACK TO SAVEPOINT"), "the failure was not contained"


def test_a_success_releases_its_savepoint():
    """An unreleased savepoint per pick leaks server-side state across a loop
    that runs every 5 seconds."""
    conn = FakeConn()
    ls._record_live_features(conn, [_pick()])
    assert conn.sql_of("RELEASE SAVEPOINT")


def test_one_bad_pick_does_not_stop_the_next_one():
    conn = FakeConn()
    picks = [_pick(_features=None), _pick(game_id="MLB_2026-09-07_A_B")]
    assert ls._record_live_features(conn, picks) == 1
