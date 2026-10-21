"""
Per-model ROI, all three defensible definitions side by side.

WHY THIS EXISTS
---------------
2026-08-31, mike: "you showed me screen shots yesterday of pretty much all
these models with positive roi, now you are saying they all have negative roi?"

Both were true. They are different populations, and nothing named them clearly
enough to tell apart, so the same model reads +54.7% on one screen and -6.8% on
another. That ambiguity is the bug this report exists to remove.

THE THREE NUMBERS
-----------------
1. ISSUED  - `picks WHERE signal_type = 'BET'`, settled. The bets the system
   actually published. This is the track record: it is what a follower could
   have placed, at the price they were given.

2. BOARD   - `v_model_full_outcome_picks`, which feeds `v_public_track_record`
   and the app. It selects from `picks` with NO signal_type filter at all and
   applies TODAY's thresholds retrospectively. So it counts dead-zone NONE rows
   and AVOID rows as picks, provided they happen to clear the current cut in
   hindsight.

3. CLEARS-TODAY - the subset of (1) that would still fire under today's cuts.
   Honest for "is the current threshold any good", still in-sample.

WHY (2) READS SO MUCH HIGHER
----------------------------
Two biases compound:

  * HINDSIGHT. The thresholds were swept ON this data. Applying them back to
    the same history keeps the rows that won, which is a backtest of the tuning,
    not a record.
  * POPULATION. No signal_type filter means rows that were never bet are
    counted as if they were.

The size gap is the tell: wnba_prop_player_rebounds is 9 rows on the board
against 190 issued bets. A number computed over 5% of the evidence, chosen with
hindsight, is not the model's record.

(2) is the right shape for a threshold sweep. It is the wrong shape for
anything anyone reads as performance. See docs/sessions/ for the 2026-08-31
audit that first flagged this and deliberately left the published view alone.

USAGE
-----
    python -m scripts.model_roi_report                # every model
    python -m scripts.model_roi_report --min-bets 50  # only real samples
    python -m scripts.model_roi_report --model mlb_moneyline
"""

from __future__ import annotations

import argparse

from data.db import get_connection

SQL = """
WITH board AS (
  SELECT model_id, COUNT(*) AS n,
         ROUND((100.0*SUM(profit_units)/NULLIF(COUNT(*),0))::numeric, 2) AS roi
  FROM v_model_full_outcome_picks GROUP BY 1
),
issued AS (
  SELECT model_id, COUNT(*) AS n,
         COUNT(*) FILTER (WHERE result='WIN')  AS w,
         COUNT(*) FILTER (WHERE result='LOSS') AS l,
         ROUND((SUM(profit_flat)/NULLIF(COUNT(*),0))::numeric, 2) AS roi
  FROM picks
  WHERE signal_type='BET' AND result IN ('WIN','LOSS','PUSH')
    AND is_live IS NOT TRUE
  GROUP BY 1
),
clears AS (
  SELECT p.model_id, COUNT(*) AS n,
         ROUND((SUM(p.profit_flat)/NULLIF(COUNT(*),0))::numeric, 2) AS roi
  FROM picks p JOIN model_action_thresholds m ON m.model_id = p.model_id
  WHERE p.signal_type='BET' AND p.result IN ('WIN','LOSS','PUSH')
    AND p.is_live IS NOT TRUE
    AND p.model_probability >= m.min_prob
    AND (m.prob_only OR p.edge >= COALESCE(m.min_edge, 0))
    AND (m.min_odds IS NULL OR p.dk_odds IS NULL OR p.dk_odds >= m.min_odds)
  GROUP BY 1
)
SELECT COALESCE(i.model_id, b.model_id, c.model_id) AS model_id,
       i.n AS issued_n, i.w, i.l, i.roi AS issued_roi,
       c.n AS clears_n, c.roi AS clears_roi,
       b.n AS board_n, b.roi AS board_roi
FROM issued i
FULL JOIN board  b ON b.model_id = i.model_id
FULL JOIN clears c ON c.model_id = i.model_id
ORDER BY i.n DESC NULLS LAST
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-bets", type=int, default=0,
                    help="hide models with fewer than N issued bets")
    ap.add_argument("--model", help="one model id")
    args = ap.parse_args()

    conn = get_connection()
    try:
        rows = conn.execute(SQL).fetchall()
    finally:
        conn.close()

    print(f"{'model':<30}{'ISSUED (the record)':>26}"
          f"{'CLEARS TODAY':>20}{'BOARD (published)':>22}")
    print(f"{'':<30}{'n':>7}{'W-L':>10}{'ROI%':>9}"
          f"{'n':>7}{'ROI%':>13}{'n':>8}{'ROI%':>14}")
    print("-" * 98)

    flagged = []
    for (mid, i_n, w, l, i_roi, c_n, c_roi, b_n, b_roi) in rows:
        if args.model and mid != args.model:
            continue
        if (i_n or 0) < args.min_bets:
            continue
        wl = f"{w or 0}-{l or 0}"
        print(f"{mid:<30}{i_n or 0:>7}{wl:>10}{_f(i_roi):>9}"
              f"{c_n or 0:>7}{_f(c_roi):>13}{b_n or 0:>8}{_f(b_roi):>14}")
        # The gap that caused the confusion: board looks good, record does not.
        if i_roi is not None and b_roi is not None and b_roi - i_roi >= 10:
            flagged.append((mid, float(b_roi), float(i_roi), b_n or 0, i_n or 0))

    if flagged:
        print()
        print("BOARD OVERSTATES THE RECORD BY 10pp OR MORE:")
        for mid, b, i, bn, inn in sorted(flagged, key=lambda r: r[1] - r[2],
                                         reverse=True):
            print(f"  {mid:<30} board {b:+.1f}% on {bn:>4} rows   "
                  f"vs record {i:+.1f}% on {inn:>4} bets   "
                  f"(+{b - i:.1f}pp)")
        print("\n  The board applies TODAY's cuts to history and counts rows")
        print("  that were never bet. It is a threshold backtest, not a record.")
    return 0


def _f(v) -> str:
    return "—" if v is None else f"{float(v):+.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
