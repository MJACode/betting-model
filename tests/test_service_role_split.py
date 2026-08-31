"""
One image, two Railway services — and no job may fall between them.

Until 2026-08-30 the refresh pass, both live loops, the NFL worker and the
pre-game poller all ran in ONE container, so every deploy restarted all of
them. That day four consecutive refresh passes died mid-chain exactly that way,
and the corrected recap sat unposted for five hours as a result.

This is NOT for throughput. The worker peaks at 1.1GB of 8GB and 1.4 of 8 CPUs;
every slow step is waiting on a socket, and a second machine does not make a
socket answer faster. It is purely to shrink the blast radius of a deploy.

THE FAILURE MODE THIS GUARDS is a job owned by NOBODY. A job that runs in both
services double-fetches a metered API — visible in the credit burn. A job that
runs in neither simply stops happening, and §7's recurring lesson is that an
absent producer looks exactly like a quiet market. So the partition is tested
exhaustively, and an unknown role fails OPEN.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

_SRC = (Path(__file__).parent.parent / "scheduler.py").read_text(encoding="utf-8")


def _sched(role: str, monkeypatch):
    monkeypatch.setenv("SERVICE_ROLE", role)
    import scheduler
    return importlib.reload(scheduler)


def _all_job_ids() -> list[str]:
    """Every id passed to add_job, read from the source."""
    import re
    return re.findall(r'^\s*id="([^"]+)"', _SRC, re.M)


# ── the partition ─────────────────────────────────────────────────────────────

def test_every_job_is_owned_by_exactly_one_role(monkeypatch):
    """
    The property that matters. Not one job may run twice (double-fetching a
    metered API) or vanish (silently ceasing to happen).
    """
    pipeline = _sched("pipeline", monkeypatch)
    ids = _all_job_ids()
    assert ids, "no job ids parsed — the regex drifted from the source"
    pipe_owned = {j for j in ids if pipeline.owns(j)}

    poller = _sched("poller", monkeypatch)
    poll_owned = {j for j in ids if poller.owns(j)}

    overlap = pipe_owned & poll_owned
    orphan = set(ids) - pipe_owned - poll_owned
    assert not overlap, f"jobs owned by BOTH services (double-fetch): {sorted(overlap)}"
    assert not orphan, f"jobs owned by NEITHER service (silently gone): {sorted(orphan)}"


# The always-on supervisors. Named here rather than imported from scheduler so
# the test states the intent independently of the code it checks — importing
# _POLLER_JOBS would make this assert that the set equals itself.
# dk_direct_feed joined 2026-08-31: it is a long-running supervisor like the
# others, so it belongs to the poller service or a pipeline deploy kills it
# mid-slate. Listed explicitly because this set is asserted exactly -- a
# new loop has to be DECLARED here, which is the point of the test.
_EXPECTED_POLLERS = {"pregame_poller", "live_loop", "ncaaf_live_loop",
                     "dk_direct_feed", "bovada_feed"}


def test_the_poller_service_owns_exactly_the_long_running_supervisors(monkeypatch):
    """
    Every always-on loop, and nothing else.

    Checked as a SET, not a sample. The first version listed three of the four
    and a mutation that moved nfl_live_worker to the pipeline service passed
    cleanly — which is precisely the blast-radius bug this whole change exists
    to fix, since a pipeline deploy would then still kill it mid-tick.
    """
    s = _sched("poller", monkeypatch)
    owned = {j for j in _all_job_ids() if s.owns(j)}
    assert owned == _EXPECTED_POLLERS, (
        f"poller service owns {sorted(owned)}, expected "
        f"{sorted(_EXPECTED_POLLERS)} — a supervisor left on the pipeline "
        f"service is still killed by every pipeline deploy")


def test_the_pipeline_service_owns_no_long_running_loop(monkeypatch):
    """The complement, stated directly rather than inferred."""
    s = _sched("pipeline", monkeypatch)
    owned = {j for j in _all_job_ids() if s.owns(j)}
    assert not (owned & _EXPECTED_POLLERS), (
        f"pipeline service still owns supervisors: "
        f"{sorted(owned & _EXPECTED_POLLERS)}")


def test_the_pipeline_keeps_the_passes(monkeypatch):
    s = _sched("pipeline", monkeypatch)
    for j in ("daily_pipeline", "hourly_refresh", "evening_refresh",
              "overnight_refresh"):
        assert s.owns(j)
    assert not s.owns("pregame_poller")
    assert not s.owns("live_loop")


# ── failing open ──────────────────────────────────────────────────────────────

def test_an_unknown_role_runs_everything(monkeypatch):
    """
    A typo in a Railway variable must leave the scheduler running everything,
    never nothing. A container that schedules no jobs is indistinguishable from
    a quiet market — and nobody would look at the scheduler for that.
    """
    s = _sched("piepline", monkeypatch)          # deliberate typo
    assert all(s.owns(j) for j in _all_job_ids())


def test_the_default_preserves_the_single_container(monkeypatch):
    """
    Inert until a second service actually sets a role. A split that half-lands
    must never leave a job running nowhere.
    """
    monkeypatch.delenv("SERVICE_ROLE", raising=False)
    import scheduler
    s = importlib.reload(scheduler)
    assert s.SERVICE_ROLE == "all"
    assert all(s.owns(j) for j in _all_job_ids())


# ── the gate cannot be bypassed ───────────────────────────────────────────────

def test_role_filtering_wraps_add_job_once():
    """
    Eleven `if owns(...)` guards would be eleven chances to forget one, and the
    forgotten job runs in both services or neither. Pin the single wrap.
    """
    assert "sched.add_job = _add_job" in _SRC
    assert "def _add_job(" in _SRC
    body = _SRC[_SRC.index("def _add_job("):_SRC.index("sched.add_job = _add_job")]
    assert "owns(jid)" in body


def test_every_add_job_call_passes_an_id():
    """A job with no id cannot be filtered, so it would silently run everywhere."""
    import re
    calls = _SRC.count("sched.add_job(")
    ids = len(_all_job_ids())
    # one call is the wrapper's own definition line, not a real job
    assert ids >= calls - 1, f"{calls} add_job calls but only {ids} ids"


def test_the_nfl_worker_stays_with_the_volume(monkeypatch):
    """
    nfl_live_worker is the one supervisor that may NOT move.

    It appends its decision log to DECISION_LOG_DIR on the Railway volume
    mounted at /data, and a Railway volume attaches to exactly one service. On
    the poller service it would write to an empty path -- silently, because the
    log is append-only audit output that nothing reads back in real time. A
    split audit trail is worse than a worker a deploy can restart.

    Pinned as a test because the temptation to "finish the split" by moving it
    is obvious and the breakage is invisible.
    """
    s = _sched("pipeline", monkeypatch)
    assert s.owns("nfl_live_worker"), (
        "nfl_live_worker must stay on the volume-mounted service")
    p = _sched("poller", monkeypatch)
    assert not p.owns("nfl_live_worker")
