"""Start a throwaway Postgres cluster for the BYOM tests.

Same shape as the scratch cluster in tests/test_discord_void_notice.py.
Skips when initdb is not installed. Never points at DATABASE_URL.
"""
from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
from pathlib import Path


def pg_bin(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    root = Path("/usr/lib/postgresql")
    if not root.is_dir():
        return None
    for version in sorted(root.iterdir(), reverse=True):
        path = version / "bin" / name
        if path.is_file():
            return str(path)
    return None


class ScratchPostgres:
    """initdb + pg_ctl on a free port, trust auth, stopped on close."""

    def __init__(self) -> None:
        self.data: str | None = None
        self.dsn: str | None = None
        self._pg_ctl: str | None = None

    def start(self) -> str:
        initdb = pg_bin("initdb")
        pg_ctl = pg_bin("pg_ctl")
        if not initdb or not pg_ctl:
            raise FileNotFoundError("initdb")
        self._pg_ctl = pg_ctl
        self.data = tempfile.mkdtemp(prefix="byom-pg-")
        subprocess.run(
            [initdb, "-D", self.data, "-A", "trust", "--username", "postgres"],
            check=True, capture_output=True, text=True)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        subprocess.run(
            [pg_ctl, "-D", self.data, "-o", f"-p {port} -k {self.data}",
             "-l", str(Path(self.data) / "log"), "-w", "start"],
            check=True, capture_output=True, text=True)
        self.dsn = f"host={self.data} port={port} dbname=postgres user=postgres"
        return self.dsn

    def stop(self) -> None:
        if self.data and self._pg_ctl:
            subprocess.run(
                [self._pg_ctl, "-D", self.data, "-w", "-m", "immediate", "stop"],
                check=False, capture_output=True, text=True)
            shutil.rmtree(self.data, ignore_errors=True)
            self.data = None
