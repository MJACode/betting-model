"""Deploy drain and the merge gate that keeps a daily off a redeploy.

A merge to master redeploys the Railway worker. SIGTERM has to let the
step in progress finish and close pipeline_runs as deploy-cutoff.
SIGKILL cannot be caught. The GitHub check blocks while a daily row is
still open.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from tracking.daily_merge_gate import (
    BYPASS_MARKER,
    EMERGENCY_LABEL,
    MAX_OPEN_DAILY,
    OPEN_DAILY_SQL,
    clock_blocks,
    gate_decision,
)
from tracking.daily_retry import (
    MAX_DAILY_RUN,
    DailyRun,
    decide_daily_retry,
    today_counts,
)
from tracking.deploy_drain import (
    DEPLOY_CUTOFF,
    DeployCutoff,
    checkpoint,
    install_pipeline_handler,
    request,
    reset_for_tests,
    signal_children,
    track,
    wait_children,
)
from tracking.refresh_retry import RefreshRun, decide_refresh_retry, interrupted

ROOT = Path(__file__).resolve().parent.parent
ET = ZoneInfo("America/New_York")
UTC = timezone.utc


@pytest.fixture(autouse=True)
def _reset_drain():
    reset_for_tests()
    yield
    reset_for_tests()


def test_checkpoint_runs_the_current_step_and_refuses_the_next():
    checkpoint("first")
    request()  # SIGTERM arrived while "first" was inside its work
    with pytest.raises(DeployCutoff) as caught:
        checkpoint("second")
    assert caught.value.before_step == "second"


def test_pipeline_sigterm_handler_records_the_signal_and_returns():
    previous = signal.getsignal(signal.SIGTERM)
    try:
        install_pipeline_handler()
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        from tracking.deploy_drain import requested
        assert requested()
    finally:
        signal.signal(signal.SIGTERM, previous)


def test_every_daily_step_checks_before_it_starts():
    src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    body = src.split("def run_daily_pipeline(", 1)[1].split("\ndef setup_database", 1)[0]
    lines = body.splitlines()
    guarded = 0
    for i, line in enumerate(lines):
        match = re.match(r'\s*results\["([^"]+)"\]\s*=', line)
        if not match:
            continue
        previous = next(
            lines[j].strip() for j in range(i - 1, -1, -1) if lines[j].strip()
        )
        assert previous == f'checkpoint("{match.group(1)}")', (
            f"{match.group(1)} starts without a drain check"
        )
        guarded += 1
    assert guarded >= 50


def test_deploy_cutoff_is_a_deploy_kill_not_a_real_failure():
    started = datetime(2026, 11, 5, 6, 0, tzinfo=ET)
    finished = datetime(2026, 11, 5, 6, 12, tzinfo=ET)
    now = datetime(2026, 11, 5, 6, 20, tzinfo=ET)
    drained = DailyRun(started, finished, False, "deploy-cutoff")
    kills, failures = today_counts([drained])
    assert (kills, failures) == (1, 0)
    decision = decide_daily_retry(now=now, runs=[drained])
    assert decision.action == "run"

    mixed = DailyRun(started, finished, False, "deploy-cutoff,odds")
    assert today_counts([mixed]) == (1, 0)

    real = DailyRun(started, finished, False, "mlb_stats")
    assert today_counts([real]) == (0, 1)


def test_a_drained_refresh_with_steps_recorded_is_still_replaced():
    now = datetime(2026, 9, 20, 18, 24, tzinfo=UTC)
    drained = RefreshRun(
        "hourly",
        now - timedelta(minutes=7),
        now - timedelta(minutes=1),
        12,
        "deploy-cutoff",
    )
    assert interrupted(drained)
    decision = decide_refresh_retry(now=now, runs=[drained], enabled=True)
    assert decision.action == "run"

    finished_chain = RefreshRun(
        "hourly",
        now - timedelta(minutes=7),
        now - timedelta(minutes=1),
        36,
        "health-check",
    )
    assert not interrupted(finished_chain)


def test_health_check_does_not_treat_deploy_cutoff_as_a_producer_step():
    src = (ROOT / "tracking" / "system_health.py").read_text(encoding="utf-8")
    assert '"deploy-cutoff"' in src
    assert DEPLOY_CUTOFF == "deploy-cutoff"


def test_the_gate_window_matches_the_daily_max():
    assert MAX_OPEN_DAILY == MAX_DAILY_RUN


def test_the_open_daily_query_casts_started_at():
    assert "run_kind = 'daily'" in OPEN_DAILY_SQL
    assert "finished_at IS NULL" in OPEN_DAILY_SQL
    assert "started_at::timestamptz" in OPEN_DAILY_SQL


def _gate(now, **kw):
    base = dict(
        now=now,
        labels=[],
        body="",
        db_configured=True,
        open_run_ids=[],
        query_error=None,
    )
    base.update(kw)
    return gate_decision(**base)


def test_an_open_daily_blocks_the_merge():
    now = datetime(2026, 11, 5, 11, 10, tzinfo=UTC)
    block, message = _gate(now, open_run_ids=["abc123"])
    assert block
    assert "abc123" in message
    assert EMERGENCY_LABEL in message


def test_no_open_daily_lets_the_merge_through():
    now = datetime(2026, 11, 5, 11, 10, tzinfo=UTC)
    block, message = _gate(now)
    assert not block
    assert "no open daily" in message


def test_a_failed_ledger_read_blocks_the_merge():
    now = datetime(2026, 11, 5, 15, 0, tzinfo=UTC)
    block, message = _gate(now, query_error="OperationalError: down")
    assert block
    assert "OperationalError" in message


def test_the_emergency_label_and_the_body_marker_bypass():
    now = datetime(2026, 11, 5, 11, 10, tzinfo=UTC)
    block, message = _gate(now, labels=[EMERGENCY_LABEL], open_run_ids=["abc"])
    assert not block and "bypass" in message
    block, message = _gate(
        now, body=f"ship it\n{BYPASS_MARKER}\n", open_run_ids=["abc"],
    )
    assert not block and BYPASS_MARKER in message


def test_without_the_database_the_clock_covers_the_morning_window():
    inside = datetime(2026, 11, 5, 6, 30, tzinfo=ET)
    assert clock_blocks(inside)
    block, _ = _gate(inside, db_configured=False)
    assert block

    before = datetime(2026, 11, 5, 5, 59, tzinfo=ET)
    assert not clock_blocks(before)
    block, _ = _gate(before, db_configured=False)
    assert not block

    after = datetime(2026, 11, 5, 7, 15, tzinfo=ET)
    assert not clock_blocks(after)
    block, message = _gate(after, db_configured=False)
    assert not block
    assert "catch-up" in message


def test_sigterm_is_forwarded_and_the_child_finishes_its_step(tmp_path):
    out = tmp_path / "out"
    script = tmp_path / "child.py"
    script.write_text(textwrap.dedent(f"""
        import signal, time
        path = {str(out)!r}
        def stop(signum, frame):
            time.sleep(0.3)
            open(path, "a").write("finished")
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, stop)
        open(path, "w").write("started")
        while True:
            time.sleep(0.05)
    """), encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(script)])
    try:
        deadline = time.time() + 5
        while time.time() < deadline and (
            not out.exists() or out.read_text(encoding="utf-8") != "started"
        ):
            time.sleep(0.05)
        assert out.read_text(encoding="utf-8") == "started"
        track(proc)
        signal_children()
        wait_children()
        assert out.read_text(encoding="utf-8") == "startedfinished"
        assert proc.wait(timeout=5) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_scheduler_installs_the_sigterm_drain():
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert "signal.signal(signal.SIGTERM, _handle_deploy_sigterm)" in src
    assert "signal_children()" in src
    assert "wait_children()" in src


def _stub_python(log: Path) -> str:
    # A bash `python` so refresh_pass.sh can run without the real interpreter.
    # The odds step sleeps so a SIGTERM can land while it is in progress.
    return textwrap.dedent(f"""\
        #!/usr/bin/env bash
        printf '%s\\n' "$*" >> {str(log)!r}
        if [ "$1" = "-m" ]; then
          if [ "$3" = "start" ]; then
            echo testrun
          fi
          exit 0
        fi
        step=""
        prev=""
        for a in "$@"; do
          if [ "$prev" = "--step" ]; then
            step="$a"
          fi
          prev="$a"
        done
        if [ "$step" = "odds" ]; then
          echo odds-start >> {str(log)!r}
          sleep 8
          echo odds-done >> {str(log)!r}
        fi
        exit 0
        """)


@pytest.mark.skipif(not Path("/bin/bash").exists(), reason="needs bash")
def test_refresh_sigterm_finishes_the_open_group_and_marks_deploy_cutoff(tmp_path):
    log = tmp_path / "calls"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "python"
    stub.write_text(_stub_python(log), encoding="utf-8")
    stub.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    proc = subprocess.Popen(
        ["bash", "scripts/refresh_pass.sh", "hourly"],
        cwd=str(ROOT),
        env=env,
    )
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            if log.exists() and "odds-start" in log.read_text(encoding="utf-8"):
                break
            time.sleep(0.05)
        else:
            raise AssertionError(
                "odds never started:\n" + (
                    log.read_text(encoding="utf-8") if log.exists() else "no log"
                )
            )
        os.kill(proc.pid, signal.SIGTERM)
        assert proc.wait(timeout=30) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    text = log.read_text(encoding="utf-8")
    assert "odds-done" in text
    assert "--step nhl-over-under" not in text
    assert "deploy-cutoff" in text
    assert "--step odds" in text
