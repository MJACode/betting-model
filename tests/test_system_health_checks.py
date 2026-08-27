"""
Tests for the pipeline-observability health checks added 2026-08-27.

These exist because of a specific outage: a NameError in the WNBA prop scorer
aborted every hourly refresh pass at step 9 of 24 for three days, and every
existing health check stayed green — they all measure DATA freshness, and the
daily 6am pipeline (which continues past step failures) kept the data fresh.
Nothing measured whether the PASSES completed, or whether a captured signal was
ever actually delivered.

Each test below is one branch of that new logic.
"""

import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db_setup import SCHEMA_SQL, _MIGRATIONS
import tracking.system_health as sh


class _Shim:
    """Minimal DBConnection stand-in over sqlite3.

    The health SQL uses `?` placeholders, which sqlite3 takes natively, so no
    dialect adaptation is needed here.
    """

    def __init__(self, path):
        self._c = sqlite3.connect(path)

    def execute(self, sql, params=()):
        return self._c.execute(sql, tuple(params))

    def commit(self):
        self._c.commit()

    def close(self):
        self._c.close()


def _iso(minutes_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


@pytest.fixture
def db(monkeypatch):
    """A fresh schema-complete SQLite DB wired into system_health."""
    path = tempfile.mktemp(suffix=".db")
    c = sqlite3.connect(path)
    c.executescript(SCHEMA_SQL)
    for tbl, col, defn in _MIGRATIONS:          # columns added post-CREATE
        try:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {defn}")
        except sqlite3.OperationalError:
            pass
    # Postgres-only table the notifier and the delivery check both join.
    c.execute("""
        CREATE TABLE model_action_thresholds (
            model_id TEXT PRIMARY KEY, min_prob REAL NOT NULL,
            min_edge REAL NOT NULL DEFAULT 0, prob_only BOOLEAN NOT NULL DEFAULT 0,
            paused BOOLEAN NOT NULL DEFAULT 0, min_odds REAL)
    """)
    c.commit()
    monkeypatch.setattr(sh, "get_connection", lambda: _Shim(path))
    yield c
    c.close()


def _results(name):
    return {r["check_name"]: r for r in sh.run_system_health()["results"]}[name]


def _add_run(c, kind="hourly", started=60, finished=59, failed=None, total=24):
    c.execute(
        "INSERT INTO pipeline_runs (run_id, run_kind, started_at, finished_at,"
        " steps_total, steps_failed, failed_steps, ok) VALUES (?,?,?,?,?,?,?,?)",
        (uuid.uuid4().hex, kind, _iso(started),
         None if finished is None else _iso(finished),
         total, len(failed or []), ",".join(failed or []) or None, not failed))
    c.commit()


# ── refresh_pass_completion ──────────────────────────────────────────────────

class TestPassCompletion:
    def test_no_ledger_rows_is_empty(self, db):
        assert _results("refresh_pass_completion")["status"] == sh.EMPTY

    def test_first_pass_in_flight_is_not_a_failure(self, db):
        """The health check runs as a STEP, before the pass calls finish_run --
        so the very first pass has a started row and no finished one."""
        _add_run(db, started=5, finished=None)
        assert _results("refresh_pass_completion")["status"] == sh.SKIPPED

    def test_recent_finish_is_never_stale(self, db):
        _add_run(db, started=20, finished=19)
        assert _results("refresh_pass_completion")["status"] in (sh.OK, sh.SKIPPED)

    def test_stale_finish_is_never_ok(self, db):
        """The property that matters, independent of the ET pass window: a pass
        that last completed hours ago must never report healthy."""
        _add_run(db, started=400, finished=395)
        assert _results("refresh_pass_completion")["status"] != sh.OK

    def test_run_that_never_finished_is_caught(self, db):
        """A hang, an OOM or a worker killed mid-pass leaves finished_at NULL --
        the only way that becomes visible rather than silent."""
        _add_run(db, started=20, finished=19)
        _add_run(db, started=400, finished=None)
        assert _results("refresh_pass_completion")["status"] != sh.OK


# ── refresh_pass_steps ───────────────────────────────────────────────────────

class TestPassSteps:
    def test_too_few_passes_to_judge(self, db):
        for _ in range(2):
            _add_run(db)
        assert _results("refresh_pass_steps")["status"] == sh.SKIPPED

    def test_clean_passes_are_ok(self, db):
        for i in range(3):
            _add_run(db, started=60 + i, finished=59 + i)
        r = _results("refresh_pass_steps")
        assert (r["status"], r["severity"]) == (sh.OK, "CRIT")

    def test_persistent_failure_is_crit_and_names_the_step(self, db):
        """The exact shape of the 8/24-8/27 outage."""
        for i in range(3):
            _add_run(db, started=60 + i, finished=59 + i,
                     failed=["wnba-prop-scoring"])
        r = _results("refresh_pass_steps")
        assert (r["status"], r["severity"]) == (sh.STALE, "CRIT")
        assert "wnba-prop-scoring" in r["detail"]

    def test_intermittent_failure_warns_but_is_not_crit(self, db):
        """A flaky upstream API must not redden every run."""
        _add_run(db, started=62, finished=61, failed=["golf-odds"])
        for i in range(2):
            _add_run(db, started=60 + i, finished=59 + i)
        r = _results("refresh_pass_steps")
        assert r["severity"] == "WARN"
        assert "golf-odds" in r["detail"]

    def test_daily_runs_do_not_count_as_refresh_passes(self, db):
        for i in range(3):
            _add_run(db, kind="daily", started=60 + i, finished=59 + i)
        assert _results("refresh_pass_steps")["status"] == sh.SKIPPED


# ── signal_delivery ──────────────────────────────────────────────────────────

def _add_signal(c, *, sport="MLB", model="mlb_moneyline", locked=200,
                prob=0.80, edge=0.15, suffix="", delivered=False,
                paused=0, prob_only=0, min_prob=0.70, min_edge=0.10):
    c.execute("INSERT OR REPLACE INTO model_action_thresholds"
              " (model_id, min_prob, min_edge, prob_only, paused, min_odds)"
              " VALUES (?,?,?,?,?,NULL)", (model, min_prob, min_edge, prob_only, paused))
    lock_key = f"G1:{model}{suffix}"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    c.execute(
        "INSERT INTO opening_signals (lock_key, game_id, model_id, sport,"
        " game_date, pick_side, pick_label, model_probability, edge, locked_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (lock_key, None, model, sport, today, "home", "Test pick",
         prob, edge, _iso(locked)))
    if delivered:
        c.execute("INSERT INTO push_sent (lock_key, kind, sent_at)"
                  " VALUES (?, 'discord_signal', ?)", (lock_key, _iso(locked)))
    c.commit()
    return lock_key


@pytest.fixture
def mlb_wired(monkeypatch):
    import config
    monkeypatch.setattr(config, "DISCORD_WEBHOOKS", {"MLB": "https://x"}, raising=False)
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_DEFAULT", "", raising=False)


class TestSignalDelivery:
    def test_skipped_when_no_webhook_configured(self, db, monkeypatch):
        import config
        monkeypatch.setattr(config, "DISCORD_WEBHOOKS", {}, raising=False)
        monkeypatch.setattr(config, "DISCORD_WEBHOOK_DEFAULT", "", raising=False)
        _add_signal(db)
        assert _results("signal_delivery")["status"] == sh.SKIPPED

    def test_undelivered_signal_is_crit(self, db, mlb_wired):
        _add_signal(db, delivered=False)
        r = _results("signal_delivery")
        assert (r["status"], r["severity"]) == (sh.STALE, "CRIT")

    def test_delivered_signal_is_ok(self, db, mlb_wired):
        _add_signal(db, delivered=True)
        assert _results("signal_delivery")["status"] == sh.OK

    def test_just_locked_signal_gets_a_grace_window(self, db, mlb_wired):
        """A signal locked minutes ago has not had a pass yet."""
        _add_signal(db, locked=5, delivered=False)
        assert _results("signal_delivery")["status"] == sh.OK

    def test_sport_without_a_channel_is_not_counted(self, db, monkeypatch):
        import config
        monkeypatch.setattr(config, "DISCORD_WEBHOOKS", {"NFL": "https://x"}, raising=False)
        monkeypatch.setattr(config, "DISCORD_WEBHOOK_DEFAULT", "", raising=False)
        _add_signal(db, sport="MLB", delivered=False)
        assert _results("signal_delivery")["status"] == sh.OK

    def test_default_channel_covers_every_sport(self, db, monkeypatch):
        import config
        monkeypatch.setattr(config, "DISCORD_WEBHOOKS", {}, raising=False)
        monkeypatch.setattr(config, "DISCORD_WEBHOOK_DEFAULT", "https://x", raising=False)
        _add_signal(db, sport="NHL", model="nhl_moneyline", delivered=False)
        assert _results("signal_delivery")["status"] == sh.STALE

    def test_paused_model_is_not_postable(self, db, mlb_wired):
        _add_signal(db, paused=1, delivered=False)
        assert _results("signal_delivery")["status"] == sh.OK

    def test_below_threshold_is_not_postable(self, db, mlb_wired):
        _add_signal(db, prob=0.55, delivered=False)
        assert _results("signal_delivery")["status"] == sh.OK

    def test_early_shadow_rows_are_never_postable(self, db, mlb_wired):
        """UFC first-signal shadow rows are measurement, never display -- the
        notifier excludes them, so the delivery check must too."""
        _add_signal(db, suffix=":early", delivered=False)
        assert _results("signal_delivery")["status"] == sh.OK


# ── run_ledger ───────────────────────────────────────────────────────────────

class TestRunLedger:
    """The ledger is observability: it must record accurately, and it must never
    be able to break the pass it is observing."""

    def _wire(self, monkeypatch, path):
        import tracking.run_ledger as rl
        monkeypatch.setattr(rl, "get_connection", lambda: _Shim(path))
        return rl

    def test_creates_its_own_table(self, monkeypatch):
        """Supabase MCP is read-only and setup_database() only runs at first-time
        setup, so the ledger creates the table itself rather than needing a
        manual migration."""
        path = tempfile.mktemp(suffix=".db")
        sqlite3.connect(path).close()               # empty DB, no tables at all
        rl = self._wire(monkeypatch, path)
        run_id = rl.start_run("hourly")
        rows = sqlite3.connect(path).execute(
            "SELECT run_kind, finished_at FROM pipeline_runs WHERE run_id = ?",
            (run_id,)).fetchall()
        assert rows == [("hourly", None)]

    def test_finish_records_failed_steps(self, monkeypatch):
        path = tempfile.mktemp(suffix=".db")
        sqlite3.connect(path).close()
        rl = self._wire(monkeypatch, path)
        run_id = rl.start_run("hourly")
        rl.finish_run(run_id, 24, ["wnba-prop-scoring", "golf-odds"])
        total, failed, names, ok = sqlite3.connect(path).execute(
            "SELECT steps_total, steps_failed, failed_steps, ok FROM pipeline_runs"
            " WHERE run_id = ?", (run_id,)).fetchone()
        assert (total, failed, names) == (24, 2, "wnba-prop-scoring,golf-odds")
        assert not ok

    def test_clean_pass_is_marked_ok(self, monkeypatch):
        path = tempfile.mktemp(suffix=".db")
        sqlite3.connect(path).close()
        rl = self._wire(monkeypatch, path)
        run_id = rl.start_run("evening")
        rl.finish_run(run_id, 22, [])
        failed, names, ok = sqlite3.connect(path).execute(
            "SELECT steps_failed, failed_steps, ok FROM pipeline_runs WHERE run_id = ?",
            (run_id,)).fetchone()
        assert (failed, names, bool(ok)) == (0, None, True)

    def test_db_failure_never_raises(self, monkeypatch):
        """A dead database must not take the pass down with it."""
        import tracking.run_ledger as rl

        def boom():
            raise RuntimeError("database is on fire")

        monkeypatch.setattr(rl, "get_connection", boom)
        run_id = rl.start_run("hourly")     # still returns a usable id
        assert isinstance(run_id, str) and run_id
        rl.finish_run(run_id, 24, ["x"])    # and does not raise

    def test_finish_with_no_run_id_is_a_noop(self, monkeypatch):
        """The shell passes "" when `start` could not reach the DB."""
        import tracking.run_ledger as rl
        monkeypatch.setattr(rl, "get_connection",
                            lambda: (_ for _ in ()).throw(AssertionError("should not connect")))
        rl.finish_run("", 24, [])
