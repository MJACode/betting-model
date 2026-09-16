"""Mike's earliest-Pin vs earliest-soft one-shots. Measure only.

The unaligned totals cell is look-ahead (median 14h). These jobs remeasure
it and the 300s twin on the worker; they do not publish or unpause.
"""
from __future__ import annotations

import json
from pathlib import Path

import tracking.job_queue as jq

ROOT = Path(__file__).resolve().parents[1]
MIKE_BOOKS = [
    "draftkings", "fanduel", "betmgm", "williamhill_us",
    "bovada", "espnbet", "hardrockbet",
]


def _declared(key: str) -> dict:
    entries = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(
        encoding="utf-8"))
    match = [e for e in entries if e["key"] == key]
    assert match, f"declared_jobs.json missing {key}"
    return match[0]


def test_earliest_totals_unaligned_is_look_ahead_measure_only():
    job = _declared(
        "mlb-game-line-market-sweep-earliest-totals-unaligned-2026-09-16")
    assert job["job_type"] == "game_line_market_sweep"
    _, validate = jq.JOBS["game_line_market_sweep"]
    cleaned = validate(job["args"])
    assert cleaned["markets"] == ["totals"]
    assert cleaned["quote"] == "earliest"
    assert cleaned["max_gap_s"] is None
    assert cleaned["vs"] == "implied"
    assert cleaned["bettable"] is False
    assert cleaned["juice_abs_max"] == 200.0
    assert cleaned["min_line"] == 5.5
    assert cleaned["max_line"] == 14.5
    assert cleaned["soft_books"] == MIKE_BOOKS
    assert cleaned["date_from"] == "2024-03-20"
    note = job["note"].lower()
    assert "look-ahead" in note
    assert "does not publish" in note
    assert "does not set mlb_total_market_publish" in note


def test_earliest_totals_aligned_keeps_the_five_minute_gap():
    job = _declared(
        "mlb-game-line-market-sweep-earliest-totals-aligned-2026-09-16")
    _, validate = jq.JOBS["game_line_market_sweep"]
    cleaned = validate(job["args"])
    assert cleaned["quote"] == "earliest"
    assert cleaned["max_gap_s"] == 300.0
    assert cleaned["vs"] == "implied"
    assert cleaned["soft_books"] == MIKE_BOOKS


def test_earliest_spreads_jobs_are_measure_only():
    una = _declared(
        "mlb-game-line-market-sweep-earliest-spreads-unaligned-2026-09-16")
    ali = _declared(
        "mlb-game-line-market-sweep-earliest-spreads-aligned-2026-09-16")
    _, validate = jq.JOBS["game_line_market_sweep"]
    u = validate(una["args"])
    a = validate(ali["args"])
    assert u["markets"] == a["markets"] == ["spreads"]
    assert u["quote"] == a["quote"] == "earliest"
    assert u["max_gap_s"] is None
    assert a["max_gap_s"] == 300.0
    assert u["vs"] == "implied"
    assert "does not publish" in una["note"].lower()
    assert "does not set mlb_spread_market_publish" in una["note"].lower()
