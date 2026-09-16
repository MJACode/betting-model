"""F5 keys on the game-line market sweep job, plus the 2026-09-16 one-shots."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import tracking.job_queue as jq

ROOT = Path(__file__).resolve().parents[1]


def test_f5_markets_validate_on_both_arg_shapes():
    _, validate = jq.JOBS["game_line_market_sweep"]
    rich = validate({
        "markets": ["totals_1st_5_innings", "spreads"],
        "edges": [0.015, 0.02],
    })
    assert rich["markets"] == ["totals_1st_5_innings", "spreads"]
    legacy = validate({"sport": "MLB", "market": ["h2h_1st_5_innings"]})
    assert legacy["market"] == ["h2h_1st_5_innings"]
    with pytest.raises(ValueError, match="unknown"):
        validate({"market": ["player_points"]})


def test_spreads_plateau_declaration_asks_for_the_1p8_neighbourhood():
    entries = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(
        encoding="utf-8"))
    key = "mlb-game-line-market-sweep-spreads-plateau-2026-09-16"
    match = [e for e in entries if e["key"] == key]
    assert match, f"missing {key}"
    job = match[0]
    assert job["job_type"] == "game_line_market_sweep"
    _, validate = jq.JOBS["game_line_market_sweep"]
    cleaned = validate(job["args"])
    assert cleaned["markets"] == ["spreads"]
    assert 0.018 in cleaned["edges"]
    assert 0.015 in cleaned["edges"]
    assert 0.02 in cleaned["edges"]
    assert cleaned["vs"] == "devig"
    assert cleaned["pin_lean"] is False
    assert cleaned["bettable"] is True
    assert "PAUSED" not in job["note"] or "does not" in job["note"].lower()


def test_f5_totals_declaration_grades_the_f5_market_key():
    entries = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(
        encoding="utf-8"))
    key = "mlb-game-line-market-sweep-f5-totals-2026-09-16"
    match = [e for e in entries if e["key"] == key]
    assert match, f"missing {key}"
    _, validate = jq.JOBS["game_line_market_sweep"]
    cleaned = validate(match[0]["args"])
    assert cleaned["markets"] == ["totals_1st_5_innings"]
    assert cleaned["vs"] == "devig"
