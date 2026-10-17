"""
mike, 2026-10-11: "Nfl_live_worker has gone silent".

It had been switched off on purpose since 2026-10-04, when its model was
retired (RUN_NFL_LIVE=0; every deploy since logs "NFL in-play worker NOT
scheduled"). The alarm came from the check-in row its last run wrote before
the switch-off: a job that is never registered never beats, so that row went
stale forever, and the silence check could not tell "off on purpose" from
"stopped running".

Now the scheduler marks every watched job it owns but did not register as
"disabled" at startup, and the silence check skips those rows.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

NOW = datetime(2026, 10, 11, 18, 30, tzinfo=timezone.utc)
WEEK_AGO = "2026-10-04T13:30:32+00:00"


class Conn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=()):
        return self

    def fetchall(self):
        return self.rows


def test_a_job_marked_disabled_is_not_silent():
    from tracking import job_heartbeat as jh
    late = {j for j, _, _ in jh.stale_jobs(Conn([
        ("nfl_live_worker", WEEK_AGO, "disabled"),
        ("nfl_poll_fast", WEEK_AGO, "ok"),
    ]), NOW)}
    assert "nfl_live_worker" not in late, "off on purpose is not silence"
    assert "nfl_poll_fast" in late, "a job that is on and silent must still alarm"


def _build(monkeypatch, *, role, live):
    import scheduler
    from tracking import job_heartbeat as jh
    marked, seeded = [], []
    monkeypatch.setattr(jh, "mark_disabled", lambda jid, *a, **k: marked.append(jid))
    monkeypatch.setattr(jh, "seed", seeded.append)
    monkeypatch.setattr(scheduler, "SERVICE_ROLE", role)
    monkeypatch.setattr(scheduler, "RUN_NFL_LIVE", live)
    scheduler.build_scheduler()
    return marked, seeded


def test_startup_marks_an_owned_job_that_is_switched_off(monkeypatch):
    marked, seeded = _build(monkeypatch, role="pipeline", live=False)
    assert "nfl_live_worker" in marked
    assert not set(marked) & set(seeded), "a registered job is never marked off"


def test_a_job_that_runs_here_is_not_marked(monkeypatch):
    marked, _ = _build(monkeypatch, role="pipeline", live=True)
    assert "nfl_live_worker" not in marked


def test_a_service_leaves_alone_the_jobs_another_service_owns(monkeypatch):
    """The poller service runs none of the NFL jobs; marking them off from
    there would silence the worker's real alarms."""
    marked, _ = _build(monkeypatch, role="pollers", live=False)
    assert not [j for j in marked if j.startswith("nfl_")], marked
