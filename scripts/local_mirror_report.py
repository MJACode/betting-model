#!/usr/bin/env python
"""One row in Supabase about the copy on mike's PC, for the ops dashboard.

mike, 2026-11-16: the Database tab's PC copy section shows when the nightly
copy last ran and for how long, the tables that do not match Supabase, each
copy's size over time, and the free disk. This script writes the row it reads:
one row in public.pc_copy_snapshots each time it runs.

WHEN IT RUNS. Last in each pass of scripts/local_mirror_run.ps1 (the LocalMirror
task: 00:30 nightly, and two minutes after mike signs in), after every copy has
ended, with --source nightly, the pass's own stamp and each step's exit code.
By hand it runs with --source manual (the default) and no exit codes.

WHAT IT READS, all on this disk and nothing from the database:
  * supabase_mirror\\STATE.json: the last finished run of the Supabase copy (any
    run, a one-table run by hand included; the row says how many tables it
    covered). Written only when a run finishes, so a pass whose copy did not
    finish leaves the previous run's state, and the row says so
    (copy_this_pass false).
  * every supabase_mirror\\tables\\*\\manifest.json: rows on disk, and each
    table's latest exact-count check against Supabase. A table whose latest
    check counted a different number of rows is listed in differing_tables.
  * github\\_mirror_summary.json: when the GitHub copy last finished, and which
    repositories failed.
  * the size of everything under the root, split by copy, and the free disk.

WHAT IT WRITES. One INSERT, in one short transaction: no read of any other
table, no UPDATE, no DELETE. A nightly pass that is reported twice keeps its
first row (ON CONFLICT DO NOTHING on source and pass id). Rows are never
deleted (CLAUDE.md section 1b). The copy itself still never writes to the
database: scripts/local_mirror.py reads only.

SELF-CONTAINED. The task runs it as `python -I bin\\local_mirror_report.py`
from a copy outside the repo, so it imports nothing from the repo (isolated
mode does not put the script's folder on the import path either).

SECRETS. DATABASE_URL comes from the environment or, failing that, from the
main checkout's .env, read at run time. It is never printed; every message
that could hold it has database URLs removed.

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
import sys
import time
import traceback
from pathlib import Path
from typing import Any

UTC = dt.timezone.utc

DEFAULT_ROOT = Path(r"C:\Users\micha\Documents\betting_local_copies")
DEFAULT_ENV_FILE = Path(r"C:\Users\micha\documents\betting-model\.env")
STATEMENT_TIMEOUT_S = 30
CONNECT_TIMEOUT_S = 20
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
)
JSON_COLUMNS = frozenset({"failed_tables", "differing_tables"})

INSERT_SQL = (
    "INSERT INTO public.pc_copy_snapshots ("
    + ", ".join(COLUMNS)
    + ") VALUES ("
    + ", ".join("%s::jsonb" if c in JSON_COLUMNS else "%s" for c in COLUMNS)
    + ") ON CONFLICT (source, pass_id) DO NOTHING RETURNING snapshot_id"
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
    failed = sum(1 for r in repos
                 if not (isinstance(r, dict) and isinstance(r.get("git"), dict) and r["git"].get("ok")))
    return parse_iso(s.get("at")), len(repos), failed


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
    if pass_started is not None:
        this_pass = copy_finished is not None and copy_started is not None and copy_started >= pass_started
    else:
        this_pass = None
    failed = state.get("failed_tables")
    tables, rows, differing = read_tables(mirror)
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
    }
    row["report_ms"] = int((time.monotonic() - t0) * 1000)
    return row


def insert_row(conn, row: dict[str, Any]) -> int | None:
    """Write the row in one short transaction. The new snapshot_id, or None when
    this source and pass id already have a row (it is kept, not replaced)."""
    cur = conn.cursor()
    try:
        cur.execute(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT_S}s'")
        cur.execute("SET LOCAL idle_in_transaction_session_timeout = '30s'")
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


def _summary(row: dict[str, Any]) -> str:
    differing = json.loads(row["differing_tables"]) if row["differing_tables"] else []
    failed = json.loads(row["failed_tables"]) if row["failed_tables"] else []
    gb = 1e9
    return (f"pass {row['pass_id']} ({row['source']}); copy run {row['copy_run_id']} "
            f"{row['copy_started_at']} -> {row['copy_finished_at']}, {row['copy_tables']} table(s), "
            f"this pass: {row['copy_this_pass']}; {row['local_tables']} tables / {row['local_rows']:,} rows "
            f"on disk, {len(differing)} differing, {len(failed)} failed; "
            f"{row['total_bytes'] / gb:.2f} GB under the root "
            f"(tables {row['tables_bytes'] / gb:.2f}, GitHub {row['github_bytes'] / gb:.2f}); "
            f"disk free {(row['disk_free_bytes'] or 0) / gb:.1f} of {(row['disk_total_bytes'] or 0) / gb:.1f} GB; "
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
    ap.add_argument("--dry-run", action="store_true", help="print the row; write nothing")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    now = dt.datetime.now(UTC)
    if args.source == "nightly" and parse_stamp(args.pass_id) is None:
        print("--source nightly needs --pass-id as the pass's stamp (yyyymmddThhmmssZ)", flush=True)
        return 2
    pass_id = args.pass_id or now.strftime(STAMP_FORMAT)
    try:
        row = build_row(Path(args.root), source=args.source, pass_id=pass_id,
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
        conn = connect(url)
        try:
            snapshot_id = insert_row(conn, row)
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        print(f"no row written: {scrub(exc)}", flush=True)
        return 3
    if snapshot_id is None:
        print(f"pass {pass_id} ({args.source}) already has a row; kept it, wrote nothing", flush=True)
    else:
        print(f"wrote pc_copy_snapshots row {snapshot_id}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
