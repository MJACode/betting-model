"""Two one-off pick repairs mike approved on 2026-09-03.

Both are DML, and the Supabase MCP a dev session gets is read-only, so this
runs on the Railway worker or Matt's machine. Dry run by default.

    python -m scripts.repair_pick_data                    # show both plans
    python -m scripts.repair_pick_data --backfill --apply  # fill player_id
    python -m scripts.repair_pick_data --delete --apply    # remove orphans

────────────────────────────────────────────────────────────────────────────
1. BACKFILL player_id ON PROP PICKS THAT NEVER GOT ONE

`mv_scored_pick_outcomes` grades a prop through a LATERAL keyed on
`l.player_id = p.player_id`. NULL never matches, so a pick with no player_id
grades 'U' and is dropped from the matview entirely — invisible to every
surface built on it, even though `picks.result` settled it long ago.

Six `mlb_prop_pitcher_k` picks from 2026-05-09..05-13 are in that state
(-4.33u). Each is resolved by an EXACT player_name match inside the SAME
game, and only when exactly one candidate row carries the stat the model
needs — an ambiguous match is left alone rather than guessed, because a
wrong player_id would silently grade the pick against another man's line.

Verified before writing this: all six resolve, and the stat each one
resolves to AGREES with the settlement already in `picks.result`
(Roupp 8 Ks vs Under 5.5 = LOSS, Ashcraft 6 vs Over 4.5 = WIN, Snell 5 vs
Over 5.5 = LOSS, Strider 8 = LOSS, Detmers 6 x2 = LOSS). So the matview will
reproduce the existing record rather than change it.

────────────────────────────────────────────────────────────────────────────
2. DELETE UNGRADED ORPHANS WHOSE GAME NEVER GOT A FINAL SCORE

mike: "delete the 69 picks ... like they never existed as long as these are
not live or future games."

That guard does real work. Of the 69 ungraded BETs whose game has no final
score, only **57** are on games that are definitively over; 16 are FUTURE
games (2026-09-03..09-05), 7 kicked off within the last six hours and may
still be in play, and 1 has no `commence_time` at all and cannot be judged.
A further 6 of the 57 carry `is_live`, and mike's wording excludes live, so
they are held back too — leaving **51**.

The six-hour buffer is the point: `commence_time < NOW()` alone would delete
picks on games still being played, which is exactly what the instruction
ruled out.

RECOVERY. `picks_audit_trigger` writes every DELETE to `picks_log`, so this
is reversible from the database alone. The script also snapshots every row to
JSON first.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from data.db import get_connection

# A game is certainly finished this long after first pitch.
FINISHED_AFTER = "6 hours"

# Picks with no player_id, resolvable by an unambiguous name match in the same
# game. `needs` names the column the model grades on, so a candidate row only
# counts when it actually carries that stat — a pitcher's batting row does not.
BACKFILL_SQL = """
WITH want AS (
  SELECT p.pick_id, p.game_id,
         regexp_replace(p.pick_label, ' (Over|Under) .*$', '') AS player_name,
         CASE p.model_id
           WHEN 'mlb_prop_pitcher_k'     THEN 'p_strikeouts'
           WHEN 'mlb_prop_pitcher_walks' THEN 'p_walks'
           WHEN 'mlb_prop_pitcher_hits'  THEN 'p_hits_allowed'
           WHEN 'mlb_prop_pitcher_er'    THEN 'p_earned_runs'
           WHEN 'mlb_prop_pitcher_outs'  THEN 'innings_pitched'
           ELSE 'hits'
         END AS needs
  FROM picks p
  WHERE p.model_id LIKE 'mlb\\_prop\\_%%'
    AND p.signal_type = 'BET'
    AND p.player_id IS NULL
),
cand AS (
  SELECT w.pick_id, w.player_name,
         MIN(l.player_id) AS resolved_id,
         COUNT(DISTINCT l.player_id) AS n_candidates
  FROM want w
  JOIN player_game_log l
    ON l.game_id = w.game_id
   AND l.player_name = w.player_name
   AND ((w.needs = 'p_strikeouts'   AND l.p_strikeouts   IS NOT NULL)
     OR (w.needs = 'p_walks'        AND l.p_walks        IS NOT NULL)
     OR (w.needs = 'p_hits_allowed' AND l.p_hits_allowed IS NOT NULL)
     OR (w.needs = 'p_earned_runs'  AND l.p_earned_runs  IS NOT NULL)
     OR (w.needs = 'innings_pitched' AND l.innings_pitched IS NOT NULL)
     OR (w.needs = 'hits'           AND l.hits           IS NOT NULL))
  GROUP BY w.pick_id, w.player_name
)
SELECT c.pick_id, c.player_name, c.resolved_id, p.model_id, p.game_date,
       p.pick_label, p.result
FROM cand c JOIN picks p ON p.pick_id = c.pick_id
WHERE c.n_candidates = 1
ORDER BY c.pick_id
"""

ORPHAN_SQL = f"""
SELECT p.pick_id, p.model_id, p.sport, p.game_id, p.game_date, p.pick_label,
       p.signal_type, p.dk_odds, p.created_at, g.commence_time
FROM picks p
JOIN games g ON g.game_id = p.game_id
WHERE p.signal_type = 'BET'
  AND p.result IS NULL
  AND g.home_score IS NULL
  AND g.commence_time IS NOT NULL
  AND g.commence_time::timestamptz <= NOW() - interval '{FINISHED_AFTER}'
  AND p.is_live IS NOT TRUE
ORDER BY p.game_date, p.pick_id
"""


def _rows(conn, sql, cols):
    return [dict(zip(cols, r)) for r in conn.execute(sql).fetchall()]


def _snapshot(rows, name, backup_dir):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = Path(backup_dir) / f"{name}_{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    logger.info(f"Snapshot written to {path}")


def backfill(conn, apply_it, backup_dir) -> int:
    cols = ("pick_id", "player_name", "resolved_id", "model_id", "game_date",
            "pick_label", "result")
    rows = _rows(conn, BACKFILL_SQL, cols)
    if not rows:
        logger.info("No prop picks need a player_id backfill.")
        return 0
    logger.info(f"{len(rows)} pick(s) resolvable to exactly one player_id:")
    for r in rows:
        logger.info(f"  {r['pick_id']} {r['pick_label']} ({r['game_date']}) "
                    f"-> player_id {r['resolved_id']} [{r['result']}]")
    _snapshot(rows, "player_id_backfill", backup_dir)
    if not apply_it:
        logger.info("DRY RUN — nothing written. Re-run with --apply.")
        return 0
    for r in rows:
        conn.execute("UPDATE picks SET player_id = %s WHERE pick_id = %s "
                     "AND player_id IS NULL", (r["resolved_id"], r["pick_id"]))
    conn.commit()
    logger.info(f"Backfilled {len(rows)} player_id(s). Refresh "
                f"mv_scored_pick_outcomes to pick them up.")
    return len(rows)


def delete_orphans(conn, apply_it, backup_dir) -> int:
    cols = ("pick_id", "model_id", "sport", "game_id", "game_date",
            "pick_label", "signal_type", "dk_odds", "created_at",
            "commence_time")
    rows = _rows(conn, ORPHAN_SQL, cols)
    if not rows:
        logger.info("No ungraded orphans on finished games.")
        return 0
    logger.info(f"{len(rows)} ungraded BET pick(s) on games that never got a "
                f"final score and finished over {FINISHED_AFTER} ago:")
    by_date: dict[str, int] = {}
    for r in rows:
        by_date[r["game_date"]] = by_date.get(r["game_date"], 0) + 1
    for d, n in sorted(by_date.items()):
        logger.info(f"  {d}: {n}")
    _snapshot(rows, "ungraded_orphan_picks", backup_dir)
    if not apply_it:
        logger.info("DRY RUN — nothing deleted. Re-run with --apply.")
        return 0
    ids = [r["pick_id"] for r in rows]
    deleted = conn.execute(
        "DELETE FROM picks WHERE pick_id = ANY(%s) RETURNING pick_id", (ids,)
    ).fetchall()
    conn.commit()
    logger.info(f"Deleted {len(deleted)} pick(s); picks_audit_trigger has "
                f"logged each to picks_log.")
    if _rows(conn, ORPHAN_SQL, cols):
        logger.warning("Some orphans still match after the delete.")
        return 1
    logger.info("Verified: no ungraded orphans remain on finished games.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backfill", action="store_true", help="run repair 1")
    ap.add_argument("--delete", action="store_true", help="run repair 2")
    ap.add_argument("--apply", action="store_true",
                    help="actually write (default is a dry run)")
    ap.add_argument("--backup-dir", default="backups")
    args = ap.parse_args()

    run_all = not (args.backfill or args.delete)
    conn = get_connection()
    if args.backfill or run_all:
        backfill(conn, args.apply, args.backup_dir)
    if args.delete or run_all:
        delete_orphans(conn, args.apply, args.backup_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
