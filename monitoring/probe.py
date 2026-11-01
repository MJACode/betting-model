"""One global patch that records every outbound HTTP call this process makes.

WHY A PATCH AND NOT 75 CALL-SITE EDITS
There are ~75 `requests.get` call sites across 34 modules and no shared HTTP
helper. Wrapping `requests.sessions.Session.request` once catches all of them —
AND the calls made inside third-party libraries we do not own: MLB-StatsAPI,
nba_api, pybaseball, cloudscraper (a Session subclass whose own `request` calls
`super().request`, so it is counted exactly once). A new ingestor is covered the
day it is written, with no code change here.

THE RULES THIS MODULE LIVES BY
  * It must never change what a call returns, and never raise into a caller.
    Every hook body is wrapped; an exception in telemetry is swallowed.
    ONE deliberate exception: a request that set no timeout is given one
    (install_timeout_floor). That can surface a Timeout where the call would
    otherwise have hung forever -- which is the point, and is why the floor is
    kept independent of the telemetry kill switch.
  * It must never make a call slower. Recording is a bounded in-memory queue and
    a daemon thread; nothing touches the database on the request path.
  * A process's last calls are written before it exits, and the exit waits a
    bounded time for that (twice API_LOG_EXIT_WAIT_SEC at most). See
    _flush_on_exit.
  * It must never leak a key. The query string is dropped except for an
    allowlist of descriptive params — `apiKey`, `key` and friends can therefore
    never be persisted, not even by accident on a new host.

Install once per process, at the entrypoint:
    from monitoring.probe import install
    install("pipeline")
Kill switch: PIPELINE_TELEMETRY=0.
"""

from __future__ import annotations

import atexit
import os
import re
import queue
import threading
import time
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit

from monitoring import registry, store

# Query params worth keeping. Anything not named here is dropped, which is what
# makes credential leakage structurally impossible rather than merely unlikely.
_KEEP_PARAMS = frozenset({
    "markets", "market", "regions", "sport", "sportId", "sportid", "leagueId",
    "date", "dates", "season", "seasonType", "year", "week", "team", "teamId",
    "gameId", "eventId", "event", "oddsFormat", "bookmakers", "division",
    "tour", "file_format", "daysFrom", "limit", "player", "startWeek", "endWeek",
})

# Path/param tokens that identify a sport, so the dashboard can filter by it.
_SPORT_TOKENS = {
    "baseball_mlb": "MLB", "basketball_wnba": "WNBA", "basketball_nba": "NBA",
    "icehockey_nhl": "NHL", "americanfootball_nfl": "NFL",
    "americanfootball_ncaaf": "NCAAF", "mma_mixed_martial_arts": "UFC",
    "golf": "GOLF", "mlb": "MLB", "nfl": "NFL", "nba": "NBA", "nhl": "NHL",
    "wnba": "WNBA", "college-football": "NCAAF", "ncaaf": "NCAAF",
    # Men's college basketball (2026-27): the Odds API key, and ESPN's path
    # segment for its schedule and box scores.
    "basketball_ncaab": "NCAAB", "mens-college-basketball": "NCAAB",
}

# A request that never returns is the one failure mode this repo has no defence
# against. Our own ingestors all pass an explicit timeout (the largest is 300s),
# but the libraries we do NOT own -- MLB-StatsAPI, nba_api, pybaseball -- pass
# none, and `requests` then blocks forever. On 2026-08-30 that stalled refresh
# passes for the better part of an hour with the container at 1.1GB/8GB and
# 1.4/8 CPU: not memory, not CPU, just blocked on a socket.
#
# The probe is already the one place every library's calls pass through, so the
# floor goes here rather than in 75 call sites. It applies ONLY when the caller
# set nothing, so every deliberate timeout in this repo is left exactly as
# written; and it is looser than all of them, so it can only ever catch a hang.
_DEFAULT_TIMEOUT = (
    float(os.environ.get("HTTP_CONNECT_TIMEOUT", "10")),
    float(os.environ.get("HTTP_READ_TIMEOUT", "120")),
)

_MAX_QUEUE = int(os.environ.get("API_LOG_QUEUE", "5000"))
_FLUSH_SEC = float(os.environ.get("API_LOG_FLUSH_SEC", "0.75"))
_PRUNE_EVERY_SEC = 3600
# The longest each of the exit's two waits lasts: first for the writer to store
# what it recorded, then, only if the writer is stuck with calls still queued,
# for the standby to write those over a fresh connection. A normal final write
# from the worker is one connect plus one insert, which the scheduler log puts
# at 0.3-0.45 s. Nothing on this path sets a connect timeout, so without this
# bound an unreachable database could hold an exit for as long as the TCP
# connect takes. Both waits together are 6 s by default; the shortest timeout
# scheduler.py puts on any job is 60 s, so they cannot push a job past its own.
_EXIT_WAIT_SEC = float(os.environ.get("API_LOG_EXIT_WAIT_SEC", "3"))

_installed = False
_timeout_floor_installed = False
_lock = threading.Lock()
_q: queue.Queue = queue.Queue(maxsize=_MAX_QUEUE)
_source = "unknown"
_stop = threading.Event()               # set once, at exit
_writer: threading.Thread | None = None
_takeover = threading.Event()           # set at exit, only if calls are still queued
_standby: threading.Thread | None = None

# Odds API credits are not in the response body. Each response carries
# x-requests-last, the API's own bill for THAT call, and it is what is
# recorded. The DELTA of x-requests-used between this process's consecutive
# responses is only the fallback for a response without x-requests-last: the
# counter is the whole account's, so the delta also holds every credit any
# other process spent in between. Measured 2026-10-29: while the NCAAB history
# purchase ran on the worker (04:25-07:04Z), the pregame poller's ~600 calls an
# hour were logged at 40,918, 74,463 and 66,105 credits an hour against 2,000-
# 5,800 before it, and its daily cap, summed from this column, stopped it at
# 200,280 for the rest of the ET day. Tracked per process; with no
# x-requests-last the first call has no baseline and records NULL.
_last_used: float | None = None
_used_lock = threading.Lock()

_dropped = 0            # queue overflow, surfaced by stats()
_recorded = 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _with_params(url: str, params) -> str:
    """requests merges `params=` into the URL *after* Session.request is
    entered, so the url we are handed on the failure path has no query string.
    Re-attach it (redaction happens downstream, so a key here is still safe)."""
    try:
        if not params or urlsplit(url).query:
            return url
        if isinstance(params, (dict, list, tuple)):
            qs = urlencode(params, doseq=True)
            return f"{url}?{qs}" if qs else url
    except Exception:
        pass
    return url


def _redact(url: str) -> tuple[str, str | None]:
    """(path with an allowlisted query, sport) — never any credential."""
    try:
        parts = urlsplit(url)
        path = parts.path or "/"
        kept = []
        sport = None
        for k, v in parse_qsl(parts.query, keep_blank_values=False):
            if k in _KEEP_PARAMS:
                kept.append(f"{k}={v}")
                if sport is None:
                    sport = _SPORT_TOKENS.get(v.lower())
        if sport is None:
            for seg in path.lower().split("/"):
                if seg in _SPORT_TOKENS:
                    sport = _SPORT_TOKENS[seg]
                    break
        if kept:
            path = f"{path}?{'&'.join(kept)}"
        return path[:400], sport
    except Exception:
        return ("/", None)


# requests embeds the FULL request URL — query string and all — in its
# exception messages ("Max retries exceeded with url: /v1/x?key=SECRET"). The
# path is redacted by _redact, but the error text is a second, easily-missed
# path to the same credential. Found by asserting no key appears anywhere in a
# recorded row, which is why that assertion is a test and not a code comment.
# Matches at a word boundary, not just after ? or & — a library that prints a
# bare `token=abc123` in its message leaks exactly as much as one that prints a
# whole URL.
_SENSITIVE_PARAM = re.compile(
    r"(^|[?&\s,;(])([A-Za-z0-9_\-]*(?:key|token|secret|password|auth|sig)"
    r"[A-Za-z0-9_\-]*=)[^&\s'\"\)]+",
    re.IGNORECASE,
)
_URL_QUERY = re.compile(r"((?:https?://|url:\s*/)[^\s'\"\)]*)\?[^\s'\"\)]*")


def _scrub(text: str | None) -> str | None:
    """Strip credentials out of a free-text error message."""
    if not text:
        return text
    try:
        cleaned = _URL_QUERY.sub(r"\1", text)
        return _SENSITIVE_PARAM.sub(r"\1\2***", cleaned)
    except Exception:
        return "error"


def _credits_from(resp) -> tuple[float | None, float | None]:
    """(credits spent by this call, credits remaining) from Odds API headers.

    x-requests-last when the response has it; otherwise the delta of
    x-requests-used since this process's previous response."""
    global _last_used
    try:
        used_raw = resp.headers.get("x-requests-used")
        last_raw = resp.headers.get("x-requests-last")
        remaining_raw = resp.headers.get("x-requests-remaining")
        remaining = float(remaining_raw) if remaining_raw not in (None, "") else None
        prev = used = None
        if used_raw not in (None, ""):
            used = float(used_raw)
            with _used_lock:            # keep the baseline current for the fallback
                prev = _last_used
                _last_used = used
        if last_raw not in (None, ""):
            return (float(last_raw), remaining)
        if used is None:
            return (None, remaining)
        # A negative delta means the billing period reset — report nothing
        # rather than a nonsense figure.
        if prev is None or used < prev:
            return (None, remaining)
        return (used - prev, remaining)
    except Exception:
        return (None, None)


def _enqueue(row: tuple) -> None:
    global _dropped, _recorded
    try:
        _q.put_nowait(row)
        _recorded += 1
    except queue.Full:
        # Drop the OLDEST record, not the newest: during an incident the recent
        # calls are the ones worth having.
        _dropped += 1
        try:
            _q.get_nowait()
            _q.put_nowait(row)
        except Exception:
            pass


def record(url: str, method: str, status: int | None, ok: bool,
           duration_ms: int, resp_bytes: int | None = None,
           credits: float | None = None, quota_remaining: float | None = None,
           error: str | None = None) -> None:
    """Record one call. Public so non-requests clients (websockets, a raw
    socket probe) can report through the same pipe."""
    try:
        host, api, category, _paid = registry.classify(url)
        path, sport = _redact(url)
        _enqueue((
            _now(), api, host, category, (method or "GET").upper(), path, sport,
            status, bool(ok), int(duration_ms), resp_bytes, credits,
            quota_remaining, _scrub(error) or None, _source,
        ))
    except Exception:
        pass


# ── the writer ───────────────────────────────────────────────────────────────

def _drain(max_rows: int = 500) -> list[tuple]:
    rows: list[tuple] = []
    while len(rows) < max_rows:
        try:
            rows.append(_q.get_nowait())
        except queue.Empty:
            break
    return rows


def _writer_loop() -> None:
    conn = None
    ensured = False
    # The clock starts now, not at 0. At 0 every process pruned -- and rolled up
    # the whole log -- on its FIRST flush, so each short-lived pipeline step paid
    # a full scan of api_call_log: 29,609 runs at ~7 s each by 2026-10-03, the
    # database's largest disk reader. The long-running worker and pollers still
    # prune hourly.
    last_prune = time.time()
    while True:
        # A wait on the stop flag rather than a sleep: at exit the flag is set
        # and the writer goes straight to its last pass instead of finishing
        # the nap. A batch already in hand is written first, because the exit
        # waits for this thread (_flush_on_exit), not for the queue.
        stopping = _stop.wait(_FLUSH_SEC)
        rows = _drain(max_rows=_MAX_QUEUE if stopping else 500)
        if rows:
            try:
                if conn is None:
                    from data.db import get_connection
                    conn = get_connection()
                    ensured = False
                if not ensured:
                    store.ensure_table(conn)
                    ensured = True
                conn.executemany(store.INSERT_SQL, rows)
                conn.commit()

                now = time.time()
                if not stopping and now - last_prune > _PRUNE_EVERY_SEC:
                    last_prune = now
                    store.prune(conn)
            except Exception:
                # A dead connection (the Supabase pooler drops idle ones) or a
                # transient failure: drop this batch, reconnect next tick.
                # Telemetry is never worth retrying into a backlog -- and that
                # holds at exit too: a failed last batch is lost, not retried.
                try:
                    if conn is not None:
                        conn.close()
                except Exception:
                    pass
                conn = None
        if stopping:
            break
    try:
        if conn is not None:
            conn.close()
    except Exception:
        pass


def _standby_loop() -> None:
    """The exit's second writer, for calls a stuck writer cannot reach.

    Idle until _flush_on_exit sets _takeover, which it does only when calls
    remain on the queue after the wait for the writer: the writer is stuck
    (say its connection is hung inside an insert on a socket that died without
    a reset) or gone. It takes everything left, writes it once over its own
    fresh connection, and stops. It is started with the writer at install, so the
    exit never has to start a thread while the interpreter is shutting down.

    Nothing is written twice. The queue hands each row to one taker, and the
    batch the stuck writer holds is not on the queue. That batch is lost:
    there is no way to reach it.
    """
    _takeover.wait()
    rows = _drain(max_rows=_MAX_QUEUE)
    if not rows:
        return
    conn = None
    try:
        from data.db import get_connection
        conn = get_connection()
        store.ensure_table(conn)
        conn.executemany(store.INSERT_SQL, rows)
        conn.commit()
    except Exception:
        pass                    # a failed last write is lost, not retried
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def _flush_on_exit() -> None:
    """Let the writer store what this process recorded, for at most
    _EXIT_WAIT_SEC; if it is stuck with calls still queued, let the standby
    write those, for at most _EXIT_WAIT_SEC more; then let the process go.

    WHY THE WRITER DOES IT, NOT THIS FUNCTION. This used to drain the queue and
    write the rows itself. But the writer may already have drained them: it
    takes a batch off the queue and only then connects and inserts, 0.3-0.45 s
    from the worker. A process that exited inside that window found the queue empty
    here, and the interpreter then stopped the writer -- a daemon thread --
    with the rows in hand. Measured 2026-10-31: the NCAAB odds capture, one
    call in a ~1.3 s process, made 72 calls in six hours and api_call_log kept
    31; each of the 41 lost calls shows as its 3 credits missing from the Odds
    API's remaining count. In the scheduler log a lost run exits within 0.1 s
    of its last line, and a kept one 0.3-0.45 s after it: the kept rows were
    the ones this function still found on the queue and wrote. So this now
    sets the stop flag and joins the writer, which finishes the batch it
    holds, drains the rest and stops.

    WHY A STANDBY. The writer holds one connection. If that connection hangs
    inside an insert, the writer cannot reach the calls still on the queue,
    and waiting longer does not help. The old exit drained those itself and
    wrote them over a new connection, so the standby keeps that: it writes them
    over its own fresh connection (_standby_loop). It runs only when the queue
    is not empty after the writer's wait, so a healthy exit never opens a
    second connection. If the writer is gone (it catches every Exception, so
    only something like a KeyboardInterrupt inside it could end it), the
    standby writes what it left on the queue the same way.

    The main thread never touches the database here, so the two joins'
    timeouts are the whole bound: twice _EXIT_WAIT_SEC at most. Past that the
    rows are lost and the exit goes ahead: a process must not hang on its
    telemetry.
    """
    _stop.set()
    t = _writer
    if t is not None and t.is_alive():
        t.join(_EXIT_WAIT_SEC)
    if _q.empty():
        return
    s = _standby
    if s is not None and s.is_alive():
        _takeover.set()
        s.join(_EXIT_WAIT_SEC)


# ── the patch ────────────────────────────────────────────────────────────────

def _patch_curl_cffi() -> None:
    """Instrument curl_cffi's Session too, if it is installed. Best-effort."""
    try:
        from curl_cffi import requests as _cc
    except Exception:
        return
    try:
        target = _cc.Session
        original = target.request
        if getattr(original, "__wrapped__", None) is not None:
            return                                   # already patched
    except Exception:
        return

    def instrumented(self, method, url, *args, **kwargs):
        started = time.perf_counter()
        try:
            resp = original(self, method, url, *args, **kwargs)
        except Exception as exc:
            try:
                record(_with_params(url, kwargs.get("params")), method, None,
                       False, int((time.perf_counter() - started) * 1000),
                       error=f"{type(exc).__name__}: {exc}"[:300])
            except Exception:
                pass
            raise
        try:
            elapsed = int((time.perf_counter() - started) * 1000)
            status = getattr(resp, "status_code", None)
            ok = bool(status and 200 <= int(status) < 400)
            try:
                size = len(resp.content) if resp.content is not None else None
            except Exception:
                size = None
            record(getattr(resp, "url", None) or _with_params(url, kwargs.get("params")),
                   method, status, ok, elapsed, resp_bytes=size,
                   error=None if ok else f"HTTP {status}")
        except Exception:
            pass
        return resp

    instrumented.__wrapped__ = original
    try:
        target.request = instrumented
    except Exception:
        pass


def install_timeout_floor() -> bool:
    """
    Give every un-timed request a deadline. Idempotent; returns True if it took.

    Deliberately NOT gated on PIPELINE_TELEMETRY. The floor is a reliability
    guarantee, not observability, and it must not disappear because someone
    turned the dashboard off -- an unbounded socket wait is exactly the failure
    that leaves no trace to observe in the first place.

    A no-op once install() has patched, since that wrapper applies the same
    default; this exists so the floor still holds with telemetry disabled.
    """
    global _timeout_floor_installed
    with _lock:
        if _timeout_floor_installed or _installed:
            return False
        try:
            import requests.sessions as _sessions
        except Exception:
            return False
        original = _sessions.Session.request

        def timed(self, method, url, *args, **kwargs):
            if kwargs.get("timeout") is None:
                kwargs["timeout"] = _DEFAULT_TIMEOUT
            return original(self, method, url, *args, **kwargs)

        timed.__wrapped__ = original
        _sessions.Session.request = timed
        _timeout_floor_installed = True
    return True


def install(source: str = "unknown", start_writer: bool = True) -> bool:
    """Patch requests and start the writer. Idempotent; returns True if it took."""
    global _installed, _source, _timeout_floor_installed, _writer, _standby
    if os.environ.get("PIPELINE_TELEMETRY", "1") == "0":
        # The deadline still applies -- see install_timeout_floor.
        install_timeout_floor()
        return False
    with _lock:
        if _installed:
            _source = source or _source
            return False
        try:
            import requests.sessions as _sessions
        except Exception:
            return False

        _source = source or "unknown"
        # If the bare floor got in first, unwrap it: this wrapper applies the
        # same default, and stacking them would double every call's frames for
        # nothing.
        if _timeout_floor_installed:
            _sessions.Session.request = getattr(
                _sessions.Session.request, "__wrapped__",
                _sessions.Session.request)
            _timeout_floor_installed = False
        original = _sessions.Session.request

        def instrumented(self, method, url, *args, **kwargs):
            started = time.perf_counter()
            # `timeout` is keyword-only on Session.request, so a caller who set
            # one always appears here and is never overridden.
            if kwargs.get("timeout") is None:
                kwargs["timeout"] = _DEFAULT_TIMEOUT
            try:
                resp = original(self, method, url, *args, **kwargs)
            except Exception as exc:
                # A transport failure is the single most valuable event this
                # module captures — a 403 wall or a DNS death shows up here
                # before any downstream check notices missing data.
                try:
                    record(_with_params(url, kwargs.get("params")), method,
                           None, False,
                           int((time.perf_counter() - started) * 1000),
                           error=f"{type(exc).__name__}: {exc}"[:300])
                except Exception:
                    pass
                raise
            try:
                elapsed = int((time.perf_counter() - started) * 1000)
                credits, remaining = _credits_from(resp)
                try:
                    size = int(resp.headers.get("content-length") or len(resp.content))
                except Exception:
                    size = None
                err = None if resp.ok else f"HTTP {resp.status_code}"
                # The PREPARED url is the one actually sent: it carries params=
                # merged in, and any redirect the session followed.
                final = getattr(getattr(resp, "request", None), "url", None) or url
                record(final, method, resp.status_code, bool(resp.ok), elapsed,
                       resp_bytes=size, credits=credits,
                       quota_remaining=remaining, error=err)
            except Exception:
                pass
            return resp

        instrumented.__wrapped__ = original          # so tests can assert/unwrap
        _sessions.Session.request = instrumented

        # curl_cffi is a SEPARATE http stack (it replays a browser TLS
        # fingerprint), so patching requests does not reach it. Nothing in the
        # pipeline imports it today — only the DK freshness collector — but a
        # feed that records nothing looks identical to a feed that is down, and
        # that is precisely the confusion this dashboard exists to remove.
        _patch_curl_cffi()

        _installed = True

    if start_writer:
        # Still a daemon: a process that never reaches atexit (os._exit, a
        # kill) must not be held open by its telemetry. _flush_on_exit is what
        # gives it the time to finish.
        _writer = threading.Thread(target=_writer_loop, name="api-telemetry",
                                   daemon=True)
        _writer.start()
        _standby = threading.Thread(target=_standby_loop,
                                    name="api-telemetry-exit", daemon=True)
        _standby.start()
        atexit.register(_flush_on_exit)
    return True


def stats() -> dict:
    return {"installed": _installed, "source": _source, "queued": _q.qsize(),
            "recorded": _recorded, "dropped": _dropped}
