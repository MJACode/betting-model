"""One-shot worker job: retrain mlb_runline, then sweep the new pickle.

Honest path from `.github/workflows/runline_sweep.yml`. Combined so the sweep
cannot score the pre-retrain live artifact. register defaults false — same as
every queued retrain — so production stays on the committed pickle.
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
DECLARED_KEY = "mlb-runline-retrain-sweep-2026-09-15"


def test_mlb_runline_retrain_sweep_is_a_registered_job_type():
    assert "mlb_runline_retrain_sweep" in jq.JOBS
    assert "command" not in jq.JOBS


def test_the_runner_retrains_then_sweeps_the_new_artifact():
    """Source pin: combined job, --artifact, no live-registry sweep, no recut."""
    fn, _ = jq.JOBS["mlb_runline_retrain_sweep"]
    src = inspect.getsource(fn)
    assert "_job_retrain_model" in src
    assert "scripts.mlb_runline_sweep" in src
    assert "--artifact" in src
    assert "refusing to sweep" in src
    assert "PAUSED_MODELS" not in src
    assert "ACTION_THRESHOLDS" not in src
    # Freeze guard stays in the sweep script; this job must not delete it.
    sweep_src = (ROOT / "scripts" / "mlb_runline_sweep.py").read_text(
        encoding="utf-8")
    assert "assert_retrain_allowed" in sweep_src
    assert "--artifact" in sweep_src


def test_empty_args_mean_the_honest_2019_2025_holdout_2026_path():
    _, validate = jq.JOBS["mlb_runline_retrain_sweep"]
    cleaned = validate({})
    assert cleaned["model_id"] == "mlb_runline"
    assert cleaned["seasons"] == [2019, 2020, 2021, 2022, 2023, 2024, 2025]
    assert cleaned["holdout"] == 2026
    assert cleaned["register"] is False
    assert cleaned["sweep_seasons"] == [2026]
    assert cleaned["min_bets"] == 30
    assert validate({"register": True, "command": "rm"})["register"] is True
    assert "command" not in validate({"command": "rm"})


def test_other_models_and_bad_bounds_are_refused():
    _, validate = jq.JOBS["mlb_runline_retrain_sweep"]
    with pytest.raises(ValueError, match="mlb_runline"):
        validate({"model_id": "mlb_moneyline"})
    with pytest.raises(ValueError, match="sweep_seasons"):
        validate({"sweep_seasons": []})
    with pytest.raises(ValueError, match="min_bets"):
        validate({"min_bets": 0})


def test_the_declared_key_is_present_and_does_not_register():
    entries = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(
        encoding="utf-8"))
    match = [e for e in entries if e["key"] == DECLARED_KEY]
    assert match, f"declared_jobs.json missing {DECLARED_KEY}"
    job = match[0]
    assert job["job_type"] == "mlb_runline_retrain_sweep"
    assert job["requested_by"] == "mike"
    assert job["args"]["register"] is False
    assert job["args"]["holdout"] == 2026
    assert job["args"]["seasons"] == [2019, 2020, 2021, 2022, 2023, 2024, 2025]
    assert job["args"]["sweep_seasons"] == [2026]
    assert "ONE-SHOT" in job["note"]
    assert "TEAM_STATS_ASOF_REBUILD_COMPLETE" in job["note"]
    _, validate = jq.JOBS["mlb_runline_retrain_sweep"]
    cleaned = validate(job.get("args") or {})
    assert cleaned["register"] is False


def test_retrain_then_sweep_passes_the_new_path(monkeypatch):
    seen = {}

    def fake_retrain(**kw):
        seen["retrain"] = kw
        return {"path": "/tmp/mlb_runline_baseline.pkl", "version": "vtest"}

    fake = types.ModuleType("scripts.mlb_runline_sweep")

    def fake_main():
        seen["argv"] = list(sys.argv[1:])
        print("=== mlb_runline — sweep on real DK run-line prices, seasons [2026] ===")
        print("VERDICT: this sits on a plateau")

    fake.main = fake_main
    monkeypatch.setattr(jq, "_job_retrain_model", fake_retrain)
    monkeypatch.setitem(sys.modules, "scripts.mlb_runline_sweep", fake)

    out = jq._job_mlb_runline_retrain_sweep(
        model_id="mlb_runline",
        seasons=[2019, 2020, 2021, 2022, 2023, 2024, 2025],
        holdout=2026, trials=None, register=False,
        statement_timeout_ms=1_800_000,
        sweep_seasons=[2026], min_bets=30,
    )
    assert seen["retrain"]["model_id"] == "mlb_runline"
    assert seen["retrain"]["register"] is False
    assert seen["retrain"]["holdout"] == 2026
    assert "--artifact" in seen["argv"]
    assert "/tmp/mlb_runline_baseline.pkl" in seen["argv"]
    assert "--seasons" in seen["argv"]
    assert "2026" in seen["argv"]
    assert out["registered"] is False
    assert out["artifact"] == "/tmp/mlb_runline_baseline.pkl"
    assert "VERDICT" in out["stdout"]
    assert "plateau" in out["summary"]


def test_missing_artifact_path_refuses_to_sweep_live(monkeypatch):
    monkeypatch.setattr(jq, "_job_retrain_model", lambda **kw: {"version": "vtest"})
    with pytest.raises(RuntimeError, match="refusing to sweep"):
        jq._job_mlb_runline_retrain_sweep(
            model_id="mlb_runline", seasons=[2019], holdout=2026,
            trials=None, register=False, statement_timeout_ms=1_800_000,
            sweep_seasons=[2026], min_bets=30,
        )


def test_marker_file_is_in_tree_so_the_freeze_would_not_block_the_worker():
    """Confirm, don't bypass. The sweep asserts this at import on the worker."""
    marker = ROOT / "data" / "TEAM_STATS_ASOF_REBUILD_COMPLETE"
    assert marker.is_file(), (
        "data/TEAM_STATS_ASOF_REBUILD_COMPLETE missing — MLB retrain/sweep "
        "stays frozen (docs/team_stats_leak.md). Do not delete the guard."
    )
