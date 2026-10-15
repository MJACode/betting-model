#!/usr/bin/env python3
"""
Void picks that should never have been official, WITHOUT deleting them.

    python -m scripts.void_picks --model nfl_wind_totals --before 2026-09-06T17:21:24Z \
        --reason "fired outside the validated lead window (pre-#517)"
    python -m scripts.void_picks --pick-id 1634280 --pick-id 1655591 --reason "..."
    python -m scripts.void_picks ... --apply        # writes; omit for a dry run
    python -m scripts.void_picks --pick-id 2558703 --allow-posted --reason "..."

WHY THIS EXISTS, AND WHY IT IS NOT A DELETE

CLAUDE.md §1c: a pick is a pick, and a BET is never deleted. That rule is about
LINE MOVEMENT -- the number moved, the bet still happened, and erasing it
misreports what the model said. It is not about a row the model should never
have produced, and §1c already carves those out: "deletes that remain are scoped
to rows that were never a pick".

A row produced by a model firing OUTSIDE its validated window, or on a game that
was never eligible, is in that category. But deleting it throws away the
evidence that it happened, which is the other half of what §1c protects -- and
that evidence is usually the reason anyone noticed the bug.

So: VOID, don't delete. `result = 'NO_ACTION'` is the repo's existing void
state (`tracking/paper_tracker.py` uses it for a player who did not play). It
is already excluded from net, ROI and the record everywhere in the app
(`mobile/src/lib/trackedPerformance.ts`: "NO_ACTION -> shown but excluded from
the record"), and every settlement query in `paper_tracker` is bounded on
`result IS NULL`, so a voided pick is never re-graded when the game finally
plays.

WHAT IT PRESERVES

  * the row, its `created_at`, its line and its price -- the record stands
  * the reason, in `condition_status` / `condition_note`
  * the insert-once lock: the game still HAS a pick, so a card that reruns
    inside the firing window does not silently produce a duplicate

WHAT IT REFUSES

A pick already graded WIN / LOSS / PUSH. Voiding one of those is not correcting
a bug, it is rewriting a settled result, and nothing in §1c permits it.

A pick already POSTED as a signal, BY DEFAULT. (Matt, 2026-09-28: "if a bet is
posted as a signal it should be locked".) Once the channel has it, members were
told to bet it, and a void cannot take the message back. This script does
not edit or delete the Discord message. The 2026-09-19 EV-floor void showed what
happens otherwise: Ailin Perez ML was posted, stayed on the board, won, and the
daily recap said no UFC pick cleared the bar that day. "Posted" is the publish
ledger on the pick's lock_key: tracking/publish_keys.posted_sql, the same join
the app's published-picks view makes.

THE OPT-IN, AND WHEN IT IS MEANT TO BE USED. Matt's lock shipped with no
override flag, so that changing it would have to be a code change. mike made
that change on 2026-10-09 ("Change the rule, void them"): `--allow-posted` here,
`"allow_posted": true` on the worker job. It exists for one case: a posted pick
that was DECIDED ON A PRICE NOBODY COULD BET. The first use was eight NCAAF
unders the scorer priced from DraftKings rows last stored 2026-09-05, 15 to 28
days before each pick, after the odds feed had stopped listing those games. Not
for a rule or threshold change after posting: that is a pick that existed at a
real number, and Matt's reasoning above still applies to it in full.

With the opt-in, a posted pick is voided like any other. Without it, it is
refused and the refusal says how to opt in. A graded pick is refused either
way. The original message stays where it is. After the void commits, a pick
that was posted gets a void notice in that sport's channel, with this reason
(tracking.discord_notifier.notify_discord_void). An unposted void posts
nothing. A notice Discord rejects is logged and does not undo the void.

FIRST USE: 2026-09-07 (mike), the six `nfl_wind_totals` Week 1 picks that fired
at 7.2-8.7 day leads before #517 landed the firing gate. All six had lost their
premise by the time they were voided -- four had the wind forecast collapse to
2.9-7.1 mph against an 11 mph bar, and two were on retractable-roof stadiums
that were never eligible. See docs/nfl_wind_lead_evidence.md.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from loguru import logger

VOID_RESULT = "NO_ACTION"
VOID_STATUS = "VOID"

# Results that mean the bet was graded against a real outcome. Voiding one of
# these rewrites history rather than correcting a bug.
GRADED = ("WIN", "LOSS", "PUSH")


def _posted_sql() -> str:
    from tracking.publish_keys import posted_sql
    return posted_sql("p")


POSTED_SQL = _posted_sql()


POSTED_REFUSAL = ("posted as a signal -- a posted signal is locked; to void it "
                  "anyway pass --allow-posted (worker job: \"allow_posted\": true)")


def plan_voids(rows: list[dict], reason: str,
               allow_posted: bool = False) -> tuple[list[dict], list[dict]]:
    """Split candidate rows into (to_void, refused). Pure; the tests drive this.

    Idempotent: a pick already carrying the void result is reported as a no-op
    rather than refused, so re-running the same command is safe.

    `allow_posted` lifts ONLY the posted-signal lock (see the module docstring
    for when it is meant to be used). A graded pick is refused with or without it.
    """
    to_void, refused = [], []
    for r in rows:
        result = (r.get("result") or "").strip().upper()
        if result in GRADED:
            refused.append({**r, "why": f"already graded {result}"})
        elif result == VOID_RESULT:
            refused.append({**r, "why": "already void (no-op)"})
        elif r.get("posted") and not allow_posted:
            refused.append({**r, "why": POSTED_REFUSAL})
        elif not reason.strip():
            refused.append({**r, "why": "no reason given"})
        else:
            to_void.append(r)
    return to_void, refused


def _select(conn, pick_ids, model, before, game_ids):
    where, params = ["1=1"], []
    if pick_ids:
        where.append("pick_id = ANY(%s)")
        params.append(list(pick_ids))
    if model:
        where.append("model_id = %s")
        params.append(model)
    if game_ids:
        where.append("game_id = ANY(%s)")
        params.append(list(game_ids))
    if before:
        where.append("created_at < %s")
        params.append(before)
    sql = (f"SELECT pick_id, game_id, model_id, pick_label, signal_type, result, "
           f"created_at, {POSTED_SQL} AS posted "
           f"FROM picks p WHERE {' AND '.join(where)} ORDER BY created_at")
    cols = ("pick_id", "game_id", "model_id", "pick_label", "signal_type",
            "result", "created_at", "posted")
    return [dict(zip(cols, r)) for r in conn.execute(sql, params).fetchall()]


def announce_posted_voids(rows: list[dict], reason: str) -> dict | None:
    """Post a void notice for picks that were already on the channel.

    Called only after the void has committed. Unposted rows post nothing, so
    a void of a pick the channel never had does not open a Discord connection.
    DiscordVoidRejected, and any other failure, is logged and swallowed: the
    void stands either way. The original message is not edited or deleted.
    """
    posted = [r for r in rows if r.get("posted")]
    if not posted:
        return None
    ids = [int(r["pick_id"]) for r in posted]
    try:
        from tracking.discord_notifier import (
            DiscordVoidRejected, notify_discord_void,
        )
        return notify_discord_void(ids, reason=reason, dry_run=False)
    except DiscordVoidRejected as exc:
        logger.warning(f"Discord void notice not posted for {ids}: {exc}")
        return {"error": str(exc), "pick_ids": ids}
    except Exception as exc:                              # noqa: BLE001
        logger.warning(f"Discord void notice failed for {ids}: {exc}")
        return {"error": str(exc), "pick_ids": ids}


def void(conn, rows: list[dict], reason: str, now: str | None = None) -> int:
    """Apply the void. Matches the shape paper_tracker's own NO_ACTION path uses."""
    now = now or datetime.now(timezone.utc).isoformat()
    for r in rows:
        conn.execute("""
            UPDATE picks
            SET result               = %s,
                profit_flat          = 0,
                profit_kelly         = 0,
                settled_at           = %s,
                condition_status     = %s,
                condition_note       = %s,
                condition_checked_at = %s
            WHERE pick_id = %s
        """, (VOID_RESULT, now, VOID_STATUS, reason[:500], now, r["pick_id"]))
    return len(rows)


def build_parser() -> argparse.ArgumentParser:
    """The command line, separate from main() so a test can parse it."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-id", type=int, action="append", default=[])
    ap.add_argument("--model")
    ap.add_argument("--game-id", action="append", default=[])
    ap.add_argument("--before", help="ISO timestamp; only picks created before it")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="actually write. Without it this is a dry run.")
    ap.add_argument("--allow-posted", action="store_true",
                    help="also void picks already posted as a signal (mike, "
                         "2026-10-09). Only for a posted pick decided on a "
                         "price nobody could bet. Graded picks stay refused.")
    return ap


def main() -> int:
    a = build_parser().parse_args()

    if not (a.pick_id or a.model or a.game_id):
        raise SystemExit("refusing to match every pick: give --pick-id, --model or --game-id")

    from data.db import get_connection
    conn = get_connection()
    try:
        rows = _select(conn, a.pick_id, a.model, a.before, a.game_id)
        to_void, refused = plan_voids(rows, a.reason, allow_posted=a.allow_posted)

        for r in refused:
            print(f"  SKIP  {r['pick_id']}  {r['pick_label']}  -- {r['why']}")
        for r in to_void:
            print(f"  VOID  {r['pick_id']}  {r['pick_label']}  "
                  f"({r['signal_type']}, created {r['created_at']})")

        if not a.apply:
            print(f"\nDRY RUN: {len(to_void)} would be voided, {len(refused)} skipped. "
                  "Re-run with --apply to write.")
            return 0

        n = void(conn, to_void, a.reason)
        conn.commit()
        notice = announce_posted_voids(to_void, a.reason)
        print(f"\nvoided {n} pick(s): result={VOID_RESULT}, "
              f"condition_status={VOID_STATUS}")
        print(f"reason: {a.reason}")
        if notice is not None:
            print(f"void notice: {notice}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
