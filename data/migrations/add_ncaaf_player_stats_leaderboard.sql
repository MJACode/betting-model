-- Migration: add_ncaaf_player_stats_leaderboard
-- Applied to Supabase 2026-08-30 as migrations:
--   add_ncaaf_player_stats_leaderboard
--   tighten_football_player_log_grants (the grant block at the foot of this file)
-- NCAAF per-player per-game stats + the season-totals view and last-N RPCs that
-- back the mobile Stats tab's NCAAF player leaderboard — the same shapes every
-- other sport already uses (v_player_season_totals_*, player_window_totals_*,
-- player_recent_games_*, player_season_stat_values_*). NFL
-- (add_nfl_player_stats_leaderboard.sql) is the reference implementation and
-- the column names match it wherever the two sports share a stat, so the
-- mobile stat catalog reads one key per stat across both football leagues.
--
-- Source: CFBD /games/players via data/ingestors/cfbd_ingestor.py — the SAME
-- payload that already fills ncaaf_qb_game, parsed wider. No extra API calls.
--
-- ncaaf_qb_game is NOT replaced: it is the modelling substrate (one row per
-- PASSER, with `is_primary`, FK'd by a decade of training rows). This table is
-- display only — one row per PLAYER, every category, and no model reads it.
--
-- NO POSITION COLUMN: CFBD's box score names participants, not positions, so
-- the leaderboard groups by stat (a passing board is whoever threw) rather
-- than by a position we would have to guess. Tackles, TFL and sacks are
-- NUMERIC because college box scores charge shared tackles in halves.

CREATE TABLE IF NOT EXISTS ncaaf_player_game_log (
    log_id          BIGSERIAL PRIMARY KEY,
    game_id         TEXT NOT NULL,
    team            TEXT NOT NULL,
    opponent        TEXT,
    season          INTEGER NOT NULL,
    week            INTEGER,
    season_type     TEXT,
    game_date       TEXT NOT NULL,
    player_id       TEXT NOT NULL,
    player_name     TEXT,
    completions     INTEGER, attempts INTEGER,
    passing_yards   INTEGER, passing_tds INTEGER, interceptions INTEGER,
    carries         INTEGER, rushing_yards INTEGER, rushing_tds INTEGER,
    receptions      INTEGER, receiving_yards INTEGER, receiving_tds INTEGER,
    def_tackles     NUMERIC, def_solo NUMERIC, def_sacks NUMERIC,
    def_tfl         NUMERIC, def_pd INTEGER, def_interceptions INTEGER,
    created_at      TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(game_id, team, player_id)
);
CREATE INDEX IF NOT EXISTS idx_ncaaf_plog_player ON ncaaf_player_game_log(player_id, game_date);
CREATE INDEX IF NOT EXISTS idx_ncaaf_plog_season ON ncaaf_player_game_log(season);
CREATE INDEX IF NOT EXISTS idx_ncaaf_plog_team   ON ncaaf_player_game_log(team, game_date);

-- The pipeline writes as the table owner via the service-role DATABASE_URL
-- (RLS does not apply to it); the mobile anon key reads through the
-- security-invoker view and RPCs below, so it needs SELECT and nothing else.
-- Default privileges hand anon ALL, and REVOKE ... FROM PUBLIC does not undo
-- that — so revoke BY NAME first, then grant back only SELECT.
ALTER TABLE public.ncaaf_player_game_log ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.ncaaf_player_game_log FROM anon, authenticated;
GRANT SELECT ON public.ncaaf_player_game_log TO anon, authenticated;
CREATE POLICY "anon read ncaaf_player_game_log"
    ON public.ncaaf_player_game_log FOR SELECT TO anon, authenticated USING (true);

-- ── Season totals per (player_id, season) — mobile Stats leaderboard ─────────
-- rush_rec_tds = rushing + receiving TDs (the "anytime TD" style stat), derived
-- here exactly as the NFL view derives it.
CREATE OR REPLACE VIEW v_player_season_totals_ncaaf
WITH (security_invoker = on) AS
SELECT
    player_id,
    (array_agg(player_name ORDER BY game_date DESC))[1] AS player_name,
    season,
    (array_agg(team ORDER BY game_date DESC))[1] AS team,
    COUNT(DISTINCT game_id)              AS games_played,
    COALESCE(SUM(completions), 0)        AS completions,
    COALESCE(SUM(attempts), 0)           AS attempts,
    COALESCE(SUM(passing_yards), 0)      AS passing_yards,
    COALESCE(SUM(passing_tds), 0)        AS passing_tds,
    COALESCE(SUM(interceptions), 0)      AS interceptions,
    COALESCE(SUM(carries), 0)            AS carries,
    COALESCE(SUM(rushing_yards), 0)      AS rushing_yards,
    COALESCE(SUM(rushing_tds), 0)        AS rushing_tds,
    COALESCE(SUM(receptions), 0)         AS receptions,
    COALESCE(SUM(receiving_yards), 0)    AS receiving_yards,
    COALESCE(SUM(receiving_tds), 0)      AS receiving_tds,
    COALESCE(SUM(COALESCE(rushing_tds,0) + COALESCE(receiving_tds,0)), 0) AS rush_rec_tds,
    COALESCE(SUM(def_tackles), 0)        AS def_tackles,
    COALESCE(SUM(def_solo), 0)           AS def_solo,
    COALESCE(SUM(def_sacks), 0)          AS def_sacks,
    COALESCE(SUM(def_tfl), 0)            AS def_tfl,
    COALESCE(SUM(def_pd), 0)             AS def_pd,
    COALESCE(SUM(def_interceptions), 0)  AS def_interceptions
FROM ncaaf_player_game_log
GROUP BY player_id, season;

-- Default privileges hand anon/authenticated ALL on anything new in public, and
-- CREATE OR REPLACE VIEW re-applies them — so the revoke has to come AFTER the
-- view exists, and has to name the roles (REVOKE ... FROM PUBLIC does nothing).
REVOKE ALL ON v_player_season_totals_ncaaf FROM anon, authenticated;
GRANT SELECT ON v_player_season_totals_ncaaf TO anon, authenticated;

-- ── Last-N-games window totals (Stats tab time-window chips) ─────────────────
CREATE OR REPLACE FUNCTION public.player_window_totals_ncaaf(
    p_season integer,
    p_window integer DEFAULT NULL
)
RETURNS TABLE (
    player_id text, player_name text, season integer, team text,
    games_played bigint,
    completions bigint, attempts bigint, passing_yards bigint, passing_tds bigint,
    interceptions bigint, carries bigint, rushing_yards bigint, rushing_tds bigint,
    receptions bigint, receiving_yards bigint, receiving_tds bigint,
    rush_rec_tds bigint,
    def_tackles numeric, def_solo numeric, def_sacks numeric, def_tfl numeric,
    def_pd bigint, def_interceptions bigint
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH ranked AS (
        SELECT n.*,
               ROW_NUMBER() OVER (PARTITION BY n.player_id
                                  ORDER BY n.game_date DESC, n.game_id DESC) AS rn
        FROM ncaaf_player_game_log n
        WHERE n.season = p_season
    )
    SELECT
        player_id,
        (array_agg(player_name ORDER BY game_date DESC))[1] AS player_name,
        p_season AS season,
        (array_agg(team ORDER BY game_date DESC))[1] AS team,
        COUNT(DISTINCT game_id) AS games_played,
        COALESCE(SUM(completions),0), COALESCE(SUM(attempts),0),
        COALESCE(SUM(passing_yards),0), COALESCE(SUM(passing_tds),0),
        COALESCE(SUM(interceptions),0), COALESCE(SUM(carries),0),
        COALESCE(SUM(rushing_yards),0), COALESCE(SUM(rushing_tds),0),
        COALESCE(SUM(receptions),0),
        COALESCE(SUM(receiving_yards),0), COALESCE(SUM(receiving_tds),0),
        COALESCE(SUM(COALESCE(rushing_tds,0)+COALESCE(receiving_tds,0)),0) AS rush_rec_tds,
        COALESCE(SUM(def_tackles),0), COALESCE(SUM(def_solo),0),
        COALESCE(SUM(def_sacks),0), COALESCE(SUM(def_tfl),0),
        COALESCE(SUM(def_pd),0), COALESCE(SUM(def_interceptions),0)
    FROM ranked
    WHERE p_window IS NULL OR rn <= p_window
    GROUP BY player_id;
$$;

-- ── Raw last-N per-game rows (Stats tab "Hit Rate" mode) ─────────────────────
CREATE OR REPLACE FUNCTION public.player_recent_games_ncaaf(
    p_season integer,
    p_window integer DEFAULT 10
)
RETURNS TABLE (
    player_id text, player_name text, team text,
    game_id text, game_date text, season integer, week integer,
    opponent text, rn integer,
    completions int, attempts int, passing_yards int, passing_tds int,
    interceptions int, carries int, rushing_yards int, rushing_tds int,
    receptions int, receiving_yards int, receiving_tds int, rush_rec_tds int,
    def_tackles numeric, def_solo numeric, def_sacks numeric, def_tfl numeric,
    def_pd int, def_interceptions int
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH ranked AS (
        SELECT n.*,
               ROW_NUMBER() OVER (PARTITION BY n.player_id
                                  ORDER BY n.game_date DESC, n.game_id DESC) AS rn
        FROM ncaaf_player_game_log n
        WHERE n.season = p_season
    )
    SELECT
        player_id, player_name, team, game_id, game_date, season, week,
        opponent, rn::int,
        completions, attempts, passing_yards, passing_tds, interceptions,
        carries, rushing_yards, rushing_tds,
        receptions, receiving_yards, receiving_tds,
        (COALESCE(rushing_tds,0) + COALESCE(receiving_tds,0))::int AS rush_rec_tds,
        def_tackles, def_solo, def_sacks, def_tfl, def_pd, def_interceptions
    FROM ranked
    WHERE rn <= LEAST(COALESCE(p_window, 10), 25)
    ORDER BY player_id, rn;
$$;

-- ── Whole-season per-game values for ONE stat (Hit Rate mode, Season window) ──
-- Same CASE-whitelist / value-array shape as every other sport's variant: an
-- unknown stat key yields no rows rather than an error.
CREATE OR REPLACE FUNCTION public.player_season_stat_values_ncaaf(
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
                WHEN 'def_tackles'       THEN n.def_tackles
                WHEN 'def_solo'          THEN n.def_solo
                WHEN 'def_sacks'         THEN n.def_sacks
                WHEN 'def_tfl'           THEN n.def_tfl
                WHEN 'def_pd'            THEN n.def_pd::numeric
                WHEN 'def_interceptions' THEN n.def_interceptions::numeric
                ELSE NULL
            END AS val
        FROM ncaaf_player_game_log n
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

GRANT EXECUTE ON FUNCTION public.player_window_totals_ncaaf(integer, integer)     TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_recent_games_ncaaf(integer, integer)      TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_ncaaf(integer, text)   TO anon, authenticated;

-- Same exposure on the NFL pair this leaderboard was copied from: anon held
-- INSERT/UPDATE/DELETE at the grant level, blocked only by RLS carrying no
-- write policy. Reads go through the view and the RPCs; nothing client-side
-- writes either table.
REVOKE ALL ON public.v_player_season_totals_nfl FROM anon, authenticated;
GRANT SELECT ON public.v_player_season_totals_nfl TO anon, authenticated;
REVOKE ALL ON public.nfl_player_game_log FROM anon, authenticated;
GRANT SELECT ON public.nfl_player_game_log TO anon, authenticated;
