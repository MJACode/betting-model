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


def test_f5_markets_map_to_game_families():
    assert sweep.market_family("totals_1st_5_innings") == "totals"
    assert sweep.market_family("spreads_1st_5_innings") == "spreads"
    assert sweep.market_family("h2h_1st_5_innings") == "h2h"
    assert sweep.market_family("totals") == "totals"


def test_f5_totals_grade_uses_f5_scores_not_full_game():
    """3+1 = 4 vs F5 line 4.5 is under; a full-game 8-7 would be over."""
    meta = {"G1": (3.0, 1.0, "2026-09-15")}
    assert sweep.grade("totals_1st_5_innings", "under", meta["G1"], 4.5) is True
    assert sweep.grade("totals_1st_5_innings", "over", meta["G1"], 4.5) is False
    assert sweep.grade("h2h_1st_5_innings", "home", meta["G1"], None) is True
    # F5 tie is a moneyline push.
    assert sweep.grade("h2h_1st_5_innings", "home", (2.0, 2.0, "2026-09-15"), None) is None


def test_f5_load_sql_reads_f5_scores():
    src = inspect.getsource(sweep.load)
    assert "home_score_f5" in src
    assert "away_score_f5" in src
    assert "market in F5_MARKETS" in src


def test_f5_totals_collect_picks_grades_f5_line():
    """Pin fair over vs a soft de-vig that is cheap on over — F5 3+2=5 > 4.5."""
    by_game = {
        "G1": {
            "pinnacle": dict(home=None, away=None, spread=None, total=4.5,
                             over=-120, under=100, snap="2026-09-15T16:00:00Z"),
            "fanduel": dict(home=None, away=None, spread=None, total=4.5,
                            over=-102, under=-118, snap="2026-09-15T16:00:00Z"),
        }
    }
    meta = {"G1": (3.0, 2.0, "2026-09-15")}
    picks, diag = sweep.collect_picks(
        by_game, meta, "totals_1st_5_innings", vs="devig", pin_lean=False,
        soft_books=("fanduel",))
    assert diag["compared"] == 1
    assert len(picks) == 1
    _date, _edge, price, won, book = picks[0]
    assert book == "fanduel"
    assert price == -102
    assert won is True


def test_validator_accepts_f5_markets():
    _, validate = jq.JOBS["game_line_market_sweep"]
    got = validate({
        "sport": "MLB",
        "markets": ["totals_1st_5_innings"],
        "edges": [0.015, 0.02],
        "snapshot_type": "open",
        "bettable": True,
        "vs": "devig",
    })
    assert got["markets"] == ["totals_1st_5_innings"]
    with pytest.raises(ValueError, match="unknown markets"):
        validate({"markets": ["player_points"], "vs": "devig"})


def test_declared_f5_totals_job_validates():
    import json
    from pathlib import Path
    entries = json.loads((Path(__file__).resolve().parents[1]
                          / "jobs" / "declared_jobs.json")
                         .read_text(encoding="utf-8"))
    match = [e for e in entries
             if e["key"] == "mlb-f5-totals-market-sweep-2026-09-19"]
    assert match, "declared_jobs.json missing F5 totals remesure job"
    assert "ONE-SHOT" in match[0]["note"]
    _, validate = jq.JOBS["game_line_market_sweep"]
    cleaned = validate(match[0]["args"])
    assert cleaned["markets"] == ["totals_1st_5_innings"]
    assert cleaned["vs"] == "devig"
    assert cleaned["pin_lean"] is False
