"""ModelCalibration — the weekly agent, and the two exemptions it removed.

mike, 2026-08-31: recurring calibrated sweeps on ALL models, as a global rule.
"Global" is the load-bearing word: the two models that most needed reviewing
were the two the old sweep could not see.
"""

from __future__ import annotations

from datetime import date

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


class _ProbeConn:
    """Answers one freshness probe with a fixed row."""

    def __init__(self, row):
        self._row = row

    def execute(self, *a, **k):
        return self

    def fetchone(self):
        return self._row

    def rollback(self):
        pass



def test_the_scheduler_catches_up_stale_weekly_work_on_boot():
    """A weekly cron has a one-week worst case, and that bit us: the Savant job
    was added hours AFTER its Monday trigger had passed, so a four-month-stale
    pitcher snapshot and an entirely absent batter one would have waited
    another seven days.

    Behavioural rather than source-matched since 2026-09-01, when the Savant
    probe moved into `_savant_is_stale` so a second weekly job could reuse the
    surrounding loop. Matching the text of one function pinned its SHAPE; what
    has to hold is that stale data still triggers the refresh on boot.
    """
    import inspect

    import scheduler

    stale, _, _ = scheduler._savant_is_stale(_ProbeConn((None, 0)), 2026)
    assert stale, "an empty season must read as stale"
    fresh, _, _ = scheduler._savant_is_stale(
        _ProbeConn((date.today().isoformat(), 2)), 2026)
    assert not fresh, ("no freshness guard — a crash-looping container would "
                       "re-pull on every restart")

    src = inspect.getsource(scheduler.catch_up_weekly_jobs)
    assert "run_savant_refresh()" in src
    # Only one service should do the ingest, or the API spend doubles. The
    # guard moved INTO the catch-up on 2026-09-01: gating the whole function on
    # this one job meant a role that did not own Savant skipped every other
    # weekly catch-up too.
    assert 'owns("savant_refresh")' in src

    main_src = inspect.getsource(scheduler.main)
    assert "catch_up_weekly_jobs()" in main_src


def test_model_calibration_is_registered_weekly():
    import scheduler

    job = {j.id: j for j in scheduler.build_scheduler().get_jobs()}["model_calibration"]
    assert "mon" in str(job.trigger)


# ── the catch-up's own first run failed, and taught two things ───────────────
#
# 2026-08-31, first deploy carrying catch_up_weekly_jobs():
#     ERROR catch-up check failed (scheduler continues)
# because player_savant_stats.as_of_date does not exist in production. Two
# separate defects behind one log line:
#   1. _run_migrations only ever ran inside setup_database() -- first-time setup
#      -- so every column added since has been missing in production. The Savant
#      upsert names as_of_date in its INSERT, so the refresh this catch-up
#      triggers would have failed too.
#   2. The probe failed CLOSED: it could not tell whether the data was stale, so
#      it did nothing. For idempotent two-request work, "cannot tell" must mean
#      "do it".

def test_the_probe_defaults_to_stale():
    """A failed freshness probe must still run the refresh.

    Asserted on behaviour rather than on the initialiser's source text: what
    matters is the ANSWER a broken probe gives, and a test that only pins the
    line `stale = True` passes just as happily if a later branch overwrites it.
    """
    import scheduler

    class _Boom:
        def execute(self, *a, **k):
            raise RuntimeError("column as_of_date does not exist")

        def rollback(self):
            pass

    stale, newest, kinds = scheduler._savant_is_stale(_Boom(), 2026)
    assert stale is True, (
        "a probe that cannot tell must refresh — for idempotent two-request "
        "work, 'cannot tell' means 'do it'")
    assert newest is None and kinds == 0


def test_the_catch_up_applies_column_migrations_first():
    """Otherwise it probes, and then refreshes into, a column that does not exist."""
    import inspect

    import scheduler

    src = inspect.getsource(scheduler.catch_up_weekly_jobs)
    # The IMPORT, not the word. Mutation-checked 2026-09-01: the comment above
    # the block names `_run_migrations`, so matching the bare identifier found
    # the comment and the assertion held with the call moved BELOW the probe —
    # a test that passes with the fix removed is not a test (CLAUDE.md §7).
    call = "from data.db_setup import _run_migrations"
    assert call in src
    # The probe itself lives in _savant_is_stale since 2026-09-01; the ordering
    # guarantee is against the CALL, which is the thing that has to come second.
    assert src.index(call) < src.index("_savant_is_stale("), (
        "the catch-up probes, and then refreshes into, a column the migrations "
        "have not created yet")


def test_column_migrations_run_every_pipeline_pass():
    """The gap data/view_migrations closed for views, left open for columns:
    a schema change with no path into production is not a schema change."""
    import run_pipeline

    src = (config.ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    assert hasattr(run_pipeline, "step_apply_column_migrations")
    assert 'results["column_migrations"] = step_apply_column_migrations' in src
    assert '"apply-column-migrations"' in src


def test_the_savant_column_is_in_the_migration_list():
    """The column the ingestor writes has to be one the migrations create."""
    from data.db_setup import _MIGRATIONS

    assert ("player_savant_stats", "as_of_date", "TEXT") in _MIGRATIONS


# ── the table this agent creates must not be born wide open ──────────────────
#
# 2026-09-01. `model_calibration_sweeps` has never existed in production, so the
# CREATE in this module had never once run -- which is precisely why both
# defects below were invisible to every reviewer and to #389's sweep of the
# seven modules that DO re-run DDL. The boot catch-up added in this branch is
# what fires it for the first time.

def test_the_sweeps_table_is_locked_down_when_created():
    """CLAUDE.md §7: after creating anything in public, REVOKE from anon and
    authenticated BY NAME. Default privileges grant them ALL.

    docs/followups.md already tracks this gap for `worker_jobs` and
    `odds_history_pulls`; creating a third instance while shipping the fix for
    those would be absurd.
    """
    from tracking import model_calibration_agent as mca

    stmts = " | ".join(mca.LOCKDOWN)
    assert "ENABLE ROW LEVEL SECURITY" in stmts
    assert "FROM anon" in stmts, "REVOKE FROM PUBLIC does not cover anon"
    assert "FROM authenticated" in stmts
    assert all("model_calibration_sweeps" in s for s in mca.LOCKDOWN)


def test_the_ddl_is_guarded_so_it_does_not_fire_pgrst_ddl_watch_every_sweep():
    """Measured 2026-09-01 (#389): re-running this shape of block cost 11.6
    hours of database time and ~3,600 forced PostgREST schema-cache reloads,
    503ing the whole app. The guard is one catalog SELECT that fails closed.
    """
    import inspect

    from tracking import model_calibration_agent as mca

    src = inspect.getsource(mca.run_agent)
    guard = src.index("schema_is_current(")
    assert src.index("conn.execute(DDL)") > guard, (
        "the DDL must run only when the guard says the schema is not current")
    assert "LOCKDOWN" in src, "the lockdown must run alongside the CREATE"


def test_the_guard_asks_about_the_things_the_lockdown_sets():
    """A guard that checks less than the block does is worse than none: it
    returns True while RLS is off and the REVOKEs never run."""
    import inspect

    from tracking import model_calibration_agent as mca

    call = inspect.getsource(mca.run_agent)
    call = call[call.index("schema_is_current("):]
    call = call[:call.index(")") + 1]
    assert "rls=True" in call
    assert "anon" in call and "authenticated" in call

