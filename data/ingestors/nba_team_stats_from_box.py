"""
nba_team_stats_from_box.py — NBA season-to-date team stats built from the box
scores we already store, on the worker.

WHY. `nba_team_stats` was only ever written by `nba_stats_ingestor`, which calls
stats.nba.com and so runs only from a residential machine (stats.nba.com blocks
datacenter IPs). That job wrote nothing for 2026-27: on 2026-11-02 the table
held season 2026 up to as_of 2026-08-30 and no season 2027 row at all, so the
app's Teams board had no Net Rtg / Off Rtg / Def Rtg / Pace / eFG% / TOV% for
the season being played. The 2026-27 box scores ARE on the worker
(`nba_player_game_log`, written by `nba_results_ingestor` from ESPN), and every
one of the 184 team-games stored at that date summed to its final score.

METHOD. The same formulas as `nba_stats_ingestor._build_team_stat_rows`:
possessions = FGA - OREB + TOV + 0.44*FTA, ratings per 100 possessions, eFG% =
(FGM + 0.5*3PM) / FGA. Points come from `games` (the final score), the shooting
and turnover counts from the summed player box lines. Only games strictly
before `as_of_date`, so a row never carries a game played that day.

VALIDATED against the source it stands in for (2026-11-02, season 2026, all 30
teams, rebuilt from that season's player logs vs the stored stats.nba.com row):
Net Rtg correlation 0.9999; Off/Def Rtg mean abs diff 0.79 / 0.80; pace 0.71;
eFG% 0.0002; TOV% 0.60. Ratings run ~0.8 HIGH because player box lines carry no
TEAM turnovers (shot-clock and similar), so possessions are slightly low. The
bias is the same on both sides, so Net Rtg and every ranking are unaffected.

ON CONFLICT DO NOTHING: when the residential stats.nba.com job does run, it
upserts the same (team, season, as_of_date) key and its row wins either way.

No live model reads `nba_team_stats` (the NBA game models that did were retired
2026-06; config.RETIRED_MODELS). It feeds the Teams board and team page only.
"""

from __future__ import annotations

from loguru import logger

from data.ingestors.nba_stats_ingestor import _nba_season_for_date

_UPSERT_SQL = """
WITH g AS (
  SELECT game_id, home_team, away_team, home_score, away_score
  FROM games
  WHERE sport = 'NBA' AND season = :season
    AND home_score IS NOT NULL AND away_score IS NOT NULL
    AND game_date < :as_of
),
box AS (
  SELECT l.game_id, l.team,
         sum(l.fg_made) AS fgm, sum(l.fg_att) AS fga,
         sum(l.fg3_made) AS fg3m, sum(l.fg3_att) AS fg3a,
         sum(l.ft_made) AS ftm, sum(l.ft_att) AS fta,
         sum(l.offensive_reb) AS oreb, sum(l.rebounds) AS reb,
         sum(l.assists) AS ast, sum(l.turnovers) AS tov
  FROM nba_player_game_log l
  JOIN g USING (game_id)
  WHERE l.season = :season
  GROUP BY l.game_id, l.team
),
tg AS (
  SELECT b.*,
         (b.team = g.home_team) AS is_home,
         CASE WHEN b.team = g.home_team THEN g.home_score ELSE g.away_score END AS pts,
         CASE WHEN b.team = g.home_team THEN g.away_score ELSE g.home_score END AS opp
  FROM box b JOIN g USING (game_id)
  WHERE b.team IN (g.home_team, g.away_team)
),
a AS (
  SELECT team, count(*) AS n,
         sum(pts) AS pts, sum(opp) AS opp,
         sum(fga - oreb + tov + 0.44 * fta) AS poss,
         sum(fgm) AS fgm, sum(fga) AS fga, sum(fg3m) AS fg3m, sum(fg3a) AS fg3a,
         sum(ftm) AS ftm, sum(fta) AS fta, sum(reb) AS reb, sum(ast) AS ast,
         sum(tov) AS tov,
         count(*) FILTER (WHERE pts > opp) AS w,
         count(*) FILTER (WHERE pts < opp) AS l,
         avg(pts) FILTER (WHERE is_home) AS pts_home,
         avg(pts) FILTER (WHERE NOT is_home) AS pts_away
  FROM tg GROUP BY team
)
INSERT INTO nba_team_stats (
  team, season, as_of_date, games_played, points_per_game, points_allowed_pg,
  pace, off_rating, def_rating, efg_pct, fg_pct, fg3_pct, ft_pct,
  reb_per_game, ast_per_game, tov_pct, points_home, points_away,
  wins, losses, point_differential
)
SELECT team, :season, :as_of, n,
       round(pts::numeric / n, 2), round(opp::numeric / n, 2),
       round(poss / n, 2),
       round(100 * pts / nullif(poss, 0), 2),
       round(100 * opp / nullif(poss, 0), 2),
       round((fgm + 0.5 * fg3m)::numeric / nullif(fga, 0), 4),
       round(fgm::numeric / nullif(fga, 0), 4),
       round(fg3m::numeric / nullif(fg3a, 0), 4),
       round(ftm::numeric / nullif(fta, 0), 4),
       round(reb::numeric / n, 2), round(ast::numeric / n, 2),
       round(100 * tov / nullif(poss, 0), 2),
       round(pts_home, 2), round(pts_away, 2),
       w, l, round((pts - opp)::numeric / n, 2)
FROM a
WHERE n > 0
ON CONFLICT (team, season, as_of_date) DO NOTHING
"""


def run_nba_team_stats_from_box(as_of_date: str, season: int | None = None,
                                conn=None) -> dict:
    """Write one season-to-date `nba_team_stats` row per team, as of `as_of_date`.

    Returns {"season", "as_of_date", "written"}. Writes zero rows off-season
    (no finished games) or when every key already exists.
    """
    from data.db import get_connection

    season = season if season is not None else _nba_season_for_date(as_of_date)
    own = conn is None
    conn = conn or get_connection()
    try:
        cur = conn.execute(_UPSERT_SQL, {"season": season, "as_of": as_of_date})
        written = cur.rowcount if cur is not None and cur.rowcount is not None else 0
        conn.commit()
    finally:
        if own:
            conn.close()
    logger.info(f"NBA team stats from box: season {season} as of {as_of_date}: {written} rows")
    return {"season": season, "as_of_date": as_of_date, "written": written}
