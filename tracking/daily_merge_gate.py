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

05:45–06:20 America/New_York blocks even when the ledger has no open
row. The 6:00am start can land between cron ticks, and a ``:00`` tick
is often late, so a green check from 05:50 would otherwise stay green
across the start.

The pull-request job runs from the base branch (``pull_request_target``)
and does not check out the PR head, so the script that reads the
database is the one on master. ``--refresh-open-prs`` is the scheduled
job on master: it posts a check run named ``daily pipeline not running``
on every open PR head, which is the name the pull-request job already
uses. The newest check with that name is the one branch protection reads.

Emergency bypass, either one:

* the pull-request label ``emergency-merge`` (the workflow re-runs when
  the label is added)
* the literal ``bypass-daily-gate`` in the pull-request body, when the
  author association is OWNER or MEMBER, then re-run the failed check

A repository admin can also merge with GitHub's bypass of branch
protections, once this check is required on ``master``. The workflow
alone reports the status. It blocks merges only after that status is
required.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Lockstep with tracking.daily_retry.MAX_DAILY_RUN. A test pins the two.
MAX_OPEN_DAILY = timedelta(minutes=75)
DAILY_HOUR = 6
DAILY_MINUTE = 0

# Across the 6:00am ET start. Inclusive of 05:45, exclusive of 06:20.
# A cron that is late past 06:20 is outside this stretch; an open row
# still blocks through the database.
DAILY_START_BLOCK_HOUR = 5
DAILY_START_BLOCK_MINUTE = 45
DAILY_START_BLOCK_END_HOUR = 6
DAILY_START_BLOCK_END_MINUTE = 20

EMERGENCY_LABEL = "emergency-merge"
BYPASS_MARKER = "bypass-daily-gate"
# Anyone can edit a PR body on a public repo. The label requires write
# access. The body marker does not.
BODY_BYPASS_ASSOCIATIONS = frozenset({"OWNER", "MEMBER"})

# The Actions job name. A check run posted by the scheduled refresh uses
# the same name, so branch protection sees one check and the latest run.
CHECK_NAME = "daily pipeline not running"

BYPASS_HELP = (
    "Emergency bypass: add the label emergency-merge "
    "(this check re-runs when the label is added), or, as an owner or "
    "member, put bypass-daily-gate in the PR body and re-run this check. "
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


def _as_et(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(ET)


def clock_blocks(now: datetime) -> bool:
    """True during 06:00 ET plus MAX_OPEN_DAILY, when the database is unread."""
    et = _as_et(now)
    start = et.replace(
        hour=DAILY_HOUR, minute=DAILY_MINUTE, second=0, microsecond=0,
    )
    return start <= et < start + MAX_OPEN_DAILY


def daily_start_blocks(now: datetime) -> bool:
    """True from 05:45 ET until 06:20 ET, whatever the ledger says.

    The scheduled daily starts at 06:00. A check posted at 05:50 stays
    green until the next cron tick, and that tick is often late.
    """
    et = _as_et(now)
    start = et.replace(
        hour=DAILY_START_BLOCK_HOUR,
        minute=DAILY_START_BLOCK_MINUTE,
        second=0,
        microsecond=0,
    )
    end = et.replace(
        hour=DAILY_START_BLOCK_END_HOUR,
        minute=DAILY_START_BLOCK_END_MINUTE,
        second=0,
        microsecond=0,
    )
    return start <= et < end


def bypass_reason(
    labels,
    body: str | None,
    author_association: str | None = None,
) -> str | None:
    names = list(labels or [])
    if EMERGENCY_LABEL in names:
        return f"label {EMERGENCY_LABEL}"
    association = (author_association or "").strip().upper()
    if (
        BYPASS_MARKER in (body or "")
        and association in BODY_BYPASS_ASSOCIATIONS
    ):
        return f"PR body contains {BYPASS_MARKER} ({association})"
    return None


def gate_decision(
    *,
    now: datetime,
    labels,
    body: str | None,
    db_configured: bool,
    open_run_ids: list[str],
    query_error: str | None,
    author_association: str | None = None,
) -> tuple[bool, str]:
    """Return ``(block, message)``. ``block`` fails the GitHub check."""
    why = bypass_reason(labels, body, author_association)
    if why:
        return False, f"bypass: {why}"
    if daily_start_blocks(now):
        return True, (
            "Blocking 05:45–06:20 America/New_York, across the 6:00am "
            "daily start. A check from the previous cron tick stays green "
            "until the next tick, and that tick is often late. "
            f"{BYPASS_HELP}"
        )
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


def load_open_daily(now: datetime) -> tuple[bool, list[str], str | None]:
    """``(db_configured, open run ids, error)``.

    ``db_configured`` is false when ``DATABASE_URL`` is unset. The clock
    fallback in ``gate_decision`` is that case. A connection or query
    error is configured and blocking: an unread ledger is not an empty one.
    """
    db_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not db_url:
        return False, [], None
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        try:
            return True, query_open_daily_ids(conn, now), None
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — a failed read blocks the merge
        return True, [], f"{type(exc).__name__}: {exc}"


def checks_for_pull_requests(
    prs,
    *,
    now: datetime,
    db_configured: bool,
    open_run_ids: list[str],
    query_error: str | None,
) -> list[dict]:
    """One completed check-run body per open PR that has a head sha.

    The database result is shared. Bypass is per PR: a label or a body
    marker on that PR, not on its neighbor.
    """
    out = []
    for pr in prs or []:
        if not isinstance(pr, dict):
            continue
        head = pr.get("head") or {}
        sha = head.get("sha") if isinstance(head, dict) else None
        if not sha:
            continue
        labels = []
        for item in pr.get("labels") or []:
            if isinstance(item, dict) and item.get("name"):
                labels.append(str(item["name"]))
            elif isinstance(item, str):
                labels.append(item)
        block, message = gate_decision(
            now=now,
            labels=labels,
            body=pr.get("body") or "",
            db_configured=db_configured,
            open_run_ids=open_run_ids,
            query_error=query_error,
            author_association=pr.get("author_association"),
        )
        title = message if len(message) <= 80 else message[:77] + "..."
        out.append({
            "name": CHECK_NAME,
            "head_sha": sha,
            "status": "completed",
            "conclusion": "failure" if block else "success",
            "output": {"title": title, "summary": message},
        })
    return out


def _github_json(method: str, url: str, token: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:200]
        raise RuntimeError(f"GitHub {exc.code} {method} {url}: {detail}") from exc
    return json.loads(raw) if raw else None


def list_open_master_prs(repo: str, token: str) -> list[dict]:
    """Open PRs whose base is master. One page is 100; follow until short."""
    prs: list[dict] = []
    page = 1
    while page <= 20:
        url = (
            f"https://api.github.com/repos/{repo}/pulls"
            f"?state=open&base=master&per_page=100&page={page}"
        )
        batch = _github_json("GET", url, token) or []
        if not isinstance(batch, list):
            raise RuntimeError("GitHub pulls list was not a list")
        prs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return prs


def refresh_open_prs() -> int:
    """Post a fresh check on every open PR head. Exit 0 when the posts land.

    A blocked PR is a failed check, not a failed job. The job fails when
    the PR list itself cannot be read, or every post fails.
    """
    repo = (os.environ.get("GITHUB_REPOSITORY") or "").strip()
    token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    if not repo or not token:
        print("GITHUB_REPOSITORY and GITHUB_TOKEN are required to refresh checks")
        return 1
    now = datetime.now(timezone.utc)
    db_configured, open_ids, query_error = load_open_daily(now)
    try:
        prs = list_open_master_prs(repo, token)
    except Exception as exc:  # noqa: BLE001
        print(f"could not list open pull requests: {type(exc).__name__}: {exc}")
        return 1
    payloads = checks_for_pull_requests(
        prs,
        now=now,
        db_configured=db_configured,
        open_run_ids=open_ids,
        query_error=query_error,
    )
    failed = 0
    for payload in payloads:
        url = f"https://api.github.com/repos/{repo}/check-runs"
        try:
            _github_json("POST", url, token, payload)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            sha = str(payload.get("head_sha") or "")[:7]
            print(f"check for {sha} failed: {type(exc).__name__}: {exc}")
    print(
        f"refreshed {len(payloads) - failed} of {len(payloads)} "
        f"open pull requests"
    )
    if payloads and failed == len(payloads):
        return 1
    return 0


def _event_labels_and_body(event: dict) -> tuple[list[str], str, str]:
    pr = event.get("pull_request") or {}
    labels = []
    for item in pr.get("labels") or []:
        if isinstance(item, dict) and item.get("name"):
            labels.append(str(item["name"]))
        elif isinstance(item, str):
            labels.append(item)
    return (
        labels,
        pr.get("body") or "",
        str(pr.get("author_association") or ""),
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--refresh-open-prs" in argv:
        return refresh_open_prs()
    now = datetime.now(timezone.utc)
    event: dict = {}
    path = os.environ.get("GITHUB_EVENT_PATH")
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            event = json.load(fh)
    labels, body, author_association = _event_labels_and_body(event)
    if os.environ.get("DAILY_GATE_BYPASS") in ("1", "true", "True"):
        labels = list(labels) + [EMERGENCY_LABEL]

    db_configured, open_ids, query_error = load_open_daily(now)
    block, message = gate_decision(
        now=now,
        labels=labels,
        body=body,
        db_configured=db_configured,
        open_run_ids=open_ids,
        query_error=query_error,
        author_association=author_association,
    )
    print(message)
    if block:
        print(f"::error::{message}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
