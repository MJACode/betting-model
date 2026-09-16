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


def test_f5_market_maps_to_base_and_load_selects_f5_scores():
    assert sweep.base_market("totals_1st_5_innings") == "totals"
    assert sweep.base_market("spreads_1st_5_innings") == "spreads"
    assert sweep.base_market("h2h_1st_5_innings") == "h2h"
    assert sweep.base_market("spreads") == "spreads"
    src = inspect.getsource(sweep.load)
    assert "home_score_f5" in src
    assert "away_score_f5" in src
    assert "market in F5_MARKETS" in src or "F5_MARKETS" in src


def test_f5_h2h_grades_first_five_not_full_game():
    """Full game 8-1 home; F5 2-3 away. Grading the FG score would flip the bet."""
    by_game = {
        "G1": {
            "pinnacle": dict(home=120, away=-140, spread=None, total=None,
                             over=None, under=None, snap="2026-09-15T16:00:00Z"),
            "draftkings": dict(home=-110, away=-110, spread=None, total=None,
                               over=None, under=None, snap="2026-09-15T16:00:00Z"),
        }
    }
    # F5 scores: away winning. FG would be (8, 1) and home would cover ML.
    meta = {"G1": (2.0, 3.0, "2026-09-15")}
    picks, _ = sweep.collect_picks(
        by_game, meta, "h2h_1st_5_innings", vs="devig", pin_lean=True,
        soft_books=("draftkings",))
    assert len(picks) == 1
    assert picks[0][3] is True  # Pin away-lean won the F5
    fg_would_lose = sweep.grade("h2h", "away", (8.0, 1.0, "2026-09-15"), None)
    assert fg_would_lose is False


def test_f5_totals_do_not_use_the_full_game_run_total():
    """F5 2+2=4 under 4.5; FG 8+8=16 over. Under must win on the F5 key."""
    by_game = {
        "G1": {
            "pinnacle": dict(home=None, away=None, spread=None, total=4.5,
                             over=100, under=-120, snap="2026-09-15T16:00:00Z"),
            "draftkings": dict(home=None, away=None, spread=None, total=4.5,
                               over=-110, under=-110, snap="2026-09-15T16:00:00Z"),
        }
    }
    meta = {"G1": (2.0, 2.0, "2026-09-15")}
    picks, _ = sweep.collect_picks(
        by_game, meta, "totals_1st_5_innings", vs="devig", pin_lean=True,
        soft_books=("draftkings",))
    assert len(picks) == 1
    assert picks[0][3] is True  # Pin under-lean, F5 total 4
    fg_would_lose = sweep.grade("totals", "under", (8.0, 8.0, "2026-09-15"), 4.5)
    assert fg_would_lose is False


def test_f5_spreads_match_the_run_line_not_a_total():
    by_game = {
        "G1": {
            "pinnacle": dict(home=-150, away=130, spread=-0.5, total=None,
                             over=None, under=None, snap="2026-09-15T16:00:00Z"),
            "draftkings": dict(home=-110, away=-110, spread=-0.5, total=None,
                               over=None, under=None, snap="2026-09-15T16:00:00Z"),
        }
    }
    # F5 3-2, home covers -0.5. A totals fallback would see total=None and skip.
    meta = {"G1": (3.0, 2.0, "2026-09-15")}
    picks, diag = sweep.collect_picks(
        by_game, meta, "spreads_1st_5_innings", vs="devig", pin_lean=False,
        soft_books=("draftkings",))
    assert len(picks) == 1
    assert picks[0][3] is True
    assert diag.get("line_mismatch", 0) == 0


def test_job_validator_accepts_f5_keys():
    _, validate = jq.JOBS["game_line_market_sweep"]
    got = validate({"markets": ["totals_1st_5_innings"], "edges": [0.02]})
    assert got["markets"] == ["totals_1st_5_innings"]
    with pytest.raises(ValueError, match="unknown"):
        validate({"markets": ["player_points"]})
