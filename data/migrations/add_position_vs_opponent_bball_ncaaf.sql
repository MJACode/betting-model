-- Migration: add_position_vs_opponent_bball_ncaaf
--
-- Phase 3 of the player page's "same position vs the next opponent" card
-- (Matt, 2026-10-05): NBA, WNBA and NCAAF, same row shape as the NFL and MLB
-- functions so one card draws all five. Positions come from player_positions
-- (add_player_positions.sql), keyed on OUR player_id, so the join is direct.
--
-- GROUPS. Basketball G / F / C (Matt, 2026-10-05); NCAAF the NFL buckets
-- (QB, RB, WR, TE, DL, LB, DB) — player_positions.pos_group already holds them.
--
-- "REAL ROLE ONLY" (Matt, 2026-10-05):
--   NBA / WNBA  15+ minutes. Measured 2026-10-06: median minutes per logged
--               player-game 23-24 (NBA 2025-26), 21-22 (WNBA).
--   NCAAF       QB 10+ attempts; RB 6+ carries + receptions; WR / TE 1+
--               reception; defence 2+ tackles + sacks. The college log has NO
--               targets column (CFBD box scores do not carry it), so a
--               receiver's role can only be seen through a catch — a 0-catch
--               game is excluded, which leans the receiving hit rate UP. Said
--               on the card's footnote.
--
-- OPPONENT. Basketball logs have no opponent column, so it comes from `games`
-- (as in player_h2h_stat_values_*); NCAAF stores it on the row.
--
-- Positions are CURRENT (a player's latest roster listing), applied to every
-- game in the window — a player who changed position mid-season is counted
-- under today's.
--
-- One guarded DO block; PUBLIC revoked before the named grant
-- (tests/test_ddl_guard.py). Guard: all three functions exist.

DO $mig$
BEGIN
    IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'public'
           AND p.proname IN ('position_vs_opponent_nba', 'position_vs_opponent_wnba',
                             'position_vs_opponent_ncaaf')) >= 3 THEN
        RAISE NOTICE 'position_vs_opponent_nba/wnba/ncaaf already present — skipping';
        RETURN;
    END IF;

    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.position_vs_opponent_nba(
    p_seasons integer[],
    p_stat text,
    p_pos_group text,
    p_opponent text
    )
    RETURNS TABLE (
    season integer, player_id text, player_name text, team text, pos text,
    game_id text, game_date text, week integer, value numeric,
    avg_allowed numeric, player_games integer,
    rank_most_allowed integer, teams_ranked integer
    )
    LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
    WITH g AS (
        SELECT l.*, pp.position,
               CASE WHEN gm.home_team = l.team THEN gm.away_team ELSE gm.home_team END AS opp
        FROM nba_player_game_log l
        JOIN player_positions pp
          ON pp.sport = 'NBA' AND pp.player_id = l.player_id AND pp.pos_group = p_pos_group
        JOIN games gm ON gm.game_id = l.game_id AND gm.sport = 'NBA'
        WHERE l.season = ANY(p_seasons)
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
    ok AS (SELECT * FROM q WHERE has_role AND val IS NOT NULL),
    defense AS (
        SELECT ok.season, ok.opp AS defense, avg(ok.val) AS avg_allowed,
               count(*)::int AS player_games
        FROM ok GROUP BY ok.season, ok.opp
    ),
    ranked AS (
        SELECT d.*,
               rank() OVER (PARTITION BY d.season ORDER BY d.avg_allowed DESC)::int AS rank_most_allowed,
               count(*) OVER (PARTITION BY d.season)::int AS teams_ranked
        FROM defense d
    )
    SELECT ok.season::int, ok.player_id::text, ok.player_name::text, ok.team::text,
           ok.position::text, ok.game_id::text, ok.game_date::text, NULL::int, ok.val,
           round(r.avg_allowed, 3), r.player_games, r.rank_most_allowed, r.teams_ranked
    FROM ok
    JOIN ranked r ON r.season = ok.season AND r.defense = ok.opp
    WHERE ok.opp = p_opponent
    $fn$
    $ddl$;

    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.position_vs_opponent_wnba(
    p_seasons integer[],
    p_stat text,
    p_pos_group text,
    p_opponent text
    )
    RETURNS TABLE (
    season integer, player_id text, player_name text, team text, pos text,
    game_id text, game_date text, week integer, value numeric,
    avg_allowed numeric, player_games integer,
    rank_most_allowed integer, teams_ranked integer
    )
    LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
    WITH g AS (
        SELECT l.*, pp.position,
               CASE WHEN gm.home_team = l.team THEN gm.away_team ELSE gm.home_team END AS opp
        FROM wnba_player_game_log l
        JOIN player_positions pp
          ON pp.sport = 'WNBA' AND pp.player_id = l.player_id AND pp.pos_group = p_pos_group
        JOIN games gm ON gm.game_id = l.game_id AND gm.sport = 'WNBA'
        WHERE l.season = ANY(p_seasons)
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
    ok AS (SELECT * FROM q WHERE has_role AND val IS NOT NULL),
    defense AS (
        SELECT ok.season, ok.opp AS defense, avg(ok.val) AS avg_allowed,
               count(*)::int AS player_games
        FROM ok GROUP BY ok.season, ok.opp
    ),
    ranked AS (
        SELECT d.*,
               rank() OVER (PARTITION BY d.season ORDER BY d.avg_allowed DESC)::int AS rank_most_allowed,
               count(*) OVER (PARTITION BY d.season)::int AS teams_ranked
        FROM defense d
    )
    SELECT ok.season::int, ok.player_id::text, ok.player_name::text, ok.team::text,
           ok.position::text, ok.game_id::text, ok.game_date::text, NULL::int, ok.val,
           round(r.avg_allowed, 3), r.player_games, r.rank_most_allowed, r.teams_ranked
    FROM ok
    JOIN ranked r ON r.season = ok.season AND r.defense = ok.opp
    WHERE ok.opp = p_opponent
    $fn$
    $ddl$;

    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.position_vs_opponent_ncaaf(
    p_seasons integer[],
    p_stat text,
    p_pos_group text,
    p_opponent text
    )
    RETURNS TABLE (
    season integer, player_id text, player_name text, team text, pos text,
    game_id text, game_date text, week integer, value numeric,
    avg_allowed numeric, player_games integer,
    rank_most_allowed integer, teams_ranked integer
    )
    LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
    WITH g AS (
        SELECT l.*, pp.position, l.opponent AS opp
        FROM ncaaf_player_game_log l
        JOIN player_positions pp
          ON pp.sport = 'NCAAF' AND pp.player_id = l.player_id AND pp.pos_group = p_pos_group
        WHERE l.season = ANY(p_seasons)
    ),
    q AS (
        SELECT g.*,
               CASE p_pos_group
                   WHEN 'QB' THEN COALESCE(g.attempts,0) >= 10
                   WHEN 'RB' THEN COALESCE(g.carries,0) + COALESCE(g.receptions,0) >= 6
                   WHEN 'WR' THEN COALESCE(g.receptions,0) >= 1
                   WHEN 'TE' THEN COALESCE(g.receptions,0) >= 1
                   ELSE COALESCE(g.def_tackles,0) + COALESCE(g.def_sacks,0) >= 2
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
                   WHEN 'def_tackles'       THEN g.def_tackles::numeric
                   WHEN 'def_solo'          THEN g.def_solo::numeric
                   WHEN 'def_sacks'         THEN g.def_sacks::numeric
                   WHEN 'def_tfl'           THEN g.def_tfl::numeric
                   WHEN 'def_pd'            THEN g.def_pd::numeric
                   WHEN 'def_interceptions' THEN g.def_interceptions::numeric
                   ELSE NULL
               END AS val
        FROM g
    ),
    ok AS (SELECT * FROM q WHERE has_role AND val IS NOT NULL),
    defense AS (
        SELECT ok.season, ok.opp AS defense, avg(ok.val) AS avg_allowed,
               count(*)::int AS player_games
        FROM ok GROUP BY ok.season, ok.opp
    ),
    ranked AS (
        SELECT d.*,
               rank() OVER (PARTITION BY d.season ORDER BY d.avg_allowed DESC)::int AS rank_most_allowed,
               count(*) OVER (PARTITION BY d.season)::int AS teams_ranked
        FROM defense d
    )
    SELECT ok.season::int, ok.player_id::text, ok.player_name::text, ok.team::text,
           ok.position::text, ok.game_id::text, ok.game_date::text, ok.week::int, ok.val,
           round(r.avg_allowed, 3), r.player_games, r.rank_most_allowed, r.teams_ranked
    FROM ok
    JOIN ranked r ON r.season = ok.season AND r.defense = ok.opp
    WHERE ok.opp = p_opponent
    $fn$
    $ddl$;

    EXECUTE 'REVOKE ALL ON FUNCTION public.position_vs_opponent_nba(integer[], text, text, text) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.position_vs_opponent_nba(integer[], text, text, text) TO anon, authenticated';
    EXECUTE 'REVOKE ALL ON FUNCTION public.position_vs_opponent_wnba(integer[], text, text, text) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.position_vs_opponent_wnba(integer[], text, text, text) TO anon, authenticated';
    EXECUTE 'REVOKE ALL ON FUNCTION public.position_vs_opponent_ncaaf(integer[], text, text, text) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.position_vs_opponent_ncaaf(integer[], text, text, text) TO anon, authenticated';

    RAISE NOTICE 'position_vs_opponent_nba/wnba/ncaaf created';
END
$mig$;
