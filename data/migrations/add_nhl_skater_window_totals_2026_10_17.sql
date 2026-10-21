-- NHL Stats Players tab: season and last-N sums, the same read the other
-- sports take from player_window_totals_*.
--
-- The source is nhl_skater_game_log, written by data/ingestors/nhl_game_logs.py.
-- The shots column is `shots`. Season is the ENDING year: 2027 is the
-- 2026-27 season (measured 2026-10-17: season 2027, game_type 2, 4,247 rows,
-- 2026-09-29 through 2026-10-15). game_type 2 is the regular season, the
-- same cut v_player_season_totals_nhl uses in #962.
--
-- This file does not GRANT on the log and does not add an RLS policy.
-- Those are add_nhl_stats_views_2026_10_16.sql (#962, draft, not applied).
-- The function is SECURITY INVOKER. Until this migration runs, PostgREST
-- answers PGRST202, or Postgres answers 42883: the function is not in the
-- schema. Until #962 grants anon SELECT and adds a policy, a call answers
-- 42501, permission denied for nhl_skater_game_log. Both are errors.
-- The app treats those codes as an empty average and still shows lines.
-- Merging #962 is the OK for that grant.
--
-- One statement. It returns once the function exists, so a later change
-- needs a new migration. NOT applied from a development session.
-- ACTIVE_MIGRATIONS is what runs it. It does not touch the published record.

DO $mig$
BEGIN
    SET LOCAL lock_timeout = '10s';

    IF EXISTS (
        SELECT 1
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'public'
           AND p.proname = 'player_window_totals_nhl'
    ) THEN
        RAISE NOTICE 'player_window_totals_nhl already present — skipping';
        RETURN;
    END IF;

    EXECUTE $ddl$
    CREATE FUNCTION public.player_window_totals_nhl(
        p_season integer,
        p_window integer DEFAULT NULL
    )
    RETURNS TABLE (
        player_id text,
        player_name text,
        team text,
        pos text,
        season integer,
        games_played bigint,
        goals bigint,
        assists bigint,
        points bigint,
        shots bigint
    )
    LANGUAGE sql
    STABLE
    SECURITY INVOKER
    SET search_path = public, pg_temp
    AS $fn$
        WITH ranked AS (
            SELECT s.player_id,
                   s.player_name,
                   s.team,
                   s.position,
                   s.game_date,
                   s.nhl_game_id,
                   s.goals,
                   s.assists,
                   s.points,
                   s.shots
              FROM public.nhl_skater_game_log s
             WHERE s.season = p_season
               AND s.game_type = 2
        ),
        numbered AS (
            SELECT ranked.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY ranked.player_id
                       ORDER BY ranked.game_date DESC, ranked.nhl_game_id DESC
                   ) AS rn
              FROM ranked
        )
        SELECT
            player_id::text,
            (array_agg(player_name ORDER BY game_date DESC, nhl_game_id DESC))[1],
            (array_agg(team ORDER BY game_date DESC, nhl_game_id DESC))[1],
            (array_agg(position ORDER BY game_date DESC, nhl_game_id DESC))[1],
            p_season,
            COUNT(DISTINCT nhl_game_id),
            COALESCE(SUM(goals), 0),
            COALESCE(SUM(assists), 0),
            COALESCE(SUM(points), 0),
            COALESCE(SUM(shots), 0)
          FROM numbered
         WHERE p_window IS NULL OR (p_window > 0 AND rn <= p_window)
         GROUP BY player_id
    $fn$
    $ddl$;

    EXECUTE 'REVOKE ALL ON FUNCTION public.player_window_totals_nhl(integer, integer) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_window_totals_nhl(integer, integer) TO anon, authenticated';
END
$mig$;
