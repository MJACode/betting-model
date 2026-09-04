"""
MLB's in-play quote must not predate the score it has not priced yet.

THE INCIDENT THIS PORTS (2026-09-03, Akron at Wake Forest — NCAAF, not MLB).
A live total was posted at 44.5 on a DraftKings quote stamped 62.2s earlier,
0.6 seconds after the loop saw a touchdown; the book re-hung at 50.5 within the
minute. Every guard in that loop bounded the quote's AGE, and age cannot see an
event.

MLB already had the age bound (LIVE_ODDS_MAX_AGE_SEC, 30s — the tightest of the
three sports) and the edge cap (LIVE_MAX_EDGE_CAP). It did not have this one.
The failure it prevents is a run scoring between DraftKings' publish and ours:
milder than football, where a touchdown moves a total ~6 points against a run's
0.5-1, but a grand slam is not mild.

WHY THIS READS THE STATE TABLE INSTEAD OF KEEPING A CLOCK. NCAAF and NFL hold a
ScoreClock in memory across passes. `run_live_scorer` is invoked fresh per
trigger, so the same trick here would report first sight forever — a guard dead
code can satisfy. `_score_changed_at` asks `live_game_state`, which already
holds the history.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.live_scorer import (_get_live_dk_odds,          # noqa: E402
                                _score_changed_at)

def _ts(age_sec: float) -> str:
    """Relative to NOW AT CALL TIME, not at import.

    `_age_seconds` measures against the real wall clock, so a module-level NOW
    silently ages: these tests passed alone and failed in the full suite, where
    ~3 minutes of other tests ran first and turned a "10s-old" quote into a
    3-minute-old one that the 30s bound rejected for the wrong reason."""
    return (datetime.now(timezone.utc)
            - timedelta(seconds=age_sec)).isoformat()


class _FakeConn:
    """Dispatches on the SQL, because the guarded path issues two queries: the
    odds read, then the score-change lookup."""

    def __init__(self, odds_row, score_change_ts):
        self._odds_row = odds_row
        self._score = score_change_ts
        self.saw_state_query = False
        self._pending = None

    def execute(self, sql, params=None):
        self._pending = "state" if "live_game_state" in sql else "odds"
        if self._pending == "state":
            self.saw_state_query = True
        return self

    def fetchone(self):
        return ((self._score,) if self._pending == "state"
                else self._odds_row)


# cols, in the order _get_live_dk_odds selects them
def _odds(age_sec: float):
    return (-110, -110, None, 8.5, -105, -115, _ts(age_sec),
            None, None, None, None)


def test_a_quote_published_before_the_score_is_declined():
    """The fix. The quote is 10s old — far inside the 30s bound — but the run
    scored 4s ago, so the number is already extinct."""
    conn = _FakeConn(_odds(age_sec=10), score_change_ts=_ts(4))
    assert _get_live_dk_odds(conn, "MLB_G", "totals") is None
    assert conn.saw_state_query


def test_the_age_bound_alone_would_have_allowed_it():
    """The control. Identical quote, no score change on record, so the old
    behaviour returns it. If this flips, the test above proves nothing."""
    conn = _FakeConn(_odds(age_sec=10), score_change_ts=None)
    got = _get_live_dk_odds(conn, "MLB_G", "totals")
    assert got is not None and got["total_line"] == 8.5


def test_a_quote_republished_after_the_score_is_kept():
    """Self-clearing: the block lasts only until DraftKings re-hangs."""
    conn = _FakeConn(_odds(age_sec=3), score_change_ts=_ts(20))
    assert _get_live_dk_odds(conn, "MLB_G", "totals") is not None


def test_the_age_bound_still_fires_independently():
    """The new guard must not have displaced the old one."""
    conn = _FakeConn(_odds(age_sec=600), score_change_ts=None)
    assert _get_live_dk_odds(conn, "MLB_G", "totals") is None


def test_the_score_lookup_is_scoped_and_ordered():
    """The query must bound to one game and compare against the LATEST state —
    a lookup that drifted onto another game, or onto the first score of the
    night, would block every quote for the rest of the game."""
    seen = {}

    class _Probe(_FakeConn):
        def execute(self, sql, params=None):
            if "live_game_state" in sql:
                seen["sql"], seen["params"] = sql, params
            return super().execute(sql, params)

    _get_live_dk_odds(_Probe(_odds(5), _ts(2)), "MLB_G", "totals")
    sql = seen["sql"]
    assert "game_id = %(g)s" in sql
    assert seen["params"] == {"g": "MLB_G"}
    assert "ORDER BY snapshot_at DESC" in sql       # latest state
    assert "IS DISTINCT FROM" in sql                # NULL-safe score compare
