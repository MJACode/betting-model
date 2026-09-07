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


# ── Alert plumbing: state, throttling, and the ops channel ────────────────────
#
# Extracted 2026-09-06 when the failure alerter became the SECOND thing that
# needs to say "this is broken" without saying it every ten minutes forever.
# The heartbeat watchdog worked this out first and its versions are the ones
# these are modelled on; it deliberately keeps its own copies for now, because
# it is the last line of defence during a database outage and refactoring it in
# the same change that adds a database-DEPENDENT alerter would couple the safe
# thing to the new thing. Migrating it is a follow-up, not this PR.

import json
import os
import tempfile
from datetime import timedelta
from pathlib import Path


# The embed colours for an ops message. Defined here rather than per-watch so
# an alert looks the same whichever watch raised it.
COLOR_ALERT = 0xE74C3C
COLOR_RECOVERY = 0x2ECC71


def alert_state_path(filename: str) -> Path:
    """Where a watch keeps its de-duplication state.

    Prefers the Railway volume: state on ephemeral container disk is wiped by
    every deploy, so a redeploy during an incident would re-alert on everything
    that was already announced. Falls back to temp so a service with no volume
    still runs — noisier, but running.
    """
    for env_var in ("WATCHDOG_STATE_DIR", "RAILWAY_VOLUME_MOUNT_PATH"):
        raw = os.environ.get(env_var, "").strip()
        if raw:
            try:
                d = Path(raw)
                d.mkdir(parents=True, exist_ok=True)
                return d / filename
            except OSError:
                continue
    return Path(tempfile.gettempdir()) / filename


def read_alert_state(filename: str) -> dict:
    """No state means "nothing has alerted yet" — which errs toward alerting."""
    try:
        return json.loads(alert_state_path(filename).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_alert_state(filename: str, state: dict) -> None:
    try:
        alert_state_path(filename).write_text(json.dumps(state), encoding="utf-8")
    except OSError as exc:  # noqa: BLE001 — bookkeeping must not break the watch
        logger.warning(f"could not persist alert state {filename}: {exc}")


def should_notify(state: dict, key: str, now: datetime, minutes: int) -> bool:
    """True when this condition is new, or has gone unrepeated long enough.

    The repeat exists so a long outage stays visible without burying the
    channel. Without it, a condition that holds all night posts once per tick.
    """
    last_raw = (state.get(key) or {}).get("last") if isinstance(
        state.get(key), dict) else state.get(key)
    if not last_raw:
        return True
    try:
        last = datetime.fromisoformat(str(last_raw))
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return now - last >= timedelta(minutes=minutes)


def post_ops_alert(title: str, detail: str, *, recovery: bool = False,
                   post=None) -> bool:
    """One message to the ops channel. True only on a CONFIRMED post.

    An unset webhook is logged at CRITICAL rather than swallowed: a watch that
    can see a problem and cannot say so is a DIFFERENT failure from a healthy
    system, and the two must not look alike in the logs (§7 — nothing is
    ledgered unless a POST confirmed).

    `post` exists so a caller can hand in its OWN module-level `_post`. The
    heartbeat watchdog's tests patch `heartbeat_watchdog._post` to capture what
    would have been sent; resolving the poster only inside this function would
    silently step around that seam and let a test suite make real HTTP calls.
    A shared helper must not take away the caller's ability to be tested.
    """
    import config

    if post is None:
        from tracking.discord_notifier import _post as post

    url = getattr(config, "DISCORD_WEBHOOK_OPS", "")
    if not url:
        logger.critical(
            f"OPS {'RECOVERY' if recovery else 'ALERT'} — {title}: {detail} "
            "(DISCORD_WEBHOOK_OPS is not set, so this alert reached nobody)")
        return False
    payload = {"embeds": [{
        "title": ("✅ " if recovery else "🚨 ") + title,
        "description": detail[:4000],
        "color": COLOR_RECOVERY if recovery else COLOR_ALERT,
    }]}
    return bool(post(url, payload))
