"""A pick written after first pitch is not a pre-game pick, and a pre-game pick
is not posted after the game starts.

mike, 2026-09-03: "add the first pitch guard."

TWO GUARDS, BECAUSE THE DATA SHOWED TWO DIFFERENT FAILURES. 507 opening_signals
rows were locked after their game's first pitch:

  * 485 had their PICK created after first pitch too. Those were never pre-game
    picks (§7) and capture should not have locked them at all.
  * 22 were legitimate: the pick existed before first pitch and the CAPTURE step
    merely ran later. The 2026-08-31 MIN/DET signal is one — created 38 seconds
    before the 23:41Z first pitch, captured four minutes after it. Dropping
    those at capture would delete a real signal from the shadow record (§1c:
    the pick existed, timing is data), but POSTING one sends a member to a game
    already in progress at a pre-game number.

So capture is keyed on the PICK's created_at, and delivery is keyed on whether
the game has started by the time the card is built.
"""

from __future__ import annotations

import inspect
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking import discord_notifier as dn  # noqa: E402
from tracking import opening_signals as osig  # noqa: E402

NOW = datetime(2026, 9, 3, 18, 0, tzinfo=timezone.utc)


# ── capture: the pick itself must pre-date first pitch ───────────────────────

def test_capture_compares_the_picks_own_clock_not_the_capture_clock():
    """Keyed on p.created_at. Keyed on the capture clock instead, it would drop
    the 22 legitimate late-captured signals as well as the 485 bad ones."""
    src = inspect.getsource(osig.capture_opening_signals)
    assert "p.created_at::timestamptz <= g.commence_time::timestamptz" in src
    assert "os.locked_at" not in src.split("INSERT INTO opening_signals")[1]


def test_capture_fails_open_on_a_missing_timestamp():
    """Synthetic and backfilled rows carry no commence_time and must keep
    flowing (§7) — a guard that closes on NULL empties the shadow track."""
    src = inspect.getsource(osig.capture_opening_signals)
    assert "g.commence_time IS NULL OR p.created_at IS NULL" in src


def test_the_dry_run_count_uses_the_same_predicate_as_the_insert():
    """A count that disagrees with the write reports work that will not happen."""
    src = inspect.getsource(osig.capture_opening_signals)
    assert src.count(
        "p.created_at::timestamptz <= g.commence_time::timestamptz") == 2


# ── delivery: the game must not have started ─────────────────────────────────

def test_a_game_in_progress_is_not_postable():
    started = (NOW - timedelta(minutes=4)).isoformat()
    assert dn._still_pre_game(started, now=NOW) is False


def test_an_upcoming_game_is_postable():
    upcoming = (NOW + timedelta(hours=2)).isoformat()
    assert dn._still_pre_game(upcoming, now=NOW) is True


@pytest.mark.parametrize("missing", [None, "", "not-a-timestamp"])
def test_delivery_fails_open_too(missing):
    """A feed that stops populating commence_time must not silently empty the
    board — the same direction every other guard here fails."""
    assert dn._still_pre_game(missing, now=NOW) is True


def test_mixed_timestamp_shapes_are_parsed_not_string_compared():
    """'Z' suffix vs '+00:00' offset vs naive. A string comparison silently
    keeps the wrong rows (§7)."""
    z = "2026-09-03T17:56:00Z"                     # 4 minutes before NOW
    assert dn._still_pre_game(z, now=NOW) is False
    naive = "2026-09-03T20:00:00"                  # treated as UTC, after NOW
    assert dn._still_pre_game(naive, now=NOW) is True


def test_the_restatement_path_is_deliberately_not_guarded():
    """_locked_signals feeds notify_discord_restate, which re-publishes a whole
    PAST slate as a correction. Filtering its started games would make the
    correction incomplete — a different job from advertising a live game."""
    src = inspect.getsource(dn._locked_signals)
    assert "_still_pre_game" not in src
    assert "_still_pre_game" in inspect.getsource(dn._new_signals)
