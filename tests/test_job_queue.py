"""The worker job queue — the answer to "why on my machine?".

What these pin is not the happy path, which is trivial, but the four things
that make a queue safe to leave running: it cannot execute arbitrary commands,
it cannot hand one job to two workers, it cannot loop forever on a job that
kills the container, and it cannot fail silently.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

import config
from tracking import job_queue as q


class _Conn:
    """Records SQL, serves canned rows. Enough to exercise claim/run/record."""

    def __init__(self, pending=None):
        self.pending = list(pending or [])
        self.sql: list[tuple[str, object]] = []
        self.updates: list[dict] = []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        self._last = (sql, params)
        if "SET status = 'running'" in sql or "SET status='running'" in sql:
            self._claimed = self.pending.pop(0) if self.pending else None
        if "SET status='done'" in sql:
            self.updates.append({"status": "done", "params": params})
        if "SET status = %s, finished_at" in sql:
            self.updates.append({"status": params[0], "params": params})
        return self

    def fetchone(self):
        sql = self._last[0]
        if "RETURNING job_id, job_type, args, attempts" in sql:
            return getattr(self, "_claimed", None)
        if "RETURNING job_id" in sql:
            return (1,)
        return None

    def fetchall(self):
        return []

    def commit(self):
        pass

    def rollback(self):
        pass


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr(q, "_announce", lambda *a, **k: None)
    monkeypatch.setenv("RUN_JOB_QUEUE", "1")


# ── no arbitrary execution ───────────────────────────────────────────────────

def test_there_is_no_shell_or_command_column():
    """The obvious design — a command TEXT column the worker runs — would make
    every credential on the worker reachable by anyone who can write one row."""
    import inspect

    src = inspect.getsource(q)
    assert "subprocess" not in src
    assert "os.system" not in src
    assert "shell=True" not in src
    assert "command" not in q.DDL.lower()


def test_an_unknown_job_type_cannot_be_queued():
    with pytest.raises(ValueError, match="unknown job_type"):
        q.enqueue(_Conn(), "rm_minus_rf", {})


def test_an_unknown_job_type_already_in_the_table_fails_the_run_not_the_worker():
    """A row can outlive the build that knew its type. That must be a failed
    job, not a crashed scheduler."""
    conn = _Conn(pending=[(7, "type_from_the_future", {}, 1)])
    out = q.run_one(conn)
    assert out["status"] == "failed"
    assert "unknown job_type" in out["error"]


# ── arguments are validated before anything runs ─────────────────────────────

def test_a_bad_model_id_is_refused_at_queue_time():
    with pytest.raises(ValueError, match="unknown model_id"):
        q.enqueue(_Conn(), "retrain_model", {"model_id": "not_a_model"})


def test_a_real_model_id_validates():
    cleaned = q._validate_retrain({"model_id": "mlb_prop_batter_hits",
                                   "seasons": [2020, 2021], "holdout": 2025})
    assert cleaned["model_id"] == "mlb_prop_batter_hits"
    assert cleaned["seasons"] == [2020, 2021]
    assert cleaned["register"] is False, "a queued retrain must not register by default"


def test_a_retrain_defaults_to_not_registering():
    """A training run otherwise deactivates the live model and activates what it
    just built, whose .pkl is not committed. Queued runs default to safe."""
    assert q._validate_retrain({"model_id": "mlb_moneyline"})["register"] is False


def test_the_historical_backfill_requires_a_sane_credit_cap():
    base = {"sport": "MLB", "start": "2024-04-01", "end": "2024-04-02"}
    with pytest.raises(ValueError, match="credit_cap"):
        q._validate_historical_odds({**base, "credit_cap": 10_000_000})
    assert q._validate_historical_odds({**base, "credit_cap": 5000})["credit_cap"] == 5000


def test_the_backfill_rejects_a_reversed_date_range():
    with pytest.raises(ValueError, match="end is before start"):
        q._validate_historical_odds({"sport": "MLB", "start": "2024-05-01",
                                     "end": "2024-04-01"})


def test_the_backfill_defaults_to_every_history_book_not_just_dk():
    """The bug this whole change exists to fix: the historical fetcher asked for
    draftkings only, so seventeen seasons hold one book."""
    cleaned = q._validate_historical_odds({"sport": "MLB", "start": "2024-04-01",
                                           "end": "2024-04-02"})
    assert "pinnacle" in cleaned["bookmakers"]
    assert len(cleaned["bookmakers"]) > 1


def test_two_snapshots_a_day_is_the_default():
    """One snapshot per date gives a level. Movement needs two moments."""
    cleaned = q._validate_historical_odds({"sport": "MLB", "start": "2024-04-01",
                                           "end": "2024-04-02"})
    assert len(cleaned["hours_utc"]) >= 2


# ── one claim, ever ──────────────────────────────────────────────────────────

def test_the_claim_uses_skip_locked():
    """Two services poll this queue. Without SKIP LOCKED the second either
    blocks on the first's row or takes it too."""
    conn = _Conn(pending=[])
    q.claim_one(conn)
    claim_sql = [s for s, _ in conn.sql if "SET status = 'running'" in s][0]
    assert "FOR UPDATE SKIP LOCKED" in claim_sql
    assert "ORDER BY created_at" in claim_sql


def test_an_empty_queue_is_idle_not_an_error():
    assert q.run_one(_Conn(pending=[]))["status"] == "idle"


# ── bounded retries ──────────────────────────────────────────────────────────

def test_a_failing_job_is_requeued_until_the_attempt_cap():
    def _boom(**kw):
        raise RuntimeError("nope")

    q.JOBS["_test_boom"] = (_boom, lambda a: {})
    try:
        first = q.run_one(_Conn(pending=[(1, "_test_boom", {}, 1)]))
        assert first["status"] == "failed" and first["final"] is False
        last = q.run_one(_Conn(pending=[(1, "_test_boom", {}, q.MAX_ATTEMPTS)]))
        assert last["final"] is True
    finally:
        q.JOBS.pop("_test_boom")


def test_stale_reclaim_gives_up_after_the_cap():
    """A job that kills the container comes back, kills it again... The cap is
    what stops the queue becoming a crash loop."""
    import inspect

    src = inspect.getsource(q._reclaim_stale)
    assert "attempts >= %s" in src
    assert "'failed'" in src


def test_the_stale_window_exceeds_the_slowest_job():
    """Reclaiming a running retrain as 'stale' would run it twice."""
    assert q.STALE_AFTER_MINUTES >= 120


# ── nothing fails silently ───────────────────────────────────────────────────

def test_a_final_failure_is_announced():
    posted = []

    def _boom(**kw):
        raise RuntimeError("nope")

    q.JOBS["_test_boom2"] = (_boom, lambda a: {})
    original = q._announce
    q._announce = lambda job, ok, detail: posted.append((job["job_type"], ok))
    try:
        q.run_one(_Conn(pending=[(1, "_test_boom2", {}, q.MAX_ATTEMPTS)]))
        assert posted and posted[0][1] is False
    finally:
        q._announce = original
        q.JOBS.pop("_test_boom2")


def test_a_success_is_announced_too():
    posted = []
    q.JOBS["_test_ok"] = (lambda **kw: {"ran": True}, lambda a: {})
    original = q._announce
    q._announce = lambda job, ok, detail: posted.append((job["job_type"], ok))
    try:
        out = q.run_one(_Conn(pending=[(2, "_test_ok", {}, 1)]))
        assert out["status"] == "done"
        assert posted and posted[0][1] is True
    finally:
        q._announce = original
        q.JOBS.pop("_test_ok")


def test_the_kill_switch_stops_it(monkeypatch):
    monkeypatch.setenv("RUN_JOB_QUEUE", "0")
    assert q.run_one(_Conn(pending=[(1, "savant_refresh", {}, 1)]))["status"] == "disabled"


def test_it_is_scheduled_on_the_worker():
    import scheduler

    job = {j.id: j for j in scheduler.build_scheduler().get_jobs()}["job_queue"]
    assert "*/5" in str(job.trigger) or "5" in str(job.trigger)


# ── declared jobs: a queued job is a commit ──────────────────────────────────

class _DedupeConn(_Conn):
    """Models the UNIQUE(dedupe_key) constraint the real table carries."""

    def __init__(self, pending=None):
        super().__init__(pending)
        self.keys: set[str] = set()
        self.inserted: list[str] = []

    def execute(self, sql, params=None):
        if "INSERT INTO worker_jobs (dedupe_key" in sql:
            self.sql.append((sql, params))
            self._last = (sql, params)
            key = params[0]
            self._conflicted = "ON CONFLICT (dedupe_key) DO NOTHING" in sql and key in self.keys
            if not self._conflicted:
                self.keys.add(key)
                self.inserted.append(key)
            return self
        return super().execute(sql, params)

    def fetchone(self):
        sql = self._last[0]
        if "INSERT INTO worker_jobs (dedupe_key" in sql:
            return None if getattr(self, "_conflicted", False) else (len(self.inserted),)
        return super().fetchone()


def _write_declared(tmp_path, entries):
    path = tmp_path / "declared_jobs.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def test_a_declared_job_is_queued_once_however_often_it_is_read(tmp_path):
    """The file is read on every five-minute tick. Without the dedupe key that
    is 288 duplicate backfills a day, each one billing 10x credits."""
    path = _write_declared(tmp_path, [{
        "key": "pilot-1", "job_type": "historical_odds",
        "args": {"sport": "MLB", "start": "2024-06-01", "end": "2024-06-02",
                 "credit_cap": 2000},
    }])
    conn = _DedupeConn()
    first = q.sync_declared_jobs(conn, path)
    second = q.sync_declared_jobs(conn, path)
    third = q.sync_declared_jobs(conn, path)
    assert len(first) == 1
    assert second == [] and third == []
    assert conn.inserted == ["pilot-1"]


def test_the_insert_carries_on_conflict_do_nothing():
    """Belt to the braces above: the dedupe has to live in the SQL, not only in
    a fake. Two workers can call this at the same instant."""
    import inspect

    assert "ON CONFLICT (dedupe_key) DO NOTHING" in inspect.getsource(q.enqueue)


def test_one_malformed_declaration_does_not_block_the_others(tmp_path):
    path = _write_declared(tmp_path, [
        {"key": "bad", "job_type": "historical_odds",
         "args": {"sport": "NOTASPORT", "start": "2024-06-01", "end": "2024-06-02"}},
        {"key": "good", "job_type": "savant_refresh", "args": {"season": 2026}},
    ])
    conn = _DedupeConn()
    queued = q.sync_declared_jobs(conn, path)
    assert len(queued) == 1
    assert conn.inserted == ["good"]


def test_a_missing_declarations_file_is_silent(tmp_path):
    assert q.sync_declared_jobs(_DedupeConn(), tmp_path / "nope.json") == []


def test_the_shipped_declarations_file_validates():
    """Every entry in jobs/declared_jobs.json must pass its own validator, or
    the worker discovers it at 3am by logging a rejection nobody reads."""
    path = config.ROOT / "jobs" / "declared_jobs.json"
    entries = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(entries, list) and entries
    seen = set()
    for entry in entries:
        assert entry["key"] not in seen, f"duplicate key {entry['key']}"
        seen.add(entry["key"])
        _, validator = q.JOBS[entry["job_type"]]
        validator(entry.get("args") or {})


def test_the_tick_syncs_declarations_before_claiming():
    """A declaration added five minutes ago must be claimable on this tick, not
    the next one."""
    import inspect

    src = inspect.getsource(q.run_one)
    assert src.index("sync_declared_jobs") < src.index("claim_one")
