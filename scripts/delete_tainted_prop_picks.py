"""Delete the prop BETs that were priced off an IN-PLAY quote.

mike, 2026-09-03: "delete tainted picks."

WHAT THESE ROWS ARE. `models/scorer.py::_latest_dk_prop_row` used to take the
newest DraftKings prop quote with no time bound and no snapshot_type filter.
The prop ingestor keeps snapshotting after first pitch and labels those rows
'open', so a pick scored late was priced against a LIVE number. A pre-game
probability read against a live price is a large FAKE EDGE, so these picks
cleared their cut on arithmetic against a price that never existed pre-game.
The bound shipped the same day (tests/test_prop_price_pregame_bound.py); this
script removes the rows it already wrote.

WHY DELETE RATHER THAN KEEP. CLAUDE.md §1c says a pick is a pick and line
movement never retracts one. That rule protects a REAL bet whose number later
moved. It does not reach these: the qualifying price was never available to
anyone, so no bet was ever given at it. §1c's own carve-out is "rows that were
never a pick", and mike made the call explicitly.

THE SET, stated so it is reproducible and cannot quietly widen. A row must
satisfy BOTH, which is why the count is small and every member is explicable:

  1. its recorded dk_odds is more than 20 percentage points of implied
     probability away from EVERY DraftKings pre-game quote for that exact
     player + market + line (snapshot_at <= commence_time, not in_play), and
  2. it was created AFTER commence_time -- the mechanism itself.

Measured on production 2026-09-03: 47 picks, all of them satisfying (2) as
well as (1). mlb_prop_batter_hits 46 (16-30, -11.18u, 2026-05-25 -> 06-20) and
wnba_prop_player_threes 1 (0-1, 2026-06-21).

RECOVERY. picks_audit_trigger writes every DELETE to picks_log, so this is
reversible from the database alone. The script ALSO writes a JSON snapshot of
every row before deleting, because a backup you have to reconstruct from an
audit table is not the one you want at 2am.

Dry run by default. Nothing is written without --apply.

    python -m scripts.delete_tainted_prop_picks            # show the set
    python -m scripts.delete_tainted_prop_picks --apply    # delete it
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from data.db import get_connection

# Implied-probability distance beyond which a recorded price cannot be
# explained by ordinary movement between hourly pre-game snapshots.
GAP_THRESHOLD = 0.20

# model_id -> the market name used in player_prop_odds.
MARKET_BY_MODEL = {
    "mlb_prop_batter_hits":      "batter_hits",
    "mlb_prop_batter_runs":      "batter_runs_scored",
    "mlb_prop_batter_rbi":       "batter_rbis",
    "mlb_prop_batter_walks":     "batter_walks",
    "mlb_prop_batter_tb":        "batter_total_bases",
    "mlb_prop_batter_sb":        "batter_stolen_bases",
    "mlb_prop_pitcher_k":        "pitcher_strikeouts",
    "mlb_prop_pitcher_walks":    "pitcher_walks",
    "mlb_prop_pitcher_hits":     "pitcher_hits_allowed",
    "mlb_prop_pitcher_er":       "pitcher_earned_runs",
    "mlb_prop_pitcher_outs":     "pitcher_outs",
    "wnba_prop_player_points":   "player_points",
    "wnba_prop_player_rebounds": "player_rebounds",
    "wnba_prop_player_assists":  "player_assists",
    "wnba_prop_player_threes":   "player_threes",
    "wnba_prop_player_pra":      "player_points_rebounds_assists",
}

_MARKET_CASE = "\n".join(
    f"             WHEN '{m}' THEN '{mk}'" for m, mk in MARKET_BY_MODEL.items()
)

# One statement so the set cannot drift between the preview and the delete.
SELECT_TAINTED = f"""
WITH mk AS (
  SELECT p.pick_id, p.model_id, p.sport, p.game_id, p.game_date, p.pick_label,
         p.pick_side, p.scored_line, p.dk_odds, p.result, p.profit_flat,
         p.clv_pct, p.created_at, g.commence_time,
         regexp_replace(p.pick_label, ' (Over|Under) .*$', '') AS player,
         CASE p.model_id
{_MARKET_CASE}
         END AS market
  FROM picks p
  JOIN games g ON g.game_id = p.game_id
  WHERE p.model_id LIKE '%%\\_prop\\_%%'
    AND p.signal_type = 'BET'
    AND p.is_live IS NOT TRUE
    AND p.dk_odds IS NOT NULL
    AND g.commence_time IS NOT NULL
    AND p.created_at::timestamptz > g.commence_time::timestamptz
),
i AS (
  SELECT mk.*,
         CASE WHEN dk_odds < 0 THEN -dk_odds / (-dk_odds + 100.0)
              ELSE 100.0 / (dk_odds + 100.0) END AS bet_ip
  FROM mk WHERE market IS NOT NULL
),
gap AS (
  SELECT i.pick_id,
         MIN(abs(i.bet_ip - CASE WHEN i.pick_side = 'over'
             THEN (CASE WHEN o.over_price < 0
                        THEN -o.over_price / (-o.over_price + 100.0)
                        ELSE 100.0 / (o.over_price + 100.0) END)
             ELSE (CASE WHEN o.under_price < 0
                        THEN -o.under_price / (-o.under_price + 100.0)
                        ELSE 100.0 / (o.under_price + 100.0) END)
         END)) AS closest_pregame_gap
  FROM i
  JOIN player_prop_odds o
    ON  o.game_id     = i.game_id
    AND o.player_name = i.player
    AND o.market      = i.market
    AND o.line        = i.scored_line
    AND o.bookmaker   = 'draftkings'
    AND o.snapshot_type != 'in_play'
    AND o.snapshot_at::timestamptz <= i.commence_time::timestamptz
    AND o.over_price IS NOT NULL
    AND o.under_price IS NOT NULL
  GROUP BY i.pick_id
)
SELECT i.pick_id, i.model_id, i.sport, i.game_id, i.game_date, i.pick_label,
       i.pick_side, i.scored_line, i.dk_odds, i.result, i.profit_flat,
       i.clv_pct, i.created_at, i.commence_time,
       ROUND(gap.closest_pregame_gap::numeric, 4) AS closest_pregame_gap
FROM i JOIN gap ON gap.pick_id = i.pick_id
WHERE gap.closest_pregame_gap > %s
ORDER BY i.model_id, i.game_date, i.pick_id
"""

COLUMNS = ("pick_id", "model_id", "sport", "game_id", "game_date", "pick_label",
           "pick_side", "scored_line", "dk_odds", "result", "profit_flat",
           "clv_pct", "created_at", "commence_time", "closest_pregame_gap")


def find_tainted(conn) -> list[dict]:
    rows = conn.execute(SELECT_TAINTED, (GAP_THRESHOLD,)).fetchall()
    return [dict(zip(COLUMNS, r)) for r in rows]


def _summarise(rows: list[dict]) -> None:
    by_model: dict[str, list[dict]] = {}
    for r in rows:
        by_model.setdefault(r["model_id"], []).append(r)
    for model, rs in sorted(by_model.items()):
        wins = sum(1 for r in rs if r["result"] == "WIN")
        losses = sum(1 for r in rs if r["result"] == "LOSS")
        units = sum(float(r["profit_flat"] or 0) for r in rs) / 100.0
        dates = sorted(r["game_date"] for r in rs)
        logger.info(
            f"  {model}: {len(rs)} picks, {wins}-{losses}, "
            f"{units:+.2f}u, {dates[0]} -> {dates[-1]}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="actually delete (default is a dry run)")
    ap.add_argument("--backup-dir", default="backups",
                    help="where the pre-delete JSON snapshot is written")
    args = ap.parse_args()

    conn = get_connection()
    rows = find_tainted(conn)

    if not rows:
        logger.info("No tainted prop picks found — nothing to do.")
        return 0

    logger.info(f"{len(rows)} tainted prop pick(s) — priced off an in-play quote:")
    _summarise(rows)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = Path(args.backup_dir) / f"tainted_prop_picks_{stamp}.json"
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

    logger.info(f"Deleted {len(deleted)} pick(s). "
                f"picks_audit_trigger has logged every row to picks_log.")

    remaining = find_tainted(conn)
    if remaining:
        logger.warning(f"{len(remaining)} still match after the delete — "
                       f"investigate before re-running.")
        return 1
    logger.info("Verified: the tainted set is now empty.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
