-- Migration: add_nfl_player_stats_leaderboard
-- NFL per-player per-game stats + the season-totals view and last-N RPCs that
-- back the mobile Stats tab NFL leaderboard — same shapes as MLB/WNBA/NBA
-- (v_player_season_totals_*, player_window_totals_*, player_recent_games_*).
-- Data source: nflverse stats_player_week_{season}.csv via
-- data/ingestors/nfl_player_stats_ingestor.py (self-healing daily step).
--
-- game_id is "NFL_{nflverse_id}" (platform convention) with NO FK to games:
-- only wind/opener pick games ever get a games row, while this log covers the
-- whole league. Display/stats only — no model reads this table.

CREATE TABLE IF NOT EXISTS nfl_player_game_log (
    log_id          BIGSERIAL PRIMARY KEY,
    player_id       TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    pos             TEXT,
    team            TEXT NOT NULL,
    opponent        TEXT,
    game_id         TEXT NOT NULL,
    game_date       TEXT NOT NULL,
    season          INTEGER NOT NULL,
    week            INTEGER,
    season_type     TEXT,
    completions     INTEGER, attempts INTEGER,
    passing_yards   NUMERIC, passing_tds INTEGER, interceptions INTEGER,
    carries         INTEGER, rushing_yards NUMERIC, rushing_tds INTEGER,
    receptions      INTEGER, targets INTEGER,
    receiving_yards NUMERIC, receiving_tds INTEGER,
    def_sacks       NUMERIC, def_interceptions INTEGER,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(player_id, game_id)
);
CREATE INDEX IF NOT EXISTS idx_nfl_plog_player ON nfl_player_game_log(player_id, game_date);
CREATE INDEX IF NOT EXISTS idx_nfl_plog_season ON nfl_player_game_log(season);

-- Pipeline writes via the service-role DATABASE_URL (bypasses RLS); the mobile
-- anon key reads through the invoker view/RPCs below, so it needs SELECT.
ALTER TABLE nfl_player_game_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon read nfl_player_game_log"
    ON nfl_player_game_log FOR SELECT TO anon, authenticated USING (true);

-- ── Season totals per (player_id, season) — mobile Stats leaderboard ─────────
-- rush_rec_tds = rushing + receiving TDs (the "anytime TD" style stat).
CREATE OR REPLACE VIEW v_player_season_totals_nfl
WITH (security_invoker = on) AS
SELECT
    player_id,
    (array_agg(player_name ORDER BY game_date DESC))[1] AS player_name,
    season,
    (array_agg(team ORDER BY game_date DESC))[1] AS team,
    (array_agg(pos ORDER BY game_date DESC))[1]  AS pos,
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
    COALESCE(SUM(targets), 0)            AS targets,
    COALESCE(SUM(receiving_yards), 0)    AS receiving_yards,
    COALESCE(SUM(receiving_tds), 0)      AS receiving_tds,
    COALESCE(SUM(COALESCE(rushing_tds,0) + COALESCE(receiving_tds,0)), 0) AS rush_rec_tds,
    COALESCE(SUM(def_sacks), 0)          AS def_sacks,
    COALESCE(SUM(def_interceptions), 0)  AS def_interceptions
FROM nfl_player_game_log
GROUP BY player_id, season;

GRANT SELECT ON v_player_season_totals_nfl TO anon, authenticated;

-- ── Last-N-games window totals (Stats tab time-window chips) ─────────────────
CREATE OR REPLACE FUNCTION public.player_window_totals_nfl(
    p_season integer,
    p_window integer DEFAULT NULL
)
RETURNS TABLE (
    player_id text, player_name text, season integer, team text, pos text,
    games_played bigint,
    completions bigint, attempts bigint, passing_yards numeric, passing_tds bigint,
    interceptions bigint, carries bigint, rushing_yards numeric, rushing_tds bigint,
    receptions bigint, targets bigint, receiving_yards numeric, receiving_tds bigint,
    rush_rec_tds bigint, def_sacks numeric, def_interceptions bigint
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH ranked AS (
        SELECT n.*,
               ROW_NUMBER() OVER (PARTITION BY n.player_id
                                  ORDER BY n.game_date DESC, n.game_id DESC) AS rn
        FROM nfl_player_game_log n
        WHERE n.season = p_season
    )
    SELECT
        player_id,
        (array_agg(player_name ORDER BY game_date DESC))[1] AS player_name,
        p_season AS season,
        (array_agg(team ORDER BY game_date DESC))[1] AS team,
        (array_agg(pos ORDER BY game_date DESC))[1]  AS pos,
        COUNT(DISTINCT game_id) AS games_played,
        COALESCE(SUM(completions),0), COALESCE(SUM(attempts),0),
        COALESCE(SUM(passing_yards),0), COALESCE(SUM(passing_tds),0),
        COALESCE(SUM(interceptions),0), COALESCE(SUM(carries),0),
        COALESCE(SUM(rushing_yards),0), COALESCE(SUM(rushing_tds),0),
        COALESCE(SUM(receptions),0), COALESCE(SUM(targets),0),
        COALESCE(SUM(receiving_yards),0), COALESCE(SUM(receiving_tds),0),
        COALESCE(SUM(COALESCE(rushing_tds,0)+COALESCE(receiving_tds,0)),0) AS rush_rec_tds,
        COALESCE(SUM(def_sacks),0), COALESCE(SUM(def_interceptions),0)
    FROM ranked
    WHERE p_window IS NULL OR rn <= p_window
    GROUP BY player_id;
$$;

-- ── Raw last-N per-game rows (Stats tab "Hit Rate" mode) ─────────────────────
CREATE OR REPLACE FUNCTION public.player_recent_games_nfl(
    p_season integer,
    p_window integer DEFAULT 10
)
RETURNS TABLE (
    player_id text, player_name text, team text, pos text,
    game_id text, game_date text, season integer, rn integer,
    completions int, attempts int, passing_yards numeric, passing_tds int,
    interceptions int, carries int, rushing_yards numeric, rushing_tds int,
    receptions int, targets int, receiving_yards numeric, receiving_tds int,
    rush_rec_tds int, def_sacks numeric, def_interceptions int
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH ranked AS (
        SELECT n.*,
               ROW_NUMBER() OVER (PARTITION BY n.player_id
                                  ORDER BY n.game_date DESC, n.game_id DESC) AS rn
        FROM nfl_player_game_log n
        WHERE n.season = p_season
    )
    SELECT
        player_id, player_name, team, pos, game_id, game_date, season, rn::int,
        completions, attempts, passing_yards, passing_tds, interceptions,
        carries, rushing_yards, rushing_tds, receptions, targets,
        receiving_yards, receiving_tds,
        (COALESCE(rushing_tds,0) + COALESCE(receiving_tds,0))::int AS rush_rec_tds,
        def_sacks, def_interceptions
    FROM ranked
    WHERE rn <= LEAST(COALESCE(p_window, 10), 25)
    ORDER BY player_id, rn;
$$;

GRANT EXECUTE ON FUNCTION public.player_window_totals_nfl(integer, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_recent_games_nfl(integer, integer)  TO anon, authenticated;
