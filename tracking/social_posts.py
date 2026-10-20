"""Manual posts and threads to @SignalBasePicks.

The pick slate and the results recaps stay in tracking.x_publisher. This
module does not call notify_x_picks, notify_x_results, or notify_x_period,
and it does not write push_sent. A row here is a marketing post a person
queued. The worker drains it on its own schedule.

How a row gets to X
    Insert into social_post_queue (SQL editor, or `python -m tracking.social_posts
    --enqueue`). The worker job social_post_queue runs every 5 minutes on the
    pipeline service, the same service that already holds X_API_KEY,
    X_API_SECRET, X_ACCESS_TOKEN, and X_ACCESS_TOKEN_SECRET. No new secret.

    python -m tracking.social_posts            # dry run, posts nothing
    python -m tracking.social_posts --drain    # post due rows now

Idempotency
    A row is claimed with UPDATE ... WHERE status='queued' AND tweet_id IS NULL.
    The claim is committed before the HTTP call. A second drain sees posting
    and does not send. After a confirmed tweet id the status is posted, and a
    later pass does not send it again. A row that already has a tweet_id is
    never sent, whatever its status was edited back to.

    A 429 is put back to queued: X did not create the tweet. An HTTP 4xx is
    failed: X refused. A timeout or a 5xx becomes uncertain and is NOT retried,
    because the tweet may already exist. A posting row whose claim is older
    than the lease, with no tweet id, becomes uncertain for the same reason.
    Requeue only by hand, after checking the account:

        UPDATE social_post_queue
           SET status = 'queued', error = NULL, claimed_at = NULL
         WHERE id = <id> AND status IN ('failed', 'uncertain')
           AND tweet_id IS NULL;

Threads
    Rows that share thread_key post in position order. Position 1 is the root.
    Each later post is a reply to the previous position's tweet_id. A gap, a
    failed row, or an uncertain row stops the thread. Nothing later is sent.

Links and pinning
    Pick posts still refuse URLs. A manual row whose text contains a URL is
    not sent unless allow_link is true, because X bills a URL at $0.20 instead
    of $0.015. Pinning is stored and not performed: the v2 API this client
    signs has no pin-tweet method. pin_status becomes 'unsupported' and
    pin_note says to pin the URL by hand.

The drain posts nothing when RUN_X_PUBLISHER=0 or any of the four keys is
missing. It does not change those switches.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

THREAD_KEY = "all-time-ledger-2026-10-20"
CLAIM_LEASE = timedelta(minutes=10)
TWEET_URL = "https://x.com/signalbasepicks/status/{tweet_id}"
PIN_NOTE = (
    "X API v2 with this app's OAuth 1.0a token can POST /2/tweets and reply. "
    "It has no pin-tweet method (POST /2/users/:id/pinned_lists pins a List, "
    "not a post). Pin this post by hand: {url}"
)

LOAD_SQL = (
    "SELECT id, thread_key, position, body, allow_link, pin, "
    "scheduled_at, status, tweet_id, claimed_at "
    "FROM social_post_queue ORDER BY thread_key, position"
)
RELOAD_SQL = (
    "SELECT id, thread_key, position, body, allow_link, pin, "
    "scheduled_at, status, tweet_id, claimed_at "
    "FROM social_post_queue WHERE id = %s"
)
CLAIM_SQL = (
    "UPDATE social_post_queue SET status = 'posting', claimed_at = %s, error = NULL "
    "WHERE id = %s AND status = 'queued' AND tweet_id IS NULL RETURNING id"
)
FAIL_QUEUED_SQL = (
    "UPDATE social_post_queue SET status = 'failed', error = %s "
    "WHERE id = %s AND status = 'queued' AND tweet_id IS NULL RETURNING id"
)
FINISH_SQL = (
    "UPDATE social_post_queue SET status = %s, error = %s, tweet_id = %s, "
    "tweet_url = %s, posted_at = %s, pin_status = %s, pin_note = %s, claimed_at = %s "
    "WHERE id = %s AND status = 'posting' AND tweet_id IS NULL RETURNING id"
)
HEAL_SQL = (
    "UPDATE social_post_queue SET status = 'posted', tweet_url = %s, "
    "posted_at = %s, pin_status = %s, pin_note = %s "
    "WHERE id = %s AND tweet_id IS NOT NULL AND status <> 'posted' RETURNING id"
)
EXISTS_SQL = "SELECT 1 FROM social_post_queue WHERE thread_key = %s LIMIT 1"
INSERT_SQL = (
    "INSERT INTO social_post_queue "
    "(thread_key, position, body, allow_link, pin, scheduled_at) "
    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id"
)

_COLUMNS = (
    "id", "thread_key", "position", "body", "allow_link", "pin",
    "scheduled_at", "status", "tweet_id", "claimed_at",
)
_OPEN = ("queued", "posting")


class QueueRejected(ValueError):
    """The rows were not inserted. Nothing was posted."""


def _as_utc(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _row(record) -> dict:
    return dict(zip(_COLUMNS, record))


def _can_post() -> bool:
    from tracking.x_publisher import _creds, _enabled
    return _enabled() and _creds() is not None


def _has_link(text: str) -> bool:
    from tracking.x_publisher import _assert_no_link
    try:
        _assert_no_link(text)
    except ValueError:
        return True
    return False


def _pin_fields(row: dict, tweet_url: str | None) -> tuple[str, str | None]:
    if row.get("pin"):
        note = PIN_NOTE.format(url=tweet_url or "")
        return "unsupported", note
    return "not_requested", None


def _missing_table(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "social_post_queue" in text and "does not exist" in text


def posts_to_rows(thread_key: str, bodies: list[str], *, pin_root: bool,
                  allow_link: bool, scheduled_at: datetime) -> list[dict]:
    """The rows an enqueue would insert. Raises QueueRejected and writes nothing."""
    key = (thread_key or "").strip()
    if not key or len(key) > 80 or any(c in key for c in " \n\r\t"):
        raise QueueRejected("thread_key must be 1-80 characters with no whitespace")
    if not bodies:
        raise QueueRejected("a thread needs at least one post")
    from tracking.x_publisher import MAX_TWEET
    rows = []
    for index, body in enumerate(bodies, start=1):
        if not isinstance(body, str) or not body.strip():
            raise QueueRejected(f"position {index} is empty")
        if len(body) > MAX_TWEET:
            raise QueueRejected(
                f"position {index} is {len(body)} characters; the limit is {MAX_TWEET}"
            )
        linked = _has_link(body)
        if linked and not allow_link:
            raise QueueRejected(
                f"position {index} contains a URL. Pass --allow-link to queue it. "
                "X bills a URL at $0.20 instead of $0.015. Nothing was inserted."
            )
        rows.append({
            "thread_key": key,
            "position": index,
            "body": body,
            "allow_link": linked,
            "pin": bool(pin_root and index == 1),
            "scheduled_at": scheduled_at,
        })
    return rows


def enqueue(conn, thread_key: str, bodies: list[str], *, pin_root: bool = False,
            allow_link: bool = False, scheduled_at: datetime | None = None) -> list[int]:
    """Insert one thread. Does not post. Refuses a thread_key that already has a row."""
    when = _as_utc(scheduled_at) or datetime.now(timezone.utc)
    rows = posts_to_rows(
        thread_key, bodies, pin_root=pin_root, allow_link=allow_link, scheduled_at=when)
    key = rows[0]["thread_key"]
    try:
        if conn.execute(EXISTS_SQL, (key,)).fetchone():
            raise QueueRejected(f"thread {key} already has rows; nothing inserted")
        ids = []
        for row in rows:
            rec = conn.execute(INSERT_SQL, (
                row["thread_key"], row["position"], row["body"], row["allow_link"],
                row["pin"], row["scheduled_at"],
            )).fetchone()
            if not rec:
                raise QueueRejected("insert returned no id")
            ids.append(rec[0])
        conn.commit()
        return ids
    except QueueRejected:
        _rollback(conn)
        raise
    except Exception:
        _rollback(conn)
        raise


def _rollback(conn) -> None:
    rollback = getattr(conn, "rollback", None)
    if rollback is None:
        return
    try:
        rollback()
    except Exception:  # noqa: BLE001 — the original error is the one to raise
        pass


def _load(conn) -> list[dict]:
    return [_row(record) for record in conn.execute(LOAD_SQL).fetchall()]


def _reload(conn, row_id) -> dict | None:
    record = conn.execute(RELOAD_SQL, (row_id,)).fetchone()
    return _row(record) if record else None


def _claim(conn, row_id, now: datetime) -> bool:
    claimed = conn.execute(CLAIM_SQL, (now, row_id)).fetchone()
    conn.commit()
    return claimed is not None


def _fail_queued(conn, row_id, error: str) -> None:
    conn.execute(FAIL_QUEUED_SQL, (error[:500], row_id))
    conn.commit()


def _finish(conn, row_id, *, status: str, error: str | None, tweet_id: str | None,
            tweet_url: str | None, posted_at: datetime | None, pin_status: str | None,
            pin_note: str | None, claimed_at: datetime | None) -> None:
    conn.execute(FINISH_SQL, (
        status, (error or None) and str(error)[:500], tweet_id, tweet_url, posted_at,
        pin_status, (pin_note or None) and str(pin_note)[:500], claimed_at, row_id,
    ))
    conn.commit()


def _heal(conn, row: dict, now: datetime) -> str:
    tweet_id = str(row["tweet_id"])
    url = TWEET_URL.format(tweet_id=tweet_id)
    pin_status, pin_note = _pin_fields(row, url)
    conn.execute(HEAL_SQL, (url, now, pin_status, pin_note, row["id"]))
    conn.commit()
    return url


def _threads(rows: list[dict]) -> list[list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["thread_key"], []).append(row)
    groups = list(grouped.values())

    def _key(group: list[dict]):
        dues = [_as_utc(r["scheduled_at"]) for r in group if r["status"] == "queued"]
        dues = [item for item in dues if item is not None]
        first = min(dues) if dues else datetime.max.replace(tzinfo=timezone.utc)
        return (first, group[0]["thread_key"])

    groups.sort(key=_key)
    return groups


def _actionable(group: list[dict]) -> bool:
    if all(r["status"] == "posted" and r["tweet_id"] for r in group):
        return False
    return any(r["status"] in _OPEN for r in group)


def drain_social_posts(conn, *, dry_run: bool = False, now: datetime | None = None,
                       deliver=None) -> dict:
    """Post due queued rows. Posted rows are left alone. Never raises for a missing table.

    dry_run writes nothing and does not call the network. The default deliver
    is tracking.x_publisher.deliver_tweet, which uses the existing credentials.
    """
    clock = _as_utc(now) or datetime.now(timezone.utc)
    if not dry_run and not _can_post():
        return {"status": "skipped", "reason": "x publisher off or credentials missing",
                "posted": 0, "results": []}
    try:
        groups = _threads(_load(conn))
    except Exception as exc:  # noqa: BLE001 — a missing table is not a crash
        if _missing_table(exc):
            return {"status": "no_table", "posted": 0, "results": []}
        raise

    if deliver is None:
        from tracking.x_publisher import deliver_tweet
        deliver = deliver_tweet

    results: list[dict] = []
    posted = 0
    stop_pass = False
    for group in groups:
        if stop_pass or not _actionable(group):
            continue
        parent_id = None
        expected = 1
        for row in group:
            position = int(row["position"])
            if position != expected:
                outcome = _stop_queued(
                    conn, row, dry_run,
                    f"position gap: expected {expected}, found {position}",
                    results)
                if outcome == "stop":
                    break
            expected = position + 1
            status = row["status"]
            tweet_id = row["tweet_id"]

            if tweet_id and status != "posted":
                url = None if dry_run else _heal(conn, row, clock)
                if dry_run:
                    url = TWEET_URL.format(tweet_id=tweet_id)
                parent_id = str(tweet_id)
                results.append(_result(row, "posted", tweet_id, url))
                continue
            if status == "posted":
                if not tweet_id:
                    results.append(_result(row, "uncertain", None, None,
                                           "posted with no tweet id"))
                    break
                parent_id = str(tweet_id)
                continue
            if status in ("failed", "uncertain"):
                break
            if status == "posting":
                claimed_at = _as_utc(row["claimed_at"])
                fresh = claimed_at is not None and claimed_at > clock - CLAIM_LEASE
                if fresh or dry_run:
                    results.append(_result(
                        row, "posting", None, None,
                        "claim is still inside the lease" if fresh else "dry run"))
                    break
                if not dry_run:
                    _finish(conn, row["id"], status="uncertain",
                            error="claim expired with no tweet id; not retried",
                            tweet_id=None, tweet_url=None, posted_at=None,
                            pin_status=None, pin_note=None, claimed_at=claimed_at)
                results.append(_result(
                    row, "uncertain", None, None,
                    "claim expired with no tweet id; not retried"))
                break
            if status != "queued":
                break

            scheduled_at = _as_utc(row["scheduled_at"])
            if scheduled_at is not None and scheduled_at > clock:
                break
            problem = _problem(row, parent_id)
            if problem:
                if not dry_run:
                    _fail_queued(conn, row["id"], problem)
                results.append(_result(row, "failed" if not dry_run else "would_fail",
                                       None, None, problem))
                break
            if dry_run:
                results.append(_result(
                    row, "would_post", None, None, reply_to=parent_id))
                parent_id = f"dry-run-{position}"
                continue

            if not _claim(conn, row["id"], clock):
                current = _reload(conn, row["id"])
                if current and current["tweet_id"]:
                    parent_id = str(current["tweet_id"])
                    continue
                break
            outcome, parent_id, stop_pass = _send(
                conn, row, parent_id, clock, deliver, results)
            posted += outcome
            if stop_pass or (parent_id is None and outcome == 0):
                break
        if stop_pass:
            break

    status = "dry_run" if dry_run else "ok"
    return {"status": status, "posted": posted, "results": results}


def _problem(row: dict, parent_id: str | None) -> str | None:
    from tracking.x_publisher import MAX_TWEET
    body = row["body"] or ""
    if not str(body).strip():
        return "empty post"
    if len(body) > MAX_TWEET:
        return f"{len(body)} characters; the limit is {MAX_TWEET}"
    if not row["allow_link"] and _has_link(body):
        return ("refusing to post: text contains a URL and allow_link is false "
                "(X bills a URL at $0.20 instead of $0.015)")
    if int(row["position"]) > 1 and not parent_id:
        return "no parent tweet id to reply to"
    return None


def _stop_queued(conn, row, dry_run: bool, error: str, results: list) -> str:
    if row["status"] == "queued" and not row["tweet_id"] and not dry_run:
        _fail_queued(conn, row["id"], error)
    results.append(_result(row, "failed" if not dry_run else "would_fail",
                           None, None, error))
    return "stop"


def _send(conn, row, parent_id, clock, deliver, results) -> tuple[int, str | None, bool]:
    reply_to = parent_id if int(row["position"]) > 1 else None
    try:
        if row["allow_link"]:
            logger.info(
                "social post %s allows a URL; X bills the link rate", row["id"])
        delivered = deliver(row["body"], reply_to=reply_to, allow_link=bool(row["allow_link"]))
    except Exception as exc:  # noqa: BLE001 — the claim must not be retried blindly
        detail = f"deliver raised: {exc}"[:500]
        _finish(conn, row["id"], status="uncertain", error=detail, tweet_id=None,
                tweet_url=None, posted_at=None, pin_status=None, pin_note=None,
                claimed_at=clock)
        results.append(_result(row, "uncertain", None, None, detail))
        return 0, None, True

    outcome = getattr(delivered, "outcome", None)
    detail = getattr(delivered, "detail", "") or ""
    if outcome in ("rate_limited", "dry_run"):
        # X did not create a tweet. Put the row back. A dry_run here means the
        # deliver function refused to send; the drain's own dry_run never claims.
        note = detail or outcome
        _finish(conn, row["id"], status="queued", error=note,
                tweet_id=None, tweet_url=None, posted_at=None, pin_status=None,
                pin_note=None, claimed_at=None)
        results.append(_result(row, "queued", None, None, note))
        return 0, None, True
    if outcome == "posted" and delivered.tweet_id:
        url = TWEET_URL.format(tweet_id=delivered.tweet_id)
        pin_status, pin_note = _pin_fields(row, url)
        _finish(conn, row["id"], status="posted", error=None, tweet_id=delivered.tweet_id,
                tweet_url=url, posted_at=clock, pin_status=pin_status, pin_note=pin_note,
                claimed_at=clock)
        logger.info("social post %s tweeted %s", row["id"], delivered.tweet_id)
        results.append(_result(row, "posted", delivered.tweet_id, url))
        return 1, str(delivered.tweet_id), False
    if outcome in ("rejected", "refused", "skipped"):
        _finish(conn, row["id"], status="failed", error=detail or outcome,
                tweet_id=None, tweet_url=None, posted_at=None, pin_status=None,
                pin_note=None, claimed_at=clock)
        results.append(_result(row, "failed", None, None, detail or outcome))
        return 0, None, outcome == "skipped"
    # transport, posted_without_id, or anything else: do not retry.
    _finish(conn, row["id"], status="uncertain", error=detail or outcome or "no tweet id",
            tweet_id=None, tweet_url=None, posted_at=None, pin_status=None,
            pin_note=None, claimed_at=clock)
    results.append(_result(row, "uncertain", None, None, detail or outcome or "no tweet id"))
    return 0, None, True


def _result(row, status, tweet_id, tweet_url, error=None, reply_to=None) -> dict:
    item = {
        "id": row["id"],
        "thread_key": row["thread_key"],
        "position": int(row["position"]),
        "status": status,
        "tweet_id": tweet_id,
        "tweet_url": tweet_url,
    }
    if error:
        item["error"] = error
    if reply_to:
        item["reply_to"] = reply_to
    return item


def _read_bodies(paths: list[str]) -> list[str]:
    bodies = []
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            bodies.append(handle.read())
    return bodies


def main(argv: list[str] | None = None) -> int:
    """Dry-run by default. --drain posts. --enqueue inserts and does not post
    unless --drain is also passed."""
    parser = argparse.ArgumentParser(
        description="Queue or publish manual posts to @SignalBasePicks")
    parser.add_argument("--drain", action="store_true",
                        help="post due rows (default is a dry run)")
    parser.add_argument("--enqueue", action="store_true",
                        help="insert a thread and do not post unless --drain is set")
    parser.add_argument("--thread-key", default=None)
    parser.add_argument("--body-file", action="append", default=[],
                        help="one UTF-8 file per post, in thread order; contents are exact")
    parser.add_argument("--pin", action="store_true",
                        help="ask to pin the first post; the API cannot, so it is recorded")
    parser.add_argument("--allow-link", action="store_true",
                        help="allow a URL in a post (X link rate, $0.20)")
    parser.add_argument("--scheduled-at", default=None,
                        help="ISO timestamp; default is now")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from data.db import get_connection
    conn = get_connection()
    try:
        if args.enqueue:
            if not args.thread_key or not args.body_file:
                print("enqueue needs --thread-key and at least one --body-file", file=sys.stderr)
                return 1
            when = _as_utc(args.scheduled_at) if args.scheduled_at else None
            try:
                ids = enqueue(
                    conn, args.thread_key, _read_bodies(args.body_file),
                    pin_root=args.pin, allow_link=args.allow_link, scheduled_at=when)
            except QueueRejected as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(f"queued {len(ids)} post(s) in {args.thread_key.strip()}: ids {ids}")
            if not args.drain:
                print("not posted. The worker sends them within 5 minutes of scheduled_at, "
                      "or re-run with --drain.")
                return 0
        result = drain_social_posts(conn, dry_run=not args.drain)
    finally:
        conn.close()

    print(f"status={result['status']} posted={result['posted']}")
    if result.get("reason"):
        print(result["reason"])
    for item in result.get("results", []):
        line = f"  {item['thread_key']} #{item['position']} {item['status']}"
        if item.get("tweet_url"):
            line += f" {item['tweet_url']}"
        if item.get("reply_to"):
            line += f" reply_to={item['reply_to']}"
        if item.get("error"):
            line += f" — {item['error']}"
        print(line)
    if result["status"] == "skipped" and args.drain:
        return 1
    if any(item["status"] in ("failed", "uncertain") for item in result.get("results", [])):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
