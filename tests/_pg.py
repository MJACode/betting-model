"""A scratch Postgres for the tests that drive real triggers and views.

Two test files need a real server (`test_latest_line_state.py`,
`test_discord_void_notice.py`). Either `LATEST_LINE_TEST_DSN` names one, or
this starts a throwaway cluster from whichever binaries exist:

  1. `initdb` / `pg_ctl` on PATH (a system install),
  2. the Debian layout, /usr/lib/postgresql/<major>/bin, newest major first
     (the sandbox carries 16; GitHub's runner installs 18 since 2026-11),
  3. the `embedded-postgres` pip package (declared in requirements-test.txt),
     which ships a full server beside its module — the route on this machine,
     where nothing else is installed.

With none of the three, the tests skip. The cluster is UTF-8 (production is;
the migrations carry box-drawing characters that a WIN1252 cluster refuses),
trusts local connections, listens on a free TCP port on 127.0.0.1 (Windows
has no unix sockets for libpq) and is stopped and deleted at session end.

`pg_ctl start` must NOT inherit a captured pipe: the postmaster keeps the
handle open on Windows and the caller waits forever (measured 2026-10-16,
two probes hung past 300 s). Output goes to the cluster's log file instead.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


DEBIAN_PG_ROOT = Path("/usr/lib/postgresql")


def _debian_bin(name: str, root: Path | None = None) -> str | None:
    """The newest /usr/lib/postgresql/<major>/bin/<name>. Never a pinned major:
    a hard-coded 16 made every scratch test fail in CI the day the runner's
    apt moved to 18 (PR #1426, 2026-11-16), while the workflow's own check,
    which scanned every version, passed."""
    root = DEBIAN_PG_ROOT if root is None else root
    if not root.is_dir():
        return None
    majors = [d for d in root.iterdir() if d.name.isdigit()]
    for version in sorted(majors, key=lambda d: int(d.name), reverse=True):
        cand = version / "bin" / name
        if cand.is_file():
            return str(cand)
    return None


def pg_bin(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    debian = _debian_bin(name)
    if debian:
        return debian
    try:
        import embedded_postgres  # type: ignore
    except ImportError:
        return None
    base = Path(embedded_postgres.__file__).parent / "pginstall" / "bin"
    for cand in (base / f"{name}.exe", base / name):
        if cand.is_file():
            return str(cand)
    return None


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@contextmanager
def scratch_cluster(prefix: str = "scratch-pg-"):
    """Yield a DSN for a fresh, trusted, UTF-8 cluster; tear it down after."""
    initdb, pg_ctl = pg_bin("initdb"), pg_bin("pg_ctl")
    if not initdb or not pg_ctl:
        raise RuntimeError("no initdb/pg_ctl: install postgres or embedded-postgres")
    owned = tempfile.mkdtemp(prefix=prefix)
    log = Path(owned) / "log"
    try:
        subprocess.run(
            [initdb, "-D", owned, "-A", "trust", "--username", "postgres",
             "-E", "UTF8", "--locale=C"],
            check=True, capture_output=True, text=True)
        port = _free_port()
        opts = f"-p {port}"
        if sys.platform != "win32":
            opts += f" -k {owned}"
        # pg_ctl's own chatter goes to a second file: holding the -l log open
        # ourselves makes the postmaster's open of it fail on Windows ("being
        # used by another process") and the start is refused.
        with open(Path(owned) / "pg_ctl.out", "ab") as sink:
            subprocess.run(
                [pg_ctl, "-D", owned, "-o", opts, "-l", str(log), "-w", "start"],
                check=True, stdout=sink, stderr=sink)
        yield f"host=127.0.0.1 port={port} dbname=postgres user=postgres"
    finally:
        with open(Path(owned) / "pg_ctl.out", "ab") as sink:
            subprocess.run([pg_ctl, "-D", owned, "-m", "fast", "-w", "stop"],
                           stdout=sink, stderr=sink)
        _remove(owned)


def _remove(path: str, tries: int = 20, pause: float = 0.25) -> None:
    """Delete a cluster's folder, retrying for up to about five seconds.

    One rmtree after `pg_ctl stop -w` left `log` and `pg_ctl.out` behind in
    three folders on 2026-11-17 (byom-pg- and latest-line-pg-), although the
    server had stopped. The likely cause, not measured: the server's processes
    still hold those files for a moment, and on Windows a file another process
    holds cannot be deleted. The leftover did not recur in 35 tries, so this
    retry is tested only against a stand-in delete.
    """
    for attempt in range(tries):
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.exists(path):
            return
        if attempt + 1 < tries:
            time.sleep(pause)


def env_dsn() -> str | None:
    return os.environ.get("LATEST_LINE_TEST_DSN") or None


def can_scratch() -> bool:
    return bool(pg_bin("initdb") and pg_bin("pg_ctl"))
