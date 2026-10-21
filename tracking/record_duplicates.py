"""One real event, one bet in the record: find a bet written twice under two game ids.

mike, 2026-10-09: "Count each fight once."

WHAT THIS IS. Two `games` rows can describe one real event. UFC writes a fight
under both fighter orders (`UFC_2026-06-20_kevin-borjas_andre-lima` and
`UFC_2026-06-20_andre-lima_kevin-borjas`) and, like NCAAF, under an Eastern and
a UTC date (`UFC_2026-07-18_...` and `UFC_2026-07-19_...` for one main event).
When the same model scored both rows it wrote the same bet twice, both copies
settled, and every record surface counted the event twice.

Measured 2026-10-09 (read-only, every BET ever written): three such pairs.
One was already VOID (the MLB 04-15/04-16 phantom row). The other two are both
`ufc_total_rounds`, both graded WIN on each copy, both before the published
window (2026-09-01):

    332605 kevin-borjas_andre-lima (-166)  /  332615 andre-lima_kevin-borjas (-130)
    524487 2026-07-18 (unpriced)           /  530849 2026-07-19 (unpriced)

The game-row duplicates themselves are common (78 UFC and 71 NCAAF pairs since
June 2026); what keeps them out of the record so far is that one model rarely
bets both rows. Nothing guarantees it.

WHAT HAPPENS TO THE SECOND COPY. It is marked, never re-graded:
`condition_status = config.DUPLICATE_STATUS`, `condition_note` naming the
kept pick and who asked. Result, price, line and created_at stay as written.
Every record query excludes the marker (config.duplicate_copy_exclusion_sql;
the app's passesRecordFilter). The marking write is a guarded migration that
names the pick ids, like every other write to a settled pick; this module only
FINDS candidates (system_health `one_pick_per_event`) and says which copy stays.

WHICH COPY STAYS, stated so it cannot quietly change (`choose_kept`):

  1. a copy that was POSTED to Discord beats one that was not -- a posted pick
     is locked and is the bet members saw (Matt, 2026-09-28);
  2. else the EARLIEST created_at -- the first signal is the bet of record
     (CLAUDE.md 1c), the same rule scripts/dedupe_picks.py uses;
  3. else the LOWEST pick_id, so a tie is still deterministic. The June pair
     was written in one run with identical created_at, so this rule decides it.

WHEN TWO ROWS ARE ONE EVENT (`DUPLICATE_PAIRS_SQL`). Same sport, same model,
same pick identity (tracking/publish_keys.KEY_PARTS), the same two
participants in either order, game dates at most one day apart, and:

  * UFC, NCAAF, NFL: nothing more. A fighter or team never meets the same
    opponent on consecutive days, and the start time is not trustworthy on
    these rows -- measured UFC copies of one fight sit 23-24 hours apart
    (placeholder starts), NCAAF's ET/UTC copies of Utah-BYU 23.96 hours apart.
  * every other sport plays series, so the start must also agree within
    SERIES_WINDOW_HOURS, and two finals that differ are two games (an MLB
    doubleheader under swapped ids, 2021-08-10 LAA/TOR). Measured minimum
    gap between two real games of one pairing since 2025: MLB 16.3h, WNBA
    17.1h, NHL 21.3h.

An in-play pick also has to be on the same SIDE (normalised to the team, so a
swapped row's home/away does not hide it), because a live model may hold an
over and an under on one game as two bets of record (publish_keys.LIVE key).

What this does NOT catch: a participant spelled two ways (an NCAAF school
alias). Measured 2026-10-09: no settled BET pair of that shape exists.
"""
from __future__ import annotations

from datetime import datetime, timezone

import config
from tracking.publish_keys import KEY_PARTS, posted_sql

# Sports where the same two sides never meet on consecutive days.
NO_SERIES_SPORTS: tuple[str, ...] = ("UFC", "NCAAF", "NFL")

# Every other sport: one event's two rows must start within this many hours.
SERIES_WINDOW_HOURS = 12


def _identity_join(a: str, b: str) -> str:
    return "\n     AND ".join(
        f"COALESCE({a}.{c}, '') = COALESCE({b}.{c}, '')" for c in KEY_PARTS)


_NO_SERIES = ", ".join(f"'{s}'" for s in NO_SERIES_SPORTS)

# Settled BETs not already marked, with what decides "same event" and "which
# copy stays". The finals are sorted so a swapped row's 1-0 and 0-1 agree.
DUPLICATE_PAIRS_SQL = f"""
WITH bets AS (
  SELECT p.pick_id, p.sport, p.model_id, p.game_id, p.game_date,
         p.created_at, p.is_live, p.player_id, p.player_key, p.prop_market,
         LEAST(g.home_team, g.away_team)    AS t1,
         GREATEST(g.home_team, g.away_team) AS t2,
         CASE p.pick_side WHEN 'home' THEN g.home_team
                          WHEN 'away' THEN g.away_team
                          ELSE p.pick_side END AS side,
         COALESCE(g.commence_time, p.game_time) AS starts,
         LEAST(g.home_score, g.away_score)    AS lo,
         GREATEST(g.home_score, g.away_score) AS hi
  FROM picks p
  JOIN games g ON g.game_id = p.game_id
  WHERE p.signal_type = 'BET'
    AND p.result IN ('WIN', 'LOSS', 'PUSH'){config.duplicate_copy_exclusion_sql("p")}
)
SELECT a.sport, a.model_id,
       a.pick_id, a.game_id, a.created_at, {posted_sql("pa")} AS a_posted,
       b.pick_id, b.game_id, b.created_at, {posted_sql("pb")} AS b_posted
FROM bets a
JOIN bets b
      ON a.sport = b.sport
     AND a.model_id = b.model_id
     AND {_identity_join("a", "b")}
     AND a.t1 = b.t1 AND a.t2 = b.t2
     AND a.game_id < b.game_id
     AND ABS(a.game_date::date - b.game_date::date) <= 1
     AND a.is_live IS NOT DISTINCT FROM b.is_live
     AND (a.is_live IS NOT TRUE OR a.side = b.side)
     AND (a.sport IN ({_NO_SERIES})
          OR (ABS(EXTRACT(EPOCH FROM (a.starts::timestamptz - b.starts::timestamptz)))
                  < {SERIES_WINDOW_HOURS} * 3600
              AND NOT (a.hi IS NOT NULL AND b.hi IS NOT NULL
                       AND (a.lo <> b.lo OR a.hi <> b.hi))))
JOIN picks pa ON pa.pick_id = a.pick_id
JOIN picks pb ON pb.pick_id = b.pick_id
ORDER BY a.sport, a.model_id, a.game_date, a.pick_id
"""


def _instant(value) -> datetime:
    """created_at as an aware instant. Stored as text ('... +00'); an
    unreadable stamp sorts LAST, so it can never win the keep rule."""
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).strip().replace(" ", "T", 1))
        except (TypeError, ValueError):
            return datetime.max.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def choose_kept(a: dict, b: dict) -> tuple[dict, dict]:
    """(kept, extra) for two copies of one bet. Each dict carries pick_id,
    created_at and posted. The rule is in the module docstring."""
    def rank(p: dict):
        return (0 if p.get("posted") else 1,
                _instant(p.get("created_at")),
                int(p["pick_id"]))
    kept, extra = sorted((a, b), key=rank)
    return kept, extra


def find_duplicate_pairs(conn) -> list[dict]:
    """Every unmarked pair, each with the copy that stays and the copy to mark."""
    out = []
    for (sport, model_id, a_id, a_game, a_created, a_posted,
         b_id, b_game, b_created, b_posted) in conn.execute(
            DUPLICATE_PAIRS_SQL).fetchall():
        kept, extra = choose_kept(
            {"pick_id": a_id, "game_id": a_game, "created_at": a_created,
             "posted": bool(a_posted)},
            {"pick_id": b_id, "game_id": b_game, "created_at": b_created,
             "posted": bool(b_posted)})
        out.append({"sport": sport, "model_id": model_id,
                    "kept": kept, "extra": extra})
    return out


def describe(pairs: list[dict], limit: int = 4) -> str:
    """One line for a health report: model, the copy to mark, the copy kept."""
    shown = "; ".join(
        f"{p['model_id']} {p['extra']['pick_id']} (keep {p['kept']['pick_id']})"
        for p in pairs[:limit])
    more = f" (+{len(pairs) - limit} more)" if len(pairs) > limit else ""
    return shown + more
