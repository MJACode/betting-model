"""Deploy drain and the merge gate that keeps a daily off a redeploy.

A merge to master redeploys the Railway worker. SIGTERM has to let the
step in progress finish and close pipeline_runs as deploy-cutoff.
SIGKILL cannot be caught. The GitHub check blocks while a daily row is
still open.
"""

from __future__ import annotations

import json
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
    CHECK_NAME,
    EMERGENCY_LABEL,
    MAX_OPEN_DAILY,
    OPEN_DAILY_SQL,
    checks_for_pull_requests,
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
    now = datetime(2026, 11, 5, 16, 10, tzinfo=UTC)
    block, message = _gate(now, open_run_ids=["abc123"])
    assert block
    assert "abc123" in message
    assert EMERGENCY_LABEL in message


def test_no_open_daily_lets_the_merge_through():
    now = datetime(2026, 11, 5, 16, 10, tzinfo=UTC)
    block, message = _gate(now)
    assert not block
    assert "no open daily" in message


def test_a_failed_ledger_read_blocks_the_merge():
    now = datetime(2026, 11, 5, 15, 0, tzinfo=UTC)
    block, message = _gate(now, query_error="OperationalError: down")
    assert block
    assert "OperationalError" in message


def test_the_emergency_label_and_the_body_marker_bypass():
    now = datetime(2026, 11, 5, 16, 10, tzinfo=UTC)
    block, message = _gate(now, labels=[EMERGENCY_LABEL], open_run_ids=["abc"])
    assert not block and "bypass" in message
    block, message = _gate(
        now,
        body=f"ship it\n{BYPASS_MARKER}\n",
        open_run_ids=["abc"],
        author_association="OWNER",
    )
    assert not block and BYPASS_MARKER in message
    block, message = _gate(
        now,
        body=f"ship it\n{BYPASS_MARKER}\n",
        open_run_ids=["abc"],
        author_association="MEMBER",
    )
    assert not block and "MEMBER" in message
    block, message = _gate(
        now,
        body=f"ship it\n{BYPASS_MARKER}\n",
        open_run_ids=["abc"],
        author_association="CONTRIBUTOR",
    )
    assert block
    block, message = _gate(
        now, body=f"ship it\n{BYPASS_MARKER}\n", open_run_ids=["abc"],
    )
    assert block


def test_without_the_database_the_clock_covers_the_morning_window():
    inside = datetime(2026, 11, 5, 6, 30, tzinfo=ET)
    assert clock_blocks(inside)
    block, _ = _gate(inside, db_configured=False)
    assert block

    before = datetime(2026, 11, 5, 5, 44, tzinfo=ET)
    assert not clock_blocks(before)
    block, _ = _gate(before, db_configured=False)
    assert not block

    after = datetime(2026, 11, 5, 7, 15, tzinfo=ET)
    assert not clock_blocks(after)
    block, message = _gate(after, db_configured=False)
    assert not block
    assert "catch-up" in message


def test_the_daily_start_blocks_even_when_the_ledger_is_clear():
    """05:45–06:20 ET blocks with no open row. 05:44 and 06:20 do not."""
    clear = dict(db_configured=True, open_run_ids=[], query_error=None)
    at_start = datetime(2026, 11, 5, 5, 45, tzinfo=ET)
    block, message = _gate(at_start, **clear)
    assert block
    assert "05:45" in message

    just_before_end = datetime(2026, 11, 5, 6, 19, 59, tzinfo=ET)
    block, _ = _gate(just_before_end, **clear)
    assert block

    at_end = datetime(2026, 11, 5, 6, 20, tzinfo=ET)
    block, message = _gate(at_end, **clear)
    assert not block
    assert "no open daily" in message

    early = datetime(2026, 11, 5, 5, 44, 59, tzinfo=ET)
    block, _ = _gate(early, **clear)
    assert not block

    # The label still opens the window. A body marker from outside the
    # org does not.
    block, message = _gate(
        at_start, **clear, labels=[EMERGENCY_LABEL],
    )
    assert not block and "bypass" in message
    block, _ = _gate(
        at_start,
        **clear,
        body=BYPASS_MARKER,
        author_association="NONE",
    )
    assert block


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


def test_rewriting_aborted_as_deploy_cutoff_is_still_one_deploy_kill():
    """The sweep can stamp aborted, then the draining process finish_run
    overwrites that with deploy-cutoff. Both markers are one deploy-kill.
    The retry cap does not move."""
    started = datetime(2026, 11, 5, 11, 0, tzinfo=UTC)
    finished = datetime(2026, 11, 5, 11, 20, tzinfo=UTC)
    aborted = DailyRun(started, finished, False, "aborted")
    cutoff = DailyRun(started, finished, False, "deploy-cutoff")
    assert today_counts([aborted]) == (1, 0)
    assert today_counts([cutoff]) == (1, 0)


def test_railway_drains_for_ten_minutes():
    cfg = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    from tracking.scoring_lease import DRAIN_SECONDS
    assert cfg["deploy"]["drainingSeconds"] == 600
    assert isinstance(cfg["deploy"]["drainingSeconds"], int)
    assert cfg["deploy"]["drainingSeconds"] == DRAIN_SECONDS


def test_the_gate_runs_from_the_base_branch_and_refreshes_on_a_schedule():
    text = (ROOT / ".github" / "workflows" / "daily-merge-gate.yml").read_text(
        encoding="utf-8",
    )
    assert "pull_request_target:" in text
    assert "\n  pull_request:\n" not in text
    assert "pull_request.head" not in text
    assert "github.event.pull_request.base.sha" in text
    assert "persist-credentials: false" in text
    assert 'cron: "*/10 9-23,0-3 * * *"' in text
    gate = text.split("Block the merge while a daily run is open", 1)[1]
    gate = gate.split("Refresh open pull requests", 1)[0]
    assert "DATABASE_URL_READONLY" in gate
    assert "secrets.DATABASE_URL" not in gate.replace(
        "secrets.DATABASE_URL_READONLY", "",
    )
    refresh = text.split("Refresh open pull requests", 1)[1]
    assert "secrets.DATABASE_URL" in refresh
    assert "--refresh-open-prs" in refresh
    assert "github.event_name == 'schedule'" in refresh


def test_a_refresh_posts_the_same_check_name_and_keeps_one_prs_bypass():
    now = datetime(2026, 11, 5, 16, 10, tzinfo=UTC)
    prs = [
        {
            "number": 1,
            "body": "",
            "labels": [],
            "head": {"sha": "aaa111"},
        },
        {
            "number": 2,
            "body": f"please {BYPASS_MARKER}",
            "labels": [],
            "author_association": "MEMBER",
            "head": {"sha": "bbb222"},
        },
        {"number": 3, "body": "", "labels": [], "head": {}},
    ]
    checks = checks_for_pull_requests(
        prs, now=now, db_configured=True, open_run_ids=["run-1"],
        query_error=None,
    )
    assert [c["head_sha"] for c in checks] == ["aaa111", "bbb222"]
    assert checks[0]["name"] == CHECK_NAME == "daily pipeline not running"
    assert checks[0]["conclusion"] == "failure"
    assert checks[1]["conclusion"] == "success"
    assert BYPASS_MARKER in checks[1]["output"]["summary"]


def test_the_daily_child_holds_the_lease_around_the_run_and_a_step_does_not():
    src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    cli = src.split('if __name__ == "__main__":', 1)[1]
    step, full = cli.split("# Full pipeline", 1)
    assert "acquire(" not in step
    assert 'acquire("daily")' in full
    assert full.index('acquire("daily")') < full.index("run_daily_pipeline(")
    assert full.index("run_daily_pipeline(") < full.index("lease.release()")


def test_boot_does_not_block_the_scheduler_on_the_lease():
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    main = src.split("def main(", 1)[1]
    assert "wait_for_scoring_lease" not in main
    assert main.index("\n    abort_orphaned_refresh_runs()\n") < main.index(
        "\n        sched.start()\n",
    )
    catch = src.split("def catch_up_daily_pipeline(", 1)[1].split("\ndef ", 1)[0]
    assert 'wait_for_scoring_lease("daily")' in catch
    refresh = src.split("def catch_up_refresh_pass(", 1)[1].split("\ndef ", 1)[0]
    assert 'wait_for_scoring_lease("refresh")' in refresh
    sweep = src.split("def abort_orphaned_refresh_runs(", 1)[1].split("\ndef ", 1)[0]
    assert sweep.index("drop_live_kinds") < sweep.index("get_connection")


def test_the_refresh_shell_takes_the_lease_before_the_ledger_start():
    sh = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")
    assert sh.index("--kind refresh") < sh.index("tracking.run_ledger start")
    assert "disown" in sh
    assert "release_scoring_lease" in sh
    assert sh.index("tracking.run_ledger finish") < sh.index("exit 0")
