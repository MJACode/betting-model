"""The alerter has one job: a failure reaches a person.

The gap it closes is not detection. `tracking/system_health.py` had already
written "[WARN] refresh_pass_steps: STALE" on 2026-09-06 while `odds` — the
step that fetches the lines every model prices against — was dying with
EMAXCONNSESSION. It wrote it to a table and to the log, and 32 of 50 passes
failed before a person queried `pipeline_runs` by hand and noticed.

So these tests are about DELIVERY and about not becoming noise: the throttle,
the recovery, and the rule that nothing is stamped unless the post confirmed.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking import failure_alerter as fa  # noqa: E402

NOW = datetime(2026, 9, 6, 23, 0, tzinfo=timezone.utc)


class FakeConn:
    """Answers the three queries the alerter makes, by shape.

    Heartbeats default to FRESH for every watched job, so a test about health
    checks or the clean rate is not also silently a test about job silence.
    """

    def __init__(self, health=(), runs=(), beats=None):
        self._health, self._runs, self._last = health, runs, None
        if beats is None:
            from datetime import timedelta as _td

            from tracking.job_heartbeat import MAX_SILENCE
            # Stamped ahead of every clock these tests use, so no test about
            # health checks or the clean rate is ALSO a test about job silence.
            fresh = (NOW + _td(days=1)).isoformat()
            beats = [(j, fresh) for j in MAX_SILENCE]
        self._beats = beats

    def execute(self, sql, params=()):
        if "system_health_checks" in sql:
            self._last = "health"
        elif "job_heartbeats" in sql:
            self._last = "beats"
        else:
            self._last = "runs"
        return self

    def fetchall(self):
        return list({"health": self._health, "beats": self._beats}.get(
            self._last, self._runs))


def _state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("WATCHDOG_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)


def _posts(monkeypatch, ok=True):
    """Capture ops posts instead of sending them."""
    sent = []

    def _fake(title, detail, *, recovery=False):
        sent.append({"title": title, "detail": detail, "recovery": recovery})
        return ok

    monkeypatch.setattr(fa, "post_ops_alert", _fake)
    return sent


def _clean_runs(n=12):
    return [(True, None)] * n


class TestWhatCountsAsAFailure:
    def test_a_stale_check_is_a_condition(self):
        conn = FakeConn(health=[("odds_dk_lines", "STALE", "CRIT", "no snapshot in 6h")],
                        runs=_clean_runs())
        c = fa._conditions(conn)
        assert "health:odds_dk_lines" in c
        assert c["health:odds_dk_lines"][0] == "CRIT"

    def test_ok_and_skipped_are_not(self):
        # SKIPPED is usually legitimate — no golf tournament, no NBA games —
        # and alerting on it would bury the channel out of season.
        conn = FakeConn(health=[("a", "OK", "CRIT", ""), ("b", "SKIPPED", "WARN", "")],
                        runs=_clean_runs())
        assert fa._conditions(conn, NOW) == {}

    def test_severity_carries_through(self):
        conn = FakeConn(health=[("x", "STALE", "WARN", "flaky upstream")],
                        runs=_clean_runs())
        assert fa._conditions(conn)["health:x"][0] == "WARN"

    def test_the_clean_rate_rule_fires_on_the_measured_incident(self):
        # 2026-09-06 as measured: 1 of the last 12 passes clean, `odds` in 5.
        runs = [(False, "odds,public-betting")] * 5 + [(False, "lineups")] * 6 \
            + [(True, None)]
        conn = FakeConn(health=[], runs=runs)
        c = fa._conditions(conn)
        assert "pass:clean_rate" in c
        sev, title, detail = c["pass:clean_rate"]
        assert sev == "CRIT"
        assert "1/12" in title
        assert "`odds`" in detail          # names the worst offender

    def test_a_healthy_board_is_silent(self):
        conn = FakeConn(health=[("a", "OK", "CRIT", "")], runs=_clean_runs())
        assert fa._conditions(conn, NOW) == {}

    def test_the_floor_sits_below_a_normal_day(self):
        # Measured 2026-09-04 and 09-05: 0.64 and 0.69 clean. A threshold that
        # fires on a normal day is a threshold that gets muted.
        assert fa.CLEAN_RATE_FLOOR < 0.64

    def test_too_few_passes_to_judge_says_nothing(self):
        conn = FakeConn(health=[], runs=[(False, "odds")] * 3)
        assert "pass:clean_rate" not in fa._conditions(conn)


class TestDeliveryAndNoise:
    def test_a_new_condition_alerts(self, monkeypatch, tmp_path):
        _state_dir(monkeypatch, tmp_path)
        sent = _posts(monkeypatch)
        conn = FakeConn(health=[("odds_dk_lines", "STALE", "CRIT", "stale")],
                        runs=_clean_runs())
        r = fa.run_failure_alerter(conn=conn, now=NOW)
        assert r["alerted"] == ["health:odds_dk_lines"]
        assert len(sent) == 1 and sent[0]["recovery"] is False

    def test_the_same_condition_does_not_alert_again_immediately(
            self, monkeypatch, tmp_path):
        _state_dir(monkeypatch, tmp_path)
        sent = _posts(monkeypatch)
        conn = FakeConn(health=[("odds_dk_lines", "STALE", "CRIT", "stale")],
                        runs=_clean_runs())
        fa.run_failure_alerter(conn=conn, now=NOW)
        r = fa.run_failure_alerter(conn=conn, now=NOW + timedelta(minutes=10))
        assert r["alerted"] == []
        assert len(sent) == 1, "a standing failure must not post every tick"

    def test_it_alerts_again_after_the_renotify_window(self, monkeypatch, tmp_path):
        _state_dir(monkeypatch, tmp_path)
        sent = _posts(monkeypatch)
        conn = FakeConn(health=[("odds_dk_lines", "STALE", "CRIT", "stale")],
                        runs=_clean_runs())
        fa.run_failure_alerter(conn=conn, now=NOW)
        later = NOW + timedelta(minutes=fa.RENOTIFY_CRIT_MIN + 1)
        r = fa.run_failure_alerter(conn=conn, now=later)
        assert r["alerted"] == ["health:odds_dk_lines"]
        assert len(sent) == 2

    def test_warn_is_throttled_harder_than_crit(self):
        # A WARN repeating at CRIT's cadence is how a channel stops being read.
        assert fa.RENOTIFY_WARN_MIN > fa.RENOTIFY_CRIT_MIN

    def test_a_cleared_condition_posts_a_recovery_once(self, monkeypatch, tmp_path):
        _state_dir(monkeypatch, tmp_path)
        sent = _posts(monkeypatch)
        bad = FakeConn(health=[("odds_dk_lines", "STALE", "CRIT", "stale")],
                       runs=_clean_runs())
        good = FakeConn(health=[("odds_dk_lines", "OK", "CRIT", "fine")],
                        runs=_clean_runs())
        fa.run_failure_alerter(conn=bad, now=NOW)
        r = fa.run_failure_alerter(conn=good, now=NOW + timedelta(minutes=10))
        assert r["recovered"] == ["health:odds_dk_lines"]
        assert sent[-1]["recovery"] is True
        # ...and not again on the next quiet pass.
        r2 = fa.run_failure_alerter(conn=good, now=NOW + timedelta(minutes=20))
        assert r2["recovered"] == []

    def test_a_healthy_first_run_announces_nothing(self, monkeypatch, tmp_path):
        _state_dir(monkeypatch, tmp_path)
        sent = _posts(monkeypatch)
        conn = FakeConn(health=[("a", "OK", "CRIT", "")], runs=_clean_runs())
        r = fa.run_failure_alerter(conn=conn, now=NOW)
        assert sent == [] and r["alerted"] == [] and r["recovered"] == []

    def test_a_failed_post_does_not_stamp_the_throttle(self, monkeypatch, tmp_path):
        # Stamping on a POST that never landed would silence the next two hours
        # on the strength of a message nobody received (§7).
        _state_dir(monkeypatch, tmp_path)
        sent = _posts(monkeypatch, ok=False)
        conn = FakeConn(health=[("odds_dk_lines", "STALE", "CRIT", "stale")],
                        runs=_clean_runs())
        fa.run_failure_alerter(conn=conn, now=NOW)
        r = fa.run_failure_alerter(conn=conn, now=NOW + timedelta(minutes=1))
        assert r["alerted"] == []          # still not confirmed
        assert len(sent) == 2, "an unconfirmed alert must be retried"

    def test_a_flapping_condition_alerts_on_each_new_occurrence(
            self, monkeypatch, tmp_path):
        _state_dir(monkeypatch, tmp_path)
        sent = _posts(monkeypatch)
        bad = FakeConn(health=[("x", "STALE", "CRIT", "d")], runs=_clean_runs())
        good = FakeConn(health=[("x", "OK", "CRIT", "")], runs=_clean_runs())
        fa.run_failure_alerter(conn=bad, now=NOW)
        fa.run_failure_alerter(conn=good, now=NOW + timedelta(minutes=10))
        r = fa.run_failure_alerter(conn=bad, now=NOW + timedelta(minutes=20))
        assert r["alerted"] == ["health:x"], (
            "recovery must clear the throttle, or a flapping failure is "
            "announced once and then silently repeats")


class TestItCannotBreakTheWorker:
    def test_a_dead_database_is_reported_not_raised(self, monkeypatch, tmp_path):
        _state_dir(monkeypatch, tmp_path)
        _posts(monkeypatch)

        class Boom:
            def execute(self, *a, **k):
                raise RuntimeError("connection refused")

        r = fa.run_failure_alerter(conn=Boom(), now=NOW)
        assert r["conditions"] == []

    def test_the_watchdog_still_owns_outage_detection(self):
        # This module reads the database to do its job, so during a real
        # outage it can say nothing. The watchdog covers exactly that case and
        # holds no database dependency on its alerting path — duplicating it
        # here would make a second, weaker copy of the one check that has to
        # work when everything else does not.
        src = (Path(__file__).parent.parent / "tracking"
               / "heartbeat_watchdog.py").read_text(encoding="utf-8")
        assert "db_unreachable" in src

    def test_the_scheduler_runs_it_and_never_lets_it_raise(self):
        src = (Path(__file__).parent.parent / "scheduler.py").read_text(
            encoding="utf-8")
        assert 'id="failure_alerter"' in src
        block = src[src.index("def run_failure_alerter() -> None:"):]
        block = block[:block.index("\ndef ", 10)]
        assert "except Exception" in block


class TestSilentJobs:
    """A job whose correct output is often NOTHING cannot be watched by
    watching its output. The NFL polls write a pick only when one qualifies,
    so before this a dead poll and a quiet market were identical.
    """

    def test_a_silent_job_is_a_critical_condition(self):
        from datetime import timedelta as _td
        old = (NOW - _td(hours=6)).isoformat()
        conn = FakeConn(health=[], runs=_clean_runs(),
                        beats=[("nfl_opener_poll", old)])
        c = fa._conditions(conn, NOW)
        assert "job:nfl_opener_poll" in c
        sev, title, detail = c["job:nfl_opener_poll"]
        assert sev == "CRIT"
        assert "silent" in title
        assert "360" in detail or "minutes ago" in detail

    def test_a_job_with_no_row_is_NOT_reported(self):
        """Two very different things produce no row: a job DISABLED on this
        deployment (RUN_NFL_LIVE=0 never registers) and a fresh deploy where
        nothing has ticked yet. Alerting on either means a burst of false
        alarms every deploy plus a permanent alarm per switched-off job.

        The scheduler seeds a row at REGISTRATION, so "has a row and has gone
        quiet" means "was registered and has stopped" — which is the condition
        worth waking someone for."""
        conn = FakeConn(health=[], runs=_clean_runs(), beats=[])
        assert [k for k in fa._conditions(conn, NOW) if k.startswith("job:")] == []

    def test_a_seeded_job_that_never_ticks_still_goes_stale(self):
        """Seeding must not become a permanent excuse: a job registered and
        then never run is exactly the silent failure this exists for."""
        from datetime import timedelta as _td
        seeded_long_ago = (NOW - _td(hours=3)).isoformat()
        conn = FakeConn(health=[], runs=_clean_runs(),
                        beats=[("nfl_opener_poll", seeded_long_ago)])
        assert "job:nfl_opener_poll" in fa._conditions(conn, NOW)

    def test_fresh_jobs_are_silent(self):
        conn = FakeConn(health=[], runs=_clean_runs())
        assert [k for k in fa._conditions(conn, NOW) if k.startswith("job:")] == []

    def test_the_jobs_with_no_output_check_are_watched(self):
        # The three the 2026-09-06 audit found uncovered, plus the watcher.
        from tracking.job_heartbeat import MAX_SILENCE
        for j in ("nfl_opener_poll", "nfl_poll_hourly", "nfl_live_worker",
                  "failure_alerter"):
            assert j in MAX_SILENCE, j

    def test_the_overnight_gap_does_not_trip_the_in_play_worker(self):
        # nfl_live_worker runs 9am-midnight ET, so ~9h of silence is correct
        # behaviour and must not alert.
        from tracking.job_heartbeat import MAX_SILENCE
        assert MAX_SILENCE["nfl_live_worker"] > 9 * 60
