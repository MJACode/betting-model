"""The morning disk lane, pinned to the 2026-11-12 pile-up.

Around 05:50 ET the Picks board stayed on skeletons. Disk IO was saturated.
The 06:00 daily, the 05:17 refresh, Kalshi inserts at :40/:45, the api_call_log
prune and the NCAAB/NFL polls were free to run together. These tests fail if
that set can all be admitted again, or if the 05:17 refresh comes back.
"""

from __future__ import annotations

import inspect
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import scheduler  # noqa: E402
from monitoring import store  # noqa: E402
from tracking.job_queue import QUEUE_LOCK_KEY  # noqa: E402
from tracking.morning_disk import (  # noqa: E402
    API_LOG_PRUNE_LOCK,
    DEFER_JOBS,
    ET,
    LANE_JOBS,
    MorningDisk,
    begin_api_log_prune,
    end_api_log_prune,
    in_morning_window,
)
from tracking.publish_lock import (  # noqa: E402
    DISCORD_LIVE_LOCK,
    DISCORD_SIGNALS_LOCK,
    PUSH_SIGNALS_LOCK,
    X_PICKS_LOCK,
)
from tracking.scoring_lease import _KEYS  # noqa: E402

# The minute the board was on skeletons, and the jobs Night Watch had in the
# pile. daily_busy stands in for the 06:00 pipeline still being inside prune
# and the health check.
_PILE = (
    "kalshi_ladders",
    "kalshi_game_markets",
    "job_queue",
    "ncaab_odds_capture",
    "ncaabw_odds_capture",
    "ncaab_injury_feed",
    "nfl_poll_fast",
    "nfl_opener_poll",
    "nba_prop_window",
    "ncaab_spread_card",
    "ncaab_moneyline_card",
    "ncaaf_moneyline_card",
)
_WHEN = datetime(2026, 11, 12, 6, 50, tzinfo=ET)


def test_the_window_is_0540_through_0715_et():
    assert in_morning_window(datetime(2026, 11, 12, 5, 40, tzinfo=ET))
    assert in_morning_window(datetime(2026, 11, 12, 6, 0, tzinfo=ET))
    assert in_morning_window(datetime(2026, 11, 12, 7, 14, tzinfo=ET))
    assert not in_morning_window(datetime(2026, 11, 12, 5, 32, tzinfo=ET))
    assert not in_morning_window(datetime(2026, 11, 12, 5, 39, tzinfo=ET))
    assert not in_morning_window(datetime(2026, 11, 12, 7, 15, tzinfo=ET))
    assert not in_morning_window(datetime(2026, 11, 12, 7, 20, tzinfo=ET))
    # The same instant in UTC is 11:50Z in November (EST). A naive reading of
    # the clock as UTC would put the window in the wrong hour.
    assert in_morning_window(datetime(2026, 11, 12, 11, 50, tzinfo=ZoneInfo("UTC")))


def test_the_nov12_pile_cannot_all_run():
    """What was in flight at 06:50 ET. One heavy tick, and not the recorders
    or the job queue. A second lane tick waits for the next cron."""
    disk = MorningDisk()
    admitted = []
    for job_id in _PILE:
        decision = disk.admit(job_id, now=_WHEN, daily_busy=True)
        if decision.admitted:
            admitted.append((job_id, decision))
    assert len(admitted) == 1, [j for j, _ in admitted]
    assert admitted[0][0] not in DEFER_JOBS
    admitted[0][1].release()
    nxt = disk.admit("ncaab_odds_capture", now=_WHEN, daily_busy=True)
    assert nxt.admitted
    nxt.release()


def test_kalshi_runs_at_0532_and_not_at_0632_and_catches_up_at_0720():
    disk = MorningDisk()
    early = datetime(2026, 11, 12, 5, 32, tzinfo=ET)
    during = datetime(2026, 11, 12, 6, 32, tzinfo=ET)
    catch = datetime(2026, 11, 12, 7, 20, tzinfo=ET)
    assert disk.admit("kalshi_ladders", now=early).admitted
    held = disk.admit("kalshi_ladders", now=during)
    assert not held.admitted
    assert "morning disk window" in held.reason
    assert disk.admit("kalshi_ladders_morning", now=catch).admitted
    still = disk.admit("kalshi_ladders_morning", now=catch, daily_busy=True)
    assert not still.admitted
    assert "daily pipeline" in still.reason


def test_the_lane_does_not_apply_outside_the_window():
    disk = MorningDisk()
    now = datetime(2026, 11, 12, 20, 0, tzinfo=ET)
    first = disk.admit("ncaab_odds_capture", now=now)
    second = disk.admit("nfl_poll_fast", now=now)
    assert first.admitted and second.admitted


def test_the_daily_is_not_gated_on_the_lane():
    disk = MorningDisk()
    held = disk.admit("ncaab_odds_capture", now=_WHEN)
    assert held.admitted
    daily = disk.admit("daily_pipeline", now=_WHEN, daily_busy=True)
    assert daily.admitted
    held.release()


def test_the_prune_lock_is_not_someone_elses_lock():
    others = set(_KEYS.values()) | {
        QUEUE_LOCK_KEY,
        DISCORD_SIGNALS_LOCK,
        DISCORD_LIVE_LOCK,
        PUSH_SIGNALS_LOCK,
        X_PICKS_LOCK,
    }
    assert API_LOG_PRUNE_LOCK not in others


class _Conn:
    def __init__(self, got=True, boom=False):
        self.got = got
        self.boom = boom
        self.sql: list[str] = []
        self.committed = 0

    def execute(self, sql, params=None):
        self.sql.append(sql)
        if self.boom:
            raise RuntimeError("no advisory lock")
        got = self.got

        class _Row:
            def fetchone(self_inner):
                return (got,)

        return _Row()

    def commit(self):
        self.committed += 1

    def rollback(self):
        pass


def test_the_prune_waits_out_the_morning_window_without_taking_the_lock():
    conn = _Conn()
    assert begin_api_log_prune(conn, _WHEN) == "wait"
    assert conn.sql == []


def test_a_second_prune_skips_when_the_lock_is_held():
    conn = _Conn(got=False)
    assert begin_api_log_prune(conn, datetime(2026, 11, 12, 8, 0, tzinfo=ET)) == "skip"
    assert "pg_try_advisory_lock" in conn.sql[0]


def test_the_prune_fails_open_when_the_lock_cannot_be_asked():
    conn = _Conn(boom=True)
    assert begin_api_log_prune(conn, datetime(2026, 11, 12, 8, 0, tzinfo=ET)) == "run"


def test_end_prune_unlocks():
    conn = _Conn()
    end_api_log_prune(conn)
    assert "pg_advisory_unlock" in conn.sql[0]
    assert conn.committed == 1


def test_the_writer_does_not_advance_its_clock_while_the_window_is_closed():
    """A wait that set last_prune would not try again until an hour after
    07:15, so the rows would sit and then every process would delete together."""
    from monitoring import probe
    src = inspect.getsource(probe._writer_loop)
    assert "begin_api_log_prune" in src
    assert src.index("begin_api_log_prune") < src.index("last_prune = now")
    assert 'action == "wait"' in src


def test_prune_deletes_in_batches_and_stops_on_a_short_one(monkeypatch):
    monkeypatch.setattr(store, "roll_up", lambda conn: 0)

    class Conn:
        def __init__(self):
            self.deletes = 0
            self.timeouts = 0

        def execute(self, sql, params=None):
            if "statement_timeout" in sql:
                self.timeouts += 1
            if sql.startswith("DELETE"):
                self.deletes += 1
                n = store.PRUNE_BATCH if self.deletes == 1 else 3

                class Rows:
                    def fetchall(self_inner):
                        return [(1,)] * n

                return Rows()

            class Rows:
                def fetchall(self_inner):
                    return []

            return Rows()

        def commit(self):
            pass

        def rollback(self):
            pass

    conn = Conn()
    deleted = store.prune(conn)
    assert conn.deletes == 2
    assert conn.timeouts == 2
    assert deleted == store.PRUNE_BATCH + 3
    assert "ORDER BY ts LIMIT" in inspect.getsource(store._prune_batch)


def test_prune_stops_at_the_time_budget(monkeypatch):
    monkeypatch.setattr(store, "roll_up", lambda conn: 0)
    monkeypatch.setattr(store, "PRUNE_BUDGET_S", 5)
    ticks = {"n": 0}

    def mono():
        ticks["n"] += 1
        return 0 if ticks["n"] < 3 else 100

    monkeypatch.setattr(store.time, "monotonic", mono)

    class Conn:
        def __init__(self):
            self.deletes = 0

        def execute(self, sql, params=None):
            if sql.startswith("DELETE"):
                self.deletes += 1

                class Rows:
                    def fetchall(self_inner):
                        return [(1,)] * store.PRUNE_BATCH

                return Rows()

            class Rows:
                def fetchall(self_inner):
                    return []

            return Rows()

        def commit(self):
            pass

        def rollback(self):
            pass

    conn = Conn()
    deleted = store.prune(conn)
    assert conn.deletes == 1
    assert deleted == store.PRUNE_BATCH


def _jobs():
    return {j.id: j for j in scheduler.build_scheduler().get_jobs()}


def _field(job, name):
    return next(f for f in job.trigger.fields if f.name == name)


def _values(field) -> set[int]:
    out = set()
    for expr in field.expressions:
        lo = getattr(expr, "first", None)
        hi = getattr(expr, "last", None)
        if lo is None and hi is None:
            return set(range(24))
        if hi is None or hi == lo:
            out.add(lo)
        else:
            out.update(range(lo, hi + 1))
    return out


def test_the_schedule_moves_the_0517_refresh_and_the_kalshi_minutes():
    jobs = _jobs()
    assert _values(_field(jobs["overnight_refresh"], "hour")) == set(range(0, 5))
    assert _values(_field(jobs["kalshi_ladders"], "minute")) == {32}
    assert _values(_field(jobs["kalshi_game_markets"], "minute")) == {37}
    ladders = jobs["kalshi_ladders_morning"]
    games = jobs["kalshi_game_markets_morning"]
    assert _values(_field(ladders, "hour")) == {7}
    assert _values(_field(ladders, "minute")) == {20}
    assert _values(_field(games, "hour")) == {7}
    assert _values(_field(games, "minute")) == {25}
    for job_id in ("kalshi_ladders_morning", "kalshi_game_markets_morning"):
        assert job_id in scheduler._PIPELINE_JOBS
        assert job_id in DEFER_JOBS
    assert LANE_JOBS  # the cap has someone to cap


def test_the_wrapper_asks_the_gate_before_the_job():
    src = inspect.getsource(scheduler.build_scheduler)
    assert src.index("admit(") < src.index("return func(")


def test_a_refresh_does_not_start_while_the_daily_holds_its_lock(monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler, "_run", lambda *a, **k: calls.append(a) or "ok")
    assert scheduler._DAILY_LOCK.acquire(blocking=False)
    try:
        scheduler.run_refresh_pass()
        assert calls == []
        assert scheduler._REFRESH_LOCK.acquire(blocking=False)
        scheduler._REFRESH_LOCK.release()
    finally:
        scheduler._DAILY_LOCK.release()


def test_the_daily_waits_for_an_in_flight_refresh_then_runs(monkeypatch):
    monkeypatch.setattr(scheduler, "DAILY_REFRESH_WAIT_S", 2)
    monkeypatch.setattr(scheduler, "_wait_for_nhl_window", lambda label: True)
    ran = []
    monkeypatch.setattr(scheduler, "_run", lambda *a, **k: ran.append(a) or "ok")
    assert scheduler._REFRESH_LOCK.acquire(blocking=False)

    def drop():
        time.sleep(0.05)
        scheduler._REFRESH_LOCK.release()

    threading.Thread(target=drop).start()
    try:
        assert scheduler.run_daily_pipeline() == "ok"
        assert ran and ran[0][0][-1] == "run_pipeline.py"
    finally:
        if scheduler._DAILY_LOCK.locked():
            scheduler._DAILY_LOCK.release()
        if scheduler._REFRESH_LOCK.locked():
            scheduler._REFRESH_LOCK.release()
