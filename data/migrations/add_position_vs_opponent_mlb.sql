-- Migration: add_position_vs_opponent_mlb
--
-- Phase 2 of the player page's "same position vs the next opponent" card
-- (Matt, 2026-10-05: "MLB - line up spot and starter"). The NFL version is
-- add_position_vs_opponent_nfl.sql; this returns the SAME row shape so the
-- app draws both with one card.
--
-- GROUPS. Fielding position says little about how a hitter does against a
-- pitching staff, so batters are grouped by where they hit:
--   TOP  batting 1st-3rd     MID  4th-6th     BOT  7th-9th
-- and pitchers by role: SP = the game's starting pitcher.
--
-- "REAL ROLE ONLY" (Matt, 2026-10-05). A batter counts only in a game he
-- STARTED in that lineup spot (batting_order 1-9; it is NULL for pinch
-- hitters and late subs — 7,326 of 47,014 batter rows in 2026, measured
-- 2026-10-06). A pitcher counts only when is_starter. The same cut feeds the
-- rank.
--
-- THE OPPONENT comes from `games`: player_game_log has no opponent column
-- (as in player_h2h_stat_values_mlb). Rank 1 = the team that allows the most
-- per qualifying player-game, over the teams with any qualifying game that
-- season.
--
-- KNOWN GAP (measured 2026-10-06, not fixed here): the 2025 log holds no game
-- involving ARI, CWS, OAK or WSH — 26 teams, while `games` has all 162 of
-- ARI's. So "last season" vs those four is empty and 2025 ranks are "of 26".
-- 2026 has all 30.
--
-- Same DDL discipline as the NFL file: one guarded DO block, PUBLIC revoked
-- before the named grant (tests/test_ddl_guard.py).

DO $mig$
BEGIN
    IF EXISTS (SELECT 1
                 FROM pg_proc p
                 JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public'
                  AND p.proname = 'position_vs_opponent_mlb') THEN
        RAISE NOTICE 'position_vs_opponent_mlb already present — skipping';
        RETURN;
    END IF;

    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.position_vs_opponent_mlb(
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
    WITH grp AS (
        SELECT pgl.*,
               CASE WHEN g.home_team = pgl.team THEN g.away_team ELSE g.home_team END AS opp,
               CASE
                   WHEN pgl.player_type = 'pitcher' AND pgl.is_starter THEN 'SP'
                   WHEN pgl.player_type = 'batter' AND pgl.batting_order BETWEEN 1 AND 3 THEN 'TOP'
                   WHEN pgl.player_type = 'batter' AND pgl.batting_order BETWEEN 4 AND 6 THEN 'MID'
                   WHEN pgl.player_type = 'batter' AND pgl.batting_order BETWEEN 7 AND 9 THEN 'BOT'
               END AS pos_group
        FROM player_game_log pgl
        JOIN games g ON g.game_id = pgl.game_id AND g.sport = 'MLB'
        WHERE pgl.season = ANY(p_seasons)
    ),
    q AS (
        SELECT g.*,
               CASE p_stat
                   -- batting
                   WHEN 'hits'            THEN g.hits::numeric
                   WHEN 'home_runs'       THEN g.home_runs::numeric
                   WHEN 'total_bases'     THEN g.total_bases::numeric
                   WHEN 'rbi'             THEN g.rbi::numeric
                   WHEN 'runs'            THEN g.runs::numeric
                   WHEN 'walks'           THEN g.walks::numeric
                   WHEN 'stolen_bases'    THEN g.stolen_bases::numeric
                   WHEN 'doubles'         THEN g.doubles::numeric
                   WHEN 'triples'         THEN g.triples::numeric
                   WHEN 'strikeouts'      THEN g.strikeouts::numeric
                   WHEN 'at_bats'         THEN g.at_bats::numeric
                   -- pitching
                   WHEN 'p_strikeouts'    THEN g.p_strikeouts::numeric
                   WHEN 'p_walks'         THEN g.p_walks::numeric
                   WHEN 'p_hits_allowed'  THEN g.p_hits_allowed::numeric
                   WHEN 'p_earned_runs'   THEN g.p_earned_runs::numeric
                   WHEN 'p_home_runs'     THEN g.p_home_runs::numeric
                   WHEN 'innings_pitched' THEN g.innings_pitched::numeric
                   WHEN 'pitches'         THEN g.pitches::numeric
                   ELSE NULL
               END AS val
        FROM grp g
        WHERE g.pos_group = p_pos_group
    ),
    ok AS (
        SELECT * FROM q WHERE val IS NOT NULL
    ),
    defense AS (
        SELECT ok.season, ok.opp AS defense,
               avg(ok.val) AS avg_allowed,
               count(*)::int AS player_games
        FROM ok
        GROUP BY ok.season, ok.opp
    ),
    ranked AS (
        SELECT d.*,
               rank() OVER (PARTITION BY d.season ORDER BY d.avg_allowed DESC)::int AS rank_most_allowed,
               count(*) OVER (PARTITION BY d.season)::int AS teams_ranked
        FROM defense d
    )
    SELECT ok.season::int, ok.player_id::text, ok.player_name::text, ok.team::text,
           CASE WHEN ok.pos_group = 'SP' THEN 'SP' ELSE ok.batting_order::text END,
           ok.game_id::text, ok.game_date::text, NULL::int, ok.val,
           round(r.avg_allowed, 3), r.player_games, r.rank_most_allowed, r.teams_ranked
    FROM ok
    JOIN ranked r ON r.season = ok.season AND r.defense = ok.opp
    WHERE ok.opp = p_opponent
    $fn$
    $ddl$;

    EXECUTE 'REVOKE ALL ON FUNCTION public.position_vs_opponent_mlb(integer[], text, text, text) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.position_vs_opponent_mlb(integer[], text, text, text) TO anon, authenticated';

    RAISE NOTICE 'position_vs_opponent_mlb created';
END
$mig$;
