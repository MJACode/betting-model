"""NBA first-quarter team stats: one row per team per game, for the Stats tab.

WHY. Matt, 2026-10-28, from member feedback: show each NBA team's
first-quarter record, last 5 / last 10 and home/away splits, and
first-quarter offensive and defensive efficiency. These are stats, not picks.
The first-quarter model was tested and closed (docs/nba_models_2026.md §9).

WHAT IT WRITES. nba_team_q1_games (data/migrations/add_nba_team_q1_2026_10_28.sql
creates it), rebuilt from what Supabase already holds:

  points       nba_period_scores, period 1 (the number a 1Q bet settles on)
  possessions  nba_stints, period 1, counted from play-by-play events
               (data/ingestors/nba_stints.py). NULL when the stints' 1Q points
               do not equal the quarter score, so a bad derivation is not
               counted in the ratings. Measured 2026-10-28 on 2025-26:
               1 game of 1,230.

Regular season only (games holds no postseason rows). Recomputes the given
seasons with one INSERT ... SELECT. A row is rewritten only when a value
changed.

    python -m data.ingestors.nba_team_q1 --seasons 2026 2027
"""
from __future__ import annotations

import argparse

from loguru import logger

from data.db import get_connection

TABLE = "nba_team_q1_games"

REBUILD_SQL = """
WITH g AS (
  SELECT game_id, season, game_date, home_team, away_team
    FROM games
   WHERE sport = 'NBA' AND season = ANY(%(seasons)s)
),
p AS (
  SELECT ps.game_id, ps.home_points, ps.away_points
    FROM nba_period_scores ps
    JOIN g USING (game_id)
   WHERE ps.period = 1
),
s AS (
  SELECT st.game_id,
         sum(st.home_poss) AS hposs, sum(st.away_poss) AS aposs,
         sum(st.home_pts)  AS hpts,  sum(st.away_pts)  AS apts
    FROM nba_stints st
   WHERE st.period = 1 AND st.season = ANY(%(seasons)s)
   GROUP BY st.game_id
),
j AS (
  SELECT g.game_id, g.season, g.game_date, g.home_team, g.away_team,
         p.home_points, p.away_points,
         CASE WHEN s.hpts = p.home_points AND s.apts = p.away_points THEN s.hposs END AS hposs,
         CASE WHEN s.hpts = p.home_points AND s.apts = p.away_points THEN s.aposs END AS aposs
    FROM g
    JOIN p USING (game_id)
    LEFT JOIN s USING (game_id)
),
rows AS (
  SELECT game_id, home_team AS team, season, game_date, away_team AS opponent, TRUE AS is_home,
         home_points AS pts_for, away_points AS pts_against,
         hposs AS poss_for, aposs AS poss_against
    FROM j
  UNION ALL
  SELECT game_id, away_team, season, game_date, home_team, FALSE,
         away_points, home_points, aposs, hposs
    FROM j
)
INSERT INTO nba_team_q1_games AS t
       (game_id, team, season, game_date, opponent, is_home,
        pts_for, pts_against, poss_for, poss_against)
SELECT game_id, team, season, game_date, opponent, is_home,
       pts_for, pts_against, poss_for, poss_against
  FROM rows
ON CONFLICT (game_id, team) DO UPDATE SET
       season = EXCLUDED.season,
       game_date = EXCLUDED.game_date,
       opponent = EXCLUDED.opponent,
       is_home = EXCLUDED.is_home,
       pts_for = EXCLUDED.pts_for,
       pts_against = EXCLUDED.pts_against,
       poss_for = EXCLUDED.poss_for,
       poss_against = EXCLUDED.poss_against,
       updated_at = NOW()
 WHERE (t.season, t.game_date, t.opponent, t.is_home, t.pts_for, t.pts_against,
        t.poss_for, t.poss_against)
       IS DISTINCT FROM
       (EXCLUDED.season, EXCLUDED.game_date, EXCLUDED.opponent, EXCLUDED.is_home,
        EXCLUDED.pts_for, EXCLUDED.pts_against, EXCLUDED.poss_for, EXCLUDED.poss_against)
"""


def table_exists(conn) -> bool:
    row = conn.execute("SELECT to_regclass('public.nba_team_q1_games') IS NOT NULL").fetchone()
    return bool(row and row[0])


def rebuild(conn, seasons: list[int]) -> dict:
    """Upsert every team-game of `seasons`. Returns rows written; the table is
    created by the view migration, so a pass before it lands writes nothing."""
    seasons = sorted({int(s) for s in seasons})
    if not seasons:
        return {"seasons": [], "rows": 0}
    if not table_exists(conn):
        logger.warning(f"{TABLE} does not exist yet (add_nba_team_q1_2026_10_28.sql); skipped")
        return {"seasons": seasons, "rows": 0, "skipped": "no table"}
    cur = conn.execute(REBUILD_SQL, {"seasons": seasons})
    n = cur.rowcount if cur.rowcount is not None else 0
    conn.commit()
    return {"seasons": seasons, "rows": n}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seasons", type=int, nargs="+", required=True)
    a = ap.parse_args()
    conn = get_connection()
    try:
        print(rebuild(conn, a.seasons))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
