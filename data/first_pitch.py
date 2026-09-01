"""
Actual first pitch, as distinct from the scheduled start.

WHY
---
mike, 2026-09-01: "should be commence time."

Every pre-game guard in this repo bounds on `snapshot_at <= commence_time`
(CLAUDE.md §7). `commence_time` is the SCHEDULED start, taken from the odds
feed, and measured against reality it is late:

    413 games with live-state coverage (2026-07 onward)
    first live_game_state row vs commence_time:
        mean   -19.5 minutes   (the game is live BEFORE its commence_time)
        median -15.9 minutes
        only 4 of 413 games began AFTER their commence_time

So the boundary is roughly a quarter-hour too generous, and rows inside that
window are treated as pre-game while the game is already under way. It leaks in
the PERMISSIVE direction, which is the dangerous one: a model trained on a line
that already reflects the first inning looks prescient in backtest.

It is also the explanation for the 48,712 rows the live loop labelled `in_play`
whose timestamp sits at or before their commence_time. Those rows were right and
the boundary was wrong.

WHAT THIS DOES, AND WHAT IT DELIBERATELY DOES NOT
-------------------------------------------------
Derives `games.first_pitch_at` from the earliest `live_game_state` row where
`abstract_game_state = 'Live'`, and leaves `commence_time` untouched. The
schedule is the right thing to show in the app and the right thing to sort a
board by; it is only the wrong thing to bound a leak with.

Coverage is 2026-07 onward, because that is when live_game_state begins. Every
older game keeps a NULL, which is why every reader uses
COALESCE(first_pitch_at, commence_time) and why the guards already fail open.

ONE THING THIS CANNOT SETTLE. Whether the ~19 minutes is genuine (games start
before their listed time) or a feed artefact (the API reporting "Live" during
warmups) needs a timestamped play-by-play source, and `plays` carries no
timestamp. Recorded here rather than guessed at: the direction of the bias is
measured, its cause is not, and the fix is conservative either way -- an
earlier boundary can only exclude rows, never admit them.
"""

from __future__ import annotations

from loguru import logger

DERIVE_SQL = """
UPDATE games g
   SET first_pitch_at = f.first_live
  FROM (
        SELECT game_id, MIN(snapshot_at) AS first_live
          FROM live_game_state
         WHERE abstract_game_state = 'Live'
         GROUP BY game_id
       ) f
 WHERE f.game_id = g.game_id
   AND (g.first_pitch_at IS NULL OR g.first_pitch_at <> f.first_live)
RETURNING g.game_id
"""


def derive_first_pitch(conn) -> dict:
    """Fill games.first_pitch_at from live game state. Idempotent."""
    rows = conn.execute(DERIVE_SQL).fetchall()
    conn.commit()
    n = len(rows or [])
    logger.success(f"first_pitch_at derived for {n} games")
    return {"updated": n}


def pregame_cutoff_sql(alias: str = "g") -> str:
    """The bound every pre-game read should use, as SQL.

    Named once so the three call sites cannot drift. COALESCE, not a plain
    swap: first_pitch_at is NULL for every game before 2026-07, and a NULL
    bound would silently exclude seventeen seasons.
    """
    return f"COALESCE({alias}.first_pitch_at, {alias}.commence_time)"
