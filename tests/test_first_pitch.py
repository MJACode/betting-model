"""Actual first pitch vs the scheduled start.

mike, 2026-09-01: "should be commence time." Measured over the 413 games with
live-state coverage, the first `Live` snapshot lands 19.5 minutes BEFORE
commence_time on average (median 15.9); only 4 of 413 began after theirs. So
the §7 pre-game boundary is ~a quarter-hour too generous and leaks in the
PERMISSIVE direction — a model trained on a line that already reflects the first
inning looks prescient in backtest.
"""

from __future__ import annotations

import inspect

from data.first_pitch import DERIVE_SQL, pregame_cutoff_sql
from features.feature_engine import _is_pregame_snapshot


# ── the guard ────────────────────────────────────────────────────────────────

def test_the_actual_start_wins_over_the_schedule():
    """A snapshot after real first pitch but before the listed time is NOT
    pre-game, and that is exactly the window the bias creates."""
    assert _is_pregame_snapshot("2026-08-30T22:00:00Z", "2026-08-30T23:10:00Z") is True
    assert _is_pregame_snapshot("2026-08-30T22:00:00Z", "2026-08-30T23:10:00Z",
                                "2026-08-30T21:50:00Z") is False


def test_a_missing_actual_start_falls_back_to_the_schedule():
    """first_pitch_at is NULL for every game before 2026-07. Treating NULL as
    "no bound" would drop seventeen seasons; treating it as zero would drop
    everything."""
    assert _is_pregame_snapshot("2026-08-30T22:00:00Z",
                                "2026-08-30T23:10:00Z", None) is True


def test_both_missing_still_fails_open():
    """SBR and synthetic rows carry no usable timing and must survive."""
    assert _is_pregame_snapshot("2026-08-30T22:00:00Z", None, None) is True
    assert _is_pregame_snapshot(None, "2026-08-30T23:10:00Z", None) is True


def test_the_boundary_itself_is_pregame():
    assert _is_pregame_snapshot("2026-08-30T21:50:00Z", "2026-08-30T23:10:00Z",
                                "2026-08-30T21:50:00Z") is True


# ── the derivation ───────────────────────────────────────────────────────────

def test_it_derives_from_live_state_not_from_the_schedule():
    assert "abstract_game_state = 'Live'" in DERIVE_SQL
    assert "MIN(snapshot_at)" in DERIVE_SQL


def test_it_never_overwrites_commence_time():
    """The schedule is the right thing to show in the app and to sort a board
    by. It is only the wrong thing to bound a leak with."""
    assert "SET first_pitch_at" in DERIVE_SQL
    assert "commence_time =" not in DERIVE_SQL


def test_the_derivation_is_idempotent():
    """It runs on a schedule; rewriting every row every pass would churn the
    table for nothing."""
    assert "g.first_pitch_at IS NULL OR g.first_pitch_at <> f.first_live" in DERIVE_SQL


def test_the_shared_cutoff_coalesces():
    sql = pregame_cutoff_sql("g")
    assert sql == "COALESCE(g.first_pitch_at, g.commence_time)"


# ── every reader uses it ─────────────────────────────────────────────────────

def test_the_market_movement_loader_uses_the_better_bound():
    from features import market_movement

    src = inspect.getsource(market_movement.load_market_movement)
    assert "COALESCE(g.first_pitch_at, g.commence_time)" in src


def test_the_in_play_relabel_uses_the_better_bound():
    from data.ingestors.odds_ingestor import relabel_in_play

    src = inspect.getsource(relabel_in_play)
    assert "COALESCE(g.first_pitch_at, g.commence_time)" in src


def test_the_backfills_in_play_marker_prefers_the_actual_start():
    from data.ingestors.odds_ingestor import _mark_in_play

    src = inspect.getsource(_mark_in_play)
    assert 'g.get("first_pitch_at")' in src


def test_the_derivation_is_a_queued_job():
    """It needs the database, so it runs on the worker like everything else."""
    from tracking.job_queue import JOBS

    assert "derive_first_pitch" in JOBS
