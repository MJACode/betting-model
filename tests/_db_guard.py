"""Refuse any database connection a test makes to a host off this machine.

WHY. tests/conftest.py imports data.db before any test file runs, and data.db
loads the checkout's .env. In the main checkout that .env names the production
database, so a test file's own
`os.environ.setdefault("DATABASE_URL", "...localhost...")` never wins there,
and any test that reaches a connection without mocking it is talking to
production. #1396 counted 329 such connections in one full run on 2026-11-16:
323 heartbeat writes from building the scheduler, and 6 from the pick grader,
the in-play push notifier and the scorer's paused-model check.

WHAT. `install()` wraps `psycopg2.connect`, the call every route in this repo
goes through (data.db._open, the scripts that dial psycopg2 directly, and
SQLAlchemy's psycopg2 dialect, which calls the module's `connect`). A host that
is not this machine raises OperationalError at once, without dialling, and is
recorded in REFUSED for the run's summary (conftest's
pytest_terminal_summary). OperationalError, because that is what the code
under test already handles: the same tests get it from a refused localhost
connect in a checkout with no .env.

LOCAL means: no host at all (libpq then uses the local socket), a socket
directory, `localhost`, or a loopback address. The scratch Postgres in
tests/_pg.py is `host=127.0.0.1 port=N ...`, libpq's key=value form; #1396's
first guard did not read that form and blocked it.

NOT COVERED. A child process a test starts does not import conftest, so it is
not guarded. #1396's guarded run recorded no child-process connection.
"""
from __future__ import annotations

import ipaddress
import os

# (test node id, [the hosts refused]) for every refused connection this run.
REFUSED: list[tuple[str, list[str]]] = []

_LOCAL_NAMES = {"", "localhost"}


def is_local(host: str) -> bool:
    host = (host or "").strip()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if host.lower() in _LOCAL_NAMES or host.startswith("/") or host.startswith("@"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def far_hosts(dsn=None, **kwargs) -> list[str]:
    """The hosts in a connect call that are not this machine.

    Reads what libpq would read: the DSN (a URL or key=value), keywords that
    override it, then PGHOST / PGHOSTADDR when neither names a host. A service
    file can name any host, so a `service` is reported as one off the machine.
    """
    from psycopg2 import extensions
    params = {k: v for k, v in kwargs.items() if k not in ("async", "async_")}
    parsed = extensions.parse_dsn(extensions.make_dsn(dsn, **params))
    service = parsed.get("service") or os.environ.get("PGSERVICE", "")
    if service:
        return [f"service={service}"]
    hosts = []
    for key, env in (("host", "PGHOST"), ("hostaddr", "PGHOSTADDR")):
        value = parsed.get(key)
        if value is None:
            value = os.environ.get(env, "")
        hosts += [h.strip() for h in str(value).split(",")]
    return [h for h in hosts if not is_local(h)]


def install() -> None:
    """Wrap psycopg2.connect. Idempotent."""
    import psycopg2
    original = psycopg2.connect
    if getattr(original, "_refuses_far_hosts", False):
        return

    class RefusedDatabaseHost(psycopg2.OperationalError):
        """An OperationalError, so a caller's `except` handles it as the
        refused connect it would get from a checkout with no .env."""

    def connect(dsn=None, connection_factory=None, cursor_factory=None, **kwargs):
        try:
            far = far_hosts(dsn, **kwargs)
        except psycopg2.Error:
            far = []          # a malformed DSN: psycopg2 refuses it, nothing dials
        if far:
            test = os.environ.get("PYTEST_CURRENT_TEST", "(outside a test)")
            REFUSED.append((test.rsplit(" (", 1)[0], far))
            # The host is kept out of the message: `beat` and others log it,
            # and from the main checkout it is production's.
            raise RefusedDatabaseHost(
                "a test tried to connect to a database not on this machine; "
                "tests/_db_guard.py refuses it. Mock the connection, or use "
                "the scratch Postgres in tests/_pg.py")
        return original(dsn, connection_factory=connection_factory,
                        cursor_factory=cursor_factory, **kwargs)

    connect._refuses_far_hosts = True
    connect.__wrapped__ = original
    psycopg2.connect = connect


def summary_lines() -> list[str]:
    """The run's count, one line per test that was refused. Hosts are left
    out for the reason the refusal's message leaves them out."""
    if not REFUSED:
        return ["database guard: refused 0 connections to a database off this machine"]
    per_test: dict[str, int] = {}
    for test, _hosts in REFUSED:
        per_test[test] = per_test.get(test, 0) + 1
    lines = [f"database guard: refused {len(REFUSED)} connection(s) to a database "
             f"off this machine, from {len(per_test)} test(s):"]
    for test, count in sorted(per_test.items()):
        lines.append(f"  {count:>3}  {test}")
    return lines
