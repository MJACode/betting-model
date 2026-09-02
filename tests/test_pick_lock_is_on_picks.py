"""The lock is on PICKS, not on games.

mike, 2026-08-30: "once a pick crosses a threshold, it's picked. no pick
because bad number then it drifts into pick territory" is a pick we should
take; "if it's originally a pick, we cant then update the number or pick it
again. we simply lost on CLV."

Both halves matter and they pull in opposite directions:

  * a BET freezes its pair FOREVER -- line movement after that is lost CLV,
    never a re-price and never a withdrawal (§1c);
  * a pair that has produced NO bet has not been decided, so it must keep
    being scored all day. A 6am no-signal that crosses at 3pm is a real pick
    we were simply blind to.

Until now the lock froze a pair the moment ANY row was written for it --
including a dead-zone NONE. That made "we looked at this game" mean the same
as "we bet this game". NCAAF already had the correct behaviour, because a
sport scored across a WEEK made the difference impossible to miss; a one-day
board hid it everywhere else.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

SRC = (Path(__file__).parent.parent / "models/scorer.py").read_text(encoding="utf-8")


def _between(start: str, end: str) -> str:
    i = SRC.index(start)
    return SRC[i:SRC.index(end, i)]


def _sql(block: str) -> str:
    """Just the statement. The prose around these queries names the sports it
    used to special-case, so a check on the whole block would match its own
    explanation rather than the code."""
    return re.search(r'"""(.*?)"""', block, re.S).group(1)


def test_only_a_bet_locks_a_pair():
    q = _sql(_between("locked_pairs: set[tuple] = set()", "locked_pairs.add("))
    assert "p.signal_type = 'BET'" in q, \
        "a NONE or AVOID row must not freeze a pair that has produced no bet"


def test_the_lock_is_no_longer_ncaaf_specific():
    """The carve-out was right and was the general rule all along. If a sport
    name reappears in this query, the blindness has come back for every other
    sport."""
    q = _sql(_between("locked_pairs: set[tuple] = set()", "locked_pairs.add("))
    assert "NCAAF" not in q and "sport" not in q


def test_unlocked_rows_are_cleaned_up_so_they_cannot_duplicate():
    """A pair left open is re-scored every pass, so its previous row has to go
    or the board grows a copy per pass."""
    d = _between("# Housekeeping for the pairs the lock deliberately leaves open.",
                 "logger.info(f\"Cleared unsettled picks")
    assert "DELETE FROM picks" in d
    assert "signal_type != 'BET'" in d


def test_the_cleanup_never_touches_a_started_game_or_a_live_row():
    """Two things it must not reach: a game already under way (its picks are
    settleable) and the in-play board (its own lock owns those)."""
    d = _between("# Housekeeping for the pairs the lock deliberately leaves open.",
                 "logger.info(f\"Cleared unsettled picks")
    assert "commence_time > %s" in d, "must be scoped to unstarted games"
    assert "is_live IS NOT TRUE" in d, "must not reach the live board"


def test_the_cleanup_covers_the_whole_look_ahead_window():
    """Stopping at today would leave duplicate no-signal rows on exactly the
    boards scored furthest ahead -- NCAAF and UFC both reach a week out."""
    d = _between("# Housekeeping for the pairs the lock deliberately leaves open.",
                 "logger.info(f\"Cleared unsettled picks")
    assert "max(ncaaf_horizon, ufc_horizon)" in d


def test_the_prop_and_live_locks_are_unchanged():
    """This change is about the GAME board. Props lock at first signal on a
    confirmed lineup and live locks at the first BET in a lane; neither is in
    scope and a silent change to either would be a regression."""
    assert "def _locked_prop_keys" in SRC
    assert "LOCK_PROP_PICKS_AT_FIRST_SIGNAL" in SRC
    assert "def _locked_live_lanes" in SRC


def test_a_bet_is_still_never_re_scored():
    """The half that must NOT change: once a pair is locked the scorer skips
    it, so no later pass can re-price or withdraw the number given."""
    i = SRC.index("if (game_id, model_id) in locked_pairs:")
    body = SRC[i:i + 200]
    assert "continue" in body, "a locked pair must be skipped, not re-scored"
