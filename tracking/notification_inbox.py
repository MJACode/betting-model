"""Per-user notification history and per-sport mutes.

The push producers in tracking/push_notifier.py call this when the hand
migration data/migrations/notification_inbox_2026_11_19.sql is applied.
Until that column and those tables exist, inbox_ready is false and the
producers send exactly as they did before.

A muted sport is dropped before the title and body are built. If nothing
remains, that user gets no push and no inbox row. Feedback replies and the
Settings test have no sport and are not filtered here.

The inbox, the bell and the app-icon badge count unread rows from the last
7 days whose sport is null or not muted. Rows older than 7 days are hidden
by that window. prune_notification_inbox is the physical delete, and it
deletes nothing unless config.data_deletion_approved('notification_inbox')
is open (CLAUDE.md section 1b). The push step calls it. No new scheduler.
"""

from __future__ import annotations

import json
import uuid
from collections import OrderedDict

# Fixed namespace so a retry of the same alert produces the same inbox id.
_INBOX_NS = uuid.UUID("6f1b6c3a-8e4d-4c1a-9b2e-3d5a7c9e1f04")

from loguru import logger

RETENTION_DAYS = 7

_READY = """
SELECT
  (SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'device_push_tokens'
      AND column_name = 'user_id') IS NOT NULL
  AND (SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'notification_inbox') IS NOT NULL
  AND (SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'notification_sport_prefs') IS NOT NULL
"""

_DEVICES = """
SELECT token, device_id, user_id::text
FROM device_push_tokens
WHERE enabled = TRUE
"""

_MUTES = """
SELECT user_id::text, sport
FROM notification_sport_prefs
WHERE enabled = FALSE
"""

_UNREAD = """
SELECT user_id::text, sport
FROM notification_inbox
WHERE read_at IS NULL
  AND sent_at >= pg_catalog.now() - make_interval(days => %s)
"""

# After notification_inbox_hide_2026_11_26.sql: a row the member deleted from
# their list is hidden (deleted_at set, never removed) and is not unread.
_UNREAD_VISIBLE = """
SELECT user_id::text, sport
FROM notification_inbox
WHERE read_at IS NULL
  AND deleted_at IS NULL
  AND sent_at >= pg_catalog.now() - make_interval(days => %s)
"""

_HAS_DELETED_AT = """
SELECT 1 FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'notification_inbox'
   AND column_name = 'deleted_at'
"""

_INSERT = """
INSERT INTO notification_inbox
    (user_id, kind, title, body, sport, route, notification_id)
VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
ON CONFLICT (user_id, notification_id) DO NOTHING
"""

_DELETE = """
DELETE FROM notification_inbox
 WHERE id IN (
       SELECT id FROM notification_inbox
        WHERE sent_at < pg_catalog.now() - make_interval(days => %s)
        LIMIT %s
 )
"""


def inbox_ready(conn) -> bool:
    """True only when the hand migration has been applied.

    A missing column must not raise: the producers run on every push step,
    and this migration is applied by hand after the code ships.
    """
    try:
        row = conn.execute(_READY).fetchone()
    except Exception as exc:  # noqa: BLE001 — a probe must not sink the push
        logger.warning(f"Push inbox probe failed, sending without history: {exc}")
        return False
    return bool(row and row[0])


def visible_signals(signals: list[dict], muted: set[str]) -> list[dict]:
    """Drop signals whose sport is muted. A signal with no sport stays."""
    if not muted:
        return list(signals)
    return [s for s in signals if not s.get("sport") or s["sport"] not in muted]


def sport_is_muted(user_id: str | None, sport: str | None, mutes: dict[str, set[str]]) -> bool:
    """A line-change alert is skipped when that pick's sport is muted."""
    if not user_id or not sport:
        return False
    return sport in mutes.get(str(user_id), set())


def group_by_user(devices: list[dict]) -> list[tuple[str | None, list[dict]]]:
    """Devices with no user share one group (None) and get the unfiltered batch."""
    buckets: OrderedDict[str | None, list[dict]] = OrderedDict()
    for device in devices:
        key = device.get("user_id") or None
        buckets.setdefault(key, []).append(device)
    return list(buckets.items())


def load_devices(conn) -> list[dict]:
    rows = conn.execute(_DEVICES).fetchall()
    return [{"token": r[0], "device_id": r[1], "user_id": r[2]} for r in rows]


def load_mutes(conn) -> dict[str, set[str]]:
    mutes: dict[str, set[str]] = {}
    for user_id, sport in conn.execute(_MUTES).fetchall():
        if user_id and sport:
            mutes.setdefault(str(user_id), set()).add(sport)
    return mutes


def has_deleted_at(conn) -> bool:
    """True once the hide migration is applied. A failed probe is False, so
    the badge keeps counting the way it did before the column existed."""
    try:
        row = conn.execute(_HAS_DELETED_AT).fetchone()
    except Exception as exc:  # noqa: BLE001 — a probe must not sink the push
        logger.warning(f"Push inbox deleted_at probe failed: {exc}")
        return False
    return bool(row)


def unread_counts(conn, mutes: dict[str, set[str]]) -> dict[str, int]:
    """Unread rows inside the 7-day window, after mutes. Sport-less rows count."""
    counts: dict[str, int] = {}
    sql = _UNREAD_VISIBLE if has_deleted_at(conn) else _UNREAD
    try:
        rows = conn.execute(sql, (RETENTION_DAYS,)).fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Push inbox unread count failed: {exc}")
        return counts
    for user_id, sport in rows:
        if not user_id:
            continue
        if sport and sport in mutes.get(str(user_id), set()):
            continue
        counts[str(user_id)] = counts.get(str(user_id), 0) + 1
    return counts


def stable_notification_id(user_id: str, kind: str, parts: list[str]) -> str:
    """Same alert, same id, including when the parts arrive in another order.

    A retry then hits ON CONFLICT (user_id, notification_id) DO NOTHING
    instead of writing a second row.
    """
    material = "|".join([str(user_id), kind, *sorted(str(p) for p in parts)])
    return str(uuid.uuid5(_INBOX_NS, material))


def bind_inbox_id(user_id: str, kind: str, parts: list[str], data: dict) -> dict:
    """Copy `data` and set inboxId. Callers must not share one dict across tokens."""
    route = dict(data)
    route["inboxId"] = stable_notification_id(user_id, kind, parts)
    return route


def make_row(user_id: str, kind: str, title: str, body: str, data: dict) -> dict:
    """One inbox row. notification_id is also data.inboxId so the phone can
    dismiss the delivered OS notification that belongs to this row."""
    preset = data.get("inboxId")
    nid = preset if isinstance(preset, str) and preset else stable_notification_id(
        user_id, kind or "alert", [title, body],
    )
    route = dict(data)
    route["inboxId"] = nid
    sport = route.get("sport")
    return {
        "user_id": str(user_id),
        "kind": kind or "alert",
        "title": title,
        "body": body,
        "sport": sport if isinstance(sport, str) else None,
        "route": route,
        "notification_id": nid,
    }


def attach_inbox(
    user_id: str | None,
    messages: list[dict],
    rows: list[dict],
    unread_before: dict[str, int],
) -> None:
    """Stamp one inbox id per distinct alert onto that user's messages.

    Devices that share a user share the id. The badge is the user's unread
    count after these new rows. A device with no user_id is not stamped and
    gets no badge, because there is no row to count.
    """
    if not user_id or not messages:
        return
    seen: dict[tuple, dict] = {}
    for msg in messages:
        data = dict(msg.get("data") or {})
        key = (msg.get("title"), data.get("type"), data.get("pickId"), data.get("threadId"))
        if key not in seen:
            seen[key] = make_row(
                user_id,
                str(data.get("type") or "alert"),
                str(msg.get("title") or ""),
                str(msg.get("body") or ""),
                data,
            )
            rows.append(seen[key])
        msg["data"] = seen[key]["route"]
    badge = unread_before.get(str(user_id), 0) + len(seen)
    for msg in messages:
        msg["badge"] = badge


def insert_rows(conn, rows: list[dict]) -> None:
    """Write inbox rows. A failure is rolled back to a savepoint so the push
    ledger and the send still commit."""
    if not rows:
        return
    try:
        conn.execute("SAVEPOINT notification_inbox")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Push inbox savepoint failed: {exc}")
        return
    try:
        for row in rows:
            conn.execute(
                _INSERT,
                (
                    row["user_id"],
                    row["kind"],
                    row["title"],
                    row["body"],
                    row["sport"],
                    json.dumps(row["route"]),
                    row["notification_id"],
                ),
            )
        conn.execute("RELEASE SAVEPOINT notification_inbox")
    except Exception as exc:  # noqa: BLE001 — history must not sink delivery
        logger.error(f"Push inbox insert failed ({len(rows)} row(s)): {exc}")
        try:
            conn.execute("ROLLBACK TO SAVEPOINT notification_inbox")
        except Exception as roll:  # noqa: BLE001
            logger.error(f"Push inbox savepoint rollback failed: {roll}")


def prune_notification_inbox(conn=None, *, days: int | None = None, batch: int = 5000) -> int:
    """Delete inbox rows older than `days`. Returns how many were deleted.

    Deletes nothing unless mike has approved the job. The 7-day window is
    already applied on every read, so the inbox does not show the rows
    either way.
    """
    import config

    if not config.data_deletion_approved("notification_inbox"):
        return 0
    if days is None:
        days = RETENTION_DAYS
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
        if not inbox_ready(conn):
            return 0
        while True:
            cur = conn.execute(_DELETE, (days, batch))
            n = cur.rowcount
            conn.commit()
            if n is None or n < 0:
                raise RuntimeError(f"notification inbox prune reported rowcount {n}")
            deleted += n
            if n < batch:
                return deleted
    finally:
        if own:
            conn.close()
