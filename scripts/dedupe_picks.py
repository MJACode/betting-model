"""Remove the duplicate pick rows a released lock wrote, keeping the FIRST.

Matt, 2026-09-05, on seeing eleven identical "Logan Allen Over 4.5 Hits" rows
on the model detail screen: *"The same bet showed multiple times for a signal.
It should just be the first one?"*

WHAT THESE ROWS ARE. Both pick locks used to ask for `result IS NULL`, so a
pick left the lock set the moment settle_picks graded it and the next refresh
pass scored the same player again. That needs a game that is FINAL while its
`games` row still says "not started", which is exactly a doubleheader: both
games share one game_id (docs/followups.md), so game 1's final score settles
the pick while game 2's commence_time keeps the pre-game cutoff open. Each new
row was settled ~2 minutes later by the next settle pass, which released the
lock again -- one copy per 10-minute pass until first pitch of game 2.

Measured on production 2026-09-05, over all 144,669 pre-game pick rows ever
written: 63 duplicate rows, every one of them MLB. In the published window
(>= 2026-09-01, settled, passing the current cuts) 20 of 132 settled BETs were
copies -- 15% of the published record, +7.38u/+5.59% ROI as shown against
+5.68u/+5.07% once deduplicated.

WHY DELETE RATHER THAN KEEP. CLAUDE.md section 1c protects a REAL pick whose
number later moved; it does not reach a row that is a second copy of a pick
that already existed. Its own carve-out is "rows that were never a pick", and
the first row of each key -- the one this script keeps -- IS the pick, with its
original created_at intact. Keeping the copies would mean every consumer (the
app, Retool's q_performance, the graded matview, the custom-model backtest)
has to remember to deduplicate, forever, and the one that forgets publishes an
inflated record. Deleting them makes `picks` mean what every surface already
assumes it means: one row per pick.

WHICH ROW SURVIVES, stated so it cannot quietly change:

  1. a BET beats a non-BET for the same key -- a dead-zone NONE written at 6am
     must never displace the BET that crossed at 3pm;
  2. among equals, the EARLIEST created_at (the first signal is the bet of
     record, section 1c);
  3. ties broken by the lowest pick_id, so the choice is deterministic.

The key is (game_date, model_id, game_id, player_id, pick_side) on PRE-GAME
rows. Deliberately NOT keyed on scored_line: a re-score that moved the line is
the same bug wearing a different number, and collapsing it is the point. Live
rows are excluded -- the live lock and tracking/first_signal_repair own those,
and they carry no duplicates on this key today (measured: 564 live BETs, 0).

RECOVERY. picks_audit_trigger writes every DELETE to picks_log, so this is
reversible from the database alone. The script ALSO writes a JSON snapshot of
every row it removes, because a backup you have to reconstruct from an audit
table is not the one you want at 2am.

Dry run by default. Nothing is written without --apply.

    python -m scripts.dedupe_picks            # show what would go
    python -m scripts.dedupe_picks --apply    # delete it
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from data.db import get_connection

# The identity of a pick, and the survivor rule, in one statement so the
# preview and the delete cannot disagree about the set.
SELECT_DUPLICATES = """
WITH ranked AS (
  SELECT p.pick_id, p.model_id, p.sport, p.game_id, p.game_date, p.pick_label,
         p.pick_side, p.signal_type, p.scored_line, p.dk_odds, p.result,
         p.profit_flat, p.created_at,
         ROW_NUMBER() OVER (
           PARTITION BY p.game_date, p.model_id, p.game_id,
                        COALESCE(p.player_id, ''), p.pick_side
           ORDER BY (p.signal_type = 'BET') DESC, p.created_at, p.pick_id
         ) AS rn
  FROM picks p
  WHERE p.is_live IS NOT TRUE
)
SELECT pick_id, model_id, sport, game_id, game_date, pick_label, pick_side,
       signal_type, scored_line, dk_odds, result, profit_flat, created_at
FROM ranked
WHERE rn > 1
ORDER BY model_id, game_date, pick_id
"""

COLUMNS = ("pick_id", "model_id", "sport", "game_id", "game_date", "pick_label",
           "pick_side", "signal_type", "scored_line", "dk_odds", "result",
           "profit_flat", "created_at")


def find_duplicates(conn) -> list[dict]:
    return [dict(zip(COLUMNS, r))
            for r in conn.execute(SELECT_DUPLICATES).fetchall()]


def _summarise(rows: list[dict]) -> None:
    by_model: dict[str, list[dict]] = {}
    for r in rows:
        by_model.setdefault(r["model_id"], []).append(r)
    for model, rs in sorted(by_model.items()):
        bets = [r for r in rs if r["signal_type"] == "BET"]
        settled = [r for r in bets if r["result"] in ("WIN", "LOSS", "PUSH")]
        units = sum(float(r["profit_flat"] or 0)
                    for r in settled if r["dk_odds"] is not None) / 100.0
        dates = sorted(r["game_date"] for r in rs)
        logger.info(
            f"  {model}: {len(rs)} duplicate row(s), {len(bets)} BET, "
            f"{len(settled)} settled ({units:+.2f}u of published P&L), "
            f"{dates[0]} -> {dates[-1]}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="actually delete (default is a dry run)")
    ap.add_argument("--backup-dir", default="backups",
                    help="where the pre-delete JSON snapshot is written")
    args = ap.parse_args()

    conn = get_connection()
    rows = find_duplicates(conn)

    if not rows:
        logger.info("No duplicate pick rows found — nothing to do.")
        return 0

    logger.info(f"{len(rows)} duplicate pick row(s) — a pick re-written after "
                f"its lock was released:")
    _summarise(rows)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = Path(args.backup_dir) / f"duplicate_picks_{stamp}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    logger.info(f"Snapshot written to {backup}")

    if not args.apply:
        logger.info("DRY RUN — nothing deleted. Re-run with --apply to delete.")
        return 0

    ids = [r["pick_id"] for r in rows]
    # ANY(%s) rather than a built IN-list: one bound parameter, no string
    # interpolation of ids into SQL.
    deleted = conn.execute(
        "DELETE FROM picks WHERE pick_id = ANY(%s) RETURNING pick_id", (ids,)
    ).fetchall()
    conn.commit()

    logger.info(f"Deleted {len(deleted)} row(s). picks_log holds every one of "
                f"them, and {backup} holds a copy.")
    logger.info("Next: the pipeline's view migrations will create "
                "uq_picks_one_row_per_pick on the now-clean table, and "
                "run_pipeline.py --step refresh-outcomes rebuilds the matview.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
