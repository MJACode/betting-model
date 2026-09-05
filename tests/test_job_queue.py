"""The worker job queue — the answer to "why on my machine?".

What these pin is not the happy path, which is trivial, but the four things
that make a queue safe to leave running: it cannot execute arbitrary commands,
it cannot hand one job to two workers, it cannot loop forever on a job that
kills the container, and it cannot fail silently.
"""

from __future__ import annotations

import json
import os
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
        if "pg_try_advisory_lock" in sql:
            return (True,)            # the queue lock is free unless a test says otherwise
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


def test_reclaim_is_immediate_because_the_lock_proves_orphanhood():
    """The original 180-minute timer left an interrupted retrain parked for
    three hours AND allowed the overlap that exhausted the pooler. Holding the
    queue lock means exactly one runner exists, so any row still `running` is
    orphaned by definition."""
    import inspect

    src = inspect.getsource(q._reclaim_stale)
    assert "WHERE status = 'running'" in src
    assert "heartbeat_at" not in src, "no timer — the lock is the proof"
    assert not hasattr(q, "STALE_AFTER_MINUTES"), "the timer should be gone"


def test_the_lock_is_taken_before_anything_is_claimed():
    """Claiming first and then finding the queue busy would leave a job marked
    running that nobody is running."""
    import inspect

    src = inspect.getsource(q.run_one)
    assert src.index("pg_try_advisory_lock") < src.index("_reclaim_stale")
    assert src.index("pg_try_advisory_lock") < src.index("claim_one")


def test_a_busy_queue_claims_nothing():
    class _Locked(_Conn):
        def fetchone(self):
            if "pg_try_advisory_lock" in self._last[0]:
                return (False,)
            return super().fetchone()

    conn = _Locked(pending=[(1, "savant_refresh", {}, 1)])
    assert q.run_one(conn)["status"] == "busy"
    assert not any("SET status = 'running'" in s for s, _ in conn.sql)


def test_the_lock_is_released_even_when_the_job_raises():
    """A lock leaked by an exception would wedge the queue until the container
    restarted."""
    def _boom(**kw):
        raise RuntimeError("nope")

    class _Lockable(_Conn):
        def fetchone(self):
            if "pg_try_advisory_lock" in self._last[0]:
                return (True,)
            return super().fetchone()

    q.JOBS["_test_lock_boom"] = (_boom, lambda a: {})
    try:
        conn = _Lockable(pending=[(1, "_test_lock_boom", {}, 1)])
        q.run_one(conn)
        assert any("pg_advisory_unlock" in s for s, _ in conn.sql)
    finally:
        q.JOBS.pop("_test_lock_boom")


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


# ── what the first real run of the queue taught it ───────────────────────────

def test_a_retrain_raises_its_own_statement_timeout():
    """mlb_prop_batter_runs died at exactly 120s — the database's
    statement_timeout, which a prop bulk load exceeds. Raised for the retrain's
    connections only: a longer timeout is a licence to hold a pooler slot
    longer, and that licence belongs to the job that earned it."""
    cleaned = q._validate_retrain({"model_id": "mlb_prop_batter_runs"})
    assert cleaned["statement_timeout_ms"] >= 600_000

    import inspect
    src = inspect.getsource(q._job_retrain_model)
    assert "DB_STATEMENT_TIMEOUT_MS" in src


def test_the_raised_timeout_is_restored_after_the_job(monkeypatch):
    """Functional, not textual: the first version of this asserted a variable
    NAME appeared in the source and passed against a mutation that kept the
    variable and deleted the restore. Leaving it set would hand every later
    job on this worker a thirty-minute licence to hold a pooler slot."""
    import models.trainer as trainer

    monkeypatch.delenv("DB_STATEMENT_TIMEOUT_MS", raising=False)
    seen = {}

    def _fake_train(model_id, **kw):
        seen["during"] = os.environ.get("DB_STATEMENT_TIMEOUT_MS")
        return {"ok": True}

    monkeypatch.setattr(trainer, "train_prop_model", _fake_train)
    q._job_retrain_model(model_id="mlb_prop_batter_runs", seasons=None,
                         holdout=None, trials=None, register=False,
                         statement_timeout_ms=1_800_000)

    assert seen["during"] == "1800000", "the timeout must be set DURING the run"
    assert os.environ.get("DB_STATEMENT_TIMEOUT_MS") is None, \
        "and gone afterwards"


def test_the_restore_puts_back_a_pre_existing_value(monkeypatch):
    import models.trainer as trainer

    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "5000")
    monkeypatch.setattr(trainer, "train_prop_model", lambda model_id, **kw: {})
    q._job_retrain_model(model_id="mlb_prop_batter_runs", seasons=None,
                         holdout=None, trials=None, register=False,
                         statement_timeout_ms=1_800_000)
    assert os.environ["DB_STATEMENT_TIMEOUT_MS"] == "5000"


def test_the_timeout_is_bounded_at_both_ends():
    with pytest.raises(ValueError, match="statement_timeout_ms"):
        q._validate_retrain({"model_id": "mlb_moneyline", "statement_timeout_ms": 5})
    with pytest.raises(ValueError, match="statement_timeout_ms"):
        q._validate_retrain({"model_id": "mlb_moneyline",
                             "statement_timeout_ms": 99_999_999})


def test_the_connection_only_sets_a_timeout_when_asked(monkeypatch):
    """Every other caller keeps the database's own 120s. A runaway live-loop
    query should still be killed."""
    import inspect

    import data.db

    src = inspect.getsource(data.db.get_connection)
    assert 'os.environ.get("DB_STATEMENT_TIMEOUT_MS"' in src
    assert "isdigit()" in src, "a non-numeric value must not reach the DSN"


def test_a_reclaim_gives_the_attempt_back():
    """A container restart is not the job failing. My own merges consumed two
    jobs' entire retry budget: every deploy orphaned whatever was running and
    the re-claim charged it an attempt."""
    import inspect

    src = inspect.getsource(q._reclaim_stale)
    assert "attempts = GREATEST(attempts - 1, 0)" in src


def test_a_failed_job_needs_a_new_key_to_rerun():
    """Terminal by design — a job that failed three times should not quietly
    resurrect on the next tick. The requeues in the declarations file carry an
    -r2 suffix for exactly this reason."""
    entries = json.loads((config.ROOT / "jobs" / "declared_jobs.json")
                         .read_text(encoding="utf-8"))
    keys = [e["key"] for e in entries]
    assert "opp-starter-baseline-hits" in keys
    assert "opp-starter-baseline-hits-r2" in keys


# ── publish_discord_signals ──────────────────────────────────────────────────
# 2026-09-05. Two Week 1 nfl_wind_totals picks were on the app board and had
# never reached Discord. By the time it was noticed the leak (#489) was already
# fixed and both picks were selectable -- what was missing was anything that
# could RUN the producer before the next :17 refresh pass, and that pass had
# just been killed mid-run by a deploy. The worker holds the webhooks and polls
# this queue every five minutes.

def test_the_discord_publish_job_is_registered():
    assert "publish_discord_signals" in q.JOBS


def test_the_discord_publish_job_takes_an_optional_date():
    """Omitted means today. The date bounds only picks with no commence_time,
    so a future NFL kickoff is reached either way -- but a caller repairing an
    older slate must still be able to name it."""
    assert q._validate_publish_discord_signals({}) == {}
    assert q._validate_publish_discord_signals({"target_date": ""}) == {}
    assert (q._validate_publish_discord_signals({"target_date": "2026-09-05"})
            == {"target_date": "2026-09-05"})
    for bad in ("2026-9-5", "tomorrow", "20260905", "2026-09-05T00:00"):
        with pytest.raises(ValueError):
            q._validate_publish_discord_signals({"target_date": bad})


def test_the_discord_publish_job_calls_the_ordinary_producer(monkeypatch):
    """THE SAFETY ARGUMENT, pinned. It must call notify_discord_signals by its
    ordinary name and pass nothing that could widen it: the started-game guard,
    the model_action_thresholds cut and the push_sent ledger all live inside
    that function, so forcing it can only ever send what was never sent."""
    import tracking.discord_notifier as dn

    calls = []
    monkeypatch.setattr(dn, "notify_discord_signals",
                        lambda target_date=None, dry_run=False:
                        (calls.append((target_date, dry_run)), 2)[1])
    out = q._job_publish_discord_signals(target_date="2026-09-05")
    assert calls == [("2026-09-05", False)]
    assert out["posted"] == 2

    calls.clear()
    q._job_publish_discord_signals()
    assert calls == [(None, False)], "no date means today, not a widened window"


def test_the_discord_publish_job_never_restates(monkeypatch):
    """A restatement RE-publishes something members have already seen and is
    gated on an explicit date list for that reason. This job has no such gate
    because it cannot reach an already-posted pick at all -- it must never
    reach for the restate producer to make itself look more useful."""
    # Read off the CODE OBJECT, not the source text: the docstring explains
    # why it is not a restatement and would satisfy a grep for the word.
    names = q._job_publish_discord_signals.__code__.co_names
    assert "notify_discord_signals" in names
    assert "notify_discord_restate" not in names
    assert not any("push_sent" in str(c)
                   for c in q._job_publish_discord_signals.__code__.co_consts
                   if not isinstance(c, str) or "\n" not in c), \
        "clearing the ledger would turn this into an unlabelled restatement"
