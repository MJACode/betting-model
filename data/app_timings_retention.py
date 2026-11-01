"""Delete app_timings rows older than APP_TIMINGS_RETENTION_DAYS.

The phone writes a row per Supabase read. The Live tab polls often enough
that the table would grow without a bound. 45 days keeps the 7-day p50/p90
window in docs/app_timings.md, plus a month of history behind it, and drops
the rest. The daily pipeline calls prune_app_timings once a morning.

The per-caller cap lives in log_app_timings (hand migration
app_timings_cap_2026_11_01.sql). This module does not change that function
and does not need the migration: it only deletes by received_at.
"""

from __future__ import annotations

APP_TIMINGS_RETENTION_DAYS = 45
_BATCH = 5_000

_DELETE = """
DELETE FROM app_timings
 WHERE id IN (
       SELECT id FROM app_timings
        WHERE received_at < now() - make_interval(days => %s)
        ORDER BY received_at
        LIMIT %s
 )
"""


def prune_app_timings(conn=None, *, days: int | None = None, batch: int = _BATCH) -> int:
    """Delete rows older than `days`. Returns how many were deleted.

    Pass `conn` in tests. With no connection, opens one and closes it.
    Commits each batch so a long backlog does not hold one transaction open.
    """
    if days is None:
        days = APP_TIMINGS_RETENTION_DAYS
    if days < 1:
        raise ValueError(f"retention days must be >= 1, got {days}")
    if batch < 1:
        raise ValueError(f"batch must be >= 1, got {batch}")
    own = conn is None
    if own:
        from data.db import get_connection
        conn = get_connection()
    deleted = 0
    try:
        while True:
            cur = conn.execute(_DELETE, (days, batch))
            n = cur.rowcount
            conn.commit()
            if n is None or n < 0:
                raise RuntimeError(f"app_timings prune reported rowcount {n}")
            deleted += n
            if n < batch:
                return deleted
    finally:
        if own:
            conn.close()
