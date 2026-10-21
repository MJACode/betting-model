"""A scratch Postgres for the tests that drive real triggers and views.

Two test files need a real server (`test_latest_line_state.py`,
`test_discord_void_notice.py`). Either `LATEST_LINE_TEST_DSN` names one, or
this starts a throwaway cluster from whichever binaries exist:

  1. `initdb` / `pg_ctl` on PATH (a system install),
  2. the Debian path the Linux sandbox carries (/usr/lib/postgresql/16/bin),
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
from contextlib import contextmanager
from pathlib import Path


def pg_bin(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    debian = Path(f"/usr/lib/postgresql/16/bin/{name}")
    if debian.is_file():
        return str(debian)
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
        shutil.rmtree(owned, ignore_errors=True)


def env_dsn() -> str | None:
    return os.environ.get("LATEST_LINE_TEST_DSN") or None


def can_scratch() -> bool:
    return bool(pg_bin("initdb") and pg_bin("pg_ctl"))
