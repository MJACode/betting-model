"""The This PC window's readers (pc_monitor/), fed real lines from the PC.

Every fixture below was copied from the PC's own logs, Task Scheduler and
processes on 2026-11-21. The parsers take their input and the time to judge
against as arguments, so these run anywhere; nothing here touches the machine
except tmp_path.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pc_monitor import readers as R

ROOT = Path(__file__).resolve().parent.parent


def utc(s: str) -> float:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()


# ── the in-play feed's log ──────────────────────────────────────────────────

FEED_LOG = """\
2026-11-21 11:42:13,293 INFO reading NBA, NCAAB, NCAABW, NCAAF, NFL; a live league every 1.0 s, an idle one every 30 s, at least 0.5 s between requests
2026-11-21 13:38:49,619 WARNING NCAAB: DraftKings event 35058565 (Queens NC @ LSU) does not resolve onto a game
2026-11-21 13:39:53,536 WARNING NCAAB: DraftKings event 35058565 (Queens NC @ LSU) does not resolve onto a game
2026-11-21 13:41:18,512 INFO read 6701 (NBA): {'ok': True, 'live': 1, 'matched': 1, 'written': 0}
2026-11-21 13:42:57,643 INFO read 6801 (NCAAF): {'ok': True, 'live': 16, 'matched': 16, 'written': 1}
2026-11-21 13:44:40,489 INFO read 6901 (NCAAB): {'ok': True, 'live': 7, 'matched': 6, 'written': 1}
2026-11-21 13:46:21,507 INFO read 7001 (NCAABW): {'ok': True, 'live': 1, 'matched': 1, 'written': 0}
2026-11-21 13:48:03,135 INFO read 7101 (NBA): {'ok': True, 'live': 1, 'matched': 1, 'written': 0}
2026-11-21 13:49:16,817 WARNING NCAAB: DraftKings event 35058565 (Queens NC @ LSU) does not resolve onto a game
2026-11-21 13:49:46,229 INFO read 7201 (NCAAF): {'ok': True, 'live': 16, 'matched': 16, 'written': 1}
"""


def test_read_rate_is_reads_over_time_between_the_hundred_read_lines():
    s = R.feed_log_summary(R.parse_log_lines(FEED_LOG.splitlines()))
    rate = s["rate"]
    assert rate["reads"] == 500
    # 13:41:18.512 -> 13:49:46.229 is 507.717 s.
    assert rate["to_at"] - rate["from_at"] == pytest.approx(507.717, abs=1e-3)
    assert rate["per_s"] == pytest.approx(500 / 507.717, rel=1e-6)
    assert s["last_read"]["n"] == 7201 and s["last_read"]["sport"] == "NCAAF"
    assert s["last_read"]["detail"] == {"ok": True, "live": 16, "matched": 16, "written": 1}


def test_read_rate_uses_only_the_run_since_the_last_restart():
    restarted = FEED_LOG + (
        "2026-11-21 13:50:13,052 INFO reading NBA, NCAAB, NCAABW, NCAAF, NFL; a live league every 1.0 s\n"
        "2026-11-21 13:50:14,000 INFO read 1 (NBA): {'ok': True, 'live': 1, 'matched': 1, 'written': 1}\n"
        "2026-11-21 13:51:54,000 INFO read 101 (NCAAF): {'ok': True, 'live': 16, 'matched': 16, 'written': 1}\n")
    rate = R.feed_log_summary(R.parse_log_lines(restarted.splitlines()))["rate"]
    assert rate["reads"] == 100
    assert rate["to_at"] - rate["from_at"] == pytest.approx(100.0)


def test_one_read_line_is_not_a_rate():
    one = "2026-11-21 13:41:18,512 INFO read 6701 (NBA): {'ok': True, 'live': 1, 'matched': 1, 'written': 0}"
    assert R.feed_log_summary(R.parse_log_lines([one]))["rate"] is None


def test_repeated_warnings_collapse_to_one_row_with_a_count():
    problems = R.feed_log_summary(R.parse_log_lines(FEED_LOG.splitlines()))["problems"]
    assert len(problems) == 1
    p = problems[0]
    assert p["count"] == 3
    assert p["message"] == "NCAAB: DraftKings event 35058565 (Queens NC @ LSU) does not resolve onto a game"
    assert p["last_at"] - p["first_at"] == pytest.approx(10 * 60 + 27.198, abs=1e-3)


def test_a_traceback_joins_the_line_above_it():
    lines = ["2026-11-21 13:00:00,000 ERROR write failed",
             "Traceback (most recent call last):",
             '  File "x.py", line 1, in <module>',
             "psycopg2.OperationalError: server closed the connection unexpectedly",
             "2026-11-21 13:00:01,000 INFO read 1 (NBA): {'ok': True}"]
    entries = R.parse_log_lines(lines)
    assert [e["level"] for e in entries] == ["ERROR", "INFO"]
    assert entries[0]["msg"].endswith("server closed the connection unexpectedly")
    assert R.collapse_problems(entries)[0]["message"] == "write failed"


def test_the_idle_exit_is_reported_as_the_stop():
    lines = ["2026-11-21 01:58:13,062 INFO reading NBA, NCAAB, NCAABW, NCAAF, NFL; a live league every 1.0 s",
             "2026-11-21 02:43:19,715 INFO no live event in NBA, NCAAB, NCAABW, NCAAF, NFL for 45 minutes - exiting"]
    s = R.feed_log_summary(R.parse_log_lines(lines))
    assert s["stopped"]["message"].endswith("- exiting")
    # A later start clears it.
    s2 = R.feed_log_summary(R.parse_log_lines(lines + ["2026-11-21 02:44:13,052 INFO reading NBA; x"]))
    assert s2["stopped"] is None


# ── the feed launcher's log ─────────────────────────────────────────────────

LAUNCHER_LOG = """\
--- start 2026-11-21T06:58:03Z
--- exit 0 2026-11-21T07:43:20Z
--- start 2026-11-21T07:44:03Z
--- start 2026-11-21T14:00:03Z
--- start 2026-11-21T14:29:20Z
--- exit 0 2026-11-21T15:14:42Z
--- start 2026-11-21T15:15:01Z
--- exit 0 2026-11-21T16:00:20Z
--- start 2026-11-21T16:01:01Z
--- exit -1 2026-11-21T16:42:04Z
--- start 2026-11-21T16:42:06Z
"""


def test_launcher_runs_keep_a_start_with_no_exit_as_unknown():
    runs = R.parse_launcher_log(LAUNCHER_LOG.splitlines())
    assert len(runs) == 7
    assert runs[0] == {"start_at": utc("2026-11-21T06:58:03"), "exit_code": 0, "exit_at": utc("2026-11-21T07:43:20")}
    assert runs[1]["exit_code"] is None and runs[1]["exit_at"] is None
    assert runs[5]["exit_code"] == -1
    assert runs[6]["exit_at"] is None


# ── the tennis task's pass log and summaries ────────────────────────────────

TENNIS_PASSES = """\
--- start 2026-11-21T17:52:04Z
dk exit  2026-11-21T17:56:26Z
pinnacle exit  2026-11-21T17:56:30Z
tennisexplorer exit  2026-11-21T17:56:46Z
--- start 2026-11-21T18:22:01Z
dk exit  2026-11-21T18:26:22Z
pinnacle exit 1 2026-11-21T18:26:25Z
"""


def test_a_blank_exit_code_is_not_recorded_and_its_time_is_not_read_as_a_code():
    passes = R.parse_tennis_passes(TENNIS_PASSES.splitlines())
    assert len(passes) == 2
    dk = passes[1]["collectors"]["dk"]
    assert dk == {"exit_code": None, "at": utc("2026-11-21T18:26:22")}
    assert passes[1]["collectors"]["pinnacle"] == {"exit_code": 1, "at": utc("2026-11-21T18:26:25")}
    assert "tennisexplorer" not in passes[1]["collectors"]   # still running
    assert passes[0]["collectors"]["tennisexplorer"]["at"] == utc("2026-11-21T17:56:46")


def test_collector_summary_is_the_last_json_line():
    dk = ('{"seen_at": "2026-11-21T18:22:10+00:00", "leagues": 40, "pages": 194, "leagues_gone": 1, '
          '"subpages_tried": 155, "subpages_gone": 0, "seen": 2511, "stored": 550}\n')
    assert R.last_json_line(dk)["stored"] == 550
    assert R.last_json_line('{"pages": 4, "rows": 230}') == {"pages": 4, "rows": 230}
    assert R.last_json_line("") is None
    assert R.last_json_line("not json") is None


# ── Task Scheduler ──────────────────────────────────────────────────────────

# The PowerShell read's output for the three tasks, 2026-11-21 13:58 ET.
TASKS_JSON = json.dumps([
    {"name": "DkLiveBoard", "state": "Running", "last_run_at": "2026-11-21T18:58:00.0000000Z",
     "next_run_at": "2026-11-21T18:59:00.0000000Z", "last_result": 2147946720,
     "action": 'C:\\Windows\\pyw.exe "C:\\Users\\micha\\Documents\\betting_local_copies\\bin\\run_hidden.pyw" '
               'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File '
               '"C:\\Users\\micha\\Documents\\betting-model\\.claude\\feeds\\dk-live-board\\scripts\\dk_live_board_run.ps1" '
               '-Feed "C:\\Users\\micha\\Documents\\betting-model\\.claude\\feeds\\dk-live-board"',
     "triggers": [{"type": "MSFT_TaskDailyTrigger", "start": "2026-11-13T09:00:00-05:00", "delay": None,
                   "enabled": True, "interval": "PT1M", "duration": "PT18H"},
                  {"type": "MSFT_TaskLogonTrigger", "start": None, "delay": "PT2M", "enabled": True,
                   "interval": None, "duration": None}]},
    {"name": "LocalMirror", "state": "Ready", "last_run_at": "2026-11-21T16:27:48.0000000Z",
     "next_run_at": "2026-11-22T05:30:00.0000000Z", "last_result": 0,
     "action": 'C:\\Windows\\pyw.exe "C:\\Users\\micha\\Documents\\betting_local_copies\\bin\\run_hidden.pyw" '
               'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File '
               'C:\\Users\\micha\\Documents\\betting_local_copies\\bin\\local_mirror_run.ps1',
     "triggers": [{"type": "MSFT_TaskDailyTrigger", "start": "2026-11-03T00:30:00", "delay": None,
                   "enabled": True, "interval": None, "duration": None},
                  {"type": "MSFT_TaskLogonTrigger", "start": None, "delay": "PT2M", "enabled": True,
                   "interval": None, "duration": None}]},
    {"name": "TennisFeeds", "state": "Ready", "last_run_at": "2026-11-21T18:52:01.0000000Z",
     "next_run_at": "2026-11-21T19:22:00.0000000Z", "last_result": 0,
     "action": 'C:\\Windows\\pyw.exe "C:\\Users\\micha\\Documents\\betting_local_copies\\bin\\run_hidden.pyw" '
               'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File '
               'C:\\Users\\micha\\Documents\\betting_local_copies\\bin\\tennis_feeds_run.ps1 -Feed '
               '"C:\\Users\\micha\\Documents\\betting-model\\.claude\\feeds\\tennis"',
     "triggers": [{"type": "MSFT_TaskTimeTrigger", "start": "2026-11-13T18:52:00", "delay": None,
                   "enabled": True, "interval": "PT30M", "duration": ""}]},
])


def test_tasks_parse_schedule_window_script_and_result():
    tasks = {t["name"]: t for t in R.parse_tasks(TASKS_JSON)}
    dk, bk, tn = tasks["DkLiveBoard"], tasks["LocalMirror"], tasks["TennisFeeds"]
    assert dk["script"] == "dk_live_board_run.ps1"
    assert bk["script"] == "local_mirror_run.ps1"
    assert tn["script"] == "tennis_feeds_run.ps1"
    assert dk["schedule"] == "every 1 min from 09:00 for 18 h, at sign-in (+2 min)"
    assert dk["window"] == {"start_minute": 9 * 60, "duration_s": 18 * 3600}
    assert bk["schedule"] == "daily at 00:30, at sign-in (+2 min)" and bk["window"] is None
    assert tn["schedule"] == "every 30 min" and tn["window"] is None
    assert dk["result"]["code"] == "0x800710E0" and dk["result"]["tone"] == "ok"
    assert dk["last_run_at"] == utc("2026-11-21T18:58:00")
    # PowerShell unwraps a one-task list into a bare object.
    assert R.parse_tasks(json.dumps(json.loads(TASKS_JSON)[2]))[0]["name"] == "TennisFeeds"


@pytest.mark.parametrize("code,tone,words", [
    (0, "ok", "without an error"),
    (0x41301, "ok", "running now"),
    (2147946720, "ok", "already running"),      # 0x800710E0 as Task Scheduler stores it
    (-2147020576, "ok", "already running"),     # the same code read as signed
    (0x8007042B, "bad", "ended unexpectedly"),
    (1, "bad", "exit code 1"),
    (0x80070005, "warn", "0x80070005"),
])
def test_task_results_in_plain_words(code, tone, words):
    d = R.describe_task_result(code)
    assert d["tone"] == tone and words in d["text"]


@pytest.mark.parametrize("hhmm,inside", [
    ("08:59", False), ("09:00", True), ("13:00", True), ("23:59", True), ("02:59", True), ("03:00", False)])
def test_the_feed_window_runs_past_midnight(hhmm, inside):
    h, m = map(int, hhmm.split(":"))
    assert R.in_daily_window(h * 60 + m, 9 * 60, 18 * 3600) is inside


# ── processes ───────────────────────────────────────────────────────────────

FEED_CMD = ["C:\\Users\\micha\\AppData\\Local\\Programs\\Python\\Python314\\python.exe", "-m",
            "data.ingestors.dk_live_board", "--log",
            "C:\\Users\\micha\\Documents\\betting_local_copies\\logs\\dk_live_board_feed_20261121.log",
            "--exit-on-new-master"]
LAUNCHER_CMD = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File",
                "C:\\Users\\micha\\Documents\\betting-model\\.claude\\feeds\\dk-live-board\\scripts\\dk_live_board_run.ps1",
                "-Feed", "C:\\Users\\micha\\Documents\\betting-model\\.claude\\feeds\\dk-live-board"]


def test_processes_are_found_by_what_they_run():
    assert R.is_dk_feed("python.exe", FEED_CMD)
    assert R.arg_value(FEED_CMD, "--log").endswith("dk_live_board_feed_20261121.log")
    assert R.runs_script(LAUNCHER_CMD, "dk_live_board_run.ps1")
    assert not R.runs_script(LAUNCHER_CMD, "tennis_feeds_run.ps1")
    # A shell whose command text merely mentions the script is not its launcher.
    assert not R.runs_script(["powershell.exe", "-Command", "Get-Content scripts/dk_live_board_run.ps1"],
                             "dk_live_board_run.ps1")
    assert not R.is_dk_feed("python.exe", ["python.exe", "-c", "print('data.ingestors.dk_live_board')"])


# ── judgements ──────────────────────────────────────────────────────────────

NOW = utc("2026-11-21T19:00:00")


def test_feed_presence():
    runs = [{"start_at": NOW - 3000, "exit_code": 0, "exit_at": NOW - 30}]
    assert R.feed_presence(True, NOW, True, runs)["tone"] == "ok"
    assert R.feed_presence(False, NOW, False, runs, "09:00 to 03:00")["text"] == \
        "off by schedule (the task runs 09:00 to 03:00)"
    assert R.feed_presence(False, NOW, True, runs)["text"].startswith("between runs")
    assert R.feed_presence(False, NOW + 600, True, runs)["tone"] == "bad"
    killed = [{"start_at": NOW - 3000, "exit_code": -1, "exit_at": NOW - 30}]
    assert R.feed_presence(False, NOW, True, killed) == {"tone": "bad", "text": "stopped with exit code -1, under a minute ago"}
    starting = runs + [{"start_at": NOW - 20, "exit_code": None, "exit_at": None}]
    assert R.feed_presence(False, NOW, True, starting)["text"].startswith("starting")


@pytest.mark.parametrize("row,running,tone", [
    ({"age_s": 3.6, "live_events": 4, "ok": True}, True, "ok"),
    ({"age_s": 8.0, "live_events": 4, "ok": True}, True, "ok"),
    ({"age_s": 8.1, "live_events": 4, "ok": True}, True, "bad"),
    ({"age_s": 28.0, "live_events": 0, "ok": True}, True, "idle"),     # NBA with no live game
    ({"age_s": 75.0, "live_events": 0, "ok": True}, True, "warn"),
    ({"age_s": 3.0, "live_events": 4, "ok": False}, True, "bad"),
    ({"age_s": 900.0, "live_events": 4, "ok": True}, False, "idle"),   # feed down: judged there instead
])
def test_league_freshness(row, running, tone):
    assert R.sport_status(row, running)["tone"] == tone


# ── the backup ──────────────────────────────────────────────────────────────

PROGRESS = {"started_at": "2026-11-21T16:28:43+00:00", "now": "2026-11-21T17:52:39+00:00",
            "table": "public.odds", "table_rows": 50000, "rows_pulled": 1250089,
            "estimated_total_rows": 226174800, "elapsed_s": 5035, "paused_s": 855,
            "rows_per_s_wall": 248, "rows_per_s_reading": 299}
STATE_DONE = {"run_started_at": "2026-11-21T16:27:58+00:00", "run_id": "20261121T162758Z", "kind": "diff",
              "run_finished_at": "2026-11-21T17:56:47+00:00", "tables": 338, "failed_tables": [],
              "mismatched_tables": [], "rows_pulled": 1360686}
STATE_EARLIER = {**STATE_DONE, "run_started_at": "2026-11-21T14:31:23+00:00",
                 "run_finished_at": "2026-11-21T15:44:28+00:00", "run_id": "20261121T143123Z"}
COPYING = {"bin_refresh.err": {"size": 0}, "catchup.log": {"size": 671}, "github.log": {"size": 7223},
           "github.err": {"size": 0}, "supabase.err": {"size": 0}, "supabase.log": {"size": 0}}
REPORT = ("2026-11-21T17:58:21.084565+00:00 pass 20261121T162749Z (nightly); copy run 20261121T162758Z "
          "2026-11-21 16:27:58+00:00 -> 2026-11-21 17:56:47+00:00, 338 table(s), this pass: True; 338 tables / "
          "233,628,692 rows on disk, 0 differing, 0 failed; 11.18 GB under the root (tables 5.57, GitHub 0.70); "
          "disk free 615.1 of 999.0 GB; kind diff; next task run 2026-11-22T05:30:00.0000000Z, next full from "
          "2026-12-01; read in 2320 ms\nwrote pc_copy_snapshots row 14\n")


def test_backup_mid_copy_shows_live_progress_without_a_percent():
    now = utc("2026-11-21T17:52:50")
    s = R.backup_status("20261121T162749Z", COPYING, PROGRESS, None, STATE_EARLIER, now, True)
    assert s["stage"] == "copying the database and GitHub"
    assert s["copy"]["table"] == "public.odds" and s["copy"]["rows_pulled"] == 1250089
    assert s["copy"]["age_s"] == pytest.approx(11.0)
    assert "estimated_total_rows" not in json.dumps(s)
    assert s["warnings"] == []
    assert s["last_copy"]["run_id"] == "20261121T143123Z"


def test_progress_left_behind_by_a_finished_run_is_not_live():
    # 2026-11-21: progress.json last said 17:52:39 and the run finished 17:56:47.
    now = utc("2026-11-21T18:00:00")
    s = R.backup_status("20261121T162749Z", {**COPYING, "duckdb.err": {"size": 0}}, PROGRESS, None,
                        STATE_DONE, now, True)
    assert s["stage"] == "building the local DuckDB copy"
    assert s["copy"] is None
    finished = {**COPYING, "duckdb.err": {"size": 0}, "report.err": {"size": 0},
                "report.log": {"size": 453, "mtime": utc("2026-11-21T17:58:24")}}
    s2 = R.backup_status("20261121T162749Z", finished, PROGRESS, None, STATE_DONE, now, False)
    assert s2["stage"] == "finished" and s2["copy"] is None and s2["warnings"] == []


def test_a_copy_that_stops_reporting_is_flagged():
    now = utc("2026-11-21T18:10:00")
    s = R.backup_status("20261121T162749Z", COPYING, PROGRESS, None, STATE_EARLIER, now, True)
    assert s["warnings"] == ["the table copy has not reported progress for 17 min"]
    s2 = R.backup_status("20261121T162749Z", COPYING, PROGRESS, None, STATE_EARLIER, now, False)
    assert "the pass is not finished but the backup task is not running" in s2["warnings"]


def test_report_line_and_newest_pass():
    r = R.parse_report(REPORT)
    assert r == {"tables": 338, "rows": 233628692, "differing": 0, "failed": 0,
                 "disk_free_gb": 615.1, "disk_total_gb": 999.0, "snapshot_row": 14}
    names = ["report_20261121T143104Z.log", "supabase_20261121T162749Z.err", "dk_live_board_20261121.log",
             "catchup_20261121T053003Z.log"]
    assert R.newest_pass(names) == "20261121T162749Z"
    # A pass's first file is its fetch log (seen 2026-11-21 at 15:08).
    assert R.newest_pass(names + ["fetch_20261121T200831Z.log"]) == "20261121T200831Z"
    assert R.pass_started_at("20261121T162749Z") == utc("2026-11-21T16:27:49")


def test_iso_times_with_seven_fraction_digits_and_durations():
    assert R.parse_iso("2026-11-22T05:30:00.0000000Z") == utc("2026-11-22T05:30:00")
    assert R.parse_iso("2026-11-21T16:28:43+00:00") == utc("2026-11-21T16:28:43")
    assert R.parse_iso("") is None and R.parse_iso(None) is None and R.parse_iso("soon") is None
    assert R.parse_duration("PT18H") == 64800 and R.parse_duration("PT2M") == 120
    assert R.parse_duration("") is None and R.parse_duration(None) is None


# ── the view keeps working when the database does not ──────────────────────

def test_view_without_the_database_still_shows_tasks_processes_and_logs():
    from pc_monitor.app import view
    tasks = R.parse_tasks(TASKS_JSON)
    panels = {
        "tasks": {"data": tasks, "read_at": NOW},
        "processes": {"data": [
            {"pid": 16256, "started_at": NOW - 8000, "role": "dk_feed", "label": "python.exe -m data.ingestors.dk_live_board",
             "cmdline": FEED_CMD, "cpu_pct": 0.4, "mem_mb": 116.0},
            {"pid": 22140, "started_at": NOW - 8002, "role": "launcher:dk_live_board_run.ps1",
             "label": "powershell.exe dk_live_board_run.ps1", "cmdline": LAUNCHER_CMD, "cpu_pct": 0.0, "mem_mb": 62.0}],
            "read_at": NOW},
        "launcher_log": {"data": {"runs": R.parse_launcher_log(LAUNCHER_LOG.splitlines())}, "read_at": NOW},
        "feed_log": {"data": R.feed_log_summary(R.parse_log_lines(FEED_LOG.splitlines())), "read_at": NOW},
        "db": {"data": None, "read_at": None, "error": "OperationalError", "failed_at": NOW},
    }
    v = view(panels, NOW)
    assert v["db"]["connected"] is False and v["db"]["error"] == "OperationalError"
    assert v["feed"]["presence"]["tone"] == "ok"
    assert v["feed"]["process"]["pid"] == 16256 and "cmdline" not in v["feed"]["process"]
    assert [p["pid"] for p in v["feed"]["launcher"]] == [22140]
    assert v["feed"]["sports"] == []
    assert v["feed"]["log"]["rate"]["reads"] == 500
    assert {t["name"] for t in v["tasks"]} == {"DkLiveBoard", "LocalMirror", "TennisFeeds"}
    assert v["backup"]["task"]["name"] == "LocalMirror" and v["tennis"]["task"]["name"] == "TennisFeeds"
    json.dumps(v)  # the page receives it as JSON
    # And with nothing at all read yet, it still answers.
    assert view({}, NOW)["feed"]["presence"]["tone"] == "bad"


def _feed_rows(read_at: float) -> dict:
    return {"data": [{"sport": "NCAAF", "age_s": 1.7, "ok": True, "live_events": 11, "matched": 11,
                      "detail": "", "db_now": read_at}], "read_at": read_at, "error": None}


def test_old_database_rows_are_never_judged_late():
    """After the database drops (or the collectors pause), the last rows stay
    in memory. Their ages keep growing, but that is not evidence the feed is
    late, so they must turn grey, not red."""
    from pc_monitor.app import view
    procs = {"data": [{"pid": 16256, "started_at": NOW - 8000, "role": "dk_feed", "label": "x",
                       "cmdline": FEED_CMD, "cpu_pct": 0.4, "mem_mb": 116.0}], "read_at": NOW}
    fresh = view({"db_feed": _feed_rows(NOW - 1), "processes": procs,
                  "db": {"data": {"connected": True}, "read_at": NOW - 1}}, NOW)
    ncaaf = lambda v: next(s for s in v["feed"]["sports"] if s["sport"] == "NCAAF")  # noqa: E731
    assert ncaaf(fresh)["status"]["tone"] == "ok"
    assert fresh["db"]["connected"] is True
    dropped = view({"db_feed": _feed_rows(NOW - 30), "processes": procs,
                    "db": {"data": {"connected": True}, "read_at": NOW - 30, "error": "OperationalError",
                           "failed_at": NOW - 5}}, NOW)
    s = ncaaf(dropped)
    assert s["status"]["tone"] == "idle"
    assert s["status"]["text"] == "not read from the database for 30 s"
    assert dropped["db"]["connected"] is False
    assert dropped["feed"]["sources"]["db_feed"]["stale_s"] == pytest.approx(30)


def test_old_process_list_makes_the_feed_unknown_not_down():
    from pc_monitor.app import view
    old = {"data": [], "read_at": NOW - 90}
    p = view({"processes": old}, NOW)["feed"]["presence"]
    assert p["tone"] == "idle" and p["text"] == "unknown: processes not read for 90 s"


# ── log files: encodings and big files ──────────────────────────────────────

def test_log_text_sniffs_utf16_and_drops_a_partial_first_line(tmp_path):
    from pc_monitor.sources import read_text
    text = "".join(f"2026-11-21 13:{i:02d}:00,000 INFO line {i}\n" for i in range(60))
    u16 = tmp_path / "u16.log"
    u16.write_bytes(b"\xff\xfe" + text.encode("utf-16-le"))
    got, cut = read_text(u16)
    assert got == text and cut is False
    u8 = tmp_path / "u8.log"
    u8.write_bytes(text.encode("utf-8"))
    tail, cut = read_text(u8, max_bytes=200)
    assert cut is True
    assert tail.splitlines()[0].startswith("2026-11-21 13:")   # whole lines only
    assert tail.endswith("INFO line 59\n")
    tail16, _ = read_text(u16, max_bytes=301)                    # odd cut on UTF-16 stays aligned
    assert tail16.endswith("INFO line 59\n") and tail16.splitlines()[0].startswith("2026-11-21 13:")


def test_under_pythonw_output_goes_to_the_log_even_when_a_stream_is_handed_over(tmp_path, monkeypatch):
    """A pythonw started by a pythonw (the restart after an update) is handed a
    stdout whose reader is closed; its first print raised OSError and it died
    silently (2026-11-21). Under pythonw both streams must go to the log."""
    import io
    import sys
    import pc_monitor.__main__ as M
    import pc_monitor.sources as S
    monkeypatch.setattr(S, "LOG_DIR", tmp_path)
    monkeypatch.setattr(sys, "executable", r"C:\Python314\pythonw.exe")
    handed = io.StringIO()
    monkeypatch.setattr(sys, "stdout", handed)
    monkeypatch.setattr(sys, "stderr", handed)
    M._quiet_stdio()
    try:
        assert sys.stdout is not handed and sys.stderr is sys.stdout
        print("start pid 1", flush=True)
    finally:
        sys.stdout.close()
    assert "start pid 1" in next(tmp_path.glob("pc_monitor_*.log")).read_text(encoding="utf-8")
    # From a console, the console keeps its output.
    monkeypatch.setattr(sys, "executable", r"C:\Python314\python.exe")
    monkeypatch.setattr(sys, "stdout", handed)
    monkeypatch.setattr(sys, "stderr", handed)
    M._quiet_stdio()
    assert sys.stdout is handed


# ── guards ──────────────────────────────────────────────────────────────────

def test_constants_match_the_code_they_mirror():
    src = (ROOT / "models" / "ncaab_live_dk.py").read_text(encoding="utf-8")
    assert float(re.search(r"^FEED_MAX_AGE_SEC\s*=\s*([\d.]+)", src, re.M).group(1)) == R.FEED_MAX_AGE_SEC
    feed = (ROOT / "data" / "ingestors" / "dk_live_board.py").read_text(encoding="utf-8")
    idle = re.search(r'^IDLE_POLL_SEC\s*=\s*float\(os\.environ\.get\("DK_LIVE_IDLE_POLL_SEC",\s*"([\d.]+)"\)\)',
                     feed, re.M)
    assert float(idle.group(1)) == R.IDLE_POLL_SEC


def test_every_child_process_starts_without_a_window():
    """The app runs under pythonw; a child without CREATE_NO_WINDOW opens a
    console window on mike's screen every time it runs."""
    spawners = {"run", "Popen", "call", "check_call", "check_output"}
    found = 0
    for path in (ROOT / "pc_monitor").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                if f.value.id == "subprocess" and f.attr in spawners:
                    found += 1
                    assert any(k.arg == "creationflags" for k in node.keywords), \
                        f"{path.name}:{node.lineno} starts a process without creationflags"
                assert not (f.value.id == "os" and f.attr in ("system", "popen")), \
                    f"{path.name}:{node.lineno} uses os.{f.attr}, which opens a console"
    assert found >= 3   # hidden_run, the window, the relaunch: the guard is looking at real calls


# ── leagues DraftKings does not list, and every other book (2026-11-26) ─────

def test_feed_leagues_books_and_their_kinds_match_the_feed_code():
    from data.ingestors import book_live_boards as L
    from data.ingestors import dk_live_board as B
    assert R.FEED_LEAGUES == tuple(sorted(B.LEAGUES))
    assert R.NOT_LISTED == B.NOT_LISTED
    kinds = {b.key: ("home page" if b.discover else "parsed" if b.parse is not None else "captured")
             for b in L.BOOKS}
    assert R.BOOK_KINDS == kinds and list(R.BOOK_KINDS) == [b.key for b in L.BOOKS]
    assert set(R.BOOK_NAMES) == {"draftkings", *kinds}
    assert R.BOOK_POLL_SEC == L.POLL_SEC and R.BOOK_HOME_PAGE_SEC == L.DISCOVER_SEC


def test_a_league_draftkings_does_not_list_says_so():
    row = {"age_s": 12.0, "ok": True, "live_events": 0, "detail": R.NOT_LISTED + "; asked again every 10 min"}
    st = R.sport_status(row, True)
    assert st["tone"] == "idle" and "not listing this league" in st["text"]


def _procs():
    return {"data": [{"pid": 16256, "started_at": NOW - 8000, "role": "dk_feed", "label": "x",
                      "cmdline": FEED_CMD, "cpu_pct": 0.4, "mem_mb": 116.0}], "read_at": NOW}


def test_every_league_the_feed_reads_is_listed_with_or_without_a_row():
    from pc_monitor.app import view
    feed = {"data": [{"sport": "NBA", "age_s": 1.0, "ok": True, "live_events": 3, "matched": 3,
                      "detail": "", "db_now": NOW}], "read_at": NOW, "error": None}
    v = view({"db_feed": feed, "processes": _procs(), "db": {"data": {"connected": True}, "read_at": NOW}}, NOW)
    assert [s["sport"] for s in v["feed"]["sports"]] == list(R.FEED_LEAGUES)
    eu = next(s for s in v["feed"]["sports"] if s["sport"] == "EUROLEAGUE")
    assert eu["status"]["text"] == "never read"
    nba = next(s for s in v["feed"]["sports"] if s["sport"] == "NBA")
    assert nba["status"]["tone"] == "ok"


@pytest.mark.parametrize("row,kind,tone,words", [
    ({"age_s": 5.0, "ok": True, "live_events": 5, "matched": 5}, "parsed", "ok", "fresh"),
    ({"age_s": 5.0, "ok": True, "live_events": 5, "matched": 2}, "parsed", "warn", "3 of 5"),
    ({"age_s": 5.0, "ok": True, "live_events": 0, "matched": 0}, "parsed", "idle", "no live game"),
    ({"age_s": 400.0, "ok": True, "live_events": 5, "matched": 5}, "parsed", "idle", "not read lately"),
    ({"age_s": 5.0, "ok": False, "status": 403, "detail": "refused"}, "captured", "bad", "refused"),
    ({"age_s": 5.0, "ok": False, "status": 400, "detail": "HTTP 400"}, "captured", "bad", "HTTP 400"),
    ({"age_s": 5.0, "ok": True, "status": 200, "live_events": 0}, "captured", "idle", "answer stored"),
    ({"age_s": 5.0, "ok": True, "status": 200}, "home page", "idle", "home page stored"),
    ({"age_s": None}, "parsed", "idle", "never read"),
])
def test_each_books_last_read_in_words(row, kind, tone, words):
    st = R.book_status(row, kind)
    assert st["tone"] == tone and words in st["text"]


def test_live_lines_by_sportsbook_lists_draftkings_then_every_book_in_order():
    from pc_monitor.app import view
    feed = {"data": [{"sport": "NHL", "age_s": 1.0, "ok": True, "live_events": 6, "matched": 6,
                      "detail": "", "db_now": NOW}], "read_at": NOW, "error": None}
    books = {"data": [
        {"book": "williamhill_us", "sport": "NBA", "age_s": 4.0, "ok": False, "status": 403,
         "live_events": 0, "matched": 0, "written": 0, "detail": "refused"},
        {"book": "fanduel", "sport": "NHL", "age_s": 4.0, "ok": True, "status": 200,
         "live_events": 5, "matched": 5, "written": 15, "detail": ""},
        {"book": "hardrockbet", "sport": "*", "age_s": 4.0, "ok": True, "status": 200,
         "live_events": 0, "matched": 0, "written": 0, "detail": ""},
    ], "read_at": NOW, "error": None}
    v = view({"db_feed": feed, "db_books": books, "processes": _procs(),
              "db": {"data": {"connected": True}, "read_at": NOW}}, NOW)
    rows = v["books"]["rows"]
    assert [(r["book"], r["sport"]) for r in rows] == [
        ("draftkings", "NHL"), ("fanduel", "NHL"), ("williamhill_us", "NBA"), ("hardrockbet", "home page")]
    assert [r["status"]["tone"] for r in rows] == ["ok", "ok", "bad", "idle"]
    assert rows[1]["written"] == 15 and rows[1]["name"] == "FanDuel" and rows[2]["name"] == "Caesars"
    json.dumps(v)
    # The database gone: the last rows stay, judged unknown rather than late.
    old = view({"db_feed": feed, "db_books": {**books, "read_at": NOW - 60}, "processes": _procs(),
                "db": {"data": {"connected": True}, "read_at": NOW}}, NOW)
    fd = next(r for r in old["books"]["rows"] if r["book"] == "fanduel")
    assert fd["status"]["tone"] == "idle" and "not read from the database" in fd["status"]["text"]


def test_the_page_draws_the_sportsbook_section():
    page = (ROOT / "pc_monitor" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'id="books"' in page and "renderBooks(now, s.books)" in page


# ── the monitor follows master by itself (2026-11-26) ───────────────────────

def test_the_monitor_restarts_only_when_master_changed_its_files(monkeypatch):
    import pc_monitor.__main__ as M
    asked = []

    def git(*args):
        asked.append(args)
        return "pc_monitor/static/index.html\n" if args[0] == "diff" else ""
    assert M.changed_on_master(git) is False and asked == []          # not its own copy: never
    monkeypatch.setattr(M, "ROOT", Path("C:/Users/x/betting-model/.claude/feeds/pc-monitor"))
    assert M.changed_on_master(git) is True
    assert asked[0][:2] == ("fetch", "-q") and asked[1][:4] == ("diff", "--name-only", "HEAD", "origin/master")
    assert set(M.WATCH_PATHS) <= set(asked[1])
    assert M.changed_on_master(lambda *a: "") is False
    assert M.changed_on_master(lambda *a: None) is False               # git failed: never restart


def test_a_change_on_master_stops_the_server_for_a_restart():
    import pc_monitor.__main__ as M

    class Srv:
        stopped = False

        def shutdown(self):
            self.stopped = True
    srv, flag, answers = Srv(), {"restart": False}, iter([False, True])
    M.watch_master(srv, flag, every=0, check=lambda: next(answers), sleep=lambda s: None)
    assert flag["restart"] is True and srv.stopped is True
