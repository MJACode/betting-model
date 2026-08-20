-- Migration: add_player_season_stat_values_nfl
-- NFL variant of the player_season_stat_values_* RPCs (see
-- add_player_season_stat_values_rpcs.sql for the full rationale) — backs the
-- Stats tab Hit Rate mode's SEASON window for the NFL leaderboard added in
-- add_nfl_player_stats_leaderboard.sql. Same CASE-whitelist / value-array
-- shape; rush_rec_tds is derived (rushing + receiving TDs) to match the
-- season-totals view.

CREATE OR REPLACE FUNCTION public.player_season_stat_values_nfl(
    p_season integer,
    p_stat text
)
RETURNS TABLE (
    player_id text, player_name text, team text,
    games integer, "values" numeric[]
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH vals AS (
        SELECT
            n.player_id, n.player_name, n.team, n.game_date, n.game_id,
            CASE p_stat
                WHEN 'passing_yards'     THEN n.passing_yards::numeric
                WHEN 'passing_tds'       THEN n.passing_tds::numeric
                WHEN 'completions'       THEN n.completions::numeric
                WHEN 'attempts'          THEN n.attempts::numeric
                WHEN 'interceptions'     THEN n.interceptions::numeric
                WHEN 'rushing_yards'     THEN n.rushing_yards::numeric
                WHEN 'rushing_tds'       THEN n.rushing_tds::numeric
                WHEN 'carries'           THEN n.carries::numeric
                WHEN 'rush_rec_tds'      THEN (COALESCE(n.rushing_tds,0) + COALESCE(n.receiving_tds,0))::numeric
                WHEN 'receptions'        THEN n.receptions::numeric
                WHEN 'receiving_yards'   THEN n.receiving_yards::numeric
                WHEN 'receiving_tds'     THEN n.receiving_tds::numeric
                WHEN 'targets'           THEN n.targets::numeric
                WHEN 'def_sacks'         THEN n.def_sacks::numeric
                WHEN 'def_interceptions' THEN n.def_interceptions::numeric
                ELSE NULL
            END AS val
        FROM nfl_player_game_log n
        WHERE n.season = p_season
    )
    SELECT
        v.player_id,
        (array_agg(v.player_name ORDER BY v.game_date DESC, v.game_id DESC))[1] AS player_name,
        (array_agg(v.team        ORDER BY v.game_date DESC, v.game_id DESC))[1] AS team,
        count(v.val)::int AS games,
        (array_agg(v.val ORDER BY v.game_date DESC, v.game_id DESC)
             FILTER (WHERE v.val IS NOT NULL)) AS "values"
    FROM vals v
    GROUP BY v.player_id
    HAVING count(v.val) > 0;
$$;

GRANT EXECUTE ON FUNCTION public.player_season_stat_values_nfl(integer, text) TO anon, authenticated;
