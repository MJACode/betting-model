"""
Signal-flip push notifications.

Runs as the last pipeline step (after opening-signal capture). It diffs the
locked opening signals against a `push_sent` ledger to find:

  • new_bet — a signal that just cleared the action thresholds (a fresh,
    bettable BET the user would want to know about), not yet pushed.
  • dropped — a previously-pushed signal whose live pick has since flipped to
    AVOID (the line moved against it), game not yet started, not yet pushed.

It sends ONE summary push per event type per device (not one per signal) to bound
noise, then ledgers every notified lock_key so nothing is pushed twice across the
hourly runs. Idempotent and safe to re-run; --dry-run prints intended pushes
without sending or ledgering.

Delivery uses the keyless Expo Push API (exp.host). Device tokens come from
device_push_tokens, which the mobile app populates once a user opts in (see
docs/push_notifications.md — that half needs expo-notifications + a native
build + APNs/FCM credentials, configured on Matt's machine).
"""

from __future__ import annotations

from datetime import datetime, date
from zoneinfo import ZoneInfo

import requests
from loguru import logger

from data.db import get_connection

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
_MAX_LABELS = 3          # labels listed in a summary body before "+N more"
_EXPO_CHUNK = 100        # Expo accepts up to 100 messages per request

# Payload contract version. The APP is the other half of this (mobile/src/lib/
# pushRoute.ts, which pins the same number) and an old build can be installed
# for months, so the router ignores a payload it does not understand rather than
# guessing. Bump only for a BREAKING change; adding an optional key is not one.
PUSH_ROUTE_VERSION = 1


# ── Routing payloads ─────────────────────────────────────────────────────────
#
# Every message carries `data` saying where a tap should land. Before this
# (2026-09-06) none did, so the app had nothing to route on: a tap opened
# wherever the user had last been, which for a live pick — a number that is
# ~45s stale by construction — is the whole value of the notification lost.
#
# Two shapes, because a push is usually a SUMMARY ("3 new BET signals"), not one
# pick:
#   - exactly one pick  -> `pickId`, and the tap opens that pick's detail.
#   - more than one     -> no pickId, and the tap opens the board view that
#                          holds them, on the right sport.
# `sport` is only set when every pick in the batch shares one. A push spanning
# MLB and NCAAF must NOT switch the user's sport, because the board shows one
# sport at a time and either choice would hide the other half.

def _shared_sport(signals: list[dict]) -> str | None:
    """The one sport in this batch, or None when it spans several."""
    sports = {s.get("sport") for s in signals if s.get("sport")}
    return sports.pop() if len(sports) == 1 else None


def _route(kind: str, signals: list[dict]) -> dict:
    """The `data` payload for a summary push of `signals`."""
    payload: dict = {"v": PUSH_ROUTE_VERSION, "type": kind}
    sport = _shared_sport(signals)
    if sport:
        payload["sport"] = sport
    if len(signals) == 1 and signals[0].get("pick_id") is not None:
        payload["pickId"] = signals[0]["pick_id"]
    return payload


# ── Detection ────────────────────────────────────────────────────────────────

def _new_bet_signals(conn, target_date: str) -> list[dict]:
    """Bettable picks that have not been pushed yet.

    READS `picks`, NOT `opening_signals` (2026-09-05, Matt: "the app and discord
    should always show the same picks. They should be identical"). The rule was
    given about Discord; it applies here for the same reason and more sharply.
    This is the APP's own notification, so a pick the app displays and the phone
    stays silent about is the divergence in its purest form.

    Push was the worst of the three surfaces. It read `opening_signals` (a gate
    the app does not have -- see tracking/discord_notifier._new_signals for the
    measured leak) AND bounded on `os.game_date = target_date`, without even the
    look-ahead widening Discord carried. So a pick written days ahead -- every
    NFL wind and opener pick, every NCAAF look-ahead -- could not be pushed on
    the day it was written, and by its game day it had long since been ledgered
    as old news or never captured at all. Both Week 1 wind picks of 2026-09-05
    reached the app and notified nobody.

    Mirrors the Discord producer exactly: same table, same thresholds row, same
    first-BET-wins rule, same synthesised lock_key -- so the `push_sent` ledger
    carries over and nothing already pushed pushes twice. The two ledger kinds
    stay independent (`new_bet` here, `discord_signal` there), so neither
    surface can suppress the other.
    """
    rows = conn.execute("""
        WITH bet AS (
            SELECT DISTINCT ON (p.game_id, p.model_id, COALESCE(p.player_id, ''))
                   p.game_id || ':' || p.model_id
                       || COALESCE(':' || p.player_id, '') AS lock_key,
                   p.pick_label, p.sport, p.created_at, p.pick_id
            FROM picks p
            JOIN model_action_thresholds t ON t.model_id = p.model_id
            LEFT JOIN games g ON g.game_id = p.game_id
            WHERE p.signal_type = 'BET'
              AND (p.is_live IS NULL OR p.is_live = FALSE)
              AND p.model_id NOT LIKE '%%_live_%%'
              -- Never push a pre-game pick for a game already under way. Same
              -- guard and same reasoning as the Discord producer: if it is
              -- wrong to post a bet the reader cannot take, it is wrong to buzz
              -- their phone about it. An unknown start time never suppresses
              -- (golf has none).
              AND (g.commence_time IS NULL
                   OR g.commence_time::timestamptz > NOW())
              AND (g.commence_time IS NOT NULL OR p.game_date >= %s)
              AND t.paused = FALSE
              AND p.model_probability >= t.min_prob
              AND (t.prob_only = TRUE OR p.edge >= COALESCE(t.min_edge, 0))
              AND (t.min_odds IS NULL OR p.dk_odds IS NULL
                   OR p.dk_odds >= t.min_odds)
            ORDER BY p.game_id, p.model_id, COALESCE(p.player_id, ''),
                     p.created_at
        )
        SELECT lock_key, pick_label, sport, pick_id FROM bet
        WHERE NOT EXISTS (
            SELECT 1 FROM push_sent s
            WHERE s.lock_key = bet.lock_key AND s.kind = 'new_bet'
        )
        ORDER BY created_at
    """, (target_date,)).fetchall()
    return [{"lock_key": r[0], "label": r[1], "sport": r[2], "pick_id": r[3]}
            for r in rows]


def _dropped_signals(conn, target_date: str) -> list[dict]:
    """Signals we previously pushed as new_bet whose live pick is now AVOID
    (flipped against us), still pre-settlement, not yet pushed as dropped."""
    rows = conn.execute("""
        SELECT DISTINCT os.lock_key, os.pick_label, os.sport, os.locked_at
        FROM opening_signals os
        JOIN push_sent prior
          ON prior.lock_key = os.lock_key AND prior.kind = 'new_bet'
        JOIN picks p
          ON p.game_id = os.game_id
         AND p.model_id = os.model_id
         AND p.pick_side = os.pick_side
         AND COALESCE(p.player_id, '') = COALESCE(os.player_id, '')
         AND p.game_date = os.game_date
        WHERE os.game_date = %s
          AND os.lock_key NOT LIKE '%%:early'
          AND os.result IS NULL
          AND p.signal_type = 'AVOID'
          AND NOT EXISTS (
              SELECT 1 FROM push_sent s
              WHERE s.lock_key = os.lock_key AND s.kind = 'dropped'
          )
        ORDER BY os.locked_at
    """, (target_date,)).fetchall()
    return [{"lock_key": r[0], "label": r[1], "sport": r[2]} for r in rows]


# ── Message building ─────────────────────────────────────────────────────────

def _summary_body(labels: list[str]) -> str:
    shown = labels[:_MAX_LABELS]
    extra = len(labels) - len(shown)
    body = " · ".join(shown)
    if extra > 0:
        body += f" · +{extra} more"
    return body


def _build_messages(tokens: list[str], new_bets: list[dict], dropped: list[dict]) -> list[dict]:
    """One message per (token × non-empty event type)."""
    messages: list[dict] = []
    events: list[tuple[str, str, dict]] = []
    if new_bets:
        title = f"🟢 {len(new_bets)} new BET signal{'s' if len(new_bets) != 1 else ''}"
        events.append((title, _summary_body([s["label"] for s in new_bets]),
                       _route("new_bets", new_bets)))
    if dropped:
        title = f"⚠️ {len(dropped)} signal{'s' if len(dropped) != 1 else ''} flipped to AVOID"
        # Lands on Today, not Signals: a flipped pick is no longer a signal, so
        # the Signals board is the one place it is guaranteed NOT to be.
        events.append((title, _summary_body([s["label"] for s in dropped]),
                       _route("dropped", dropped)))

    for token in tokens:
        for title, body, data in events:
            messages.append({
                "to": token,
                "title": title,
                "body": body,
                "data": data,
                "sound": "default",
                "priority": "high",
            })
    return messages


def _expo_send(messages: list[dict]) -> int:
    """POST messages to the Expo push service in chunks. Returns sent count.
    Non-fatal: logs and continues on a failed chunk so one bad token can't
    sink the run."""
    sent = 0
    for i in range(0, len(messages), _EXPO_CHUNK):
        chunk = messages[i:i + _EXPO_CHUNK]
        try:
            resp = requests.post(
                EXPO_PUSH_URL,
                json=chunk,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            sent += len(chunk)
        except Exception as exc:  # noqa: BLE001 — never let delivery break the pipeline
            logger.error(f"Expo push chunk failed ({len(chunk)} msgs): {exc}")
    return sent


# ── Entry point ──────────────────────────────────────────────────────────────

def notify_signal_changes(target_date: str | None = None, dry_run: bool = False) -> int:
    """Detect new/dropped signals, push a summary to every enabled device, and
    ledger what was sent. Returns the number of push messages sent."""
    if target_date is None:
        target_date = date.today().isoformat()

    conn = get_connection()
    try:
        new_bets = _new_bet_signals(conn, target_date)
        dropped = _dropped_signals(conn, target_date)
        if not new_bets and not dropped:
            logger.info(f"Push: no new/dropped signals for {target_date}")
            return 0

        tokens = [r[0] for r in conn.execute(
            "SELECT token FROM device_push_tokens WHERE enabled = TRUE"
        ).fetchall()]

        logger.info(
            f"Push: {len(new_bets)} new, {len(dropped)} dropped for {target_date}; "
            f"{len(tokens)} device(s)"
        )

        if dry_run:
            for s in new_bets:
                logger.info(f"[dry-run] new_bet → {s['label']}")
            for s in dropped:
                logger.info(f"[dry-run] dropped → {s['label']}")
            return 0

        # Ledger regardless of token count, so a signal with zero devices online
        # isn't re-detected forever (it would spam once a device registers late).
        sent_at = datetime.now(ZoneInfo("America/New_York")).isoformat()
        messages = _build_messages(tokens, new_bets, dropped) if tokens else []
        sent = _expo_send(messages) if messages else 0

        for s in new_bets:
            conn.execute(
                "INSERT INTO push_sent (lock_key, kind, sent_at) VALUES (%s, 'new_bet', %s) "
                "ON CONFLICT (lock_key, kind) DO NOTHING",
                (s["lock_key"], sent_at),
            )
        for s in dropped:
            conn.execute(
                "INSERT INTO push_sent (lock_key, kind, sent_at) VALUES (%s, 'dropped', %s) "
                "ON CONFLICT (lock_key, kind) DO NOTHING",
                (s["lock_key"], sent_at),
            )
        conn.commit()

        logger.success(f"✓ Push: {sent} message(s) sent to {len(tokens)} device(s)")
        return sent
    finally:
        conn.close()


# ── Track-a-bet line-change alerts ───────────────────────────────────────────

def _line_change_alerts(conn, target_date: str) -> list[dict]:
    """Tracked game-level bets whose DK price has moved ≥ LINE_CHANGE_NOTIFY_PP
    (implied pp) off the user's locked price, game not yet started. One alert per
    (device, pick) per whole-multiple bucket of the threshold, so a steaming line
    escalates (4pp, 8pp, …) but doesn't spam. Props (player_id set) are a
    fast-follow — their odds live in player_prop_odds, not the game odds table."""
    from config import LINE_CHANGE_NOTIFY_PP
    from models.scorer import _get_dk_odds, american_to_implied_prob
    from tracking.paper_tracker import _market_for_pick, _SIDE_PRICE_COL

    now_utc = datetime.now(ZoneInfo("UTC")).isoformat()
    rows = conn.execute("""
        SELECT tb.device_id, tb.pick_id, tb.game_id, tb.model_id, tb.pick_side,
               tb.locked_odds, tb.pick_label
        FROM tracked_bets tb
        JOIN games g ON g.game_id = tb.game_id
        WHERE tb.game_date = %s
          AND tb.player_id IS NULL
          AND tb.locked_odds IS NOT NULL
          AND (g.commence_time IS NULL OR g.commence_time > %s)
    """, (target_date, now_utc)).fetchall()

    alerts: list[dict] = []
    for device_id, pick_id, game_id, model_id, pick_side, locked_odds, label in rows:
        col = _SIDE_PRICE_COL.get(pick_side)
        if not col:
            continue
        odds = _get_dk_odds(conn, game_id, _market_for_pick(model_id))
        current = odds.get(col) if odds else None
        if current is None:
            continue
        shift = (american_to_implied_prob(float(current))
                 - american_to_implied_prob(float(locked_odds))) * 100
        if abs(shift) < LINE_CHANGE_NOTIFY_PP:
            continue
        bucket = int(abs(shift) // LINE_CHANGE_NOTIFY_PP)   # 1 at ≥4pp, 2 at ≥8pp, …
        lock_key = f"track:{device_id}:{pick_id}"
        kind = f"line_change_{bucket}"
        already = conn.execute(
            "SELECT 1 FROM push_sent WHERE lock_key = %s AND kind = %s",
            (lock_key, kind),
        ).fetchone()
        if already:
            continue
        alerts.append({
            "device_id": device_id, "lock_key": lock_key, "kind": kind,
            "pick_id": pick_id,
            "label": label, "locked": int(locked_odds), "current": int(current),
            "against": shift > 0,
        })
    return alerts


def notify_line_changes(target_date: str | None = None, dry_run: bool = False) -> int:
    """Push a per-bet alert to the tracking device whenever a tracked game-level
    bet's DK line moves big. Ledgers each (device, pick, bucket) so it fires once
    per escalation. Returns the number of push messages sent."""
    if target_date is None:
        target_date = date.today().isoformat()

    conn = get_connection()
    try:
        alerts = _line_change_alerts(conn, target_date)
        if not alerts:
            logger.info(f"Push(line-change): nothing tracked moved for {target_date}")
            return 0

        token_by_device = {
            r[0]: r[1] for r in conn.execute(
                "SELECT device_id, token FROM device_push_tokens "
                "WHERE enabled = TRUE AND device_id IS NOT NULL"
            ).fetchall()
        }
        logger.info(f"Push(line-change): {len(alerts)} alert(s) for {target_date}")

        if dry_run:
            for a in alerts:
                arrow = "against you" if a["against"] else "in your favor"
                logger.info(f"[dry-run] line_change → {a['label']}: "
                            f"{a['locked']:+d} → {a['current']:+d} ({arrow})")
            return 0

        sent_at = datetime.now(ZoneInfo("America/New_York")).isoformat()
        messages = []
        for a in alerts:
            token = token_by_device.get(a["device_id"])
            if token:
                arrow = "moved against you" if a["against"] else "moved in your favor"
                messages.append({
                    "to": token,
                    "title": f"📈 Line {arrow}",
                    "body": f"{a['label']}: {a['locked']:+d} → {a['current']:+d}",
                    # Always one pick, so this is the one push that can always
                    # open the bet itself — which is the whole point when the
                    # line the user locked has moved.
                    "data": {"v": PUSH_ROUTE_VERSION, "type": "line_change",
                             "pickId": a["pick_id"]},
                    "sound": "default",
                    "priority": "high",
                })
        sent = _expo_send(messages) if messages else 0

        # Ledger every alert (even with no device online) so it isn't re-detected
        # forever — mirrors notify_signal_changes.
        for a in alerts:
            conn.execute(
                "INSERT INTO push_sent (lock_key, kind, sent_at) VALUES (%s, %s, %s) "
                "ON CONFLICT (lock_key, kind) DO NOTHING",
                (a["lock_key"], a["kind"], sent_at),
            )
        conn.commit()
        logger.success(f"✓ Push(line-change): {sent} message(s) sent")
        return sent
    finally:
        conn.close()


# ── Live (in-play) signal alerts ─────────────────────────────────────────────

def _new_live_signals(conn, target_date: str) -> list[dict]:
    """Live (in-play) BET picks not yet pushed. Deduped per (game, model, side)
    so the churning live board — delete+rescored every pass — doesn't re-notify
    the same signal. A signal that disappears and returns isn't re-pushed (v1)."""
    rows = conn.execute("""
        SELECT DISTINCT p.game_id, p.model_id, p.pick_side, p.pick_label,
               p.inning_at_pick, p.sport, p.pick_id
        FROM picks p
        WHERE p.game_date = %s
          AND p.is_live = TRUE
          AND p.signal_type = 'BET'
          AND p.result IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM push_sent s
              WHERE s.lock_key = 'live:' || p.game_id || ':' || p.model_id || ':' || p.pick_side
                AND s.kind = 'live_signal'
          )
        ORDER BY p.game_id
    """, (target_date,)).fetchall()
    return [{
        "lock_key": f"live:{r[0]}:{r[1]}:{r[2]}",
        "label": r[3],
        "inning": r[4],
        "sport": r[5],
        "pick_id": r[6],
    } for r in rows]


def notify_live_signals(target_date: str | None = None, dry_run: bool = False) -> int:
    """Push a summary of new in-play BET signals to every opted-in device, then
    ledger each so the live churn doesn't re-notify. Returns messages sent.
    Called at the end of each live-scorer pass (the live loop), not the hourly
    pipeline. Idempotent and safe to re-run."""
    if target_date is None:
        target_date = date.today().isoformat()

    conn = get_connection()
    try:
        new = _new_live_signals(conn, target_date)
        if not new:
            return 0

        tokens = [r[0] for r in conn.execute(
            "SELECT token FROM device_push_tokens WHERE enabled = TRUE"
        ).fetchall()]
        logger.info(f"Push(live): {len(new)} new live signal(s) for {target_date}; "
                    f"{len(tokens)} device(s)")

        if dry_run:
            for s in new:
                logger.info(f"[dry-run] live_signal → {s['label']}")
            return 0

        sent_at = datetime.now(ZoneInfo("America/New_York")).isoformat()
        title = f"🔴 {len(new)} live bet signal{'s' if len(new) != 1 else ''}"
        body = _summary_body([s["label"] for s in new])
        data = _route("live_signals", new)
        messages = [{
            "to": token, "title": title, "body": body, "data": data,
            "sound": "default", "priority": "high",
        } for token in tokens]
        sent = _expo_send(messages) if messages else 0

        for s in new:
            conn.execute(
                "INSERT INTO push_sent (lock_key, kind, sent_at) VALUES (%s, 'live_signal', %s) "
                "ON CONFLICT (lock_key, kind) DO NOTHING",
                (s["lock_key"], sent_at),
            )
        conn.commit()
        logger.success(f"✓ Push(live): {sent} message(s) sent")
        return sent
    finally:
        conn.close()


# ── Feedback replies ─────────────────────────────────────────────────────────

def _unpushed_feedback_replies(conn) -> list[dict]:
    """Support replies the asking device hasn't been notified about.

    Ledgered per MESSAGE (not per thread) so a follow-up reply in the same
    conversation still notifies, and a re-run never double-notifies. Only threads
    whose device has an enabled push token are considered — there is nowhere else
    to deliver."""
    rows = conn.execute("""
        SELECT m.id, t.device_id, d.token, t.subject, m.body, t.id
        FROM feedback_messages m
        JOIN feedback_threads t ON t.id = m.thread_id
        JOIN device_push_tokens d ON d.device_id = t.device_id AND d.enabled = TRUE
        WHERE m.sender = 'support'
          AND NOT EXISTS (
              SELECT 1 FROM push_sent s
              WHERE s.lock_key = 'feedback:' || m.id AND s.kind = 'feedback_reply'
          )
        ORDER BY m.id
    """).fetchall()
    return [{
        "lock_key": f"feedback:{r[0]}",
        "device_id": r[1],
        "token": r[2],
        "subject": r[3],
        "body": r[4],
        "thread_id": r[5],
    } for r in rows]


def notify_feedback_replies(dry_run: bool = False) -> int:
    """Tell a user we answered their feedback, on the device that asked.

    Runs with the signal-flip notifier in the hourly push step, so a reply
    written from the SQL editor / Claude mobile reaches the user within the hour
    without anything else being run by hand. The reply is already visible in the
    app's Feedback tab either way — this is the nudge, not the delivery."""
    conn = get_connection()
    try:
        replies = _unpushed_feedback_replies(conn)
        if not replies:
            return 0

        logger.info(f"Push(feedback): {len(replies)} unnotified support repl(ies)")
        if dry_run:
            for r in replies:
                logger.info(f"[dry-run] feedback_reply → {r['device_id']}: {r['subject']}")
            return 0

        sent_at = datetime.now(ZoneInfo("America/New_York")).isoformat()
        messages = [{
            "to": r["token"],
            "title": "💬 We replied to your feedback",
            "body": (r["body"] or "")[:140],
            "data": {"v": PUSH_ROUTE_VERSION, "type": "feedback_reply",
                     "threadId": r["thread_id"]},
            "sound": "default",
            "priority": "high",
        } for r in replies]
        sent = _expo_send(messages)

        # Ledger every reply, delivered or not — mirrors the other producers, so
        # a delivery failure can't turn into a nightly re-notify.
        for r in replies:
            conn.execute(
                "INSERT INTO push_sent (lock_key, kind, sent_at) VALUES (%s, 'feedback_reply', %s) "
                "ON CONFLICT (lock_key, kind) DO NOTHING",
                (r["lock_key"], sent_at),
            )
        conn.commit()
        logger.success(f"✓ Push(feedback): {sent} message(s) sent")
        return sent
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Push notifications")
    parser.add_argument("--date", default=None, help="game_date (YYYY-MM-DD), default today")
    parser.add_argument("--dry-run", action="store_true", help="print intended pushes, don't send")
    parser.add_argument("--line-changes", action="store_true",
                        help="run the track-a-bet line-change alerts instead of signal flips")
    parser.add_argument("--live", action="store_true",
                        help="run the live (in-play) signal alerts")
    parser.add_argument("--feedback", action="store_true",
                        help="notify users whose feedback we replied to")
    args = parser.parse_args()
    if args.feedback:
        n = notify_feedback_replies(dry_run=args.dry_run)
    elif args.live:
        n = notify_live_signals(target_date=args.date, dry_run=args.dry_run)
    elif args.line_changes:
        n = notify_line_changes(target_date=args.date, dry_run=args.dry_run)
    else:
        n = notify_signal_changes(target_date=args.date, dry_run=args.dry_run)
    print(f"sent {n} push message(s)")
