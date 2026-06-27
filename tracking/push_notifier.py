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


# ── Detection ────────────────────────────────────────────────────────────────

def _new_bet_signals(conn, target_date: str) -> list[dict]:
    """Locked opening signals that clear the current action thresholds and
    haven't been pushed yet. Joining model_action_thresholds applies the same
    prob/edge/paused/prob_only cut the app's passesActionFilter uses, so we only
    notify on genuinely bettable signals — not every raw BET cross."""
    rows = conn.execute("""
        SELECT os.lock_key, os.pick_label, os.sport
        FROM opening_signals os
        JOIN model_action_thresholds t ON t.model_id = os.model_id
        WHERE os.game_date = %s
          AND t.paused = FALSE
          AND os.model_probability >= t.min_prob
          AND (t.prob_only = TRUE OR os.edge >= COALESCE(t.min_edge, 0))
          AND NOT EXISTS (
              SELECT 1 FROM push_sent s
              WHERE s.lock_key = os.lock_key AND s.kind = 'new_bet'
          )
        ORDER BY os.locked_at
    """, (target_date,)).fetchall()
    return [{"lock_key": r[0], "label": r[1], "sport": r[2]} for r in rows]


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
    events: list[tuple[str, str]] = []
    if new_bets:
        title = f"🟢 {len(new_bets)} new BET signal{'s' if len(new_bets) != 1 else ''}"
        events.append((title, _summary_body([s["label"] for s in new_bets])))
    if dropped:
        title = f"⚠️ {len(dropped)} signal{'s' if len(dropped) != 1 else ''} flipped to AVOID"
        events.append((title, _summary_body([s["label"] for s in dropped])))

    for token in tokens:
        for title, body in events:
            messages.append({
                "to": token,
                "title": title,
                "body": body,
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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Push notifications")
    parser.add_argument("--date", default=None, help="game_date (YYYY-MM-DD), default today")
    parser.add_argument("--dry-run", action="store_true", help="print intended pushes, don't send")
    parser.add_argument("--line-changes", action="store_true",
                        help="run the track-a-bet line-change alerts instead of signal flips")
    args = parser.parse_args()
    if args.line_changes:
        n = notify_line_changes(target_date=args.date, dry_run=args.dry_run)
    else:
        n = notify_signal_changes(target_date=args.date, dry_run=args.dry_run)
    print(f"sent {n} push message(s)")
