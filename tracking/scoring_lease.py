"""One scoring pass at a time across a Railway overlap.

``_DAILY_LOCK`` and ``_REFRESH_LOCK`` are threading locks. They live in
one process. Railway sends SIGTERM to the old container only after the
new one is already running, and ``drainingSeconds`` (railway.json) is
how long the old process is allowed to finish its step. During that
window the new process has a free threading lock, so the boot sweep
would stamp the still-open row ``aborted`` and the catch-up would start
a second writer.

A session advisory lock is the cross-process version. The daily child
holds the daily key until it has closed its ``pipeline_runs`` row. The
refresh shell holds the refresh key the same way. The boot sweep skips
a kind whose key is held. The catch-up waits, up to the drain window,
before it starts that kind again. A connection drop releases the lock,
which is what SIGKILL does.

The keys are not ``tracking.job_queue.QUEUE_LOCK_KEY``. Two leases on
one key would stop the queue for the whole daily.

This needs a session-mode connection (``get_connection(session_mode=True)``).
Transaction mode can run the next statement on a different backend, and
the lock would not be there. ``DATABASE_URL`` on the worker is the
session pooler; session mode does not rewrite it to port 6543.

The first deploy of this code overlaps a process that is not holding
the lock. That boot still sweeps and can still overlap. The deploy
after that is the one the lease covers.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path

from loguru import logger

# railway.json deploy.drainingSeconds. SIGKILL follows SIGTERM by this
# many seconds. The wait is that plus a little, so the connection drop
# from SIGKILL is visible before we give up.
DRAIN_SECONDS = 600
LEASE_WAIT_S = DRAIN_SECONDS + 30

# Distinct from job_queue.QUEUE_LOCK_KEY (0x6A6F6271).
_KEYS = {
    "daily": 0x6461696C,     # "dail"
    "refresh": 0x72656672,   # "refr"
}

_KEEPALIVE_S = 20.0


def _connect():
    from data.db import get_connection
    return get_connection(session_mode=True)


def _key(kind: str) -> int:
    try:
        return _KEYS[kind]
    except KeyError:
        raise ValueError(f"unknown scoring lease {kind!r}") from None


def _is_timeout(exc: BaseException) -> bool:
    code = getattr(exc, "pgcode", None)
    # 55P03 lock_not_available (lock_timeout). 57014 query_canceled
    # (statement_timeout). Either means we did not confirm the lock is free.
    if code in ("55P03", "57014"):
        return True
    msg = str(exc).lower()
    return (
        "lock timeout" in msg
        or "statement timeout" in msg
        or "canceling statement" in msg
    )


def _prepare(conn, wait_s: int) -> None:
    # The database statement_timeout is 120s. A lock wait is one
    # statement, so without this the wait dies at two minutes and the
    # catch-up thinks the previous process is gone.
    conn.execute("SET statement_timeout = 0")
    conn.execute(f"SET lock_timeout = '{int(wait_s)}s'")
    conn.commit()


def _lock(conn, key: int) -> None:
    conn.execute("SELECT pg_advisory_lock(%s)", (key,))
    conn.commit()


class ScoringLease:
    """Holds one session advisory lock until ``release``.

    A thread runs ``SELECT 1`` so the pooler does not drop an idle
    session and take the lock with it. ``release`` joins that thread
    before it unlocks, so the two do not share the connection.
    """

    def __init__(self, conn, key: int, connect, keepalive_s: float):
        self._conn = conn
        self._key = key
        self._connect = connect
        self._keepalive_s = keepalive_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._released = False

    def start_keepalive(self) -> None:
        self._thread = threading.Thread(
            target=self._beat, name="scoring-lease", daemon=True,
        )
        self._thread.start()

    def _beat(self) -> None:
        while not self._stop.wait(self._keepalive_s):
            try:
                self._conn.execute("SELECT 1")
                self._conn.commit()
            except Exception as exc:  # noqa: BLE001 — the pass keeps running
                logger.error(
                    f"scoring lease: LOST — keepalive session dropped "
                    f"({type(exc).__name__}); taking the lock again"
                )
                try:
                    self._conn.close()
                except Exception:  # noqa: BLE001
                    pass
                try:
                    self._conn = self._connect()
                    _prepare(self._conn, 5)
                    row = self._conn.execute(
                        "SELECT pg_try_advisory_lock(%s)", (self._key,),
                    ).fetchone()
                    self._conn.commit()
                    if not (row and row[0]):
                        logger.error(
                            "scoring lease: LOST — reconnect did not get "
                            "the lock; this pass is running without it"
                        )
                    else:
                        logger.warning(
                            "scoring lease: reacquired after the session drop"
                        )
                except Exception as again:  # noqa: BLE001
                    logger.error(
                        f"scoring lease: LOST — could not take the lock "
                        f"again ({type(again).__name__}); this pass is "
                        f"running without it"
                    )

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        try:
            self._conn.execute("SELECT pg_advisory_unlock(%s)", (self._key,))
            self._conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"scoring lease: unlock failed ({type(exc).__name__}); "
                f"closing the session releases it"
            )
        finally:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass


def acquire(
    kind: str,
    *,
    connect=None,
    keepalive_s: float = _KEEPALIVE_S,
    wait_s: int = LEASE_WAIT_S,
) -> ScoringLease | None:
    """Hold ``kind`` until ``release``.

    ``None`` means the lock was not taken. The caller still runs the
    pass. A missing database must not stop the daily, and a lock that
    is still held after the drain window is a leaked session, not a
    reason to skip today's run. The boot catch-up is the path that
    refuses to start a second writer; this one is the path that owns
    the row.
    """
    connect = connect or _connect
    key = _key(kind)
    try:
        conn = connect()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"scoring lease: no connection ({type(exc).__name__}); "
            f"{kind} runs without the lock"
        )
        return None
    try:
        _prepare(conn, wait_s)
        _lock(conn, key)
    except Exception as exc:  # noqa: BLE001
        if _is_timeout(exc):
            logger.warning(
                f"scoring lease: {kind} lock still held after {wait_s}s; "
                f"this pass runs anyway"
            )
        else:
            logger.warning(
                f"scoring lease: {kind} lock failed "
                f"({type(exc).__name__}); this pass runs without the lock"
            )
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
        return None
    lease = ScoringLease(conn, key, connect, keepalive_s)
    lease.start_keepalive()
    return lease


def held(kind: str, *, connect=None) -> bool:
    """True when another session holds ``kind``.

    Never blocks. A database that cannot answer is reported as not
    held, which is the sweep this process already did before the lease
    existed. Tests that hand back a sqlite connection land here.
    """
    connect = connect or _connect
    key = _key(kind)
    try:
        conn = connect()
    except Exception:  # noqa: BLE001
        return False
    got = False
    try:
        row = conn.execute(
            "SELECT pg_try_advisory_lock(%s)", (key,),
        ).fetchone()
        got = bool(row and row[0])
        if got:
            conn.execute("SELECT pg_advisory_unlock(%s)", (key,))
        conn.commit()
        return not got
    except Exception:  # noqa: BLE001
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def wait_for_scoring_lease(
    kind: str,
    *,
    connect=None,
    wait_s: int = LEASE_WAIT_S,
) -> bool:
    """True when ``kind`` is free (this call took the lock and released it).

    False when the wait timed out: the previous deployment is still
    inside the step, or the wait was cancelled before we could tell.
    The catch-up skips on False. A database that cannot be asked
    returns True so a boot is not stuck behind a down database.
    """
    connect = connect or _connect
    key = _key(kind)
    try:
        conn = connect()
    except Exception:  # noqa: BLE001
        return True
    try:
        _prepare(conn, wait_s)
        _lock(conn, key)
        conn.execute("SELECT pg_advisory_unlock(%s)", (key,))
        conn.commit()
        return True
    except Exception as exc:  # noqa: BLE001
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        if _is_timeout(exc):
            logger.warning(
                f"scoring lease: {kind} still held after {wait_s}s"
            )
            return False
        logger.warning(
            f"scoring lease: {kind} wait failed ({type(exc).__name__}); "
            f"not blocking the boot on it"
        )
        return True
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def drop_live_kinds(kinds) -> list[str]:
    """Kinds whose lease is free. A held lease is a process still in the step."""
    kept = list(kinds)
    if "daily" in kept and held("daily"):
        kept = [k for k in kept if k != "daily"]
        logger.warning(
            "scoring lease: daily is still running in the previous "
            "deployment — not stamping that row aborted"
        )
    refresh = ("hourly", "evening")
    if any(k in refresh for k in kept) and held("refresh"):
        kept = [k for k in kept if k not in refresh]
        logger.warning(
            "scoring lease: a refresh is still running in the previous "
            "deployment — not stamping that row aborted"
        )
    return kept


def main(argv: list[str] | None = None) -> int:
    """Hold the refresh lease until the parent closes it.

    ``refresh_pass.sh`` starts this, waits until ``--ready`` exists,
    then runs the pass. It writes ``--release`` from the EXIT trap,
    after the ledger finish. The parent dying is the same signal:
    SIGKILL takes the shell and this process together.
    """
    ap = argparse.ArgumentParser(description="Hold a scoring lease")
    ap.add_argument("--kind", required=True, choices=sorted(_KEYS))
    ap.add_argument("--ready", required=True)
    ap.add_argument("--release", required=True)
    args = ap.parse_args(argv)
    parent = os.getppid()
    lease = acquire(args.kind)
    ready = Path(args.ready)
    release_flag = Path(args.release)
    if lease is None:
        ready.write_text("open\n", encoding="utf-8")
        return 0
    ready.write_text("held\n", encoding="utf-8")
    try:
        while not release_flag.exists():
            if os.getppid() != parent:
                break
            time.sleep(0.2)
    finally:
        lease.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
