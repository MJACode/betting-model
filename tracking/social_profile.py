"""One queued update of the @SignalBasePicks X profile.

Pick posts, recap posts, and social_post_queue are not this module. The
5-minute job calls drain_social_profile after it drains the post queue.
A row is claimed with UPDATE ... WHERE status='queued' and committed
before the HTTP call, so a second drain does not send it again.

POST https://api.x.com/1.1/account/update_profile.json, form fields name,
description, and url, signed with the same OAuth 1.0a header as a tweet.
The form fields are part of the signature. RUN_X_PUBLISHER=0 leaves the
row queued. An HTTP 4xx, including 429, is failed and is not retried. A
5xx or a timeout is failed and is not retried either: the claim already
took the row off queued, and the update may already have landed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

LOAD_SQL = (
    "SELECT id FROM social_profile_update "
    "WHERE status = 'queued' ORDER BY id"
)
CLAIM_SQL = (
    "UPDATE social_profile_update SET status = 'failed', error = 'claimed' "
    "WHERE id = %s AND status = 'queued' "
    "RETURNING id, name, description, url"
)
FINISH_SQL = (
    "UPDATE social_profile_update "
    "SET status = %s, response = %s, error = %s, applied_at = %s "
    "WHERE id = %s AND status = 'failed' AND error = 'claimed' RETURNING id"
)
RELEASE_SQL = (
    "UPDATE social_profile_update SET status = 'queued', error = NULL "
    "WHERE id = %s AND status = 'failed' AND error = 'claimed' RETURNING id"
)


def _missing_table(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "social_profile_update" in text and "does not exist" in text


def _can_post() -> bool:
    from tracking.x_publisher import _creds, _enabled
    return _enabled() and _creds() is not None


def _finish(conn, row_id, status: str, response: str | None,
            error: str | None, applied_at) -> None:
    conn.execute(FINISH_SQL, (
        status,
        (response or None) and str(response)[:4000],
        (error or None) and str(error)[:500],
        applied_at,
        row_id,
    ))
    conn.commit()


def drain_social_profile(conn, *, update=None, now: datetime | None = None) -> dict:
    """Apply each queued profile row once. Does not tweet.

    A missing table is a no-op. RUN_X_PUBLISHER=0 or missing credentials
    leaves every row queued.
    """
    clock = now or datetime.now(timezone.utc)
    if not _can_post():
        return {"status": "skipped", "reason": "x publisher off or credentials missing",
                "applied": 0, "results": []}
    if update is None:
        from tracking.x_publisher import update_profile
        update = update_profile
    try:
        pending = conn.execute(LOAD_SQL).fetchall()
    except Exception as exc:  # noqa: BLE001 — a missing table is not a crash
        if _missing_table(exc):
            return {"status": "no_table", "applied": 0, "results": []}
        raise

    results = []
    applied = 0
    for record in pending:
        row_id = record[0]
        claimed = conn.execute(CLAIM_SQL, (row_id,)).fetchone()
        conn.commit()
        if not claimed:
            continue
        _id, name, description, url = claimed
        try:
            outcome = update(name=name, description=description, url=url)
        except Exception as exc:  # noqa: BLE001
            detail = f"update raised: {exc}"[:500]
            _finish(conn, row_id, "failed", None, detail, None)
            results.append({"id": row_id, "status": "failed", "error": detail})
            continue
        kind = getattr(outcome, "outcome", None)
        detail = getattr(outcome, "detail", "") or ""
        body = getattr(outcome, "body", "") or ""
        if kind == "skipped":
            conn.execute(RELEASE_SQL, (row_id,))
            conn.commit()
            results.append({"id": row_id, "status": "queued", "error": detail or kind})
            continue
        if kind == "updated":
            _finish(conn, row_id, "done", body, None, clock)
            logger.info("social profile %s updated", row_id)
            results.append({"id": row_id, "status": "done"})
            applied += 1
            continue
        # rejected (4xx, including 429) and transport: do not retry.
        error = detail or kind or "profile update failed"
        _finish(conn, row_id, "failed", body or None, error, None)
        results.append({"id": row_id, "status": "failed", "error": error})
    return {"status": "ok", "applied": applied, "results": results}
