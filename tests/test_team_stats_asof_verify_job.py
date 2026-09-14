"""team_stats_asof_verify job + health wiring after the rebuild marker.

The rebuild landed 2026-09-03; the marker lifts the #710 freeze. These pins
keep the ongoing verify-only gate from drifting: a declared job that runs the
same checks as `python -m data.team_stats_rebuild --verify-only`, and a
system_health CRIT check for the two invariants.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import tracking.job_queue as jq

ROOT = Path(__file__).resolve().parents[1]


def test_team_stats_asof_verify_is_registered():
    assert "team_stats_asof_verify" in jq.JOBS


def test_validator_accepts_empty_args():
    _, validate = jq.JOBS["team_stats_asof_verify"]
    assert validate({}) == {}


def test_validator_accepts_sport_and_seasons():
    _, validate = jq.JOBS["team_stats_asof_verify"]
    assert validate({"sport": "mlb", "seasons": [2024, 2025]}) == {
        "sport": "MLB", "seasons": [2024, 2025],
    }


def test_validator_rejects_unknown_sport():
    _, validate = jq.JOBS["team_stats_asof_verify"]
    with pytest.raises(ValueError, match="unknown sport"):
        validate({"sport": "NCAAF"})


def test_validator_rejects_empty_seasons():
    _, validate = jq.JOBS["team_stats_asof_verify"]
    with pytest.raises(ValueError, match="seasons"):
        validate({"seasons": []})


def test_job_calls_verify_and_never_rebuilds():
    """Source pin: verify-only. A future edit that DELETE/rebuilds here reopens
    the overwrite risk the rebuild script guards against."""
    fn, _ = jq.JOBS["team_stats_asof_verify"]
    src = inspect.getsource(fn)
    assert "verify(" in src
    assert "rebuild_sport" not in src
    assert "DELETE FROM" not in src
    assert "RuntimeError" in src
    # Surfaces verify()'s live-season skip in the job summary (not a rebuild).
    assert "skipped_live_season" in src


def test_declared_job_is_present_and_validates():
    entries = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(
        encoding="utf-8"))
    match = [e for e in entries if e["job_type"] == "team_stats_asof_verify"]
    assert match, "declared_jobs.json missing team_stats_asof_verify entry"
    entry = match[0]
    assert entry["key"].startswith("team-stats-asof-verify")
    _, validate = jq.JOBS[entry["job_type"]]
    validate(entry.get("args") or {})


def test_system_health_wires_asof_integrity_check():
    src = (ROOT / "tracking" / "system_health.py").read_text(encoding="utf-8")
    assert 'r.add("team_stats_asof_integrity"' in src
    assert "team_stats_rebuild" in src
    # Must not rebuild from health either.
    block_start = src.index("team_stats_asof_integrity")
    # Look at the surrounding try block roughly
    window = src[block_start - 800: block_start + 800]
    assert "rebuild_sport" not in window
    assert "DELETE FROM" not in window
