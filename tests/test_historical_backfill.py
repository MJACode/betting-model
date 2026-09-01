"""The historical backfill, and the two bugs its own pilot exposed.

Both were found by reading the 1,515 rows the first run wrote rather than the
summary it returned — which reported "6 calls, 0 errors" and was true.
"""

from __future__ import annotations

import inspect

from data.ingestors.odds_ingestor import (PULL_LEDGER_DDL, _mark_in_play,
                                          run_historical_odds_range)


# ── bug 1: post-start snapshots wearing a pre-game label ─────────────────────

def test_a_snapshot_after_first_pitch_is_marked_in_play():
    """A 22:00Z historical pull catches afternoon games in the sixth inning.
    The pilot stored ARI@NYM at 21:55Z as home -1213 / away +747 — a mid-game
    number sitting in a column every pre-game reader trusts."""
    games = [{"game_id": "G_LATE", "commence_time": "2024-06-01T23:10:00Z"},
             {"game_id": "G_EARLY", "commence_time": "2024-06-01T17:05:00Z"}]
    rows = [{"game_id": "G_LATE", "snapshot_at": "2024-06-01T21:55:10Z",
             "snapshot_type": "open"},
            {"game_id": "G_EARLY", "snapshot_at": "2024-06-01T21:55:10Z",
             "snapshot_type": "open"}]
    assert _mark_in_play(games, rows) == 1
    assert [r["snapshot_type"] for r in rows] == ["open", "in_play"]


def test_a_snapshot_exactly_at_first_pitch_stays_pregame():
    """Strictly after, not at or after. The boundary is the definition of
    pre-game everywhere else in the repo."""
    games = [{"game_id": "G", "commence_time": "2024-06-01T23:10:00Z"}]
    rows = [{"game_id": "G", "snapshot_at": "2024-06-01T23:10:00Z",
             "snapshot_type": "open"}]
    assert _mark_in_play(games, rows) == 0


def test_unknown_timing_fails_open():
    """Synthetic and SBR rows carry no usable commence_time. Marking those
    in_play would silently delete them from every pre-game read."""
    games = [{"game_id": "G", "commence_time": None}]
    rows = [{"game_id": "G", "snapshot_at": "2024-06-01T21:55:10Z",
             "snapshot_type": "open"},
            {"game_id": "MISSING", "snapshot_at": "2024-06-01T21:55:10Z",
             "snapshot_type": "open"}]
    assert _mark_in_play(games, rows) == 0
    assert all(r["snapshot_type"] == "open" for r in rows)


def test_the_backfill_marks_in_play_before_writing():
    """After the insert would be a table that was briefly wrong, and a crash in
    between would leave it wrong permanently."""
    src = inspect.getsource(run_historical_odds_range)
    assert src.index("_mark_in_play") < src.index("_insert_odds")


# ── bug 2: resume against what was pulled, not what was asked for ────────────

def test_resume_checks_the_pull_ledger_not_the_snapshot_timestamp():
    """The API stamps rows with the market's own last_update — a 12:00Z request
    comes back 11:55:34Z — so `WHERE snapshot_at = '...T12:00:00Z'` never
    matches and every re-run re-spends the whole range at 10x rates."""
    src = inspect.getsource(run_historical_odds_range)
    assert "odds_history_pulls" in src
    assert "SELECT 1 FROM odds WHERE sport=%s AND snapshot_at=%s" not in src


def test_the_ledger_is_keyed_by_sport_date_and_hour():
    """Two snapshots a day is the whole point; a date-only key would record the
    first hour and skip the second."""
    assert "PRIMARY KEY (sport, snapshot_date, hour_utc)" in PULL_LEDGER_DDL


def test_the_ledger_row_is_written_in_the_same_commit_as_the_odds():
    """Recorded after the commit, a crash between them re-spends the call.
    Recorded before the insert, a crash marks a pull that never landed."""
    src = inspect.getsource(run_historical_odds_range)
    ledger = src.index("INSERT INTO odds_history_pulls")
    insert = src.index("_insert_odds")
    commit = src.index("conn.commit()", insert)
    assert insert < ledger < commit


# ── the guard rails that were right the first time ───────────────────────────

def test_the_credit_cap_stops_before_the_call_that_would_cross_it():
    src = inspect.getsource(run_historical_odds_range)
    assert "spent + per_call > credit_cap" in src
    assert "stopped_early" in src


def test_one_bad_day_does_not_end_the_run():
    src = inspect.getsource(run_historical_odds_range)
    assert 'stats["errors"] += 1' in src


def test_the_cost_model_treats_bookmakers_as_one_region():
    """10 credits x markets x regions, and `bookmakers` counts as ONE region —
    which is why seven books cost what one book costs, and why asking for
    draftkings alone all these years bought nothing."""
    src = inspect.getsource(run_historical_odds_range)
    assert "per_call = 10 * len(markets)" in src
