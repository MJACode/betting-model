"""Put back the NCAAB cards' NONE rows the game scorer's sweep deleted.

WHAT HAPPENED. PR #1147 (merged 2026-11-04 12:02Z) made five NCAAB cards
write a NONE row -- priced, not bet, no stake -- for every game they priced
and did not bet, so the app's All board shows every scored game (Matt,
2026-11-04). The game scorer's end-of-pass sweep (models/scorer.run_scorer)
had no model filter on a full pass and deleted every writer's unsettled
non-BET rows on unstarted games: 257 of the first 278 NCAAB NONE rows, in 27
transactions, each 0.3-2.5 s before a full scoring pass logged its finish in
pipeline_log. A card decides a game once and never writes it again, so the
rows were gone. The sweep now clears only the models its pass re-writes
(scorer._pass_rewritten_models, 2026-11-06).

WHAT THIS DOES. For each (game, card) whose NONE row picks_log shows deleted,
whose game has not started, and which has NO row in picks now (no BET, no
newer NONE), it inserts the logged row back: the same pick_id and the same
created_at (CLAUDE.md 1c: timing is data). Started games are left alone --
the All board's pre-game view of them has passed, and the decision on those
is the owner's (docs/sports/ncaab.md).

WHAT COMES BACK AND WHAT DOES NOT. picks_log keeps every column but four the
cards write. Two are rebuilt by each card's own rule, measured against the
131 NCAAB NONE rows in picks on 2026-11-06 15:06Z (every one matched on every
logged column and on both rebuilt ones):

  * model_probability_cal = model_probability (all five cards decide on
    their own number, config.MODELS_ON_OWN_PROBABILITY);
  * best_book / best_odds / best_implied_prob / best_edge = the decision_*
    columns, except: ncaab_total_blend writes none, and the two first-half
    cards write none when the decision book is DraftKings.

The two bet links (dk_bet_link, best_bet_link) are not in the log and stay
NULL. downgrade_reason stays NULL: none of the five was paused from
2026-11-04 to 11-06 (config.PAUSED_MODELS).

Safe to repeat: a game that has a row, or has started, is skipped, and the
insert is ON CONFLICT DO NOTHING. A NONE row publishes nothing and settles
nothing (Discord, push, X and the record select BETs).

Run: `python -m tracking.restore_swept_ncaab_none_rows` (counts only), add
`--apply` to write. On the worker: job type restore_swept_ncaab_none_rows.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from loguru import logger

CARDS = ("ncaab_total_blend", "ncaab_spread_market",
         "ncaab_moneyline_own_spread", "ncaab_first_half_spread",
         "ncaab_first_half_total")
NO_BEST = ("ncaab_total_blend",)
NO_BEST_AT_DK = ("ncaab_first_half_spread", "ncaab_first_half_total")
REFERENCE_BOOK = "draftkings"
# PR #1147 merged 2026-11-04 12:02Z; no NCAAB card wrote a NONE row before.
SINCE = "2026-11-04T12:00:00+00:00"

# Every picks column picks_log keeps that the cards write.
LOG_COLS = ("pick_id", "game_id", "model_id", "sport", "game_date", "game_time",
            "run_time", "pick_side", "pick_label", "model_probability",
            "dk_implied_prob", "edge", "dk_odds", "scored_line",
            "kelly_fraction", "recommended_bet", "bankroll_at_pick",
            "injury_flag", "injury_detail", "signal_type", "confidence_tier",
            "created_at", "decision_book", "decision_odds",
            "decision_implied_prob", "decision_edge", "line_book")
REBUILT_COLS = ("model_probability_cal", "best_book", "best_odds",
                "best_implied_prob", "best_edge")

_SELECT = f"""
    SELECT DISTINCT ON (l.game_id, l.model_id)
           {', '.join('l.' + c for c in LOG_COLS)}
      FROM picks_log l
      JOIN games g ON g.game_id = l.game_id
     WHERE l.operation = 'DELETE'
       AND l.sport = 'NCAAB'
       AND l.model_id = ANY(%(cards)s)
       AND l.signal_type = 'NONE'
       AND l.result IS NULL
       AND l.logged_at >= %(since)s
       AND g.commence_time IS NOT NULL
       AND g.commence_time::timestamptz > %(now)s
       AND NOT EXISTS (SELECT 1 FROM picks p
                        WHERE p.game_id = l.game_id AND p.model_id = l.model_id)
       AND NOT EXISTS (SELECT 1 FROM picks p WHERE p.pick_id = l.pick_id)
     ORDER BY l.game_id, l.model_id, l.created_at::timestamptz, l.log_id
"""

_COLS = LOG_COLS + REBUILT_COLS
_INSERT = (f"INSERT INTO picks ({', '.join(_COLS)}) "
           f"VALUES ({', '.join('%(' + c + ')s' for c in _COLS)}) "
           f"ON CONFLICT DO NOTHING RETURNING pick_id")


def rebuild(row: dict) -> dict:
    """The logged row plus the columns each card derives from it."""
    out = dict(row)
    out["model_probability_cal"] = row["model_probability"]
    no_best = (row["model_id"] in NO_BEST
               or (row["model_id"] in NO_BEST_AT_DK
                   and row["decision_book"] == REFERENCE_BOOK))
    for best, decision in (("best_book", "decision_book"),
                           ("best_odds", "decision_odds"),
                           ("best_implied_prob", "decision_implied_prob"),
                           ("best_edge", "decision_edge")):
        out[best] = None if no_best else row[decision]
    return out


def restore(conn, apply: bool = False, now: datetime | None = None) -> dict:
    """Restore what can be restored. Returns counts by card."""
    now = now or datetime.now(timezone.utc)
    rows = [dict(zip(LOG_COLS, r)) for r in conn.execute(
        _SELECT, {"cards": list(CARDS), "since": SINCE, "now": now}).fetchall()]
    found: dict[str, int] = {}
    restored: dict[str, int] = {}
    for row in rows:
        found[row["model_id"]] = found.get(row["model_id"], 0) + 1
        if not apply:
            continue
        got = conn.execute(_INSERT, rebuild(row)).fetchall()
        if got:
            restored[row["model_id"]] = restored.get(row["model_id"], 0) + 1
    if apply:
        conn.commit()
    result = {"apply": apply, "as_of": now.isoformat(),
              "found": found, "restored": restored,
              "n_found": sum(found.values()), "n_restored": sum(restored.values())}
    logger.info(f"restore_swept_ncaab_none_rows: {result}")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="write the rows (default: count only)")
    a = ap.parse_args()
    from data.db import get_connection
    conn = get_connection()
    try:
        print(restore(conn, apply=a.apply))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
