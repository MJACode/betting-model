"""
The NCAAF live loop keeps the state it priced on (2026-09-19).

When the Delaware bet was traced, the only pick whose game state could be
shown was the one whose minute the poller's log happened to hold. The loop
read the scoreboard, priced it, and threw it away. These pin the write: one
row per change in what the engine's book-move guard keys on, never per pass,
and a failed write never costs a pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ncaaf_live.gameday import (  # noqa: E402
    record_live_states, state_change_row, state_key)


def _state(**kw):
    base = dict(period=1, clock_seconds=620, home_score=0, away_score=0,
                possession="away", down=2, distance=6, yardline_100=40,
                home_timeouts=3, away_timeouts=3)
    base.update(kw)
    return base


def test_first_sight_is_written():
    seen = {}
    row = state_change_row(seen, "G", _state(), "2026-09-19T15:41:51Z", "cfbd")
    assert row is not None
    assert row["game_id"] == "G" and row["seen_at"] == "2026-09-19T15:41:51Z"
    assert row["home_score"] == 0 and row["possession"] == "away"
    assert row["source"] == "cfbd"
    assert json.loads(row["raw_state"])["clock_seconds"] == 620


def test_the_clock_ticking_is_not_a_change():
    """Per-pass rows would be ~30k an hour of identical clock ticks."""
    seen = {}
    state_change_row(seen, "G", _state(), "t0", "cfbd")
    assert state_change_row(seen, "G", _state(clock_seconds=600, down=3,
                                              distance=2), "t1", "cfbd") is None


def test_a_score_a_period_or_a_possession_change_is_written():
    seen = {}
    state_change_row(seen, "G", _state(), "t0", "cfbd")
    assert state_change_row(seen, "G", _state(away_score=7), "t1", "cfbd")
    assert state_change_row(seen, "G", _state(away_score=7, possession="home"),
                            "t2", "cfbd")
    assert state_change_row(seen, "G", _state(away_score=7, possession="home",
                                              period=2), "t3", "cfbd")
    assert state_change_row(seen, "G", _state(away_score=7, possession="home",
                                              period=2), "t4", "cfbd") is None


def test_the_key_matches_what_the_engine_guard_keys_on():
    """serve.LiveEngine.price anchors BookMoveClock on (home, away, period,
    possession). The stored change rows must agree on what a change is, or
    the caps cannot be re-measured from them."""
    assert state_key(_state(home_score=3, away_score=7, period=2,
                            possession="home")) == (3, 7, 2, "home")


def test_games_are_tracked_separately():
    seen = {}
    assert state_change_row(seen, "A", _state(), "t0", "cfbd")
    assert state_change_row(seen, "B", _state(), "t0", "cfbd")
    assert state_change_row(seen, "A", _state(), "t1", "cfbd") is None


class _Conn:
    def __init__(self, fail=False):
        self.rows, self.committed, self.rolled_back, self.fail = [], 0, 0, fail

    def execute(self, sql, params=None):
        if self.fail:
            raise RuntimeError("boom")
        assert "ON CONFLICT (game_id, seen_at) DO NOTHING" in sql
        self.rows.append(params)
        return self

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


def test_rows_are_written_once_and_committed():
    seen = {}
    rows = [state_change_row(seen, "G", _state(), "t0", "cfbd"),
            state_change_row(seen, "G", _state(away_score=7), "t1", "cfbd")]
    conn = _Conn()
    assert record_live_states(conn, rows) == 2
    assert len(conn.rows) == 2 and conn.committed == 1
    assert conn.rows[0][0] == "G" and conn.rows[1][5] == 7   # game_id, away_score


def test_a_failed_write_never_costs_the_pass():
    conn = _Conn(fail=True)
    seen = {}
    rows = [state_change_row(seen, "G", _state(), "t0", "cfbd")]
    assert record_live_states(conn, rows) == 0
    assert conn.rolled_back == 1


def test_nothing_to_write_touches_nothing():
    conn = _Conn()
    assert record_live_states(conn, []) == 0
    assert conn.committed == 0
