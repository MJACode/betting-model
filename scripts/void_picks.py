#!/usr/bin/env python3
"""
Void picks that should never have been official, WITHOUT deleting them.

    python -m scripts.void_picks --model nfl_wind_totals --before 2026-09-06T17:21:24Z \
        --reason "fired outside the validated lead window (pre-#517)"
    python -m scripts.void_picks --pick-id 1634280 --pick-id 1655591 --reason "..."
    python -m scripts.void_picks ... --apply        # writes; omit for a dry run

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

VOID_RESULT = "NO_ACTION"
VOID_STATUS = "VOID"

# Results that mean the bet was graded against a real outcome. Voiding one of
# these rewrites history rather than correcting a bug.
GRADED = ("WIN", "LOSS", "PUSH")


def plan_voids(rows: list[dict], reason: str) -> tuple[list[dict], list[dict]]:
    """Split candidate rows into (to_void, refused). Pure; the tests drive this.

    Idempotent: a pick already carrying the void result is reported as a no-op
    rather than refused, so re-running the same command is safe.
    """
    to_void, refused = [], []
    for r in rows:
        result = (r.get("result") or "").strip().upper()
        if result in GRADED:
            refused.append({**r, "why": f"already graded {result}"})
        elif result == VOID_RESULT:
            refused.append({**r, "why": "already void (no-op)"})
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
           f"created_at FROM picks WHERE {' AND '.join(where)} ORDER BY created_at")
    cols = ("pick_id", "game_id", "model_id", "pick_label", "signal_type",
            "result", "created_at")
    return [dict(zip(cols, r)) for r in conn.execute(sql, params).fetchall()]


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-id", type=int, action="append", default=[])
    ap.add_argument("--model")
    ap.add_argument("--game-id", action="append", default=[])
    ap.add_argument("--before", help="ISO timestamp; only picks created before it")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="actually write. Without it this is a dry run.")
    a = ap.parse_args()

    if not (a.pick_id or a.model or a.game_id):
        raise SystemExit("refusing to match every pick: give --pick-id, --model or --game-id")

    from data.db import get_connection
    conn = get_connection()
    try:
        rows = _select(conn, a.pick_id, a.model, a.before, a.game_id)
        to_void, refused = plan_voids(rows, a.reason)

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
        print(f"\nvoided {n} pick(s): result={VOID_RESULT}, "
              f"condition_status={VOID_STATUS}")
        print(f"reason: {a.reason}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
