"""The market is polled around the clock.

Until 2026-08-30 nothing ran between midnight and 6am ET. A line that opened at
2am was not seen until the 6am pipeline — which was also the moment the board
froze for the day, so an overnight opener was priced hours after it posted.

That is the wrong end of the CLV trade. The opening number is the one worth
having, and the §28 NFL opener rule is built entirely on being early to it.

mike, 2026-08-30: "we should be running api calls to look for new games, lines
around the clock ... the 6am push should only be to push the previous day
results, otherwise, we need to look for new lines and publish picks around the
clock as the model flags them."
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import scheduler  # noqa: E402


def _jobs():
    sched = scheduler.build_scheduler()
    return {j.id: j for j in sched.get_jobs()}


def _hours(job) -> set[int]:
    """Which ET hours a cron job can fire in."""
    field = next(f for f in job.trigger.fields if f.name == "hour")
    return {h for h in range(24)
            if any(_match(e, h) for e in field.expressions)}


def _match(expr, hour: int) -> bool:
    lo = getattr(expr, "first", None)
    hi = getattr(expr, "last", None)
    if lo is None and hi is None:                 # '*'
        return True
    if hi is None:
        return hour == lo
    return lo <= hour <= hi


def test_the_overnight_window_exists():
    jobs = _jobs()
    assert "overnight_refresh" in jobs, "nothing polls the market overnight"


def test_every_hour_of_the_day_is_covered():
    """The three refresh windows plus the 6am pipeline must tile 0-23 with no
    hole. A gap is invisible: it looks exactly like a quiet market."""
    jobs = _jobs()
    covered: set[int] = set()
    for jid in ("overnight_refresh", "hourly_refresh", "evening_refresh"):
        covered |= _hours(jobs[jid])
    # 6am is the daily pipeline's hour — it fetches odds as part of the full run.
    covered |= _hours(jobs["daily_pipeline"])
    assert covered == set(range(24)), f"unpolled hours: {sorted(set(range(24)) - covered)}"


def test_the_windows_do_not_overlap():
    """Two passes in the same hour would double-fetch a metered API for nothing."""
    jobs = _jobs()
    windows = {jid: _hours(jobs[jid])
               for jid in ("overnight_refresh", "hourly_refresh", "evening_refresh")}
    ids = list(windows)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            assert not (windows[a] & windows[b]), f"{a} and {b} overlap"


def test_the_overnight_pass_is_the_ordinary_one():
    """Not a special cut-down pass: it must re-score, or polling the lines
    achieves nothing. `mode` is unset, i.e. the default hourly chain."""
    job = _jobs()["overnight_refresh"]
    assert not job.kwargs.get("mode"), "overnight must run the full hourly chain"
    assert job.func is scheduler.run_refresh_pass
