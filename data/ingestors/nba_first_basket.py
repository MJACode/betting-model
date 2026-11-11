"""NBA first-basket stats: one row per team-game and per player-game, for the Stats tab.

WHY. Matt, 2026-11-08: a "1st Basket" board on the NBA Stats tab, one card
per game tonight, showing who is most likely to score first, how often each
player takes and makes his team's first shot, and how likely each team is to
win the tip. Stats only: we buy no first-basket odds, so there is no model
and no pick.

DEFINITIONS (Matt chose them 2026-11-08; the migration states them too):
  first basket  the game's first score of any kind, free throws included.
  tip           the opening period-1 Jumpball row; the winner is that row's
                team_side, the team that gained possession.
  first shot    the team's first field-goal attempt (a shooting play that is
                not a free throw).
Regular season only, from nba_pbp / nba_pbp_box / nba_pbp_games, which
data/ingestors/nba_pbp.fill_gaps keeps current. A game whose play-by-play
has not been loaded yet has no row, so it is never counted as a miss.

WHAT IT WRITES. nba_first_basket_games and nba_first_basket_players
(data/migrations/add_nba_first_basket_2026_11_08.sql creates both). Each
season is recomputed with one INSERT ... SELECT per table; a row is
rewritten only when a value changed, and a row its source no longer
produces is deleted.

    python -m data.ingestors.nba_first_basket --seasons 2026 2027
"""
from __future__ import annotations

import argparse

from loguru import logger

from data.db import get_connection

GAMES_TABLE = "nba_first_basket_games"
PLAYERS_TABLE = "nba_first_basket_players"

# Shared CTEs: the games, their period-1 plays, the opening tip, the game's
# first score, and each team's first shot and first score.
_BASE = """
WITH g AS (
  SELECT espn_game_id, game_id, season, game_date, home_team, away_team
    FROM nba_pbp_games
   WHERE season = ANY(%(seasons)s) AND season_type = 2 AND game_id IS NOT NULL
),
p AS (
  SELECT p.espn_game_id, p.play_no, p.team_side, p.athlete_id_1, p.type_text,
         p.shooting_play, p.scoring_play, p.points
    FROM nba_pbp p
    JOIN g USING (espn_game_id)
   WHERE p.period = 1 AND p.team_side IN ('H', 'A')
),
tip AS (
  SELECT DISTINCT ON (pp.espn_game_id)
         pp.espn_game_id, pp.team_side AS tip_side,
         pp.athlete_id_1 AS j1, pp.athlete_id_2 AS j2
    FROM nba_pbp pp
    JOIN g USING (espn_game_id)
   WHERE pp.period = 1 AND pp.type_text = 'Jumpball'
   ORDER BY pp.espn_game_id, pp.play_no
),
fs AS (
  SELECT DISTINCT ON (espn_game_id)
         espn_game_id, team_side, athlete_id_1,
         CASE WHEN type_text ILIKE 'Free Throw%%' THEN 'FT'
              WHEN points = 3 THEN '3PT' ELSE '2PT' END AS kind
    FROM p
   WHERE points > 0
   ORDER BY espn_game_id, play_no
),
tfga AS (
  SELECT DISTINCT ON (espn_game_id, team_side)
         espn_game_id, team_side, athlete_id_1, COALESCE(scoring_play, FALSE) AS made
    FROM p
   WHERE shooting_play AND type_text NOT ILIKE 'Free Throw%%'
   ORDER BY espn_game_id, team_side, play_no
),
tfs AS (
  SELECT DISTINCT ON (espn_game_id, team_side)
         espn_game_id, team_side, athlete_id_1
    FROM p
   WHERE points > 0
   ORDER BY espn_game_id, team_side, play_no
),
box AS (
  SELECT b.espn_game_id, b.espn_id, b.side, b.name, COALESCE(b.starter, FALSE) AS starter
    FROM nba_pbp_box b
    JOIN g USING (espn_game_id)
   WHERE COALESCE(b.did_not_play, FALSE) = FALSE AND b.side IN ('H', 'A')
)
"""

_GAMES_ROWS = """,
sides AS (
  SELECT g.*, s.side,
         CASE s.side WHEN 'H' THEN g.home_team ELSE g.away_team END AS team,
         CASE s.side WHEN 'H' THEN g.away_team ELSE g.home_team END AS opponent
    FROM g
   CROSS JOIN (VALUES ('H'), ('A')) AS s(side)
   -- A game with no score in period 1 has no play-by-play worth counting yet.
   WHERE EXISTS (SELECT 1 FROM fs WHERE fs.espn_game_id = g.espn_game_id)
),
rows AS (
  SELECT s.game_id, s.team, s.season, s.game_date, s.opponent,
         s.side = 'H' AS is_home,
         CASE WHEN tip.espn_game_id IS NULL THEN NULL ELSE tip.tip_side = s.side END AS won_tip,
         jb.espn_id AS jumper_espn_id, jb.name AS jumper_name,
         fs.team_side = s.side AS scored_first,
         CASE WHEN fs.team_side = s.side THEN fs.kind END AS first_score_kind,
         tfga.athlete_id_1 AS first_fga_espn_id, tfga.made AS first_fga_made,
         tfs.athlete_id_1 AS first_score_espn_id
    FROM sides s
    JOIN fs ON fs.espn_game_id = s.espn_game_id
    LEFT JOIN tip ON tip.espn_game_id = s.espn_game_id
    LEFT JOIN box jb ON jb.espn_game_id = s.espn_game_id AND jb.side = s.side
                    AND jb.espn_id IN (tip.j1, tip.j2)
    LEFT JOIN tfga ON tfga.espn_game_id = s.espn_game_id AND tfga.team_side = s.side
    LEFT JOIN tfs ON tfs.espn_game_id = s.espn_game_id AND tfs.team_side = s.side
)
"""

GAMES_SQL = _BASE + _GAMES_ROWS + """
INSERT INTO nba_first_basket_games AS t
       (game_id, team, season, game_date, opponent, is_home, won_tip, jumper_espn_id,
        jumper_name, scored_first, first_score_kind, first_fga_espn_id, first_fga_made,
        first_score_espn_id)
SELECT game_id, team, season, game_date, opponent, is_home, won_tip, jumper_espn_id,
       jumper_name, scored_first, first_score_kind, first_fga_espn_id, first_fga_made,
       first_score_espn_id
  FROM rows
ON CONFLICT (game_id, team) DO UPDATE SET
       season = EXCLUDED.season, game_date = EXCLUDED.game_date,
       opponent = EXCLUDED.opponent, is_home = EXCLUDED.is_home,
       won_tip = EXCLUDED.won_tip, jumper_espn_id = EXCLUDED.jumper_espn_id,
       jumper_name = EXCLUDED.jumper_name, scored_first = EXCLUDED.scored_first,
       first_score_kind = EXCLUDED.first_score_kind,
       first_fga_espn_id = EXCLUDED.first_fga_espn_id,
       first_fga_made = EXCLUDED.first_fga_made,
       first_score_espn_id = EXCLUDED.first_score_espn_id,
       updated_at = NOW()
 WHERE (t.season, t.game_date, t.opponent, t.is_home, t.won_tip, t.jumper_espn_id,
        t.jumper_name, t.scored_first, t.first_score_kind, t.first_fga_espn_id,
        t.first_fga_made, t.first_score_espn_id)
       IS DISTINCT FROM
       (EXCLUDED.season, EXCLUDED.game_date, EXCLUDED.opponent, EXCLUDED.is_home,
        EXCLUDED.won_tip, EXCLUDED.jumper_espn_id, EXCLUDED.jumper_name,
        EXCLUDED.scored_first, EXCLUDED.first_score_kind, EXCLUDED.first_fga_espn_id,
        EXCLUDED.first_fga_made, EXCLUDED.first_score_espn_id)
"""

_PLAYERS_ROWS = """,
rows AS (
  SELECT g.game_id, b.espn_id, g.season, g.game_date,
         CASE b.side WHEN 'H' THEN g.home_team ELSE g.away_team END AS team,
         b.name, b.starter,
         COALESCE(tfga.athlete_id_1 = b.espn_id, FALSE) AS first_fga,
         COALESCE(tfga.athlete_id_1 = b.espn_id AND tfga.made, FALSE) AS first_fga_made,
         COALESCE(fs.athlete_id_1 = b.espn_id AND fs.team_side = b.side, FALSE) AS game_first_score,
         COALESCE(tfs.athlete_id_1 = b.espn_id, FALSE) AS team_first_score,
         COALESCE(b.espn_id IN (tip.j1, tip.j2), FALSE) AS jumped,
         COALESCE(b.espn_id IN (tip.j1, tip.j2) AND tip.tip_side = b.side, FALSE) AS jump_won
    FROM box b
    JOIN g USING (espn_game_id)
    JOIN fs ON fs.espn_game_id = b.espn_game_id
    LEFT JOIN tip ON tip.espn_game_id = b.espn_game_id
    LEFT JOIN tfga ON tfga.espn_game_id = b.espn_game_id AND tfga.team_side = b.side
    LEFT JOIN tfs ON tfs.espn_game_id = b.espn_game_id AND tfs.team_side = b.side
   WHERE b.name IS NOT NULL
)
"""

PLAYERS_SQL = _BASE + _PLAYERS_ROWS + """
INSERT INTO nba_first_basket_players AS t
       (game_id, espn_id, season, game_date, team, name, starter, first_fga,
        first_fga_made, game_first_score, team_first_score, jumped, jump_won)
SELECT game_id, espn_id, season, game_date, team, name, starter, first_fga,
       first_fga_made, game_first_score, team_first_score, jumped, jump_won
  FROM rows
ON CONFLICT (game_id, espn_id) DO UPDATE SET
       season = EXCLUDED.season, game_date = EXCLUDED.game_date,
       team = EXCLUDED.team, name = EXCLUDED.name, starter = EXCLUDED.starter,
       first_fga = EXCLUDED.first_fga, first_fga_made = EXCLUDED.first_fga_made,
       game_first_score = EXCLUDED.game_first_score,
       team_first_score = EXCLUDED.team_first_score,
       jumped = EXCLUDED.jumped, jump_won = EXCLUDED.jump_won,
       updated_at = NOW()
 WHERE (t.season, t.game_date, t.team, t.name, t.starter, t.first_fga, t.first_fga_made,
        t.game_first_score, t.team_first_score, t.jumped, t.jump_won)
       IS DISTINCT FROM
       (EXCLUDED.season, EXCLUDED.game_date, EXCLUDED.team, EXCLUDED.name,
        EXCLUDED.starter, EXCLUDED.first_fga, EXCLUDED.first_fga_made,
        EXCLUDED.game_first_score, EXCLUDED.team_first_score, EXCLUDED.jumped,
        EXCLUDED.jump_won)
"""


# A row whose source is gone: a box row corrected to did-not-play, a game
# reclassified or its play-by-play removed, a player id fixed. The upserts
# above never touch it, so it would count forever (review L3, 2026-11-08).
# Scoped to the seasons being rebuilt, and to the same rows the INSERT builds.
GAMES_DELETE_SQL = _BASE + _GAMES_ROWS + """
DELETE FROM nba_first_basket_games t
 WHERE t.season = ANY(%(seasons)s)
   AND NOT EXISTS (SELECT 1 FROM rows r WHERE r.game_id = t.game_id AND r.team = t.team)
"""

PLAYERS_DELETE_SQL = _BASE + _PLAYERS_ROWS + """
DELETE FROM nba_first_basket_players t
 WHERE t.season = ANY(%(seasons)s)
   AND NOT EXISTS (SELECT 1 FROM rows r WHERE r.game_id = t.game_id AND r.espn_id = t.espn_id)
"""


def tables_exist(conn) -> bool:
    row = conn.execute(
        "SELECT to_regclass('public.nba_first_basket_games') IS NOT NULL "
        "AND to_regclass('public.nba_first_basket_players') IS NOT NULL").fetchone()
    return bool(row and row[0])


def rebuild(conn, seasons: list[int]) -> dict:
    """Upsert every team-game and player-game of `seasons`. The tables are
    created by the view migration, so a pass before it lands writes nothing."""
    seasons = sorted({int(s) for s in seasons})
    if not seasons:
        return {"seasons": [], "games": 0, "players": 0}
    if not tables_exist(conn):
        logger.warning("nba_first_basket tables do not exist yet "
                       "(add_nba_first_basket_2026_11_08.sql); skipped")
        return {"seasons": seasons, "games": 0, "players": 0, "skipped": "no table"}
    params = {"seasons": seasons}
    cur = conn.execute(GAMES_SQL, params)
    n_games = cur.rowcount if cur.rowcount is not None else 0
    cur = conn.execute(PLAYERS_SQL, params)
    n_players = cur.rowcount if cur.rowcount is not None else 0
    cur = conn.execute(GAMES_DELETE_SQL, params)
    d_games = cur.rowcount if cur.rowcount is not None else 0
    cur = conn.execute(PLAYERS_DELETE_SQL, params)
    d_players = cur.rowcount if cur.rowcount is not None else 0
    conn.commit()
    return {"seasons": seasons, "games": n_games, "players": n_players,
            "deleted_games": d_games, "deleted_players": d_players}


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
