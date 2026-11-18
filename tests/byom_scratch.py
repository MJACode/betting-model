"""Start a throwaway Postgres cluster for the BYOM tests.

The cluster is tests/_pg.py's `scratch_cluster`, behind the start()/stop()
pair these tests call. This file used to run pg_ctl itself with its output
captured. On Windows the server keeps that pipe open, so the run waited
forever (measured 2026-11-13; #1445 is the same fault in another test).

`pg_bin` is tests/_pg.py's finder too: PATH, the newest Debian major, then
the embedded-postgres wheel. This file's own finder stopped at the first two,
so on Windows, where only the wheel is installed, every test that asks it
skipped (88 of them, 2026-11-17; all pass once it can find the server).
Skips when initdb is not installed. Never points at DATABASE_URL.
"""
from __future__ import annotations

import contextlib

from tests._pg import pg_bin, scratch_cluster

__all__ = ["ScratchPostgres", "pg_bin"]


class ScratchPostgres:
    """A UTF-8, trusted cluster on a free TCP port, stopped and deleted on stop()."""

    def __init__(self) -> None:
        self.dsn: str | None = None
        self._stack: contextlib.ExitStack | None = None

    def start(self) -> str:
        if not pg_bin("initdb") or not pg_bin("pg_ctl"):
            raise FileNotFoundError("initdb")
        stack = contextlib.ExitStack()
        try:
            self.dsn = stack.enter_context(scratch_cluster("byom-pg-"))
        except BaseException:
            stack.close()
            raise
        self._stack = stack
        return self.dsn

    def stop(self) -> None:
        stack, self._stack = self._stack, None
        if stack is not None:
            stack.close()
        self.dsn = None
