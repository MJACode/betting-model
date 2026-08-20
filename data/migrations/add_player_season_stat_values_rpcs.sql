-- Migration: add_player_season_stat_values_rpcs (applied 2026-08-19)
-- Backs the Stats tab "Hit Rate" mode's SEASON window. The last-N window uses
-- player_recent_games_* (raw rows, capped at 25 games server-side); a whole
-- season of raw rows would be ~35-50K rows for MLB — far too heavy for the
-- phone. These RPCs instead return ONE row per player carrying that player's
-- full-season per-game values for a single whitelisted stat as an ordered
-- array (newest game first, nulls excluded), so the client can compute the
-- season hit rate for ANY line/direction instantly (the line ruler stays
-- client-side) at ~700 rows / a few hundred KB.
--
-- p_stat is dispatched through a CASE whitelist of game-log columns — an
-- unknown key yields all-null values and therefore zero rows (the client only
-- ever passes keys from its static stat catalog). security_invoker + anon
-- GRANTs, matching player_recent_games_* (the underlying game-log tables all
-- carry anon SELECT policies). NOTE: "values" is a reserved word, hence the
-- quoted column name — PostgREST still serializes the JSON key as `values`.

-- ── MLB: per-player season value arrays for one stat ─────────────────────────
CREATE OR REPLACE FUNCTION public.player_season_stat_values_mlb(
    p_season integer,
    p_player_type text,
    p_stat text
)
RETURNS TABLE (
    player_id text, player_name text, team text, player_type text,
    games integer, "values" numeric[]
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH vals AS (
        SELECT
            pgl.player_id, pgl.player_name, pgl.team, pgl.player_type,
            pgl.game_date, pgl.game_id,
            CASE p_stat
                -- batting
                WHEN 'hits'            THEN pgl.hits::numeric
                WHEN 'home_runs'       THEN pgl.home_runs::numeric
                WHEN 'total_bases'     THEN pgl.total_bases::numeric
                WHEN 'rbi'             THEN pgl.rbi::numeric
                WHEN 'runs'            THEN pgl.runs::numeric
                WHEN 'walks'           THEN pgl.walks::numeric
                WHEN 'stolen_bases'    THEN pgl.stolen_bases::numeric
                WHEN 'doubles'         THEN pgl.doubles::numeric
                WHEN 'triples'         THEN pgl.triples::numeric
                WHEN 'strikeouts'      THEN pgl.strikeouts::numeric
                WHEN 'at_bats'         THEN pgl.at_bats::numeric
                -- pitching
                WHEN 'p_strikeouts'    THEN pgl.p_strikeouts::numeric
                WHEN 'p_walks'         THEN pgl.p_walks::numeric
                WHEN 'p_hits_allowed'  THEN pgl.p_hits_allowed::numeric
                WHEN 'p_earned_runs'   THEN pgl.p_earned_runs::numeric
                WHEN 'p_home_runs'     THEN pgl.p_home_runs::numeric
                WHEN 'innings_pitched' THEN pgl.innings_pitched::numeric
                WHEN 'pitches'         THEN pgl.pitches::numeric
                ELSE NULL
            END AS val
        FROM player_game_log pgl
        WHERE pgl.season = p_season AND pgl.player_type = p_player_type
    )
    SELECT
        v.player_id,
        (array_agg(v.player_name ORDER BY v.game_date DESC, v.game_id DESC))[1] AS player_name,
        (array_agg(v.team        ORDER BY v.game_date DESC, v.game_id DESC))[1] AS team,
        (array_agg(v.player_type ORDER BY v.game_date DESC, v.game_id DESC))[1] AS player_type,
        count(v.val)::int AS games,
        (array_agg(v.val ORDER BY v.game_date DESC, v.game_id DESC)
             FILTER (WHERE v.val IS NOT NULL)) AS "values"
    FROM vals v
    GROUP BY v.player_id
    HAVING count(v.val) > 0;
$$;

-- ── WNBA ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.player_season_stat_values_wnba(
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
            w.player_id, w.player_name, w.team, w.game_date, w.game_id,
            CASE p_stat
                WHEN 'points'    THEN w.points::numeric
                WHEN 'rebounds'  THEN w.rebounds::numeric
                WHEN 'assists'   THEN w.assists::numeric
                WHEN 'threes'    THEN w.fg3_made::numeric
                WHEN 'steals'    THEN w.steals::numeric
                WHEN 'blocks'    THEN w.blocks::numeric
                WHEN 'turnovers' THEN w.turnovers::numeric
                WHEN 'minutes'   THEN w.minutes::numeric
                WHEN 'pra'       THEN (COALESCE(w.points,0) + COALESCE(w.rebounds,0)
                                       + COALESCE(w.assists,0))::numeric
                ELSE NULL
            END AS val
        FROM wnba_player_game_log w
        WHERE w.season = p_season
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

-- ── NBA ──────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.player_season_stat_values_nba(
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
                WHEN 'points'    THEN n.points::numeric
                WHEN 'rebounds'  THEN n.rebounds::numeric
                WHEN 'assists'   THEN n.assists::numeric
                WHEN 'threes'    THEN n.fg3_made::numeric
                WHEN 'steals'    THEN n.steals::numeric
                WHEN 'blocks'    THEN n.blocks::numeric
                WHEN 'turnovers' THEN n.turnovers::numeric
                WHEN 'minutes'   THEN n.minutes::numeric
                WHEN 'pra'       THEN (COALESCE(n.points,0) + COALESCE(n.rebounds,0)
                                       + COALESCE(n.assists,0))::numeric
                ELSE NULL
            END AS val
        FROM nba_player_game_log n
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

GRANT EXECUTE ON FUNCTION public.player_season_stat_values_mlb(integer, text, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_wnba(integer, text)      TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_nba(integer, text)       TO anon, authenticated;
