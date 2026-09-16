"""One-shot worker job that runs the game-line Pinnacle-vs-soft sweep.

Measure only: ROI grid on equal-line pre-game quotes. Does not write a
threshold, pause a model, or publish a pick.
"""
from __future__ import annotations

import inspect
import json
import sys
import types
from pathlib import Path

import pytest

import tracking.job_queue as jq

ROOT = Path(__file__).resolve().parents[1]
DECLARED_KEY = "mlb-game-line-market-sweep-2026-09-15"


def test_game_line_market_sweep_is_a_registered_job_type():
    assert "game_line_market_sweep" in jq.JOBS
    assert "command" not in jq.JOBS


def test_the_runner_imports_the_script_main_not_a_shell():
    fn, _ = jq.JOBS["game_line_market_sweep"]
    src = inspect.getsource(fn)
    assert "scripts.game_line_market_sweep" in src
    helper = inspect.getsource(jq._run_script_main)
    assert "importlib.import_module" in helper
    assert "subprocess" not in helper
    assert "PAUSED_MODELS" not in src
    assert "ACTION_THRESHOLDS" not in src


def test_empty_args_mean_mlb_spreads_and_totals():
    _, validate = jq.JOBS["game_line_market_sweep"]
    assert validate({}) == {"sport": ["MLB"], "market": ["spreads", "totals"]}
    assert validate({"sport": None, "market": ""}) == {
        "sport": ["MLB"], "market": ["spreads", "totals"]}
    assert validate({"sport": "MLB", "market": "spreads", "command": "rm"}) == {
        "sport": ["MLB"], "market": ["spreads"]}


def test_sport_and_market_are_bounded():
    _, validate = jq.JOBS["game_line_market_sweep"]
    with pytest.raises(ValueError, match="unknown sport"):
        validate({"sport": ["NHL"]})
    with pytest.raises(ValueError, match="unknown market"):
        validate({"market": ["player_points"]})
    with pytest.raises(ValueError, match="sport"):
        validate({"sport": []})
    with pytest.raises(ValueError, match="market"):
        validate({"market": []})


def test_the_declared_key_is_present_and_valid():
    entries = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(
        encoding="utf-8"))
    match = [e for e in entries if e["key"] == DECLARED_KEY]
    assert match, f"declared_jobs.json missing {DECLARED_KEY}"
    job = match[0]
    assert job["job_type"] == "game_line_market_sweep"
    assert job["requested_by"] == "mike"
    assert "ONE-SHOT" in job["note"]
    assert "measure-only" in job["note"].lower() or "measure only" in job["note"].lower()
    _, validate = jq.JOBS["game_line_market_sweep"]
    cleaned = validate(job.get("args") or {})
    assert cleaned["sport"] == ["MLB"]
    assert cleaned["market"] == ["spreads", "totals"]


def test_runner_captures_stdout_from_the_script_main(monkeypatch):
    fake = types.ModuleType("scripts.game_line_market_sweep")

    def fake_main():
        print("=== MLB spreads — sharp pinnacle, 8 soft books")
        print("    compared 12, line_mismatch 3, no_sharp 1")

    fake.main = fake_main
    monkeypatch.setitem(sys.modules, "scripts.game_line_market_sweep", fake)
    out = jq._job_game_line_market_sweep(sport=["MLB"], market=["spreads", "totals"])
    assert "compared 12" in out["stdout"]
    assert "line_mismatch 3" in out["stdout"]
    assert out["sport"] == ["MLB"]
    assert out["market"] == ["spreads", "totals"]
    assert "compared 12" in out["summary"]
