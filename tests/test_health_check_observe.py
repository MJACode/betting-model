"""A CRIT health row must not fail the refresh pass.

Measured 2026-09-14 (Supabase `pipeline_runs`, UTC day):
  09-14: 32 total, 1 clean, 20 failed_steps='health-check' only, 11 aborted
  09-13: 53 total, 23 clean, 25 health-check only, 4 aborted, 1 other
odds/score/settle succeeded; a standing CRIT reddened every hourly/evening
pass for ~2 days and tripped 'Refresh pass degraded'. Observability must
not fail the thing it observes.

Daily still fails the step on CRIT — that is the original Actions-red
intent. Hypothesis verified: `scripts/refresh_pass.sh` is hourly/evening/
overnight only (`scheduler.run_refresh_pass`); the daily pipeline calls
`step_health_check(run_date)` directly, not via `--step`. So `--step
health-check` is observe-only (`fail_on_crit=False`); daily keeps the
default True. A global always-True would have dropped the daily red.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT = Path(__file__).parent.parent
_SRC = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
_SH = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")


def _crit(monkeypatch, *, ok=False, boom=None):
    import tracking.system_health as sh

    def fake(run_date):
        if boom:
            raise boom
        return {"ok": ok, "crit": 0 if ok else 1, "warn": 0}

    monkeypatch.setattr(sh, "run_system_health", fake)


def test_a_crit_does_not_fail_the_observe_path(monkeypatch):
    import run_pipeline
    _crit(monkeypatch)
    assert run_pipeline.step_health_check("2026-09-14", fail_on_crit=False) is True


def test_a_crit_still_fails_the_daily_step(monkeypatch):
    import run_pipeline
    _crit(monkeypatch)
    assert run_pipeline.step_health_check("2026-09-14") is False
    assert run_pipeline.step_health_check("2026-09-14", fail_on_crit=True) is False


def test_ok_is_identity_in_both_modes(monkeypatch):
    """Empty/green map: observe and daily both return True."""
    import run_pipeline
    _crit(monkeypatch, ok=True)
    assert run_pipeline.step_health_check("2026-09-14", fail_on_crit=False) is True
    assert run_pipeline.step_health_check("2026-09-14", fail_on_crit=True) is True


def test_it_still_runs_the_check_when_observing(monkeypatch):
    import run_pipeline
    import tracking.system_health as sh
    called = []

    def fake(run_date):
        called.append(run_date)
        return {"ok": False, "crit": 1, "warn": 0}

    monkeypatch.setattr(sh, "run_system_health", fake)
    assert run_pipeline.step_health_check("2026-09-14", fail_on_crit=False) is True
    assert called == ["2026-09-14"]


def test_an_exception_does_not_fail_the_observe_path(monkeypatch):
    import run_pipeline
    _crit(monkeypatch, boom=RuntimeError("db down"))
    assert run_pipeline.step_health_check("2026-09-14", fail_on_crit=False) is True
    assert run_pipeline.step_health_check("2026-09-14", fail_on_crit=True) is False


def test_refresh_dispatch_observes_and_daily_does_not():
    table = _SRC[_SRC.index("step_fns = {"):_SRC.index("success = _timed_step")]
    assert "step_health_check(run_date, fail_on_crit=False)" in table
    daily = [ln for ln in _SRC.splitlines() if 'results["health_check"]' in ln]
    assert daily == ['    results["health_check"] = step_health_check(run_date)'], (
        "daily must keep the default fail_on_crit=True; a flag here would "
        "drop the Actions-red intent")


def test_refresh_pass_still_invokes_health_check():
    """It must still RUN and WRITE; decoupling is the return value, not a skip."""
    called = [ln.strip() for ln in _SH.splitlines()
              if ln.strip().startswith("step ") and len(ln.split()) > 1]
    assert "health-check" in called


def test_refresh_pass_is_not_the_daily_pipeline():
    """Hypothesis check: daily does not go through refresh_pass.sh."""
    sched = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert '["bash", "scripts/refresh_pass.sh"' in sched
    daily_fn = sched[sched.index("def run_daily_pipeline"):sched.index("def run_refresh_pass")]
    assert "refresh_pass.sh" not in daily_fn
    assert "run_pipeline.py" in daily_fn
