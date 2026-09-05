"""
Shared plumbing for the worker's watches.

Extracted 2026-09-03 when the ModelCalibration judgement pass moved to the
worker and became the second watch. CLAUDE.md §1b: prefer a shared helper the
loops call over a per-watch implementation, and the test is mechanical --
"if this had been a problem in the other watch, would we have noticed?"

Both pieces here exist because they were got WRONG once already:

  * `query_rows` rolls back. psycopg aborts the whole transaction on a failed
    statement, so a caught-but-not-rolled-back error turns one broken query
    into every subsequent one failing with "current transaction is aborted".
    That is bug #390, fixed in tracking/system_health.py, then found again in
    scripts/pipeline_report.py on the watch's FIRST live run (#417), where it
    turned one bad section into six and made the post read "0 picks" against a
    real 14.

  * `post_and_ledger` posts FIRST and ledgers only on confirmation. §7: nothing
    is ledgered unless a POST confirmed, so a `kind` with zero rows in
    `push_sent` means it has NEVER succeeded. Without that a watch is
    unverifiable -- it either posted or it did not and no query can tell you
    which, which is the same blindness that moving off the agent was meant to
    end.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from loguru import logger


def query_rows(conn, sql: str, params=(), *, label: str = "watch"):
    """Run a query; on failure log, ROLL BACK, and return [] rather than raise.

    The rollback is the load-bearing half — see the module docstring.
    """
    try:
        return conn.execute(sql, params).fetchall()
    except Exception as exc:  # noqa: BLE001 — one bad query must not sink a watch
        logger.warning(f"{label}: query failed: {exc}")
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        return []


def post_and_ledger(conn, kind: str, run_day: date, post) -> bool:
    """Post via `post()`, and record it in `push_sent` ONLY if it confirmed.

    `post` returns something truthy on success (the notifier's `_post` returns
    a message id, and None on failure), so it doubles as the confirmation.

    One row per (kind, day): `lock_key` is the ET run date and the insert is
    ON CONFLICT DO NOTHING, so a retry or a second container cannot
    double-count a run.
    """
    if not post():
        logger.warning(f"{kind}: the post did not confirm — not ledgered")
        return False
    try:
        conn.execute(
            "INSERT INTO push_sent (lock_key, kind, sent_at) "
            "VALUES (%s, %s, %s) ON CONFLICT (lock_key, kind) DO NOTHING",
            (f"{kind}:{run_day.isoformat()}", kind,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    except Exception:  # noqa: BLE001 — a failed ledger must not lose the report
        logger.exception(f"{kind}: posted but could not ledger")
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False
    return True
