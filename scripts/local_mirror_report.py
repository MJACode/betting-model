#!/usr/bin/env python
"""One row in Supabase about the copy on mike's PC, for the ops dashboard.

mike, 2026-11-16: the Database tab's PC copy section shows when the nightly
copy last ran and for how long, the tables that do not match Supabase, each
copy's size over time, and the free disk. This script writes the row it reads:
one row in public.pc_copy_snapshots each time it runs.

WHEN IT RUNS. Last in each pass of scripts/local_mirror_run.ps1 (the LocalMirror
task: 00:30 Eastern nightly, and two minutes after mike signs in), after every
copy has ended, with --source nightly, the pass's own stamp and each step's
exit code. By hand it runs with --source manual (the default) and no exit codes.

And first in each pass, with --catch-up: on 2026-11-16 the runner ended about
nine hours in while its copy carried on, so that pass never reached its last
step. The catch-up writes such a pass's row at the start of the next pass,
when its copy did finish (see catch_up_row), with its exit codes unknown, and
only when no row yet records that copy run (a report run by hand after it
counts).

WHAT IT READS, all on this disk and nothing from the database:
  * supabase_mirror\\STATE.json: the last finished run of the Supabase copy (any
    run, a one-table run by hand included; the row says how many tables it
    covered). Written only when a run finishes, so a pass whose copy did not
    finish leaves the previous run's state, and the row says so
    (copy_this_pass false).
  * every supabase_mirror\\tables\\*\\manifest.json: rows on disk, and each
    table's latest exact-count check against Supabase. A table whose latest
    check counted a different number of rows is listed in differing_tables,
    unless the copy run left that table as it is (a cache, in a diff): its
    manifest still holds an older run's verdict, not this run's.
  * github\\_mirror_summary.json: when the GitHub copy last finished, and which
    repositories failed.
  * the size of everything under the root, split by copy, and the free disk.
  * the run's kind (diff, nightly; full, monthly) from STATE.json, and the
    schedule: the LocalMirror task as Task Scheduler holds it (its triggers,
    next and last run, last result), with the last monthly full
    (supabase_mirror\\LAST_FULL.json) and the date the next one is due from.

WHAT IT WRITES. One INSERT, in one short transaction: no read of any other
table, no UPDATE, no DELETE. A nightly pass that is reported twice keeps its
first row (ON CONFLICT DO NOTHING on source and pass id). The catch-up first
reads this table for its copy run, and writes nothing when a row has it
(COPY_RECORDED_SQL). Rows are never
deleted (CLAUDE.md section 1b). The copy itself still never writes to the
database: scripts/local_mirror.py reads only.

SELF-CONTAINED. The task runs it as `python -I bin\\local_mirror_report.py`
from a copy outside the repo, so it imports nothing from the repo (isolated
mode does not put the script's folder on the import path either).

SECRETS. DATABASE_URL comes from the environment or, failing that, from the
main checkout's .env, read at run time. It is never printed. A failed write
prints the error's kind (describe_failure), never the driver's message, which
names the host, port and user, and echoes a malformed address whole.

Usage:
  python local_mirror_report.py                       # one manual row
  python local_mirror_report.py --dry-run             # print the row, write nothing
  python local_mirror_report.py --source nightly --pass-id 20261117T053002Z \\
      --github-exit 0 --supabase-exit 0 --duckdb-exit 0
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
ET = ZoneInfo("America/New_York")
TASK_NAME = "LocalMirror"
TASK_PATH = "\\BettingModel\\"
TASK_READ_TIMEOUT_S = 60
KINDS = ("diff", "full")

DEFAULT_ROOT = Path(r"C:\Users\micha\Documents\betting_local_copies")
DEFAULT_ENV_FILE = Path(r"C:\Users\micha\documents\betting-model\.env")
STATEMENT_TIMEOUT_S = 30
CONNECT_TIMEOUT_S = 20
WRITE_ATTEMPTS = 3
RETRY_PAUSE_S = 30.0  # 30 s, then 60 s: under two minutes added to a pass
WHOLE_RUN_SHARE = 0.9  # a run covering this share of the tables on disk is a pass's copy
SOURCES = ("nightly", "manual")
STAMP_FORMAT = "%Y%m%dT%H%M%SZ"

# Where each byte under the root is counted. The first prefix that matches
# wins, so the longer paths come first. Everything else is "other": logs, bin,
# and the folders other jobs keep here.
SIZE_BUCKETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tables_bytes", ("supabase_mirror", "tables")),
    ("schema_bytes", ("supabase_mirror", "schema")),
    ("storage_bytes", ("supabase_mirror", "storage")),
    ("github_bytes", ("github",)),
    ("duckdb_bytes", ("betting.duckdb",)),
)

# The INSERT's columns, in order. tests/test_local_mirror_report.py holds this
# list against the migration, and build_row() must return exactly these keys.
COLUMNS: tuple[str, ...] = (
    "source", "pass_id", "host", "pass_started_at",
    "copy_run_id", "copy_started_at", "copy_finished_at", "copy_tables",
    "copy_rows_pulled", "copy_db_seconds", "copy_paused_seconds", "copy_this_pass",
    "failed_tables", "differing_tables",
    "github_exit", "supabase_exit", "duckdb_exit",
    "github_finished_at", "github_repos", "github_repos_failed",
    "local_tables", "local_rows",
    "tables_bytes", "schema_bytes", "storage_bytes", "github_bytes", "duckdb_bytes",
    "other_bytes", "total_bytes", "total_files",
    "disk_total_bytes", "disk_free_bytes", "report_ms",
    "copy_kind", "schedule",
)
JSON_COLUMNS = frozenset({"failed_tables", "differing_tables", "schedule"})

INSERT_SQL = (
    "INSERT INTO public.pc_copy_snapshots ("
    + ", ".join(COLUMNS)
    + ") VALUES ("
    + ", ".join("%s::jsonb" if c in JSON_COLUMNS else "%s" for c in COLUMNS)
    + ") ON CONFLICT (source, pass_id) DO NOTHING RETURNING snapshot_id"
)

# The catch-up's guard: a finished copy run that a row already records gets no
# second one. ON CONFLICT cannot see it, because a report run by hand carries
# its own stamp and source (2026-11-21: the 11-20 full was recorded by hand as
# row 10, and the next pass's catch-up recorded it again as row 11). Only the
# catch-up asks: a pass whose own copy did not finish legitimately reports the
# previous run again, with copy_this_pass false.
COPY_RECORDED_SQL = (
    "SELECT snapshot_id FROM public.pc_copy_snapshots "
    "WHERE copy_run_id = %s AND copy_finished_at IS NOT NULL ORDER BY snapshot_id LIMIT 1"
)

_URL_RE = re.compile(r"postgres(?:ql)?://[^\s'\"]+", re.IGNORECASE)


def scrub(text: Any) -> str:
    """Remove anything shaped like a database URL from text that will be printed."""
    return _URL_RE.sub("<database-url>", str(text))


def read_env_value(name: str, env_file: Path | None) -> str | None:
    """The variable from the process environment, else from a .env file.

    The same rule as scripts/local_mirror.py: read at run time, so a rotated
    password reaches the next run.
    """
    val = os.environ.get(name, "").strip()
    if val:
        return val
    if env_file is None or not Path(env_file).exists():
        return None
    with open(env_file, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip().rstrip("\r")
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            if key != name:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value or None
    return None


def parse_stamp(stamp: str | None) -> dt.datetime | None:
    """A pass stamp (20261116T054324Z) as a UTC time; None when it is not one."""
    if not stamp:
        return None
    try:
        return dt.datetime.strptime(stamp, STAMP_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_iso(text: Any) -> dt.datetime | None:
    """An ISO time from one of the copy's JSON files; None when absent or unreadable."""
    if not isinstance(text, str) or not text:
        return None
    try:
        t = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _load_json(path: Path) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def disk_sizes(root: Path) -> dict[str, int]:
    """Bytes under the root, split into SIZE_BUCKETS plus other, with totals.

    One walk with os.scandir; symbolic links are not followed. An entry that
    vanishes during the walk (the copy swaps files) is skipped.
    """
    out = {name: 0 for name, _ in SIZE_BUCKETS}
    out.update(other_bytes=0, total_bytes=0, total_files=0)
    stack: list[tuple[str, tuple[str, ...]]] = [(str(root), ())]
    while stack:
        path, rel = stack.pop()
        try:
            it = os.scandir(path)
        except OSError:
            continue
        with it:
            for entry in it:
                parts = rel + (entry.name,)
                try:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append((entry.path, parts))
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    size = entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
                bucket = "other_bytes"
                for name, prefix in SIZE_BUCKETS:
                    if parts[:len(prefix)] == prefix:
                        bucket = name
                        break
                out[bucket] += size
                out["total_bytes"] += size
                out["total_files"] += 1
    return out


def read_tables(mirror: Path) -> tuple[int, int, list[dict]]:
    """(tables on disk, rows on disk, tables whose latest check differs).

    A table differs when its manifest's latest exact-count check found a
    different number of rows in the copied key ranges than Supabase holds.
    Rows written after the copy (past its last key) are not a difference: the
    next run takes them.
    """
    tables = rows = 0
    differing: list[dict] = []
    for path in sorted((mirror / "tables").glob("*/manifest.json")):
        m = _load_json(path)
        if not isinstance(m, dict):
            continue
        tables += 1
        rows += _int(m.get("rows")) or 0
        lv = m.get("last_verify")
        if not isinstance(lv, dict):
            continue
        local = _int(lv.get("local_rows"))
        server = _int(lv.get("server_rows_in_copied_ranges"))
        if local is None or server is None or local == server:
            continue
        differing.append({
            "table": m.get("table") or path.parent.name,
            "local_rows": local,
            "supabase_rows": server,
            "ranges_differ": _int(lv.get("mismatched_chunks")),
            "ranges_not_counted": _int(lv.get("ranges_not_counted_timeout")),
            "checked_at": lv.get("at"),
        })
    return tables, rows, differing


def read_github(root: Path) -> tuple[dt.datetime | None, int | None, int | None]:
    """(when the GitHub copy last finished, repositories, repositories that failed)."""
    s = _load_json(root / "github" / "_mirror_summary.json")
    if not isinstance(s, dict):
        return None, None, None
    repos = s.get("repos") if isinstance(s.get("repos"), list) else []
    # A repository fails when its git copy failed, or when its issues and pull
    # requests could not be exported (2026-11-18 and 11-19: 2 of 4 stopped on a
    # cut-off read while git was fine, and this counted 0).
    failed = sum(1 for r in repos
                 if not (isinstance(r, dict) and isinstance(r.get("git"), dict) and r["git"].get("ok"))
                 or (isinstance(r, dict) and r.get("error")))
    return parse_iso(s.get("at")), len(repos), failed


# The task as Task Scheduler holds it, as one line of JSON. Times in UTC; a
# time Windows has not set (a task that never ran) reads as null.
_TASK_PS = r"""
$ErrorActionPreference = 'Stop'
$t = Get-ScheduledTask -TaskPath '{path}' -TaskName '{name}'
$i = $t | Get-ScheduledTaskInfo
function U($d) {{ if ($d -and $d.Year -gt 1999) {{ $d.ToUniversalTime().ToString('o') }} else {{ $null }} }}
[pscustomobject]@{{
  state = $t.State.ToString()
  next_run_at = U $i.NextRunTime
  last_run_at = U $i.LastRunTime
  last_result = $i.LastTaskResult
  triggers = @($t.Triggers | ForEach-Object {{ [pscustomobject]@{{
    type = $_.CimClass.CimClassName; start = $_.StartBoundary; delay = $_.Delay; enabled = $_.Enabled }} }})
}} | ConvertTo-Json -Depth 4 -Compress
"""

_TRIGGER_TYPES = {"MSFT_TaskDailyTrigger": "daily", "MSFT_TaskLogonTrigger": "sign-in",
                  "MSFT_TaskTimeTrigger": "once", "MSFT_TaskWeeklyTrigger": "weekly",
                  "MSFT_TaskBootTrigger": "start-up"}


def read_task(name: str = TASK_NAME, path: str = TASK_PATH) -> dict[str, Any]:
    """The LocalMirror task from Task Scheduler. Raises when it cannot be read."""
    out = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
         _TASK_PS.format(path=path, name=name)],
        capture_output=True, text=True, encoding="utf-8", timeout=TASK_READ_TIMEOUT_S)
    if out.returncode != 0:
        raise RuntimeError((out.stderr or out.stdout or "").strip().splitlines()[0][:200]
                           if (out.stderr or out.stdout).strip() else f"exit {out.returncode}")
    got = json.loads(out.stdout)
    return got if isinstance(got, dict) else {}


def _trigger(t: Any) -> dict[str, Any] | None:
    if not isinstance(t, dict):
        return None
    start = t.get("start") if isinstance(t.get("start"), str) else None
    m = re.search(r"T(\d{2}:\d{2})", start or "")
    out: dict[str, Any] = {"type": _TRIGGER_TYPES.get(t.get("type"), t.get("type")),
                           "enabled": t.get("enabled") if isinstance(t.get("enabled"), bool) else None}
    if out["type"] == "daily" and m:
        out["at"] = m.group(1)  # local clock time on the PC (Eastern)
    if isinstance(t.get("delay"), str) and t["delay"]:
        out["delay"] = t["delay"]  # ISO 8601, e.g. PT2M after sign-in
    return out


def next_full_from(last_full: dict | None) -> str | None:
    """The 1st (Eastern) of the month after the last full started, as a date;
    None when there has been none (the next pass runs it). The same rule as
    scripts/local_mirror.py choose_kind."""
    started = parse_iso((last_full or {}).get("run_started_at"))
    if started is None:
        return None
    e = started.astimezone(ET)
    y, mo = (e.year + 1, 1) if e.month == 12 else (e.year, e.month + 1)
    return dt.date(y, mo, 1).isoformat()


def read_schedule(mirror: Path, now: dt.datetime) -> dict[str, Any]:
    """The backup's schedule: the task's triggers, next and last run, and the
    monthly full. A task that cannot be read is recorded, not raised: the row
    is still written."""
    last_full = _load_json(mirror / "LAST_FULL.json")
    last_full = last_full if isinstance(last_full, dict) else None
    out: dict[str, Any] = {
        "task": TASK_PATH + TASK_NAME, "read_at": now.astimezone(UTC).isoformat(timespec="seconds"),
        "diff": "every pass except the month's full", "full": "the first pass on or after the 1st of each month",
        "last_full": None if last_full is None else {
            k: last_full.get(k) for k in ("run_id", "run_started_at", "run_finished_at", "failed_tables")},
        "next_full_from": next_full_from(last_full),
    }
    try:
        task = read_task()
    except Exception as exc:  # noqa: BLE001 - recorded, never fatal
        out["error"] = scrub(exc)[:300]
        return out
    out.update({
        "state": task.get("state") if isinstance(task.get("state"), str) else None,
        "next_run_at": task.get("next_run_at") if isinstance(task.get("next_run_at"), str) else None,
        "last_run_at": task.get("last_run_at") if isinstance(task.get("last_run_at"), str) else None,
        "last_result": _int(task.get("last_result")),
        "triggers": [t for t in (_trigger(x) for x in (task.get("triggers") or [])) if t],
    })
    return out


def is_whole_run(run_tables: int | None, tables_on_disk: int) -> bool:
    """True when a copy run covered (nearly) every table, so it is a pass's
    copy and not a run by hand with --only. Not equality: tables come and go
    between runs (the last whole run covered 311 tables while 316 were on disk
    the next day, 2026-11-16)."""
    return run_tables is not None and tables_on_disk > 0 and run_tables >= WHOLE_RUN_SHARE * tables_on_disk


def catch_up_row(root: Path, *, before: str, host: str | None, now: dt.datetime,
                 started_monotonic: float | None = None) -> tuple[dict[str, Any] | None, str]:
    """The row a pass would have written, for the pass before `before`, when its
    runner stopped before its last step but its copy carried on and finished
    (2026-11-16: the runner ended at about nine hours, the copy kept running).

    Written only when STATE.json shows a whole-table run that started after
    that pass's stamp and before this pass, and finished. Its exit codes are
    unknown, so they are left empty. If that copy never finished, nothing is
    written, and the dashboard's no-report rule shows the missing night. A pass
    that did report keeps its row: the insert adds nothing (ON CONFLICT DO
    NOTHING). Returns (row or None, why)."""
    this_start = parse_stamp(before)
    if this_start is None:
        return None, f"--before {before!r} is not a pass stamp"
    stamps = sorted(s for s in (_stamp_of(p.name) for p in (root / "logs").glob("supabase_*.log"))
                    if s is not None and parse_stamp(s) < this_start)
    if not stamps:
        return None, "no earlier pass in logs"
    prev = stamps[-1]
    prev_start = parse_stamp(prev)
    state = _load_json(root / "supabase_mirror" / "STATE.json")
    state = state if isinstance(state, dict) else {}
    started = parse_iso(state.get("run_started_at"))
    finished = parse_iso(state.get("run_finished_at"))
    tables, _, _ = read_tables(root / "supabase_mirror")
    if started is None or finished is None or not (prev_start <= started < this_start):
        return None, f"no copy run that started during pass {prev} has finished"
    if not is_whole_run(_int(state.get("tables")), tables):
        return None, f"the last finished run covered {state.get('tables')} of {tables} tables, not a pass's copy"
    row = build_row(root, source="nightly", pass_id=prev, host=host,
                    exits={"github": None, "supabase": None, "duckdb": None}, now=now,
                    started_monotonic=started_monotonic)
    # Not "it has no report of its own": nothing here looks for one. That said
    # so every night, above the line saying its row was already there
    # (2026-11-22). The write below finds out, and the next line says which.
    return row, f"pass {prev}: its copy finished at {finished.isoformat()}; its row is written unless one already records it"


def _stamp_of(name: str) -> str | None:
    """The pass stamp in a log name such as supabase_20261116T054324Z.log."""
    m = re.fullmatch(r"supabase_(\d{8}T\d{6}Z)\.log", name)
    return m.group(1) if m and parse_stamp(m.group(1)) else None


def build_row(root: Path, *, source: str, pass_id: str, host: str | None,
              exits: dict[str, int | None], now: dt.datetime,
              started_monotonic: float | None = None) -> dict[str, Any]:
    """Every column of one pc_copy_snapshots row, read from the disk only."""
    t0 = time.monotonic() if started_monotonic is None else started_monotonic
    mirror = root / "supabase_mirror"
    pass_started = parse_stamp(pass_id) if source == "nightly" else None
    state = _load_json(mirror / "STATE.json")
    state = state if isinstance(state, dict) else {}
    copy_started = parse_iso(state.get("run_started_at"))
    copy_finished = parse_iso(state.get("run_finished_at"))
    failed = state.get("failed_tables")
    tables, rows, differing = read_tables(mirror)
    # A table this copy run left as it is (a cache, in a diff) was not checked
    # by it: its manifest still holds the last full's verdict. Listing it would
    # repeat that verdict every night to the next full (2026-11-21:
    # latest_prop_odds, which changed while the 11-20 full copied it).
    skipped = state.get("skipped_tables")
    skipped = {str(t) for t in skipped} if isinstance(skipped, list) else set()
    differing = [d for d in differing if d["table"] not in skipped]
    if pass_started is not None:
        # The pass's own copy: a run that finished, started after the pass did,
        # and covered the whole table list. A one-table run by hand rewrites
        # STATE.json too, and must not pass for the night's copy.
        this_pass = (copy_finished is not None and copy_started is not None
                     and copy_started >= pass_started
                     and is_whole_run(_int(state.get("tables")), tables))
    else:
        this_pass = None
    gh_at, gh_repos, gh_failed = read_github(root)
    sizes = disk_sizes(root)
    try:
        usage = shutil.disk_usage(root)
        disk_total, disk_free = usage.total, usage.free
    except OSError:
        disk_total = disk_free = None
    row: dict[str, Any] = {
        "source": source,
        "pass_id": pass_id,
        "host": host,
        "pass_started_at": pass_started,
        "copy_run_id": state.get("run_id") if isinstance(state.get("run_id"), str) else None,
        "copy_started_at": copy_started,
        "copy_finished_at": copy_finished,
        "copy_tables": _int(state.get("tables")),
        "copy_rows_pulled": _int(state.get("rows_pulled")),
        "copy_db_seconds": _int(state.get("db_seconds")),
        "copy_paused_seconds": _int(state.get("paused_seconds")),
        "copy_this_pass": this_pass,
        "failed_tables": json.dumps(sorted(str(t) for t in failed)) if isinstance(failed, list) else None,
        "differing_tables": json.dumps(differing),
        "github_exit": exits.get("github"),
        "supabase_exit": exits.get("supabase"),
        "duckdb_exit": exits.get("duckdb"),
        "github_finished_at": gh_at,
        "github_repos": gh_repos,
        "github_repos_failed": gh_failed,
        "local_tables": tables,
        "local_rows": rows,
        **{name: sizes[name] for name, _ in SIZE_BUCKETS},
        "other_bytes": sizes["other_bytes"],
        "total_bytes": sizes["total_bytes"],
        "total_files": sizes["total_files"],
        "disk_total_bytes": disk_total,
        "disk_free_bytes": disk_free,
        "report_ms": None,
        "copy_kind": state.get("kind") if state.get("kind") in KINDS else None,
        "schedule": json.dumps(read_schedule(mirror, now)),
    }
    row["report_ms"] = int((time.monotonic() - t0) * 1000)
    return row


def insert_row(conn, row: dict[str, Any], *, unless_copy_recorded: bool = False) -> int | None:
    """Write the row in one short transaction. The new snapshot_id, or None when
    this source and pass id already have a row (it is kept, not replaced), or,
    with unless_copy_recorded (the catch-up), when a row already records the
    row's finished copy run."""
    cur = conn.cursor()
    try:
        cur.execute(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT_S}s'")
        cur.execute("SET LOCAL idle_in_transaction_session_timeout = '30s'")
        if unless_copy_recorded and row.get("copy_run_id"):
            cur.execute(COPY_RECORDED_SQL, [row["copy_run_id"]])
            if cur.fetchone() is not None:
                conn.rollback()
                return None
        cur.execute(INSERT_SQL, [row[c] for c in COLUMNS])
        got = cur.fetchone()
        conn.commit()
        return got[0] if got else None
    except BaseException:
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        try:
            cur.close()
        except Exception:  # noqa: BLE001
            pass


def _transaction_endpoint(url: str) -> str:
    # The same rewrite as data/db.py and scripts/local_mirror.py: Supabase's
    # session pooler (5432) hands each client its own server connection; 6543
    # shares them.
    if "pooler.supabase.com" in url and ":5432" in url:
        return url.replace(":5432", ":6543", 1)
    return url


def connect(url: str):
    import psycopg2
    conn = psycopg2.connect(_transaction_endpoint(url), connect_timeout=CONNECT_TIMEOUT_S)
    conn.autocommit = False
    return conn


def _is_connection_error(exc: BaseException) -> bool:
    """A failure to reach the database or a dropped connection, worth one more
    try. A wrong statement or a refused value is not: trying again changes
    nothing."""
    try:
        import psycopg2
    except ImportError:
        return False
    return isinstance(exc, (psycopg2.OperationalError, psycopg2.InterfaceError))


def describe_failure(exc: BaseException) -> str:
    """What went wrong with a write, in words that carry no part of the address.

    Never the driver's own message: it names the database's host, port and
    user, and a malformed DATABASE_URL comes back whole, password included
    (measured 2026-11-16 with 'postgresql+psycopg2://', 'postgresql:/' and
    'postgres//' forms). The kind is read from the message and replaced by a
    fixed phrase; the class and Postgres's error code are kept."""
    text = str(exc).lower()
    kinds = (  # every word in the first part must appear
        (("invalid dsn",), "DATABASE_URL is not a valid address"),
        (("missing \"=\"",), "DATABASE_URL is not a valid address"),
        (("password authentication failed",), "the password was refused"),
        (("relation", "does not exist"), "the table is not in the database yet"),
        (("role", "does not exist"), "the user named in DATABASE_URL does not exist"),
        (("database", "does not exist"), "the database named in DATABASE_URL does not exist"),
        (("could not translate host name",), "the host name could not be found"),
        (("connection refused",), "the server refused the connection"),
        (("timeout expired",), "the connection timed out"),
        (("timed out",), "the connection timed out"),
        (("server closed the connection",), "the server closed the connection"),
        (("ssl",), "the SSL connection failed"),
    )
    kind = next((phrase for needles, phrase in kinds if all(n in text for n in needles)), "no detail kept")
    code = getattr(exc, "pgcode", None)
    return f"{type(exc).__name__}: {kind}" + (f" (Postgres error {code})" if code else "")


def write_with_retries(url: str, row: dict[str, Any], *, attempts: int = WRITE_ATTEMPTS,
                       pause_s: float = RETRY_PAUSE_S, sleep=None,
                       unless_copy_recorded: bool = False) -> int | None:
    """insert_row on a fresh connection, tried again after a connection error.

    The nightly report runs once per pass, so a database that cannot be reached
    for a minute would otherwise lose that night's row. Trying again is safe:
    if a commit landed but its answer was lost, the next try finds the row and
    keeps it (ON CONFLICT DO NOTHING) and returns None."""
    for attempt in range(1, attempts + 1):
        try:
            conn = connect(url)
            try:
                return insert_row(conn, row, unless_copy_recorded=unless_copy_recorded)
            finally:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
        except Exception as exc:  # noqa: BLE001
            if attempt == attempts or not _is_connection_error(exc):
                raise
            print(f"write attempt {attempt} of {attempts} could not reach the database "
                  f"({describe_failure(exc)}); trying again in {pause_s * attempt:.0f} s", flush=True)
            # Looked up on each try, not bound as a default, so a test can patch it.
            (sleep or time.sleep)(pause_s * attempt)
    return None


def _summary(row: dict[str, Any]) -> str:
    differing = json.loads(row["differing_tables"]) if row["differing_tables"] else []
    failed = json.loads(row["failed_tables"]) if row["failed_tables"] else []
    sched = json.loads(row["schedule"]) if row.get("schedule") else {}
    gb = 1e9
    return (f"pass {row['pass_id']} ({row['source']}); copy run {row['copy_run_id']} "
            f"{row['copy_started_at']} -> {row['copy_finished_at']}, {row['copy_tables']} table(s), "
            f"this pass: {row['copy_this_pass']}; {row['local_tables']} tables / {row['local_rows']:,} rows "
            f"on disk, {len(differing)} differing, {len(failed)} failed; "
            f"{row['total_bytes'] / gb:.2f} GB under the root "
            f"(tables {row['tables_bytes'] / gb:.2f}, GitHub {row['github_bytes'] / gb:.2f}); "
            f"disk free {(row['disk_free_bytes'] or 0) / gb:.1f} of {(row['disk_total_bytes'] or 0) / gb:.1f} GB; "
            f"kind {row['copy_kind']}; next task run {sched.get('next_run_at')}, "
            f"next full from {sched.get('next_full_from') or 'the next pass'}"
            f"{'; task not read: ' + sched['error'] if sched.get('error') else ''}; "
            f"read in {row['report_ms']} ms")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    ap.add_argument("--source", choices=SOURCES, default="manual")
    ap.add_argument("--pass-id", default=None,
                    help="the runner pass's stamp, e.g. 20261117T053002Z (required with --source nightly)")
    ap.add_argument("--github-exit", type=int, default=None)
    ap.add_argument("--supabase-exit", type=int, default=None)
    ap.add_argument("--duckdb-exit", type=int, default=None)
    ap.add_argument("--catch-up", action="store_true",
                    help="at the start of a pass: write the previous pass's row if its runner stopped "
                         "before reporting but its copy finished")
    ap.add_argument("--before", default=None, help="with --catch-up: this pass's stamp")
    ap.add_argument("--dry-run", action="store_true", help="print the row; write nothing")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    now = dt.datetime.now(UTC)
    root = Path(args.root)
    if args.catch_up:
        try:
            row, why = catch_up_row(root, before=args.before or "", host=socket.gethostname() or None,
                                    now=now, started_monotonic=t0)
        except Exception as exc:  # noqa: BLE001
            print(f"{now.isoformat()} catch-up could not read the copy: {scrub(exc)}", flush=True)
            return 3
        print(f"{now.isoformat()} catch-up: {why}", flush=True)
        if row is None:
            return 0
        pass_id = row["pass_id"]
    else:
        if args.source == "nightly" and parse_stamp(args.pass_id) is None:
            print("--source nightly needs --pass-id as the pass's stamp (yyyymmddThhmmssZ)", flush=True)
            return 2
        pass_id = args.pass_id or now.strftime(STAMP_FORMAT)
        try:
            row = build_row(root, source=args.source, pass_id=pass_id,
                            host=socket.gethostname() or None,
                            exits={"github": args.github_exit, "supabase": args.supabase_exit,
                                   "duckdb": args.duckdb_exit},
                            now=now, started_monotonic=t0)
        except Exception as exc:  # noqa: BLE001
            print(f"{now.isoformat()} could not read the copy: {scrub(exc)}\n{scrub(traceback.format_exc())}",
                  flush=True)
            return 3
    print(f"{now.isoformat()} {_summary(row)}", flush=True)
    if args.dry_run:
        print(json.dumps(row, default=str, indent=1), flush=True)
        return 0
    url = read_env_value("DATABASE_URL", Path(args.env_file) if args.env_file else None)
    if not url:
        print("DATABASE_URL is not set and is not in the env file; no row written", flush=True)
        return 2
    try:
        snapshot_id = write_with_retries(url, row, unless_copy_recorded=args.catch_up)
    except Exception as exc:  # noqa: BLE001
        print(f"no row written: {describe_failure(exc)}", flush=True)
        return 3
    if snapshot_id is None and args.catch_up:
        print(f"pass {pass_id}: it, or its copy run {row['copy_run_id']}, already has a row; "
              f"kept it, wrote nothing", flush=True)
    elif snapshot_id is None:
        print(f"pass {pass_id} ({row['source']}) already has a row; kept it, wrote nothing", flush=True)
    else:
        print(f"wrote pc_copy_snapshots row {snapshot_id}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
