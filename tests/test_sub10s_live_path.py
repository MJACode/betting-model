"""The sub-10-second path: score the move in the tick that saw it.

mike, 2026-08-31: "How do we get instant live odds and a model pick in under 10
seconds end to end?"

The measurement that reframed the question: on the four live picks that fired
2026-08-31, the pipeline was ALREADY sub-10s once it saw a qualifying quote --
DK publish to price in hand 2.4-5.8s, price to pick row 0.8-1.0s, pick to push
and Discord 1.1-2.2s, so 4.6-8.7s end to end. Latency was never the problem.

COVERAGE was. The aggregator shows us 29.7% of DK's line changes, so seven moves
in ten never produce a pick at all -- and a pick that is never made cannot be
fast. This path closes that by scoring off the DK-direct feed, which sees 100%.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from data.ingestors import dk_direct_feed as f

ROOT = Path(__file__).parent.parent


# -- a BET is never deleted (CLAUDE.md 1c), now enforced in SQL ---------------

def test_the_mlb_live_delete_can_never_remove_a_bet():
    """The lock is a read-then-act check and cannot close its own race.

    Two writers -- the laptop runner and the Railway loop -- can interleave:
    writer B reads `locked`, writer A inserts a BET and locks the lane, and B,
    holding a stale read, deletes A's BET and replaces it. That destroys the bet
    of record. This clause makes it impossible in the statement itself.
    """
    src = (ROOT / "models/live_scorer.py").read_text(encoding="utf-8")
    block = src[src.index("DELETE FROM picks"):]
    assert "signal_type <> 'BET'" in block[:400], (
        "an unlocked lane's delete must not be able to take a BET with it")


def test_the_ncaaf_live_delete_got_the_same_guard():
    """Section 1b: a change to how one loop operates is assessed against all."""
    src = (ROOT / "ncaaf_live/gameday.py").read_text(encoding="utf-8")
    block = src[src.index("DELETE FROM picks"):]
    assert "signal_type <> 'BET'" in block[:500]


# -- the feed reports what moved ---------------------------------------------

def test_poll_once_reports_which_games_moved():
    """Scoring every game on every tick would waste the budget the whole design
    is built around; scoring only what moved is what keeps it under 10s."""
    src = inspect.getsource(f.poll_once)
    assert 'moved: set[str] = set()' in src
    assert "moved.add(game_id)" in src
    assert 'out["moved"] = moved' in src


def test_a_quote_already_seen_does_not_count_as_a_move():
    """First-seen semantics. An unchanged number re-read 12 times a minute is
    not 12 moves, and treating it as one would score constantly for nothing."""
    src = inspect.getsource(f.poll_once)
    seen_guard = src.index("if key in seen:")
    assert src.index("moved.add(game_id)") > seen_guard


# -- the glue -----------------------------------------------------------------

def test_scoring_runs_in_the_same_tick_as_the_write():
    src = inspect.getsource(f.run)
    assert "if score and moved:" in src
    assert "run_live_scorer(game_ids=moved" in src


def test_a_scoring_failure_never_kills_the_feed():
    """A dead feed loses every future move; a failed score loses one tick, and
    the Railway loop is still running as the backstop."""
    src = inspect.getsource(f.run)
    tail = src[src.index("if score and moved:"):]
    assert "except Exception" in tail
    assert "non-fatal" in tail


def test_scoring_is_opt_in():
    """The plain feed stays a feed. Turning this on changes what a laptop does
    to the live board, which is a decision rather than a default."""
    assert "score: bool = False" in inspect.getsource(f.run)


def test_the_loop_sleeps_the_REMAINDER_of_the_interval():
    """Measured: a flat 5s sleep after ~2.3s of scoring gave a 7.5s cadence, so
    a move landing just after a poll waited 7.5s and the worst case reached
    ~11.8s -- over budget purely because the loop counted its own work as idle
    time. Holding a true 5s cadence puts the worst case at ~9.3s."""
    src = inspect.getsource(f.run)
    assert "tick_started = time.time()" in src
    assert "time.sleep(max(0.0, POLL_SEC - elapsed))" in src
    assert "time.sleep(POLL_SEC)" not in src, "a flat sleep blows the budget"


def test_the_budget_is_written_down_where_it_can_be_checked():
    """The numbers are measured, not assumed, and the docstring is where the
    next person finds out which."""
    doc = f.run.__doc__ or ""
    assert "4.6 - 8.7 s" in doc and "29.7%" in doc


def test_the_expected_consequence_is_stated():
    """Coverage 30% -> 100% moves the live regime again, exactly as the 5s poll
    plus first-signal lock did on 2026-08-29. Saying so up front is what stops a
    volume jump being misread as drift."""
    doc = f.run.__doc__ or ""
    assert "live_calibration" in doc


# -- the decision is unchanged ------------------------------------------------

def test_the_runner_reuses_the_scorer_rather_than_reimplementing_it():
    """Everything correctness-critical -- the first-signal lock, the daily caps,
    the DK-only decision, the notifier ledger -- is inherited by calling the
    same function Railway calls. A second implementation would be a second set
    of bugs."""
    src = inspect.getsource(f.run)
    assert "from models.live_scorer import run_live_scorer" in src
    for reimplemented in ("model_probability", "kelly", "signal_type"):
        assert reimplemented not in src, (
            f"{reimplemented} suggests the runner is deciding for itself")
