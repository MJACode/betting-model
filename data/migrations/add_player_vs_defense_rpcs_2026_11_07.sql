-- Migration: add_player_vs_defense_rpcs (2026-11-07)
--
-- The player page's defense-toughness filter (Matt, 2026-11-07: "when you
-- click on a player can you select a toughness so that I can see how they do
-- against similar tough opponents"). NBA, WNBA and NFL first (Matt approved
-- the rollout the same day).
--
-- ONE ROW PER GAME THE PLAYER PLAYED in his last `p_season_count` seasons
-- PLAYED inside `p_seasons` (a season he missed is skipped, not counted), each
-- carrying that opponent's defense rank FOR THAT SEASON. Plus, when
-- `p_next_opponent` is given, ONE extra row with game_id NULL: the next
-- opponent's rank in the newest season it has one.
--
-- The player's own games are NOT cut by role: they are the games the chart
-- already draws. The RANK uses the same "real role only" cut and stat list as
-- position_vs_opponent_<sport>, so a defense's rank here is the rank that card
-- prints (pinned by tests/test_player_vs_defense.py).
--
-- RANK 1 = ALLOWS THE FEWEST = THE TOUGHEST DEFENSE. The opposite of
-- position_vs_opponent_*'s rank_most_allowed, on purpose: this rank is printed
-- under the chart, where a fan reads "#1 defense" as the best one.
--
-- def_team_games is the defense's distinct games in that season, so the app
-- can say how thin an early-season rank is.
--
-- One guarded DO block; PUBLIC revoked before the named grant
-- (tests/test_ddl_guard.py). Guard: all three functions exist.

DO $mig$
BEGIN
    IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'public'
           AND p.proname IN ('player_vs_defense_nba', 'player_vs_defense_wnba',
                             'player_vs_defense_nfl')) >= 3 THEN
        RAISE NOTICE 'player_vs_defense_nba/wnba/nfl already present — skipping';
        RETURN;
    END IF;

    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_vs_defense_nba(
    p_player_id text,
    p_stat text,
    p_pos_group text,
    p_seasons integer[],
    p_season_count integer,
    p_next_opponent text
    )
    RETURNS TABLE (
    season integer, game_id text, game_date text, opponent text, is_home boolean,
    value numeric, def_rank integer, teams_ranked integer, avg_allowed numeric,
    def_team_games integer
    )
    LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
    WITH mine AS (
        SELECT l.season, l.game_id, l.game_date, (gm.home_team = l.team) AS is_home,
               CASE WHEN gm.home_team = l.team THEN gm.away_team ELSE gm.home_team END AS opp,
               CASE p_stat
                   WHEN 'points'    THEN l.points::numeric
                   WHEN 'rebounds'  THEN l.rebounds::numeric
                   WHEN 'assists'   THEN l.assists::numeric
                   WHEN 'threes'    THEN l.fg3_made::numeric
                   WHEN 'steals'    THEN l.steals::numeric
                   WHEN 'blocks'    THEN l.blocks::numeric
                   WHEN 'turnovers' THEN l.turnovers::numeric
                   WHEN 'minutes'   THEN l.minutes::numeric
                   WHEN 'pra'       THEN (COALESCE(l.points,0) + COALESCE(l.rebounds,0)
                                          + COALESCE(l.assists,0))::numeric
                   ELSE NULL
               END AS val
        FROM nba_player_game_log l
        JOIN games gm ON gm.game_id = l.game_id AND gm.sport = 'NBA'
        WHERE l.player_id = p_player_id AND l.season = ANY(p_seasons)
    ),
    played AS (
        SELECT DISTINCT m.season FROM mine m WHERE m.val IS NOT NULL
        ORDER BY m.season DESC LIMIT GREATEST(p_season_count, 1)
    ),
    wanted AS (
        SELECT pl.season FROM played pl
        UNION SELECT max(s) FROM unnest(p_seasons) AS s
    ),
    g AS (
        SELECT l.*,
               CASE WHEN gm.home_team = l.team THEN gm.away_team ELSE gm.home_team END AS opp
        FROM nba_player_game_log l
        JOIN player_positions pp
          ON pp.sport = 'NBA' AND pp.player_id = l.player_id AND pp.pos_group = p_pos_group
        JOIN games gm ON gm.game_id = l.game_id AND gm.sport = 'NBA'
        WHERE l.season IN (SELECT w.season FROM wanted w)
    ),
    q AS (
        SELECT g.*,
               COALESCE(g.minutes, 0) >= 15 AS has_role,
               CASE p_stat
                   WHEN 'points'    THEN g.points::numeric
                   WHEN 'rebounds'  THEN g.rebounds::numeric
                   WHEN 'assists'   THEN g.assists::numeric
                   WHEN 'threes'    THEN g.fg3_made::numeric
                   WHEN 'steals'    THEN g.steals::numeric
                   WHEN 'blocks'    THEN g.blocks::numeric
                   WHEN 'turnovers' THEN g.turnovers::numeric
                   WHEN 'minutes'   THEN g.minutes::numeric
                   WHEN 'pra'       THEN (COALESCE(g.points,0) + COALESCE(g.rebounds,0)
                                          + COALESCE(g.assists,0))::numeric
                   ELSE NULL
               END AS val
        FROM g
    ),
    league AS (SELECT q.season, q.game_id, q.opp, q.val FROM q WHERE q.has_role AND q.val IS NOT NULL),
    defense AS (
        SELECT lg.season, lg.opp AS defense, avg(lg.val) AS avg_allowed,
               count(DISTINCT lg.game_id)::int AS team_games
        FROM league lg GROUP BY lg.season, lg.opp
    ),
    ranked AS (
        SELECT d.*,
               rank() OVER (PARTITION BY d.season ORDER BY d.avg_allowed ASC)::int AS def_rank,
               count(*) OVER (PARTITION BY d.season)::int AS teams_ranked
        FROM defense d
    ),
    nxt AS (
        SELECT r.* FROM ranked r
        WHERE r.defense = p_next_opponent
        ORDER BY r.season DESC LIMIT 1
    )
    SELECT m.season::int AS season, m.game_id::text AS game_id, m.game_date::text AS game_date,
           m.opp::text AS opponent, m.is_home AS is_home, m.val AS value,
           r.def_rank AS def_rank, r.teams_ranked AS teams_ranked,
           round(r.avg_allowed, 3) AS avg_allowed, r.team_games AS def_team_games
    FROM mine m
    JOIN played p ON p.season = m.season
    LEFT JOIN ranked r ON r.season = m.season AND r.defense = m.opp
    WHERE m.val IS NOT NULL
    UNION ALL
    SELECT n.season::int, NULL::text, NULL::text, n.defense::text, NULL::boolean,
           NULL::numeric, n.def_rank, n.teams_ranked, round(n.avg_allowed, 3), n.team_games
    FROM nxt n
    $fn$
    $ddl$;

    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_vs_defense_wnba(
    p_player_id text,
    p_stat text,
    p_pos_group text,
    p_seasons integer[],
    p_season_count integer,
    p_next_opponent text
    )
    RETURNS TABLE (
    season integer, game_id text, game_date text, opponent text, is_home boolean,
    value numeric, def_rank integer, teams_ranked integer, avg_allowed numeric,
    def_team_games integer
    )
    LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
    WITH mine AS (
        SELECT l.season, l.game_id, l.game_date, (gm.home_team = l.team) AS is_home,
               CASE WHEN gm.home_team = l.team THEN gm.away_team ELSE gm.home_team END AS opp,
               CASE p_stat
                   WHEN 'points'    THEN l.points::numeric
                   WHEN 'rebounds'  THEN l.rebounds::numeric
                   WHEN 'assists'   THEN l.assists::numeric
                   WHEN 'threes'    THEN l.fg3_made::numeric
                   WHEN 'steals'    THEN l.steals::numeric
                   WHEN 'blocks'    THEN l.blocks::numeric
                   WHEN 'turnovers' THEN l.turnovers::numeric
                   WHEN 'minutes'   THEN l.minutes::numeric
                   WHEN 'pra'       THEN (COALESCE(l.points,0) + COALESCE(l.rebounds,0)
                                          + COALESCE(l.assists,0))::numeric
                   ELSE NULL
               END AS val
        FROM wnba_player_game_log l
        JOIN games gm ON gm.game_id = l.game_id AND gm.sport = 'WNBA'
        WHERE l.player_id = p_player_id AND l.season = ANY(p_seasons)
    ),
    played AS (
        SELECT DISTINCT m.season FROM mine m WHERE m.val IS NOT NULL
        ORDER BY m.season DESC LIMIT GREATEST(p_season_count, 1)
    ),
    wanted AS (
        SELECT pl.season FROM played pl
        UNION SELECT max(s) FROM unnest(p_seasons) AS s
    ),
    g AS (
        SELECT l.*,
               CASE WHEN gm.home_team = l.team THEN gm.away_team ELSE gm.home_team END AS opp
        FROM wnba_player_game_log l
        JOIN player_positions pp
          ON pp.sport = 'WNBA' AND pp.player_id = l.player_id AND pp.pos_group = p_pos_group
        JOIN games gm ON gm.game_id = l.game_id AND gm.sport = 'WNBA'
        WHERE l.season IN (SELECT w.season FROM wanted w)
    ),
    q AS (
        SELECT g.*,
               COALESCE(g.minutes, 0) >= 15 AS has_role,
               CASE p_stat
                   WHEN 'points'    THEN g.points::numeric
                   WHEN 'rebounds'  THEN g.rebounds::numeric
                   WHEN 'assists'   THEN g.assists::numeric
                   WHEN 'threes'    THEN g.fg3_made::numeric
                   WHEN 'steals'    THEN g.steals::numeric
                   WHEN 'blocks'    THEN g.blocks::numeric
                   WHEN 'turnovers' THEN g.turnovers::numeric
                   WHEN 'minutes'   THEN g.minutes::numeric
                   WHEN 'pra'       THEN (COALESCE(g.points,0) + COALESCE(g.rebounds,0)
                                          + COALESCE(g.assists,0))::numeric
                   ELSE NULL
               END AS val
        FROM g
    ),
    league AS (SELECT q.season, q.game_id, q.opp, q.val FROM q WHERE q.has_role AND q.val IS NOT NULL),
    defense AS (
        SELECT lg.season, lg.opp AS defense, avg(lg.val) AS avg_allowed,
               count(DISTINCT lg.game_id)::int AS team_games
        FROM league lg GROUP BY lg.season, lg.opp
    ),
    ranked AS (
        SELECT d.*,
               rank() OVER (PARTITION BY d.season ORDER BY d.avg_allowed ASC)::int AS def_rank,
               count(*) OVER (PARTITION BY d.season)::int AS teams_ranked
        FROM defense d
    ),
    nxt AS (
        SELECT r.* FROM ranked r
        WHERE r.defense = p_next_opponent
        ORDER BY r.season DESC LIMIT 1
    )
    SELECT m.season::int AS season, m.game_id::text AS game_id, m.game_date::text AS game_date,
           m.opp::text AS opponent, m.is_home AS is_home, m.val AS value,
           r.def_rank AS def_rank, r.teams_ranked AS teams_ranked,
           round(r.avg_allowed, 3) AS avg_allowed, r.team_games AS def_team_games
    FROM mine m
    JOIN played p ON p.season = m.season
    LEFT JOIN ranked r ON r.season = m.season AND r.defense = m.opp
    WHERE m.val IS NOT NULL
    UNION ALL
    SELECT n.season::int, NULL::text, NULL::text, n.defense::text, NULL::boolean,
           NULL::numeric, n.def_rank, n.teams_ranked, round(n.avg_allowed, 3), n.team_games
    FROM nxt n
    $fn$
    $ddl$;

    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_vs_defense_nfl(
    p_player_id text,
    p_stat text,
    p_pos_group text,
    p_seasons integer[],
    p_season_count integer,
    p_next_opponent text
    )
    RETURNS TABLE (
    season integer, game_id text, game_date text, opponent text, is_home boolean,
    value numeric, def_rank integer, teams_ranked integer, avg_allowed numeric,
    def_team_games integer
    )
    LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
    WITH mine AS (
        SELECT n.season, n.game_id, n.game_date, (gm.home_team = n.team) AS is_home,
               n.opponent AS opp,
               CASE p_stat
                   WHEN 'passing_yards'     THEN n.passing_yards::numeric
                   WHEN 'passing_tds'       THEN n.passing_tds::numeric
                   WHEN 'completions'       THEN n.completions::numeric
                   WHEN 'attempts'          THEN n.attempts::numeric
                   WHEN 'interceptions'     THEN n.interceptions::numeric
                   WHEN 'rushing_yards'     THEN n.rushing_yards::numeric
                   WHEN 'rushing_tds'       THEN n.rushing_tds::numeric
                   WHEN 'carries'           THEN n.carries::numeric
                   WHEN 'rush_rec_tds'      THEN (COALESCE(n.rushing_tds,0)
                                                  + COALESCE(n.receiving_tds,0))::numeric
                   WHEN 'receptions'        THEN n.receptions::numeric
                   WHEN 'receiving_yards'   THEN n.receiving_yards::numeric
                   WHEN 'receiving_tds'     THEN n.receiving_tds::numeric
                   WHEN 'targets'           THEN n.targets::numeric
                   WHEN 'def_sacks'         THEN n.def_sacks::numeric
                   WHEN 'def_interceptions' THEN n.def_interceptions::numeric
                   ELSE NULL
               END AS val
        FROM nfl_player_game_log n
        LEFT JOIN games gm ON gm.game_id = n.game_id AND gm.sport = 'NFL'
        WHERE n.player_id = p_player_id AND n.season = ANY(p_seasons)
          AND COALESCE(n.season_type, 'REG') <> 'PRE'
    ),
    played AS (
        SELECT DISTINCT m.season FROM mine m WHERE m.val IS NOT NULL
        ORDER BY m.season DESC LIMIT GREATEST(p_season_count, 1)
    ),
    wanted AS (
        SELECT pl.season FROM played pl
        UNION SELECT max(s) FROM unnest(p_seasons) AS s
    ),
    grp AS (
        SELECT n.*,
               CASE
                   WHEN n.pos = 'QB' THEN 'QB'
                   WHEN n.pos IN ('RB','FB') THEN 'RB'
                   WHEN n.pos = 'WR' THEN 'WR'
                   WHEN n.pos = 'TE' THEN 'TE'
                   WHEN n.pos IN ('DE','DT','NT','DL') THEN 'DL'
                   WHEN n.pos IN ('LB','ILB','OLB','MLB') THEN 'LB'
                   WHEN n.pos IN ('CB','S','FS','SS','SAF','DB') THEN 'DB'
               END AS pos_group
        FROM nfl_player_game_log n
        WHERE n.season IN (SELECT w.season FROM wanted w)
          AND COALESCE(n.season_type, 'REG') <> 'PRE'
    ),
    role AS (
        SELECT g.*,
               CASE g.pos_group
                   WHEN 'QB' THEN COALESCE(g.attempts,0) >= 10
                   WHEN 'RB' THEN COALESCE(g.carries,0) + COALESCE(g.targets,0) >= 6
                   WHEN 'WR' THEN COALESCE(g.targets,0) >= 3
                   WHEN 'TE' THEN COALESCE(g.targets,0) >= 2
                   ELSE COALESCE(g.def_tackles_solo,0) + COALESCE(g.def_tackle_assists,0)
                        + COALESCE(g.def_sacks,0) + COALESCE(g.def_qb_hits,0) >= 2
               END AS has_role,
               CASE p_stat
                   WHEN 'passing_yards'     THEN g.passing_yards::numeric
                   WHEN 'passing_tds'       THEN g.passing_tds::numeric
                   WHEN 'completions'       THEN g.completions::numeric
                   WHEN 'attempts'          THEN g.attempts::numeric
                   WHEN 'interceptions'     THEN g.interceptions::numeric
                   WHEN 'rushing_yards'     THEN g.rushing_yards::numeric
                   WHEN 'rushing_tds'       THEN g.rushing_tds::numeric
                   WHEN 'carries'           THEN g.carries::numeric
                   WHEN 'rush_rec_tds'      THEN (COALESCE(g.rushing_tds,0)
                                                  + COALESCE(g.receiving_tds,0))::numeric
                   WHEN 'receptions'        THEN g.receptions::numeric
                   WHEN 'receiving_yards'   THEN g.receiving_yards::numeric
                   WHEN 'receiving_tds'     THEN g.receiving_tds::numeric
                   WHEN 'targets'           THEN g.targets::numeric
                   WHEN 'def_sacks'         THEN g.def_sacks::numeric
                   WHEN 'def_interceptions' THEN g.def_interceptions::numeric
                   ELSE NULL
               END AS val
        FROM grp g
        WHERE g.pos_group = p_pos_group
    ),
    league AS (SELECT r.season, r.game_id, r.opponent AS opp, r.val FROM role r WHERE r.has_role AND r.val IS NOT NULL),
    defense AS (
        SELECT lg.season, lg.opp AS defense, avg(lg.val) AS avg_allowed,
               count(DISTINCT lg.game_id)::int AS team_games
        FROM league lg GROUP BY lg.season, lg.opp
    ),
    ranked AS (
        SELECT d.*,
               rank() OVER (PARTITION BY d.season ORDER BY d.avg_allowed ASC)::int AS def_rank,
               count(*) OVER (PARTITION BY d.season)::int AS teams_ranked
        FROM defense d
    ),
    nxt AS (
        SELECT r.* FROM ranked r
        WHERE r.defense = p_next_opponent
        ORDER BY r.season DESC LIMIT 1
    )
    SELECT m.season::int AS season, m.game_id::text AS game_id, m.game_date::text AS game_date,
           m.opp::text AS opponent, m.is_home AS is_home, m.val AS value,
           r.def_rank AS def_rank, r.teams_ranked AS teams_ranked,
           round(r.avg_allowed, 3) AS avg_allowed, r.team_games AS def_team_games
    FROM mine m
    JOIN played p ON p.season = m.season
    LEFT JOIN ranked r ON r.season = m.season AND r.defense = m.opp
    WHERE m.val IS NOT NULL
    UNION ALL
    SELECT n.season::int, NULL::text, NULL::text, n.defense::text, NULL::boolean,
           NULL::numeric, n.def_rank, n.teams_ranked, round(n.avg_allowed, 3), n.team_games
    FROM nxt n
    $fn$
    $ddl$;

    EXECUTE 'REVOKE ALL ON FUNCTION public.player_vs_defense_nba(text, text, text, integer[], integer, text) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_vs_defense_nba(text, text, text, integer[], integer, text) TO anon, authenticated';
    EXECUTE 'REVOKE ALL ON FUNCTION public.player_vs_defense_wnba(text, text, text, integer[], integer, text) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_vs_defense_wnba(text, text, text, integer[], integer, text) TO anon, authenticated';
    EXECUTE 'REVOKE ALL ON FUNCTION public.player_vs_defense_nfl(text, text, text, integer[], integer, text) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_vs_defense_nfl(text, text, text, integer[], integer, text) TO anon, authenticated';

    RAISE NOTICE 'player_vs_defense_nba/wnba/nfl created';
END
$mig$;
