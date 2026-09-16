"""One-shot worker job: retrain mlb_over_under, then sweep the new pickle.

Twin of tests/test_mlb_runline_retrain_sweep_job.py. Combined so the sweep
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
DECLARED_KEY = "mlb-over-under-retrain-sweep-2026-09-16"


def test_mlb_over_under_retrain_sweep_is_a_registered_job_type():
    assert "mlb_over_under_retrain_sweep" in jq.JOBS
    assert "command" not in jq.JOBS


def test_the_runner_retrains_then_sweeps_the_new_artifact():
    """Source pin: combined job, --artifact, no live-registry sweep, no recut."""
    fn, _ = jq.JOBS["mlb_over_under_retrain_sweep"]
    src = inspect.getsource(fn)
    assert "_job_retrain_model" in src
    assert "scripts.mlb_over_under_sweep" in src
    assert "--artifact" in src
    assert "refusing to sweep" in src
    assert "PAUSED_MODELS" not in src
    assert "ACTION_THRESHOLDS" not in src
    # Freeze guard stays in the sweep script; this job must not delete it.
    sweep_src = (ROOT / "scripts" / "mlb_over_under_sweep.py").read_text(
        encoding="utf-8")
    assert "assert_retrain_allowed" in sweep_src
    assert "--artifact" in sweep_src
    assert "feature_matrix" in sweep_src
    assert 'artifact.get("feature_cols")' in sweep_src
    assert "include_handicap" in sweep_src
    assert "pd.DataFrame([{c: feats.get(c) for c in feature_cols}])" not in sweep_src


def test_empty_args_mean_the_honest_2019_2025_holdout_2026_path():
    _, validate = jq.JOBS["mlb_over_under_retrain_sweep"]
    cleaned = validate({})
    assert cleaned["model_id"] == "mlb_over_under"
    assert cleaned["seasons"] == [2019, 2020, 2021, 2022, 2023, 2024, 2025]
    assert cleaned["holdout"] == 2026
    assert cleaned["register"] is False
    assert cleaned["sweep_seasons"] == [2026]
    assert cleaned["min_bets"] == 30
    assert validate({"register": True, "command": "rm"})["register"] is True
    assert "command" not in validate({"command": "rm"})


def test_other_models_and_bad_bounds_are_refused():
    _, validate = jq.JOBS["mlb_over_under_retrain_sweep"]
    with pytest.raises(ValueError, match="mlb_over_under"):
        validate({"model_id": "mlb_runline"})
    with pytest.raises(ValueError, match="mlb_over_under"):
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
    assert job["job_type"] == "mlb_over_under_retrain_sweep"
    assert job["requested_by"] == "mike"
    assert job["args"]["register"] is False
    assert job["args"]["holdout"] == 2026
    assert job["args"]["seasons"] == [2019, 2020, 2021, 2022, 2023, 2024, 2025]
    assert job["args"]["sweep_seasons"] == [2026]
    assert "ONE-SHOT" in job["note"]
    assert "TEAM_STATS_ASOF_REBUILD_COMPLETE" in job["note"]
    _, validate = jq.JOBS["mlb_over_under_retrain_sweep"]
    cleaned = validate(job.get("args") or {})
    assert cleaned["register"] is False
    assert cleaned["model_id"] == "mlb_over_under"


def test_retrain_then_sweep_passes_the_new_path(monkeypatch):
    seen = {}

    def fake_retrain(**kw):
        seen["retrain"] = kw
        return {"path": "/tmp/mlb_over_under_baseline.pkl", "version": "vtest"}

    fake = types.ModuleType("scripts.mlb_over_under_sweep")

    def fake_main():
        seen["argv"] = list(sys.argv[1:])
        print("=== mlb_over_under — sweep on real DK totals prices, seasons [2026] ===")
        print("VERDICT: this sits on a plateau")

    fake.main = fake_main
    monkeypatch.setattr(jq, "_job_retrain_model", fake_retrain)
    monkeypatch.setitem(sys.modules, "scripts.mlb_over_under_sweep", fake)

    out = jq._job_mlb_over_under_retrain_sweep(
        model_id="mlb_over_under",
        seasons=[2019, 2020, 2021, 2022, 2023, 2024, 2025],
        holdout=2026, trials=None, register=False,
        statement_timeout_ms=1_800_000,
        sweep_seasons=[2026], min_bets=30,
    )
    assert seen["retrain"]["model_id"] == "mlb_over_under"
    assert seen["retrain"]["register"] is False
    assert seen["retrain"]["holdout"] == 2026
    assert "--artifact" in seen["argv"]
    assert "/tmp/mlb_over_under_baseline.pkl" in seen["argv"]
    assert "--seasons" in seen["argv"]
    assert "2026" in seen["argv"]
    assert out["registered"] is False
    assert out["artifact"] == "/tmp/mlb_over_under_baseline.pkl"
    assert "VERDICT" in out["stdout"]
    assert "plateau" in out["summary"]


def test_missing_artifact_path_refuses_to_sweep_live(monkeypatch):
    monkeypatch.setattr(jq, "_job_retrain_model", lambda **kw: {"version": "vtest"})
    with pytest.raises(RuntimeError, match="refusing to sweep"):
        jq._job_mlb_over_under_retrain_sweep(
            model_id="mlb_over_under", seasons=[2019], holdout=2026,
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


def test_over_covers_when_combined_score_beats_the_total_line():
    """Grading must match paper_tracker / _compute_target, not a rebuilt line."""
    from scripts.mlb_over_under_sweep import _side_rows

    game = dict(game_id="g1", game_date="2026-06-01",
                home_score=6.0, away_score=4.0)
    odds = dict(total_line=8.5, over_price=-110, under_price=-110)
    rows = _side_rows(game, prob_over=0.60, odds=odds)
    by_side = {r["side"]: r for r in rows}
    assert set(by_side) == {"over", "under"}
    assert by_side["over"]["won"] is True
    assert by_side["under"]["won"] is False
    assert by_side["over"]["total_line"] == 8.5
    assert by_side["over"]["model_prob"] == pytest.approx(0.60)
    assert by_side["under"]["model_prob"] == pytest.approx(0.40)


def test_under_covers_when_combined_score_is_under_the_line():
    from scripts.mlb_over_under_sweep import _side_rows

    game = dict(game_id="g1", game_date="2026-06-01",
                home_score=2.0, away_score=3.0)
    odds = dict(total_line=8.5, over_price=-105, under_price=-115)
    rows = _side_rows(game, prob_over=0.45, odds=odds)
    by_side = {r["side"]: r for r in rows}
    assert by_side["over"]["won"] is False
    assert by_side["under"]["won"] is True


def test_push_on_the_total_emits_no_sides():
    from scripts.mlb_over_under_sweep import _side_rows

    game = dict(game_id="g1", game_date="2026-06-01",
                home_score=4.0, away_score=4.0)
    odds = dict(total_line=8.0, over_price=-110, under_price=-110)
    assert _side_rows(game, prob_over=0.55, odds=odds) == []


def test_price_below_the_house_floor_is_not_a_gradable_side(monkeypatch):
    """A cell measured on bets the scorer refuses is not a cut."""
    from scripts import mlb_over_under_sweep as ou

    monkeypatch.setattr(ou.config, "min_odds_for", lambda model_id: -200)
    game = dict(game_id="g1", game_date="2026-06-01",
                home_score=6.0, away_score=4.0)
    odds = dict(total_line=8.5, over_price=-250, under_price=-110)
    rows = ou._side_rows(game, prob_over=0.70, odds=odds)
    assert [r["side"] for r in rows] == ["under"]
