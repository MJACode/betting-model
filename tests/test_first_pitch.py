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
from pathlib import Path

import pytest

from data.first_pitch import (
    DERIVE_SQL,
    SUSPICIOUS_EARLY_MINUTES,
    pregame_cutoff_sql,
    trusted_first_pitch,
)
from features.feature_engine import _is_pregame_snapshot


# ── the guard ────────────────────────────────────────────────────────────────

def test_the_actual_start_wins_over_the_schedule():
    """A snapshot after real first pitch but before the listed time is NOT
    pre-game, and that is exactly the window the bias creates.

    The gap here is 16 minutes, which is the measured median (p05..p95 is
    -16.2..-10.0 over 415 games). It was 80 minutes until 2026-09-03, a gap
    the real distribution never produces -- and past the clamp added that day,
    so the fixture was asserting behaviour the data cannot generate.
    """
    assert _is_pregame_snapshot("2026-08-30T23:00:00Z", "2026-08-30T23:10:00Z") is True
    assert _is_pregame_snapshot("2026-08-30T23:00:00Z", "2026-08-30T23:10:00Z",
                                "2026-08-30T22:54:00Z") is False


def test_an_implausibly_early_first_pitch_is_not_believed():
    """7 of 415 derivations land more than an hour before the scheduled start;
    six are ~6 hours early, a doubleheader matched to the first game's live
    state. Preferring one does not tighten the bound -- it marks a whole
    afternoon of real pre-game rows as in-play. Measured: 4,316 such rows on
    MLB_2026-08-29_ARI_SF alone, and 6,148 across the seven games."""
    # the real BOS@NYY numbers: "first pitch" 6h26m before the listed start
    assert _is_pregame_snapshot("2026-08-29T20:00:00Z", "2026-08-29T23:16:00Z",
                                "2026-08-29T16:50:01Z") is True
    assert trusted_first_pitch("2026-08-29T16:50:01Z",
                               "2026-08-29T23:16:00Z") is None


def test_a_late_start_is_believed_because_it_is_real():
    """No clamp on the late side: +39 to +114 minutes are rain delays, and a
    game that truly started late truly has more pre-game quotes."""
    kept = trusted_first_pitch("2026-08-30T01:04:00Z", "2026-08-29T23:10:00Z")
    assert kept == "2026-08-30T01:04:00Z"


def test_the_clamp_sits_in_the_gap_the_data_leaves():
    """Chosen, not rounded. The offsets run continuously out to -36.0 minutes,
    then nothing until -71.0. Sixty is inside that gap, so the constant cannot
    be moved a little either way and change which games it catches."""
    assert 36 < SUSPICIOUS_EARLY_MINUTES < 71


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


def test_the_shared_cutoff_coalesces_and_clamps():
    sql = pregame_cutoff_sql("g")
    assert sql.startswith("COALESCE(CASE WHEN g.first_pitch_at"), sql
    assert f"interval '{SUSPICIOUS_EARLY_MINUTES} minutes'" in sql, sql
    assert sql.endswith("END, g.commence_time)"), sql


# ── every reader uses it ─────────────────────────────────────────────────────

def test_the_market_movement_loader_uses_the_better_bound():
    from features import market_movement

    src = inspect.getsource(market_movement.load_market_movement)
    assert "pregame_cutoff_sql(" in src


def test_the_in_play_relabel_uses_the_better_bound():
    from data.ingestors.odds_ingestor import relabel_in_play

    src = inspect.getsource(relabel_in_play)
    assert "pregame_cutoff_sql(" in src


def test_the_backfills_in_play_marker_prefers_the_actual_start():
    from data.ingestors.odds_ingestor import _mark_in_play

    src = inspect.getsource(_mark_in_play)
    assert 'g.get("first_pitch_at")' in src


def test_the_prop_scorer_uses_the_better_bound():
    """The prop price read is the newest reader and the one that decides a bet:
    it bounds on the cutoff, not on the scheduled start. Measured 2026-09-03 on
    the 30 most recent MLB games carrying a first_pitch_at, 1,926 of 3,919
    player+market keys (49%) had their "pre-game" price taken from inside the
    window between actual first pitch and scheduled start."""
    from models import scorer

    src = inspect.getsource(scorer._pregame_cutoff_map)
    assert "pregame_cutoff_sql(" in src, src


def test_the_nfl_prop_scorer_uses_the_better_bound():
    """NFL reads its slate from nfl_team_game_stats, not `games`, so it needs
    its own join to reach first_pitch_at. A no-op today -- live_game_state is
    MLB-only -- and wired so it stops being one without another change here."""
    from models import scorer

    src = inspect.getsource(scorer._nfl_pregame_cutoff_map)
    assert "LEFT JOIN games g" in src, src
    assert "THEN g.first_pitch_at END" in src, src
    assert "SUSPICIOUS_EARLY_MINUTES" in src, src


# Every module that decides "is this snapshot pre-game" with the shared helper.
_PREGAME_READERS = [
    "features/feature_engine.py",
    "features/ncaaf_feature_engine.py",
    "features/wnba_feature_engine.py",
    "features/nba_feature_engine.py",
]


@pytest.mark.parametrize("rel", _PREGAME_READERS)
def test_every_is_pregame_snapshot_caller_passes_first_pitch(rel):
    """_is_pregame_snapshot takes first_pitch_at as an OPTIONAL third argument,
    and an optional argument nobody passes is not a guard -- it is dead code
    that reads like one. Until 2026-09-03 all five callers passed two args, so
    the helper's own COALESCE never had a first_pitch_at to prefer.

    Measured before wiring them: on the 407 MLB games carrying a
    first_pitch_at, ZERO game-level (game, market) keys had their chosen
    pre-game row inside the window -- the game-level odds feed does not
    snapshot there the way the prop feed does. So this changes no feature
    today and needs no retrain; it is wired so the bound is already right when
    live state reaches the other sports.
    """
    import ast

    root = Path(__file__).parent.parent
    tree = ast.parse((root / rel).read_text(encoding="utf-8"))
    calls = [c for c in ast.walk(tree)
             if isinstance(c, ast.Call)
             and getattr(c.func, "id", "") == "_is_pregame_snapshot"]
    assert calls, f"{rel} no longer calls the shared helper"
    for c in calls:
        passed = len(c.args) + sum(1 for k in c.keywords if k.arg == "first_pitch_at")
        assert passed >= 3, (
            f"{rel}:{c.lineno} passes {len(c.args)} args -- it bounds on the "
            f"SCHEDULED start, which runs a mean 18.7 minutes late")


def test_the_wnba_prop_market_loader_coalesces_in_sql():
    """It parses timestamps itself rather than calling the shared helper, so
    the COALESCE has to be in its query."""
    from models import wnba_prop_market

    src = inspect.getsource(wnba_prop_market.load_wnba_prop_quotes)
    assert "pregame_cutoff_sql(" in src, src


def test_the_column_is_in_the_base_schema_not_only_a_migration():
    """It shipped as an ADD COLUMN only, so a database created from SCHEMA_SQL
    alone did not have it -- which is how a test fixture built from the real
    schema failed on `no such column: g.first_pitch_at`."""
    from data.db_setup import SCHEMA_SQL

    games = SCHEMA_SQL[SCHEMA_SQL.index("CREATE TABLE IF NOT EXISTS games"):]
    games = games[:games.index(");")]
    # The DECLARATION, not a mention of it: the column sits under a comment
    # block that names it, so a substring check passes on the prose alone.
    decls = [ln.split()[0] for ln in
             (l.strip().rstrip(",") for l in games.splitlines()[1:])
             if ln and not ln.startswith("--")]
    assert "first_pitch_at" in decls, decls


def test_the_derivation_is_a_queued_job():
    """It needs the database, so it runs on the worker like everything else."""
    from tracking.job_queue import JOBS

    assert "derive_first_pitch" in JOBS
