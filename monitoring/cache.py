"""A tiny shared TTL cache for the dashboard's slow panels.

WHY THIS EXISTS
The live panels (calls, picks) are cheap and tail an index. The operational
ones are not: the model performance query reads a 132k-row matview (285ms,
~3.7k disk reads) and the picks-over-time query scans two weeks of picks. Those
run on the same 10s meta tick, and #291 was a whole session spent recovering a
Disk IO budget from exactly this shape of repeated read.

Two properties matter, and they are the reason this is a module-level cache
rather than a per-connection one:

  * cost is independent of VIEWER COUNT — five people watching the dashboard
    cost the same as one, because they share the entry;
  * cost is independent of POLL RATE — the meta tick can stay at 10s while a
    panel behind a 300s TTL only actually hits the database 12 times an hour.

Staleness is the deliberate trade. Model records change at settlement, once a
day; a five-minute-old ROI is not a worse number, and every cached panel ships
its own `age_s` so the UI can say how old it is rather than implying "now".
"""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_entries: dict[str, tuple[float, object]] = {}


def cached(key: str, ttl: float, fn):
    """Return fn()'s value, recomputing only when the entry is older than ttl.

    On a refresh failure the STALE value is served rather than an error: a
    monitoring panel showing a five-minute-old number is strictly better than
    one showing nothing because the pooler dropped a connection.
    """
    now = time.time()
    with _lock:
        hit = _entries.get(key)
        if hit is not None and now - hit[0] < ttl:
            return hit[1]

    try:
        value = fn()
    except Exception:
        with _lock:
            hit = _entries.get(key)
        if hit is not None:
            return hit[1]
        raise

    with _lock:
        _entries[key] = (now, value)
    return value


def age(key: str) -> float | None:
    """Seconds since `key` was last computed, or None if never."""
    with _lock:
        hit = _entries.get(key)
    return None if hit is None else time.time() - hit[0]


def clear() -> None:
    with _lock:
        _entries.clear()
