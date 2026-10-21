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


# How far BEFORE the scheduled start a derived first pitch may sit and still be
# believed. Chosen from the data, not rounded to a nice number: over the 415 MLB
# games with coverage the offsets run continuously out to -36.0 minutes, then
# there is a 35-minute GAP, then -71.0 and six at -340 to -386. Sixty sits in
# that gap with nothing near it.
#
# The far group is not a slow start, it is a wrong game. Each of those six is a
# day-night doubleheader whose second game was matched to the FIRST game's live
# state, so "first pitch" lands six hours before the listed time. Believing it
# throws away a whole afternoon of genuinely pre-game prices -- 4,316 rows on
# MLB_2026-08-29_ARI_SF alone, which relabel_in_play has already marked in_play.
#
# No clamp on the LATE side, deliberately. +39 to +114 minutes are rain delays,
# and a game that truly started late truly has more pre-game quotes.
SUSPICIOUS_EARLY_MINUTES = 60


def trusted_first_pitch(first_pitch_at, commence_time):
    """`first_pitch_at` unless it is implausibly early, else None.

    The Python twin of the CASE in pregame_cutoff_sql, so a reader that parses
    timestamps itself applies the same rule. Fails open in both directions: an
    unparseable or missing value returns None and the caller falls back to the
    schedule.
    """
    from datetime import datetime, timedelta, timezone

    def _ts(v):
        if not v:
            return None
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        try:
            dt = datetime.fromisoformat(str(v).strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    fp, ct = _ts(first_pitch_at), _ts(commence_time)
    if fp is None:
        return None
    if ct is None:
        return first_pitch_at          # nothing to sanity-check it against
    if fp < ct - timedelta(minutes=SUSPICIOUS_EARLY_MINUTES):
        return None
    return first_pitch_at


def pregame_cutoff_sql(alias: str = "g") -> str:
    """The bound every pre-game read should use, as SQL.

    Named once so the call sites cannot drift. COALESCE, not a plain swap:
    first_pitch_at is NULL for every game before 2026-07 and for every sport
    but MLB, and a NULL bound would silently exclude seventeen seasons.

    The CASE is the second half, added 2026-09-03 after the derivation was
    measured rather than trusted: 7 of 415 games carry a first_pitch_at that is
    more than an hour before the scheduled start (see SUSPICIOUS_EARLY_MINUTES)
    and one of them is six hours early. Without it this bound is not a
    tightening for those games, it is data loss.
    """
    return (
        f"COALESCE(CASE WHEN {alias}.first_pitch_at::timestamptz"
        f" >= {alias}.commence_time::timestamptz"
        f" - interval '{SUSPICIOUS_EARLY_MINUTES} minutes'"
        f" THEN {alias}.first_pitch_at END, {alias}.commence_time)"
    )
