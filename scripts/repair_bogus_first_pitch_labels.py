"""Undo the in_play labels that a bogus first_pitch_at produced.

FOUND 2026-09-03 while wiring the pre-game cutoff into the prop price read.

WHAT HAPPENED. `data/first_pitch.py` derives `games.first_pitch_at` from the
earliest `live_game_state` row marked 'Live'. For 7 of 415 covered MLB games
that derivation is wrong by hours -- six of them ~6 hours early, which is the
signature of a day-night doubleheader whose second game was matched to the
FIRST game's live state:

    MLB_2026-08-29_BOS_NYY   first_pitch 16:50Z   commence 23:16Z   -386 min
    MLB_2026-08-29_ARI_SF    first_pitch 19:50Z   commence 02:06Z   -376 min
    ...

`relabel_in_play` bounds on COALESCE(first_pitch_at, commence_time), so on
those games it re-stamped every quote taken during the AFTERNOON as in_play.
The rows are genuinely pre-game and every pre-game reader now skips them.

    6,565 rows across 7 games. ARI_SF alone: 4,322, from 19:49:57Z (six
    seconds before the bogus "first pitch") to 02:05:58Z (two seconds before
    the real start).

THE CODE IS ALREADY FIXED. data.first_pitch.trusted_first_pitch and the CASE
in pregame_cutoff_sql refuse a first_pitch_at more than
SUSPICIOUS_EARLY_MINUTES before the scheduled start, so this cannot recur.
This script repairs the rows the old bound already wrote.

WHY THIS IS SAFE TO REVERSE, WHICH relabel_in_play IS NOT. That function is
one-directional on purpose: 48,712 rows in this database are labelled in_play
by the LIVE LOOP with a timestamp at or before their scheduled start, and
re-labelling those on the strength of a schedule would manufacture the leak it
exists to remove. This script does not touch them. It is scoped to the 7 games
whose derivation is provably wrong, and within those to rows at or before the
SCHEDULED start -- the window the bogus cutoff created and nothing else.

`odds` has no audit trigger, and the flip is NOT self-reversing: once these
rows read 'open' the same query no longer finds them, and widening it to
snapshot_type='open' would also sweep up rows that were legitimately open all
along. So the backup is the only way back, and a JSON file on a Railway
container is not one -- the disk is ephemeral, so it is gone with the deploy.

The backup is therefore a TABLE IN SUPABASE, written and COUNT-VERIFIED inside
the same transaction as the update, exactly as the team-stats rebuild did
(*_pre_rebuild_20260903). CLAUDE.md 1b: extracted data belongs in Supabase. The
JSON file is still written, as a convenience, not as the safety net.

    python -m scripts.repair_bogus_first_pitch_labels           # show the set
    python -m scripts.repair_bogus_first_pitch_labels --apply   # relabel
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from data.db import get_connection
from data.first_pitch import SUSPICIOUS_EARLY_MINUTES

# The games whose derived first pitch is not believable, and within them the
# rows the old bound flipped. Both halves are computed, never listed: a
# hard-coded game list would go stale the next time the derivation misfires.
SELECT_SQL = f"""
WITH bogus AS (
  SELECT game_id, commence_time, first_pitch_at
  FROM games
  WHERE first_pitch_at IS NOT NULL
    AND commence_time  IS NOT NULL
    AND first_pitch_at::timestamptz
        < commence_time::timestamptz - interval '{SUSPICIOUS_EARLY_MINUTES} minutes'
)
SELECT o.odds_id, o.game_id, o.sport, o.bookmaker, o.market, o.snapshot_at,
       o.snapshot_type, b.first_pitch_at, b.commence_time
FROM odds o
JOIN bogus b ON b.game_id = o.game_id
WHERE o.snapshot_type = 'in_play'
  AND o.snapshot_at::timestamptz <= b.commence_time::timestamptz
ORDER BY o.game_id, o.snapshot_at
"""

COLUMNS = ("odds_id", "game_id", "sport", "bookmaker", "market", "snapshot_at",
           "snapshot_type", "first_pitch_at", "commence_time")


def find_rows(conn) -> list[dict]:
    return [dict(zip(COLUMNS, r)) for r in conn.execute(SELECT_SQL).fetchall()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="actually relabel (default is a dry run)")
    ap.add_argument("--backup-dir", default="backups")
    ap.add_argument("--backup-table",
                    default="odds_pre_first_pitch_relabel_20260903",
                    help="Supabase table the affected rows are copied to "
                         "before the update, in the same transaction")
    args = ap.parse_args()

    conn = get_connection()
    rows = find_rows(conn)
    if not rows:
        logger.info("No rows carry an in_play label from a bogus first pitch.")
        return 0

    by_game: dict[str, list[dict]] = {}
    for r in rows:
        by_game.setdefault(r["game_id"], []).append(r)
    logger.info(f"{len(rows)} row(s) across {len(by_game)} game(s) were "
                f"labelled in_play by a first_pitch_at that is not believable:")
    for gid, rs in sorted(by_game.items(), key=lambda kv: -len(kv[1])):
        logger.info(f"  {gid}: {len(rs)} rows, "
                    f"{rs[0]['snapshot_at']} -> {rs[-1]['snapshot_at']} "
                    f"(listed start {rs[0]['commence_time']}, "
                    f"derived {rs[0]['first_pitch_at']})")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = Path(args.backup_dir) / f"bogus_first_pitch_labels_{stamp}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    logger.info(f"Snapshot written to {backup}")

    if not args.apply:
        logger.info("DRY RUN — nothing written. Re-run with --apply.")
        return 0

    ids = [r["odds_id"] for r in rows]
    tbl = args.backup_table

    # The durable backup, in the SAME transaction as the update. If the copy
    # fails, or copies the wrong number of rows, nothing is relabelled.
    conn.execute(f"DROP TABLE IF EXISTS {tbl}")
    conn.execute(f"CREATE TABLE {tbl} AS "
                 f"SELECT * FROM odds WHERE odds_id = ANY(%s)", (ids,))
    backed_up = conn.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0]
    if backed_up != len(ids):
        conn.rollback()
        logger.error(f"Backup holds {backed_up} rows, expected {len(ids)} — "
                     f"rolled back, nothing relabelled.")
        return 1
    # §7: default privileges grant anon/authenticated ALL on a new public
    # table, and REVOKE ... FROM PUBLIC does not touch a named role.
    conn.execute(f"REVOKE ALL ON {tbl} FROM anon, authenticated")
    logger.info(f"Backed up {backed_up} row(s) to {tbl} (anon/authenticated "
                f"revoked).")

    updated = conn.execute(
        "UPDATE odds SET snapshot_type = 'open' WHERE odds_id = ANY(%s) "
        "RETURNING odds_id", (ids,)
    ).fetchall()
    conn.commit()
    logger.info(f"Relabelled {len(updated)} row(s) in_play -> open. "
                f"To undo: UPDATE odds o SET snapshot_type = b.snapshot_type "
                f"FROM {tbl} b WHERE b.odds_id = o.odds_id;")

    if find_rows(conn):
        logger.warning("Some rows still match after the update.")
        return 1
    logger.info("Verified: none remain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
