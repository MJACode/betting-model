-- Migration: add_player_recent_games_rpcs
-- Adds per-sport RPCs returning the RAW last-N per-game rows per player (not
-- aggregated sums like player_window_totals_*). The mobile Stats tab's "Hit
-- Rate" mode uses these to compute, for any stat + any threshold, how many of a
-- player's last N games cleared the line ("X/N") and to draw the per-game
-- green/red dot strip — without a new RPC per stat.
--
-- Same ranked-CTE pattern as player_window_totals_* (ROW_NUMBER over each
-- player's games newest-first), but it SELECTs the ranked rows instead of
-- grouping. N is capped server-side at 25. security_invoker + anon/auth GRANTs
-- so the mobile anon key can read them, exactly like the window RPCs.

-- ── MLB: raw last-N game-log rows per player ──────────────────────────────────
CREATE OR REPLACE FUNCTION public.player_recent_games_mlb(
    p_season integer,
    p_player_type text,
    p_window integer DEFAULT 10
)
RETURNS TABLE (
    player_id text, player_name text, team text, player_type text,
    game_id text, game_date text, season integer, rn integer,
    at_bats int, hits int, doubles int, triples int, home_runs int,
    total_bases int, rbi int, runs int, walks int, strikeouts int, stolen_bases int,
    p_strikeouts int, p_walks int, p_hits_allowed int, p_earned_runs int,
    p_home_runs int, innings_pitched numeric, pitches int
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH ranked AS (
        SELECT pgl.*,
               ROW_NUMBER() OVER (PARTITION BY pgl.player_id
                                  ORDER BY pgl.game_date DESC, pgl.game_id DESC) AS rn
        FROM player_game_log pgl
        WHERE pgl.season = p_season AND pgl.player_type = p_player_type
    )
    SELECT
        player_id, player_name, team, player_type, game_id, game_date,
        season, rn::int,
        at_bats, hits, doubles, triples, home_runs, total_bases, rbi, runs,
        walks, strikeouts, stolen_bases, p_strikeouts, p_walks, p_hits_allowed,
        p_earned_runs, p_home_runs, innings_pitched, pitches
    FROM ranked
    WHERE rn <= LEAST(COALESCE(p_window, 10), 25)
    ORDER BY player_id, rn;
$$;

-- ── WNBA: raw last-N game-log rows per player ─────────────────────────────────
CREATE OR REPLACE FUNCTION public.player_recent_games_wnba(
    p_season integer,
    p_window integer DEFAULT 10
)
RETURNS TABLE (
    player_id text, player_name text, team text,
    game_id text, game_date text, season integer, rn integer,
    minutes numeric, points int, rebounds int, assists int, threes int,
    steals int, blocks int, turnovers int, pra int
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH ranked AS (
        SELECT w.*,
               ROW_NUMBER() OVER (PARTITION BY w.player_id
                                  ORDER BY w.game_date DESC, w.game_id DESC) AS rn
        FROM wnba_player_game_log w
        WHERE w.season = p_season
    )
    SELECT
        player_id, player_name, team, game_id, game_date, season, rn::int,
        minutes, points, rebounds, assists, fg3_made AS threes, steals, blocks,
        turnovers,
        (COALESCE(points,0) + COALESCE(rebounds,0) + COALESCE(assists,0))::int AS pra
    FROM ranked
    WHERE rn <= LEAST(COALESCE(p_window, 10), 25)
    ORDER BY player_id, rn;
$$;

-- ── NBA: raw last-N game-log rows per player ──────────────────────────────────
CREATE OR REPLACE FUNCTION public.player_recent_games_nba(
    p_season integer,
    p_window integer DEFAULT 10
)
RETURNS TABLE (
    player_id text, player_name text, team text,
    game_id text, game_date text, season integer, rn integer,
    minutes numeric, points int, rebounds int, assists int, threes int,
    steals int, blocks int, turnovers int, pra int
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH ranked AS (
        SELECT n.*,
               ROW_NUMBER() OVER (PARTITION BY n.player_id
                                  ORDER BY n.game_date DESC, n.game_id DESC) AS rn
        FROM nba_player_game_log n
        WHERE n.season = p_season
    )
    SELECT
        player_id, player_name, team, game_id, game_date, season, rn::int,
        minutes, points, rebounds, assists, fg3_made AS threes, steals, blocks,
        turnovers,
        (COALESCE(points,0) + COALESCE(rebounds,0) + COALESCE(assists,0))::int AS pra
    FROM ranked
    WHERE rn <= LEAST(COALESCE(p_window, 10), 25)
    ORDER BY player_id, rn;
$$;

GRANT EXECUTE ON FUNCTION public.player_recent_games_mlb(integer, text, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_recent_games_wnba(integer, integer)       TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_recent_games_nba(integer, integer)        TO anon, authenticated;
