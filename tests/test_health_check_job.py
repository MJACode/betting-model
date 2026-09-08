"""The health pass is a worker job, so nobody has to borrow a container to run it.

2026-09-08: I ran `python -m tracking.system_health` on `prop-probe` to verify a
change, and it wrote a full day-set to production under the WRONG DATE. prop-probe
holds DATABASE_URL but no `TZ`, so `run_date` came out as the UTC date -- tomorrow,
after 8pm ET -- and every "yesterday" gate shifted a day forward; it holds none of
the per-sport DISCORD_WEBHOOK_* vars either, so `signal_delivery` reported CRIT
SKIPPED about a system that was fine. Twelve red rows, none real, sitting on top of
a board that was actually five, and the first thing mike saw.

The lesson is not "be careful with prop-probe". It is that a verification run needs
the SAME environment as the real one, and the worker is the only place that has it.
So the health pass is a job type: a row in worker_jobs, run by the worker, with its
clock and its webhooks.
"""
import json
from datetime import datetime
from pathlib import Path

import pytest

import tracking.job_queue as jq

ROOT = Path(__file__).resolve().parents[1]


def test_health_check_is_a_registered_job_type():
    assert "health_check" in jq.JOBS, (
        "without this, running the health pass means borrowing another "
        "service's container, which is how a wrong-dated day-set reached "
        "production"
    )


def test_the_runner_calls_run_system_health():
    fn, _ = jq.JOBS["health_check"]
    import inspect
    src = inspect.getsource(fn)
    assert "run_system_health" in src


def test_no_run_date_means_the_module_resolves_it():
    """The DEFAULT is the point. run_system_health derives run_date from
    config.today_et(); passing the caller's clock is the bug this replaces."""
    _, validate = jq.JOBS["health_check"]
    assert validate({}) == {}
    assert validate({"run_date": None}) == {}
    assert validate({"run_date": ""}) == {}


def test_an_explicit_run_date_must_be_a_real_iso_date():
    _, validate = jq.JOBS["health_check"]
    assert validate({"run_date": "2026-09-07"}) == {"run_date": "2026-09-07"}
    for bad in ("nope", "2026-13-01", "09/07/2026", "2026-09-07T00:00:00Z"):
        with pytest.raises(ValueError):
            validate({"run_date": bad})


def test_the_validator_drops_unknown_args():
    """The allowlist is the security boundary: a job names a TYPE and its args
    are validated, so a stray key cannot ride along into the worker."""
    _, validate = jq.JOBS["health_check"]
    assert validate({"run_date": "2026-09-07", "command": "rm -rf /"}) == {
        "run_date": "2026-09-07"}


# ── the declared job that asks for the backfill run ──────────────────────────

def _declared() -> list:
    return json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))


def test_every_declared_job_names_a_registered_type():
    """A declared job for a type that does not exist fails on the worker, where
    nobody is watching, rather than here."""
    unknown = sorted({j["job_type"] for j in _declared()} - set(jq.JOBS))
    assert not unknown, f"declared jobs name unregistered types: {unknown}"


def test_every_declared_job_validates():
    """Validation runs here as well as on the worker, so a bad request fails in
    front of the person making it."""
    for job in _declared():
        _, validate = jq.JOBS[job["job_type"]]
        try:
            validate(dict(job.get("args") or {}))
        except Exception as exc:                            # noqa: BLE001
            pytest.fail(f"{job['key']}: {type(exc).__name__}: {exc}")


def test_declared_keys_are_unique():
    """The key is the dedupe: two rows sharing one would silently run once."""
    keys = [j["key"] for j in _declared()]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    assert not dupes, f"duplicate declared-job keys: {dupes}"
