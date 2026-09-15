"""game_line_market_sweep: snapshot_type on odds, commence_time on games.

Error Handler 2026-09-15: the sweep must not invent o.commence_time, must
report 2/3/4pp even when n is thin, and must be runnable as a worker job
because unbounded odds joins time out on MCP execute_sql.
"""
from __future__ import annotations

import inspect

import pytest

import tracking.job_queue as jq
from scripts import game_line_market_sweep as sweep


def test_load_sql_uses_snapshot_type_not_odds_commence_time():
    src = inspect.getsource(sweep.load)
    assert "o.snapshot_type = %s" in src
    assert "o.commence_time" not in src
    assert "g.commence_time" in src
    assert "o.snapshot_at" in src


def test_default_edges_are_two_three_four_pp():
    assert sweep.DEFAULT_EDGES == (0.02, 0.03, 0.04)


def test_thin_cells_still_report_roi():
    """n < 25 used to return (e, n, None, None, None) and hide the number."""
    # One win at -110 is +0.909u; ROI is not None.
    picks = [("2026-04-01", 0.03, -110.0, True, "draftkings")]
    rows = sweep._summarize(picks, [0.02, 0.03, 0.04])
    assert rows[0]["n"] == 1
    assert rows[0]["thin"] is True
    assert rows[0]["roi_pct"] is not None
    assert rows[1]["n"] == 1
    assert rows[2]["n"] == 0
    assert rows[2]["roi_pct"] is None


def test_pin_lean_keeps_only_pinnacles_side():
    by_game = {
        "G1": {
            "pinnacle": dict(home=-150, away=130, spread=-1.5, total=None,
                             over=None, under=None, snap="2026-09-15T16:00:00Z"),
            "draftkings": dict(home=-110, away=-110, spread=-1.5, total=None,
                               over=None, under=None, snap="2026-09-15T16:00:00Z"),
        }
    }
    meta = {"G1": (5.0, 3.0, "2026-09-15")}
    all_sides, _ = sweep.collect_picks(
        by_game, meta, "spreads", vs="implied", pin_lean=False,
        soft_books=("draftkings",))
    lean, _ = sweep.collect_picks(
        by_game, meta, "spreads", vs="implied", pin_lean=True,
        soft_books=("draftkings",))
    assert len(all_sides) == 1
    assert len(lean) == 1
    # Pin home no-vig is the lean (home -150).
    assert lean[0][1] > 0  # edge
    # side is recorded only indirectly; grade home cover: 5-3 at -1.5 covers.
    assert lean[0][3] is True


def test_job_type_is_registered_and_validates():
    assert "game_line_market_sweep" in jq.JOBS
    _, validate = jq.JOBS["game_line_market_sweep"]
    got = validate({
        "sport": "MLB",
        "markets": ["spreads", "totals"],
        "edges": [0.02, 0.03, 0.04],
        "snapshot_type": "open",
        "bettable": True,
        "command": "rm -rf /",
    })
    assert got["sport"] == "MLB"
    assert got["snapshot_type"] == "open"
    assert got["edges"] == [0.02, 0.03, 0.04]
    assert "command" not in got
    with pytest.raises(ValueError):
        validate({"snapshot_type": "pregame"})
    with pytest.raises(ValueError):
        validate({"sport": "NBA"})


def test_load_does_not_reference_odds_commence_time_anywhere_in_module():
    src = inspect.getsource(sweep)
    assert "o.commence_time" not in src
