"""Fail a pull request while a daily pipeline run is in progress.

Source of truth is ``pipeline_runs``: ``run_kind = 'daily'``,
``finished_at`` IS NULL, and ``started_at::timestamptz`` inside the last
75 minutes. That is ``tracking.daily_retry.MAX_DAILY_RUN``. An older
unfinished row is the orphan the boot sweep stamps ``aborted``, not a
live daily, and it must not block every merge.

``started_at`` is text. Compare it only after ``::timestamptz``.

When ``DATABASE_URL`` is unset (a fork PR, or the secret is missing),
fall back to the clock: 06:00 America/New_York plus those same 75
minutes. A catch-up daily outside that window is visible only to the
query.

Emergency bypass, either one:

* the pull-request label ``emergency-merge`` (the workflow re-runs when
  the label is added)
* the literal ``bypass-daily-gate`` in the pull-request body, then
  re-run the failed check

A repository admin can also merge with GitHub's bypass of branch
protections, once this check is required on ``master``. The workflow
alone reports the status. It blocks merges only after that status is
required.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Lockstep with tracking.daily_retry.MAX_DAILY_RUN. A test pins the two.
MAX_OPEN_DAILY = timedelta(minutes=75)
DAILY_HOUR = 6
DAILY_MINUTE = 0

EMERGENCY_LABEL = "emergency-merge"
BYPASS_MARKER = "bypass-daily-gate"

BYPASS_HELP = (
    "Emergency bypass: add the label emergency-merge "
    "(this check re-runs when the label is added), or put "
    "bypass-daily-gate in the PR body and re-run this check. "
    "A repo admin can also merge with GitHub's bypass of branch protections."
)

# started_at is text. The cast is the comparison. The bound is a parameter
# so the 75 minutes live in one place (MAX_OPEN_DAILY), not in the SQL.
OPEN_DAILY_SQL = """
SELECT run_id, started_at
FROM pipeline_runs
WHERE run_kind = 'daily'
  AND finished_at IS NULL
  AND started_at::timestamptz >= %s
ORDER BY started_at
"""


def clock_blocks(now: datetime) -> bool:
    """True during 06:00 ET plus MAX_OPEN_DAILY, when the database is unread."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    et = now.astimezone(ET)
    start = et.replace(
        hour=DAILY_HOUR, minute=DAILY_MINUTE, second=0, microsecond=0,
    )
    return start <= et < start + MAX_OPEN_DAILY


def bypass_reason(labels, body: str | None) -> str | None:
    names = list(labels or [])
    if EMERGENCY_LABEL in names:
        return f"label {EMERGENCY_LABEL}"
    if BYPASS_MARKER in (body or ""):
        return f"PR body contains {BYPASS_MARKER}"
    return None


def gate_decision(
    *,
    now: datetime,
    labels,
    body: str | None,
    db_configured: bool,
    open_run_ids: list[str],
    query_error: str | None,
) -> tuple[bool, str]:
    """Return ``(block, message)``. ``block`` fails the GitHub check."""
    why = bypass_reason(labels, body)
    if why:
        return False, f"bypass: {why}"
    if db_configured:
        if query_error:
            return True, (
                f"cannot read pipeline_runs ({query_error}); "
                f"blocking the merge. {BYPASS_HELP}"
            )
        if open_run_ids:
            ids = ", ".join(open_run_ids)
            return True, (
                f"daily pipeline in progress ({ids}). "
                f"Merge waits until that row has finished_at set. {BYPASS_HELP}"
            )
        return False, "no open daily in pipeline_runs"
    if clock_blocks(now):
        return True, (
            "DATABASE_URL is not set, so this check cannot read pipeline_runs. "
            "Blocking during the 6:00am ET daily window "
            f"({int(MAX_OPEN_DAILY.total_seconds() // 60)} minutes). "
            f"{BYPASS_HELP}"
        )
    return False, (
        "DATABASE_URL is not set and the clock is outside the 6:00am ET "
        "daily window. A catch-up daily outside that window is not visible "
        "without the database."
    )


def open_since(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc) - MAX_OPEN_DAILY


def query_open_daily_ids(conn, now: datetime) -> list[str]:
    """Run OPEN_DAILY_SQL. ``conn`` is a psycopg2 connection."""
    with conn.cursor() as cur:
        cur.execute(OPEN_DAILY_SQL, (open_since(now),))
        rows = cur.fetchall()
    return [str(row[0]) for row in rows or [] if row and row[0]]


def _event_labels_and_body(event: dict) -> tuple[list[str], str]:
    pr = event.get("pull_request") or {}
    labels = []
    for item in pr.get("labels") or []:
        if isinstance(item, dict) and item.get("name"):
            labels.append(str(item["name"]))
        elif isinstance(item, str):
            labels.append(item)
    return labels, pr.get("body") or ""


def main(argv: list[str] | None = None) -> int:
    now = datetime.now(timezone.utc)
    event: dict = {}
    path = os.environ.get("GITHUB_EVENT_PATH")
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            event = json.load(fh)
    labels, body = _event_labels_and_body(event)
    if os.environ.get("DAILY_GATE_BYPASS") in ("1", "true", "True"):
        labels = list(labels) + [EMERGENCY_LABEL]

    db_url = (os.environ.get("DATABASE_URL") or "").strip()
    open_ids: list[str] = []
    query_error = None
    if db_url:
        try:
            import psycopg2
            conn = psycopg2.connect(db_url)
            try:
                open_ids = query_open_daily_ids(conn, now)
            finally:
                conn.close()
        except Exception as exc:  # noqa: BLE001 — a failed read blocks the merge
            query_error = f"{type(exc).__name__}: {exc}"

    block, message = gate_decision(
        now=now,
        labels=labels,
        body=body,
        db_configured=bool(db_url),
        open_run_ids=open_ids,
        query_error=query_error,
    )
    print(message)
    if block:
        print(f"::error::{message}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
