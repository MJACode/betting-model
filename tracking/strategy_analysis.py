"""
Strategy analysis over the full picks table — opening vs closing line, and
public-betting side — to decide how we should lock and filter picks.

Unlike tracking.opening_report (which reads the opening_signals SHADOW track,
only populated since 2026-06-20), this report runs over EVERY settled,
game-level BET pick in the picks table since --since (default 2026-04-14), at
real DK odds. It answers Matt's two questions on the largest sample available:

  1. Does it matter whether we bet the OPENING line we scored vs the CLOSING
     line? → compares flat P&L at dk_odds (scored/open) vs closing_dk_odds.
  2. Does the PUBLIC side predict results? → slices by Action-Network public
     backing on our pick side (contrarian = public <=45% on our side,
     with_public = >=55%, even = 46-54%).

IMPORTANT — data coverage is the binding constraint, NOT the date range:
  * public_bet_pct was first captured 2026-05-31.
  * closing_dk_odds / clv_pct were first captured 2026-06-06.
There is no public/closing data for April–May picks, so those slices are
capped at whatever has been recorded. The report prints coverage up top so a
small slice is never mistaken for a real signal. Read-only.

Run:  python -m tracking.strategy_analysis [--since 2026-04-14]
"""

from __future__ import annotations

import argparse

from data.db import get_connection

# Game-level markets only — props/F5/UFC/golf carry no public splits and (for
# props) settle on a different path. Mirrors tracking.opening_report._EXCLUDE.
_EXCLUDE = """
  AND model_id NOT LIKE 'mlb_prop_%%'
  AND model_id NOT LIKE 'wnba_prop_%%'
  AND model_id NOT LIKE 'nba_prop_%%'
  AND model_id NOT LIKE 'ufc_%%'
  AND model_id NOT LIKE 'golf_%%'
  AND model_id NOT LIKE 'mlb_live_%%'
"""

# Flat-bet ($1 stake) profit from an American-odds column, given the result.
def _profit_sql(odds_col: str) -> str:
    return (f"CASE WHEN result='WIN' THEN "
            f"(CASE WHEN {odds_col}>0 THEN {odds_col}/100.0 ELSE 100.0/abs({odds_col}) END) "
            f"WHEN result='LOSS' THEN -1.0 ELSE 0 END")


_BASE = f"""
  FROM picks
  WHERE game_date >= %s AND (is_live IS NOT TRUE)
    AND signal_type = 'BET' AND result IN ('WIN','LOSS','PUSH')
    AND dk_odds IS NOT NULL
    {_EXCLUDE}
"""


def _row(conn, where: str, since: str, odds_col: str = "dk_odds"):
    """(wins, losses, pushes, roi_pct) for picks matching `where`, P&L at odds_col."""
    r = conn.execute(f"""
        SELECT
          SUM(CASE WHEN result='WIN'  THEN 1 ELSE 0 END),
          SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END),
          SUM(CASE WHEN result='PUSH' THEN 1 ELSE 0 END),
          AVG({_profit_sql(odds_col)})
        {_BASE} {where}
    """, (since,)).fetchone()
    w, l, p, avg = int(r[0] or 0), int(r[1] or 0), int(r[2] or 0), r[3]
    return w, l, p, (float(avg) * 100 if avg is not None else None)


def _fmt(label: str, w, l, p, roi) -> str:
    decided = w + l
    wr = w / decided if decided else 0.0
    roi_s = f"{roi:+6.1f}%" if roi is not None else "   —  "
    return f"  {label:<28} {w:>3}-{l:<3} ({p}P) | win {wr:5.1%} | ROI {roi_s} | n={decided}"


def strategy_analysis(since: str = "2026-04-14") -> None:
    conn = get_connection()
    try:
        # ---- coverage ----
        cov = conn.execute(f"""
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE public_bet_pct IS NOT NULL),
                   MIN(game_date) FILTER (WHERE public_bet_pct IS NOT NULL),
                   COUNT(*) FILTER (WHERE closing_dk_odds IS NOT NULL),
                   MIN(game_date) FILTER (WHERE closing_dk_odds IS NOT NULL)
            {_BASE}
        """, (since,)).fetchone()
        total, n_pub, pub0, n_clv, clv0 = cov

        print(f"\n{'═'*72}")
        print(f"  STRATEGY ANALYSIS — game-level settled BET picks since {since}")
        print(f"{'═'*72}")
        print(f"  Sample: {total} settled game-level BET picks")
        print(f"  Public-side data:  {n_pub} picks (first {pub0})")
        print(f"  Closing-line data: {n_clv} picks (first {clv0})")
        if (n_pub or 0) < 50 or (n_clv or 0) < 50:
            print("  ⚠ Small slices — treat every split below as directional, NOT significant.")

        # ---- Q1: opening line vs closing line (CLV-covered set only) ----
        clv_only = "AND closing_dk_odds IS NOT NULL"
        op = _row(conn, clv_only, since, "dk_odds")
        cl = _row(conn, clv_only, since, "closing_dk_odds")
        print(f"\n  Q1 — bet the OPENING line we scored vs the CLOSING line:")
        print(_fmt("bet at OPENING odds", *op))
        print(_fmt("bet at CLOSING odds", *cl))

        # ---- Q2: public side (public-covered set only), P&L at scored odds ----
        print(f"\n  Q2 — by public side on our pick (P&L at scored odds):")
        for label, cond in (
            ("contrarian (public <=45%)", "AND public_bet_pct <= 45"),
            ("even (46-54%)",             "AND public_bet_pct BETWEEN 46 AND 54"),
            ("with public (>=55%)",       "AND public_bet_pct >= 55"),
        ):
            print(_fmt(label, *_row(conn, f"AND public_bet_pct IS NOT NULL {cond}", since)))
        print(_fmt("(no public split)", *_row(conn, "AND public_bet_pct IS NULL", since)))
        print(f"{'═'*72}\n")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Opening-vs-closing + public-side analysis over all picks")
    parser.add_argument("--since", default="2026-04-14",
                        help="only count picks on/after this date (default 2026-04-14)")
    args = parser.parse_args()
    strategy_analysis(args.since)
