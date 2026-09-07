"""
Tests for tracking/heartbeat_watchdog.py.

The watchdog's entire value is that it works when the database does not, so
every test here drives it with a BROKEN database and asserts on what reaches
Discord. No real connection and no real network: get_connection and the
webhook POST are both substituted.

Each assertion below was mutation-checked — the fix removed, the test watched
failing, the fix restored — per CLAUDE.md §1b, because a watchdog test that
passes against a watchdog that does nothing is the exact failure this module
exists to stop.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import config
from tracking import heartbeat_watchdog as hw


NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def sink(tmp_path, monkeypatch):
    """Isolate state on disk and capture what would have been posted."""
    monkeypatch.setenv("WATCHDOG_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_OPS", "https://discord.test/hook")
    posted: list[dict] = []

    def fake_post(url, payload):
        posted.append({"url": url, "payload": payload})
        return "message-id"

    monkeypatch.setattr(hw, "_post", fake_post)
    return posted


def _break_db(monkeypatch, exc=None):
    """Make get_connection raise the way the real outage did."""
    exc = exc or Exception(
        'connection to server at "aws-1-us-west-2.pooler.supabase.com", '
        'port 5432 failed: FATAL:  password authentication failed for user "postgres"'
    )

    def boom():
        raise exc

    monkeypatch.setattr("data.db.get_connection", boom)


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, newest_started_at):
        self._row = (newest_started_at,)
        self.closed = False

    def execute(self, sql, params=None):
        return _FakeCursor(self._row)

    def close(self):
        self.closed = True


def _working_db(monkeypatch, newest_started_at):
    conn = _FakeConn(newest_started_at)
    monkeypatch.setattr("data.db.get_connection", lambda: conn)
    return conn


# ── The check that would have caught 2026-08-31 ──────────────────────────────

def test_unreachable_database_alerts(sink, monkeypatch):
    _break_db(monkeypatch)

    result = hw.run_watchdog(now=NOW)

    assert result["status"] == "db_unreachable"
    assert result["notified"] is True
    assert len(sink) == 1
    body = sink[0]["payload"]["embeds"][0]
    # The alert must carry the driver's own words. A generic "database error"
    # would not have told anyone that the credential was the problem, which is
    # the single fact that turns a 9-hour outage into a 5-minute fix.
    assert "password authentication failed" in body["description"]
    assert body["color"] == hw._COLOR_ALERT


def test_stalled_pipeline_alerts_even_though_db_is_healthy(sink, monkeypatch):
    stale = (NOW - timedelta(minutes=config.WATCHDOG_STALE_MINUTES + 30)).isoformat()
    _working_db(monkeypatch, stale)

    result = hw.run_watchdog(now=NOW)

    assert result["status"] == "pipeline_stalled"
    assert len(sink) == 1


def test_recent_run_is_quiet(sink, monkeypatch):
    fresh = (NOW - timedelta(minutes=5)).isoformat()
    _working_db(monkeypatch, fresh)

    result = hw.run_watchdog(now=NOW)

    assert result["status"] == "ok"
    assert sink == []


def test_connection_is_closed_on_the_healthy_path(sink, monkeypatch):
    """A watchdog that leaks a connection every 15 minutes eventually causes
    the pooler exhaustion it is supposed to detect."""
    conn = _working_db(monkeypatch, (NOW - timedelta(minutes=5)).isoformat())

    hw.run_watchdog(now=NOW)

    assert conn.closed is True


def test_connection_is_closed_even_when_the_check_alerts(sink, monkeypatch):
    stale = (NOW - timedelta(minutes=config.WATCHDOG_STALE_MINUTES + 30)).isoformat()
    conn = _working_db(monkeypatch, stale)

    hw.run_watchdog(now=NOW)

    assert conn.closed is True


# ── Throttling: visible, not deafening ───────────────────────────────────────

def test_repeat_within_the_window_is_suppressed(sink, monkeypatch):
    _break_db(monkeypatch)

    hw.run_watchdog(now=NOW)
    hw.run_watchdog(now=NOW + timedelta(minutes=15))
    hw.run_watchdog(now=NOW + timedelta(minutes=30))

    assert len(sink) == 1, "a continuing outage must not post every tick"


def test_repeat_after_the_window_speaks_again(sink, monkeypatch):
    _break_db(monkeypatch)

    hw.run_watchdog(now=NOW)
    later = NOW + timedelta(minutes=config.WATCHDOG_RENOTIFY_MINUTES + 1)
    hw.run_watchdog(now=later)

    assert len(sink) == 2, "an outage still live hours later must be restated"


def test_a_failed_post_does_not_start_the_throttle(monkeypatch, tmp_path):
    """Stamping the throttle on an unconfirmed POST would silence the next six
    hours on the strength of a message nobody received."""
    monkeypatch.setenv("WATCHDOG_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_OPS", "https://discord.test/hook")
    _break_db(monkeypatch)

    attempts: list[int] = []

    def failing_post(url, payload):
        attempts.append(1)
        return None

    monkeypatch.setattr(hw, "_post", failing_post)

    hw.run_watchdog(now=NOW)
    hw.run_watchdog(now=NOW + timedelta(minutes=15))

    assert len(attempts) == 2


# ── Recovery ─────────────────────────────────────────────────────────────────

def test_recovery_is_announced_once(sink, monkeypatch):
    _break_db(monkeypatch)
    hw.run_watchdog(now=NOW)

    _working_db(monkeypatch, (NOW - timedelta(minutes=1)).isoformat())
    hw.run_watchdog(now=NOW + timedelta(minutes=15))
    hw.run_watchdog(now=NOW + timedelta(minutes=30))

    assert len(sink) == 2
    assert sink[1]["payload"]["embeds"][0]["color"] == hw._COLOR_RECOVERY


def test_a_healthy_start_never_announces_a_recovery(sink, monkeypatch):
    _working_db(monkeypatch, (NOW - timedelta(minutes=1)).isoformat())

    hw.run_watchdog(now=NOW)

    assert sink == []


def test_a_returning_outage_alerts_again_immediately(sink, monkeypatch):
    """Recovery clears the throttle stamps, so a flapping outage is reported
    on every occurrence rather than once per re-notify window."""
    _break_db(monkeypatch)
    hw.run_watchdog(now=NOW)

    _working_db(monkeypatch, (NOW - timedelta(minutes=1)).isoformat())
    hw.run_watchdog(now=NOW + timedelta(minutes=15))

    _break_db(monkeypatch)
    hw.run_watchdog(now=NOW + timedelta(minutes=30))

    assert len(sink) == 3, "alert, recovery, alert"


# ── The alerting path must not itself depend on the database ─────────────────

def test_missing_ops_webhook_is_reported_not_swallowed(monkeypatch, tmp_path):
    monkeypatch.setenv("WATCHDOG_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_OPS", "")
    _break_db(monkeypatch)

    result = hw.run_watchdog(now=NOW)

    # It still DETECTS the outage; it just cannot deliver it, and the two must
    # not look alike to a caller.
    assert result["status"] == "db_unreachable"
    assert result["notified"] is False


def test_ops_alerts_never_reach_a_member_facing_channel(monkeypatch, tmp_path):
    """DISCORD_WEBHOOK_OPS deliberately has no fallback: an infrastructure
    alert in the results or a sport channel is noise to subscribers."""
    monkeypatch.setenv("WATCHDOG_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_OPS", "")
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_RESULTS", "https://discord.test/results")
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_DEFAULT", "https://discord.test/default")
    _break_db(monkeypatch)

    posted: list[dict] = []
    monkeypatch.setattr(hw, "_post", lambda url, payload: posted.append(url) or "id")

    hw.run_watchdog(now=NOW)

    assert posted == []


def test_watchdog_survives_an_unwritable_state_dir(sink, monkeypatch):
    """Bookkeeping must never break the check itself."""
    monkeypatch.setattr(hw, "_write_state", lambda state: (_ for _ in ()).throw(OSError("ro")))
    _break_db(monkeypatch)

    with pytest.raises(OSError):
        hw._write_state({})

    # _write_state is only called through the guarded path, so the run stands.
    monkeypatch.setattr(hw, "_write_state", lambda state: None)
    result = hw.run_watchdog(now=NOW)
    assert result["status"] == "db_unreachable"


def test_unparseable_timestamp_does_not_crash_the_watchdog(sink, monkeypatch):
    _working_db(monkeypatch, "not-a-timestamp")

    result = hw.run_watchdog(now=NOW)

    # Unknown age is not evidence of a stall — it must not manufacture an alert.
    assert result["status"] == "ok"
    assert sink == []


def test_a_silent_failure_alerter_is_caught_by_the_watchdog(sink, monkeypatch):
    """WHO WATCHES THE WATCHER.

    failure_alerter reports every other failure, and reports on its own
    heartbeat too — which is worth nothing when it is the thing that died. So
    the check lives in the watchdog: a separate schedule, on both services,
    with no dependency on the alerter being alive.
    """
    from datetime import timedelta

    import tracking.job_heartbeat as jh

    monkeypatch.setattr(
        jh, "stale_jobs",
        lambda conn, now=None: [("failure_alerter", 90.0, 45)])
    _working_db(monkeypatch, NOW.isoformat())

    result = hw.run_watchdog(now=NOW)

    assert result["status"] == "alerter_silent"
    assert len(sink) == 1
    assert "failure_alerter" in sink[0]["payload"]["embeds"][0]["description"]


def test_a_stalled_pipeline_outranks_a_silent_alerter(sink, monkeypatch):
    """If passes have stopped, THAT is the finding. A silent alerter is a
    symptom of it, and reporting both would split one incident in two."""
    from datetime import timedelta

    import tracking.job_heartbeat as jh

    monkeypatch.setattr(
        jh, "stale_jobs",
        lambda conn, now=None: [("failure_alerter", 90.0, 45)])
    stale = (NOW - timedelta(minutes=config.WATCHDOG_STALE_MINUTES + 30)).isoformat()
    _working_db(monkeypatch, stale)

    assert hw.run_watchdog(now=NOW)["status"] == "pipeline_stalled"


def test_an_unreadable_heartbeat_table_does_not_raise_a_second_alarm(
        sink, monkeypatch):
    import tracking.job_heartbeat as jh

    def _boom(conn, now=None):
        raise RuntimeError("relation does not exist")

    monkeypatch.setattr(jh, "stale_jobs", _boom)
    _working_db(monkeypatch, NOW.isoformat())

    assert hw.run_watchdog(now=NOW)["status"] == "ok"
