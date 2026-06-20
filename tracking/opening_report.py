"""
Opening-signal vs live/closing comparison report.

Answers Matt's two questions from settled data:
  1. Does locking the FIRST BET signal beat chasing the hourly live line?
     → compares the opening-signal record to the live (closing) picks record
       over the same date range, game-level markets only.
  2. Does the line moving after we lock predict the result, and does it matter
     which side the public was on?
     → slices the opening-signal record by line_move_dir (toward/against/flat)
       and public_side (with_public/contrarian).

Read-only. Game-level markets only (that's what settle_opening_signals fills).
Run:  python -m tracking.opening_report [--since 2026-04-14]
"""

from __future__ import annotations

import argparse

from loguru import logger

from data.db import get_connection

# Game-level markets only — matches what the opening track settles.
_EXCLUDE = """
  AND model_id NOT LIKE 'mlb_prop_%%'
  AND model_id NOT LIKE 'wnba_prop_%%'
  AND model_id NOT LIKE 'nba_prop_%%'
  AND model_id NOT LIKE 'ufc_%%'
  AND model_id NOT LIKE 'golf_%%'
  AND model_id NOT LIKE 'mlb_live_%%'
"""

_AGG = """
    SUM(CASE WHEN result = 'WIN'  THEN 1 ELSE 0 END)  AS wins,
    SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END)  AS losses,
    SUM(CASE WHEN result = 'PUSH' THEN 1 ELSE 0 END)  AS pushes,
    COALESCE(SUM(profit_flat), 0)                     AS flat,
    AVG(clv_pct)                                      AS avg_clv
"""


def _fmt(label: str, wins, losses, pushes, flat, avg_clv) -> str:
    wins, losses, pushes = int(wins or 0), int(losses or 0), int(pushes or 0)
    decided = wins + losses
    win_rate = wins / decided if decided else 0.0
    roi = (flat or 0.0) / (decided * 100) if decided else 0.0
    clv = f"{avg_clv:+.2f}pp" if avg_clv is not None else "—"
    return (f"  {label:<26} {wins:>3}-{losses:<3} "
            f"({pushes}P) | win {win_rate:5.1%} | "
            f"ROI {roi:+6.1%} | units {(flat or 0)/100:+6.2f} | CLV {clv}")


def opening_report(since: str = "2026-04-14") -> None:
    conn = get_connection()
    try:
        live = conn.execute(f"""
            SELECT {_AGG.replace('clv_pct', 'NULL')}
            FROM picks
            WHERE signal_type = 'BET'
              AND result IN ('WIN', 'LOSS', 'PUSH')
              AND game_date >= %s
              {_EXCLUDE}
        """, (since,)).fetchone()

        opening = conn.execute(f"""
            SELECT {_AGG}
            FROM opening_signals
            WHERE result IN ('WIN', 'LOSS', 'PUSH')
              AND game_date >= %s
              {_EXCLUDE}
        """, (since,)).fetchone()

        print(f"\n{'═'*78}")
        print(f"  OPENING SIGNAL vs LIVE/CLOSING — game-level, settled since {since}")
        print(f"{'═'*78}")
        print(_fmt("Live (closing) picks", *live))
        print(_fmt("Opening signal (locked)", *opening))

        print(f"\n  Opening signal sliced by line movement after lock:")
        for dirn in ("toward", "against", "flat"):
            row = conn.execute(f"""
                SELECT {_AGG} FROM opening_signals
                WHERE result IN ('WIN','LOSS','PUSH')
                  AND game_date >= %s AND line_move_dir = %s {_EXCLUDE}
            """, (since, dirn)).fetchone()
            print(_fmt(f"line moved {dirn}", *row))

        print(f"\n  Opening signal sliced by public side at lock:")
        for ps in ("with_public", "contrarian", "even"):
            row = conn.execute(f"""
                SELECT {_AGG} FROM opening_signals
                WHERE result IN ('WIN','LOSS','PUSH')
                  AND game_date >= %s AND public_side = %s {_EXCLUDE}
            """, (since, ps)).fetchone()
            print(_fmt(ps, *row))

        # public coverage is sparse (Action Network, full-game only) — flag it
        no_pub = conn.execute(f"""
            SELECT {_AGG} FROM opening_signals
            WHERE result IN ('WIN','LOSS','PUSH')
              AND game_date >= %s AND public_side IS NULL {_EXCLUDE}
        """, (since,)).fetchone()
        print(_fmt("(no public split)", *no_pub))
        print(f"{'═'*78}\n")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Opening vs live comparison")
    parser.add_argument("--since", default="2026-04-14",
                        help="only count picks on/after this date (default 2026-04-14)")
    args = parser.parse_args()
    opening_report(args.since)
