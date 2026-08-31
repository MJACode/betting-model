"""ModelCalibration — the weekly agent, and the two exemptions it removed.

mike, 2026-08-31: recurring calibrated sweeps on ALL models, as a global rule.
"Global" is the load-bearing word: the two models that most needed reviewing
were the two the old sweep could not see.
"""

from __future__ import annotations

import config
from scripts.calibrated_threshold_sweep import EDGE_GRID, PROB_GRID, sweep


def _rows(n=40, p=0.70, implied=0.60, units=0.9):
    return [{"date": f"2026-08-{(i % 20) + 1:02d}", "cal_p": p,
             "cal_edge": p - implied, "units": units, "result": "WIN"}
            for i in range(n)]


# ── prob-only models are now in scope ────────────────────────────────────────

def test_a_prob_only_sweep_uses_only_the_probability_dimension():
    """Their `edge` is measured against an invented baseline, not a market
    price, so sweeping it would tune a number that means nothing."""
    cells = sweep(_rows(), 7.0, _rows(), [0.0])
    assert {c["min_edge"] for c in cells} == {0.0}
    assert {c["min_prob"] for c in cells} <= set(PROB_GRID)


def test_the_full_sweep_is_unchanged_when_no_grid_is_passed():
    """The generalisation must not have moved the default behaviour."""
    cells = sweep(_rows(), 7.0, _rows())
    assert {c["min_edge"] for c in cells} <= set(EDGE_GRID)
    assert len(cells) > len(sweep(_rows(), 7.0, _rows(), [0.0]))


def test_plateau_is_computed_within_the_narrow_grid():
    """With one edge column the neighbourhood is vertical only. Indexing into
    the full EDGE_GRID here would read cells that were never swept."""
    cells = sweep(_rows(), 7.0, _rows(), [0.0])
    assert all(0 <= c["plateau"] <= 2 for c in cells)


def test_the_agent_sweeps_every_registered_model_except_live_ones():
    """Live lanes keep their own loop (tracking/live_calibration.py); judging
    them on a weekly cadence would misreport both mechanisms."""
    import inspect

    from tracking import model_calibration_agent as agent

    src = inspect.getsource(agent.run_agent)
    assert "sorted(config.ACTION_THRESHOLDS)" in src
    assert "config.LIVE_MODELS" in src
    assert "PROB_ONLY_MODELS" in src


def test_the_agent_changes_nothing_on_its_own():
    """It writes a measurement table and posts. A threshold, a pause or a
    promotion is a model update and needs a person (CLAUDE.md 1b)."""
    import inspect

    from tracking import model_calibration_agent as agent

    src = inspect.getsource(agent)
    assert "model_action_thresholds" not in src   # no threshold write
    assert "model_auto_pauses" not in src         # no pause write
    assert "SET promoted" not in src              # no promotion
    assert "promote(" not in src
    # It refits CANDIDATES. A refit that promoted itself would re-cut every
    # mapped model overnight with nobody deciding to.
    assert "run_calibration_fit" in src
    assert "promoted_only=False" in src


# ── the home-run exemption ───────────────────────────────────────────────────

def test_home_runs_are_no_longer_exempt_from_pausing():
    """The session-60 "HR is never paused" directive was lifted 2026-08-31.

    It rested on a true observation -- a longshot market always looks bad on
    W-L -- used to excuse a model that is separately overstating: claimed 22.5%
    against a realised 16.7% over 252 bets at an average +513.
    """
    src = (config.ROOT / "config.py").read_text(encoding="utf-8")
    assert "never paused" not in src
    assert "mlb_prop_batter_hr" not in config.PAUSED_MODELS


def test_the_review_rule_exempts_no_model():
    """Whatever list the review walks, it must not carry a carve-out. An
    exemption is how the worst model on the board stayed unreviewed."""
    import inspect

    from tracking import threshold_review

    src = inspect.getsource(threshold_review)
    assert "batter_hr" not in src
    assert "EXEMPT" not in src.upper().replace("EXEMPTION", "")


def test_prob_only_models_still_carry_thresholds_the_sweep_can_read():
    for model_id in sorted(config.PROB_ONLY_MODELS):
        assert model_id in config.ACTION_THRESHOLDS, model_id
        assert "min_prob" in config.ACTION_THRESHOLDS[model_id]


# ── the boot catch-up ────────────────────────────────────────────────────────

def test_the_scheduler_catches_up_stale_weekly_work_on_boot():
    """A weekly cron has a one-week worst case, and that bit us: the Savant job
    was added hours AFTER its Monday trigger had passed, so a four-month-stale
    pitcher snapshot and an entirely absent batter one would have waited
    another seven days."""
    import inspect

    import scheduler

    src = inspect.getsource(scheduler.catch_up_weekly_jobs)
    assert "player_savant_stats" in src
    assert "run_savant_refresh()" in src
    # Guarded by a freshness check, or a crash-looping container re-pulls.
    assert "stale" in src

    main_src = inspect.getsource(scheduler.main)
    assert "catch_up_weekly_jobs()" in main_src
    # Only one service should do the ingest, or the API spend doubles.
    assert 'owns("savant_refresh")' in main_src


def test_model_calibration_is_registered_weekly():
    import scheduler

    job = {j.id: j for j in scheduler.build_scheduler().get_jobs()}["model_calibration"]
    assert "mon" in str(job.trigger)
