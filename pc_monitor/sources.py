"""What the This PC window reads from the machine.

Task Scheduler, the running processes, the jobs' log files, the backup's status
files and a few small database tables. Each reader is called from the collector
in app.py inside its own try/except, so one broken source shows as an error on
its own panel and never blanks the others.

NO CONSOLE WINDOWS. The app runs under pythonw. Every child process it starts
goes through `hidden_run`, which passes CREATE_NO_WINDOW and closes stdin;
tests/test_pc_monitor.py fails on any other subprocess call in this package.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

CREATE_NO_WINDOW = 0x08000000

COPIES = Path(os.environ.get("PC_MONITOR_COPIES") or Path.home() / "Documents" / "betting_local_copies")
LOG_DIR = COPIES / "logs"
MIRROR = COPIES / "supabase_mirror"
TASK_FOLDER = "\\BettingModel\\"
PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def hidden_run(argv: list[str], timeout: float, **kw: Any) -> subprocess.CompletedProcess:
    """Run a child with no window and no stdin, capturing its output."""
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, stdin=subprocess.DEVNULL,
                          creationflags=CREATE_NO_WINDOW, **kw)


# ── Task Scheduler ──────────────────────────────────────────────────────────

_TASKS_PS = r"""
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
function U($d) { if ($d -and $d.Year -gt 1999) { $d.ToUniversalTime().ToString('o') } else { $null } }
$out = @(Get-ScheduledTask -TaskPath '__FOLDER__' | ForEach-Object {
  $i = $_ | Get-ScheduledTaskInfo
  [pscustomobject]@{
    name = $_.TaskName
    state = $_.State.ToString()
    last_run_at = U $i.LastRunTime
    next_run_at = U $i.NextRunTime
    last_result = $i.LastTaskResult
    action = (@($_.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join ' || ')
    triggers = @($_.Triggers | ForEach-Object { [pscustomobject]@{
      type = $_.CimClass.CimClassName; start = $_.StartBoundary; delay = $_.Delay
      enabled = $_.Enabled; interval = $_.Repetition.Interval; duration = $_.Repetition.Duration } })
  } })
ConvertTo-Json -InputObject $out -Depth 4 -Compress
"""


def read_tasks(folder: str = TASK_FOLDER) -> str:
    """Every task in the folder as JSON text, from one hidden PowerShell call."""
    out = hidden_run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                      "-Command", _TASKS_PS.replace("__FOLDER__", folder)], timeout=40)
    if out.returncode != 0:
        first = (out.stderr or out.stdout or "").strip().splitlines()
        raise RuntimeError(first[0][:200] if first else f"exit {out.returncode}")
    return out.stdout


# ── processes ───────────────────────────────────────────────────────────────

def _label(name: str, cmdline: list[str]) -> str:
    """A short, readable name for a process: the module, script or file it runs."""
    low = (name or "").lower()
    args = list(cmdline or [])[1:]
    if low.startswith("python") or low.startswith("pyw"):
        if "-m" in args and args.index("-m") + 1 < len(args):
            return f"{name} -m {args[args.index('-m') + 1]}"
        for a in args:
            if not a.startswith("-"):
                return f"{name} {Path(a).name}"
    if low.startswith("powershell") or low.startswith("pwsh"):
        for i, a in enumerate(args):
            if a.lower() == "-file" and i + 1 < len(args):
                return f"{name} {Path(args[i + 1]).name}"
    return name or "?"


class ProcessTable:
    """The project's processes, with CPU and memory.

    Discovery reads every process's command line, so it runs every few seconds;
    the per-second numbers come from the psutil.Process objects kept between
    samples (CPU% is measured since the previous call on the same object, so a
    fresh object always reads 0)."""

    def __init__(self) -> None:
        import psutil  # imported here: the module must stay importable without it
        self._psutil = psutil
        self._kept: dict[tuple[int, float], Any] = {}
        self._meta: dict[tuple[int, float], dict[str, Any]] = {}
        self._cpus = psutil.cpu_count() or 1

    def discover(self, scripts: list[str]) -> None:
        from pc_monitor.readers import is_dk_feed, runs_script
        ps = self._psutil
        roots: dict[tuple[int, float], dict[str, Any]] = {}
        for p in ps.process_iter(["pid", "name", "cmdline", "create_time"]):
            try:
                info = p.info
                cmd = info.get("cmdline") or []
                name = info.get("name") or ""
                role = None
                if is_dk_feed(name, cmd):
                    role = "dk_feed"
                else:
                    for s in scripts:
                        if name.lower().startswith(("powershell", "pwsh")) and runs_script(cmd, s):
                            role = "launcher:" + s
                            break
                if role:
                    roots[(info["pid"], info["create_time"])] = {"proc": p, "role": role, "cmd": cmd, "name": name}
            except (ps.NoSuchProcess, ps.AccessDenied, ps.ZombieProcess):
                continue
        found: dict[tuple[int, float], dict[str, Any]] = {}
        for key, r in roots.items():
            found[key] = r
            if r["role"].startswith("launcher:"):
                try:
                    for c in r["proc"].children(recursive=True):
                        try:
                            if (c.name() or "").lower() == "conhost.exe":
                                continue  # the hidden console host every console program gets
                            ck = (c.pid, c.create_time())
                            if ck not in roots:
                                found[ck] = {"proc": c, "role": "child:" + r["role"][9:],
                                             "cmd": c.cmdline(), "name": c.name()}
                        except (ps.NoSuchProcess, ps.AccessDenied, ps.ZombieProcess):
                            continue
                except (ps.NoSuchProcess, ps.AccessDenied):
                    pass
        for key, r in found.items():
            if key not in self._kept:
                self._kept[key] = r["proc"]
                try:
                    r["proc"].cpu_percent(None)  # start the CPU clock for this object
                except (ps.NoSuchProcess, ps.AccessDenied):
                    pass
            self._meta[key] = {"role": r["role"], "name": r["name"], "cmd": r["cmd"],
                               "label": _label(r["name"], r["cmd"])}
        for key in list(self._kept):
            if key not in found:
                self._kept.pop(key, None)
                self._meta.pop(key, None)

    def sample(self) -> list[dict[str, Any]]:
        ps = self._psutil
        out = []
        for key, p in list(self._kept.items()):
            meta = self._meta.get(key, {})
            try:
                with p.oneshot():
                    cpu = p.cpu_percent(None) / self._cpus
                    mem = p.memory_info().rss / 1048576
                    if not p.is_running():
                        raise ps.NoSuchProcess(key[0])
            except (ps.NoSuchProcess, ps.ZombieProcess):
                self._kept.pop(key, None)
                self._meta.pop(key, None)
                continue
            except ps.AccessDenied:
                cpu, mem = None, None
            out.append({"pid": key[0], "started_at": key[1], "role": meta.get("role"),
                        "label": meta.get("label"), "cmdline": meta.get("cmd"),
                        "cpu_pct": cpu, "mem_mb": mem})
        return sorted(out, key=lambda r: (str(r["role"]), r["started_at"]))


# ── files ───────────────────────────────────────────────────────────────────

def newest(folder: Path, pattern: str) -> Path | None:
    """The most recently written file matching the pattern. By write time, not
    by the date in its name: a job started before midnight keeps writing
    yesterday's file."""
    try:
        files = [p for p in folder.glob(pattern) if p.is_file()]
    except OSError:
        return None
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def _decode(data: bytes, head: bytes) -> str:
    if head.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16-le" if head.startswith(b"\xff\xfe") else "utf-16-be", errors="replace")
        return text.lstrip("﻿")  # the mark is not part of the first line
    if head.startswith(b"\xef\xbb\xbf"):
        data = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
    # UTF-16 written without a mark: every other byte of ASCII text is zero.
    sample = data[:2000]
    if len(sample) > 20 and sample[1::2].count(0) > len(sample) // 4:
        return data.decode("utf-16-le", errors="replace")
    return data.decode("utf-8", errors="replace")


def read_text(path: Path, max_bytes: int = 2_000_000) -> tuple[str, bool]:
    """A log file's text, sniffing its encoding (UTF-16 has happened here).
    For a big file only the end is read; the second value says so, and the first
    partial line is dropped."""
    with open(path, "rb") as fh:
        head = fh.read(4)
        size = fh.seek(0, os.SEEK_END)
        start = max(0, size - max_bytes)
        if head.startswith((b"\xff\xfe", b"\xfe\xff")) and start % 2:
            start += 1
        fh.seek(start)
        data = fh.read()
    text = _decode(data, head)
    if start > 0:
        text = text.split("\n", 1)[1] if "\n" in text else ""
    return text, start > 0


def file_info(path: Path) -> dict[str, Any] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return {"path": str(path), "size": st.st_size, "mtime": st.st_mtime}


def tail_lines(path: Path, n: int = 6) -> list[str]:
    text, _ = read_text(path, max_bytes=20_000)
    return [ln for ln in text.splitlines() if ln.strip()][-n:]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def backup_files() -> dict[str, Any]:
    """The newest backup pass's log files, the copy's progress and state files,
    and how many tables the running copy has finished."""
    from pc_monitor.readers import newest_pass
    try:
        names = [p.name for p in LOG_DIR.iterdir()]
    except OSError:
        names = []
    pid = newest_pass(names)
    files: dict[str, dict[str, Any]] = {}
    errors = []
    if pid:
        for stage in ("fetch", "bin_refresh", "catchup", "github", "supabase", "duckdb", "report"):
            for ext in ("log", "err"):
                info = file_info(LOG_DIR / f"{stage}_{pid}.{ext}")
                if info:
                    files[f"{stage}.{ext}"] = info
                    if ext == "err" and info["size"] > 0:
                        errors.append({"file": f"{stage}_{pid}.err",
                                       "lines": tail_lines(LOG_DIR / f"{stage}_{pid}.err")})
    report_text = None
    if "report.log" in files and files["report.log"]["size"] > 0:
        report_text, _ = read_text(LOG_DIR / f"report_{pid}.log", max_bytes=20_000)
    elif (last := newest(LOG_DIR, "report_*.log")) is not None:
        report_text, _ = read_text(last, max_bytes=20_000)
    progress_info = file_info(MIRROR / "progress.json")
    inventory = load_json(MIRROR / "tables_inventory.json")
    total = None
    if isinstance(inventory, list):
        total = len(inventory)
    elif isinstance(inventory, dict):
        tables = inventory.get("tables")
        total = len(tables) if isinstance(tables, (list, dict)) else None
    return {"pass_id": pid, "files": files, "errors": errors, "report_text": report_text,
            "progress": load_json(MIRROR / "progress.json"),
            "progress_mtime": progress_info["mtime"] if progress_info else None,
            "state": load_json(MIRROR / "STATE.json"), "tables_total": total}


def tables_done_since(since: float | None) -> int | None:
    """How many tables' manifest.json the copy has rewritten since `since`."""
    if since is None:
        return None
    n = 0
    try:
        for d in (MIRROR / "tables").iterdir():
            try:
                if (d / "manifest.json").stat().st_mtime >= since:
                    n += 1
            except OSError:
                continue
    except OSError:
        return None
    return n


def stderr_files(patterns: list[str], since: float) -> list[dict[str, Any]]:
    """Non-empty stderr / git logs of the jobs written since `since`."""
    out = []
    for pat in patterns:
        p = newest(LOG_DIR, pat)
        info = file_info(p) if p else None
        if info and info["size"] > 0 and info["mtime"] >= since:
            out.append({"file": p.name, "mtime": info["mtime"], "lines": tail_lines(p)})
    return out


# ── database ────────────────────────────────────────────────────────────────

def find_database_url() -> str | None:
    """DATABASE_URL from the environment, else from the main checkout's .env,
    found by walking up from this package (the shortcut's copy lives in
    .claude/feeds/, under the main checkout). The value is never logged."""
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    from dotenv import dotenv_values
    for d in [PACKAGE_ROOT, *PACKAGE_ROOT.parents]:
        env = d / ".env"
        if env.is_file():
            url = (dotenv_values(env) or {}).get("DATABASE_URL")
            if url:
                return url
    return None


class Database:
    """One connection, on the collector's database thread only.

    It goes through data.db.get_connection, which moves a Supabase pooler
    address to the transaction port, and every read is ended at once with
    release_read so nothing sits idle in a transaction. Errors are reported by
    type only: a connection error's message can carry the address."""

    def __init__(self) -> None:
        self.conn = None

    def connect(self) -> None:
        url = find_database_url()
        if not url:
            raise RuntimeError("no DATABASE_URL in the environment or the main checkout's .env")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("DB_STATEMENT_TIMEOUT_MS", "5000")
        os.environ.setdefault("PGCONNECT_TIMEOUT", "10")
        from data.db import get_connection, use_poller_session
        use_poller_session()
        self.conn = get_connection()

    def rows(self, sql: str, params: Any = None) -> list[tuple]:
        from data.db import release_read
        if self.conn is None:
            self.connect()
        try:
            return self.conn.execute(sql, params).fetchall()
        except Exception:
            self.close()
            raise
        finally:
            release_read(self.conn)

    def write(self, sql: str, params: Any = None) -> list[tuple]:
        """One statement that changes a row, committed at once (release_read
        leaves uncommitted writes alone, and the idle-in-transaction limit
        would end the session). Returns the rows of a RETURNING clause."""
        if self.conn is None:
            self.connect()
        try:
            cur = self.conn.execute(sql, params)
            rows = cur.fetchall() if re.search(r"\breturning\b", sql, re.IGNORECASE) else []
            self.conn.commit()
            return rows
        except Exception:
            try:
                self.conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            self.close()
            raise

    def close(self) -> None:
        try:
            if self.conn is not None:
                self.conn.close()
        except Exception:  # noqa: BLE001
            pass
        self.conn = None


SQL_FEED = """
SELECT sport, CAST(EXTRACT(EPOCH FROM (now() - last_read_at)) AS double precision) AS age_s,
       ok, live_events, matched, detail,
       CAST(EXTRACT(EPOCH FROM now()) AS double precision) AS db_now
FROM dk_live_feed ORDER BY sport
"""

# Index-only scan on dk_live_reads_sport_read_idx (measured 2026-11-21: 14 ms
# for 3,002 rows). The sport list keeps the index's leading column bound.
SQL_MINUTES = """
SELECT sport, CAST(FLOOR(EXTRACT(EPOCH FROM (now() - read_at)) / 60) AS integer) AS ago_min, count(*)
FROM dk_live_reads
WHERE sport = ANY(%s) AND read_at > now() - interval '60 minutes'
GROUP BY 1, 2
"""

# Index-only scan on idx_tennis_pinnacle_prices_seen (3 ms on 2026-11-21).
SQL_TENNIS = """
SELECT count(*), CAST(EXTRACT(EPOCH FROM max(seen_at)) AS double precision)
FROM tennis_pinnacle_prices WHERE seen_at > now() - interval '60 minutes'
"""

SQL_BACKUP = """
SELECT snapshot_id, CAST(EXTRACT(EPOCH FROM taken_at) AS double precision), pass_id, copy_kind,
       copy_rows_pulled, local_tables, local_rows
FROM pc_copy_snapshots ORDER BY snapshot_id DESC LIMIT 1
"""


# The phone link (data/migrations/pc_monitor_state_2026_11_21.sql). The row is
# made once with a fresh token; later starts keep the token, so a link saved on
# the phone keeps working.
SQL_PHONE_ROW = """
INSERT INTO pc_monitor_state (host, phone_token) VALUES (%s, %s)
ON CONFLICT (host) DO UPDATE SET host = EXCLUDED.host
RETURNING phone_token
"""

SQL_DEMAND = """
SELECT CAST(EXTRACT(EPOCH FROM (now() - demand_at)) AS double precision)
FROM pc_monitor_state WHERE host = %s
"""

SQL_PUBLISH = """
UPDATE pc_monitor_state SET view = CAST(%s AS jsonb), published_at = now() WHERE host = %s
"""

# The cloud monitor serves the phone page from here (monitoring/server.py /pc/).
PUBLIC_BASE = os.environ.get("PC_MONITOR_PUBLIC_URL", "https://worker-production-229d.up.railway.app")


def now() -> float:
    return time.time()
