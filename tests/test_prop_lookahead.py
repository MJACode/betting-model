"""Props are the surface picks actually appear on — so the look-ahead must reach them.

#519 taught the GAME scorer to price tomorrow, and it produced nothing anyone
could see. Measured on 2026-09-06: of 19 MLB BETs on that day's board, **19
were props and 0 were game-level** — the three MLB game models are two paused
and one that rarely clears its cut. Meanwhile this pipeline fetched and scored
props for TODAY only, so tomorrow's board had zero prop odds.

DraftKings had them. A probe of ATL @ PHI (ET 2026-09-07) returned 40 outcomes
across batter_hits and pitcher_strikeouts while `player_prop_odds` held zero
rows for that date. After the fix: 7,528 prop rows, 26 picks and the first BET
(Dylan Cease Under 7.5 Ks, -128, edge +10.9%).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT = Path(__file__).parent.parent


def _events_src():
    import inspect

    from data.ingestors.prop_odds_ingestor import _get_events
    return inspect.getsource(_get_events)


class TestTheOddsFetchReachesTomorrow:
    def test_the_window_is_a_range_not_an_equality(self):
        src = _events_src()
        assert "event_date == target_date" not in src, (
            "an equality here is what left tomorrow with no prop odds at all")
        assert "target_date <= event_date <= _horizon" in src

    def test_the_date_is_compared_in_ET(self):
        """THE TRAP THIS ALREADY FELL INTO ONCE. The first probe written for
        this filtered on the UTC date, picked up a 02:11Z event — 22:11 the
        PREVIOUS evening in ET, i.e. one of today's late games — and 'yes,
        props exist for tomorrow' was nearly reported off it."""
        src = _events_src()
        assert 'ZoneInfo("America/New_York")' in src or "_ET" in src
        assert "astimezone(_ET)" in src

    def test_zero_days_ahead_still_means_today_only(self):
        # The old behaviour has to remain reachable, or a caller that wants one
        # date silently pays for a week of per-event prop calls.
        src = _events_src()
        assert "days_ahead: int = 0" in src

    def test_the_horizon_cannot_go_negative(self):
        src = _events_src()
        assert "max(0, days_ahead)" in src


class TestTheScorerReachesTomorrow:
    def test_prop_scoring_loops_the_window(self):
        src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
        block = src[src.index("def step_prop_scoring("):]
        block = block[:block.index("\ndef ", 10)]
        assert "GAME_SCORE_AHEAD_DAYS" in block
        assert "for offset in range(" in block

    def test_one_bad_date_does_not_cost_the_others(self):
        """Today's board is the one with games about to start; a failure
        scoring tomorrow must not take it down."""
        src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
        block = src[src.index("def step_prop_scoring("):]
        block = block[:block.index("\ndef ", 10)]
        # rindex, not index: there is an earlier except around the config
        # import, and matching that one would pass while the LOOP body was
        # unguarded — the exact thing this test exists to prevent.
        assert "except Exception" in block
        assert block.rindex("except Exception") > block.index("for offset in range(")

    def test_it_starts_at_run_date(self):
        # offset 0 must be included, or the fix would trade tomorrow for today.
        src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
        block = src[src.index("def step_prop_scoring("):]
        block = block[:block.index("\ndef ", 10)]
        assert "range(0," in block
