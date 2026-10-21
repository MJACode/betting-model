-- Migration: position_defense_ranks_nfl
--
-- Stats > NFL > Anytime TD matchup column (Designer Option A, 2026-10-18).
-- One row per defense for a position group and a stat, so the board can rank
-- every opponent in one read instead of calling position_vs_opponent_nfl once
-- per player.
--
-- RANK 1 = ALLOWS THE MOST per qualifying player-game. That is the easiest
-- matchup for the offense. The same role cut and stat whitelist as
-- add_position_vs_opponent_nfl.sql — the two must agree or the board asks
-- for a population the card does not.
--
-- WINDOW. BLEND_UNTIL_TEAM_GAMES = 8. Team games are distinct non-preseason
-- games in the CURRENT season (max of p_seasons), counted for the defense
-- as a team, not for the position. Until a defense has played 8, the rate
-- blends every season the caller named (the app names this season and last).
-- At 8 or more, the rate is the current season only. Each defense switches
-- on its own; `blended` is what the board's one early-season note reads.
--
-- POSITION ON THE SEASON AND H2H READS. Those two NFL functions returned no
-- `pos`, so Season and H2H could not say which defense rank a row belongs
-- to. Adding an output column changes the row type, which CREATE OR REPLACE
-- refuses, so each is dropped and recreated once — guarded on the result
-- already containing `pos`. The argument lists do not change.
--
-- SAME DDL DISCIPLINE as add_position_vs_opponent_nfl.sql: one DO block,
-- each piece guarded, PUBLIC revoked before the named grant. This file runs
-- on every refresh pass and each DDL statement makes PostgREST 503 the app
-- while it reloads.

DO $mig$
BEGIN
    IF NOT EXISTS (SELECT 1
                     FROM pg_proc p
                     JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public'
                      AND p.proname = 'position_defense_ranks_nfl') THEN
        EXECUTE $ddl$
        CREATE OR REPLACE FUNCTION public.position_defense_ranks_nfl(
            p_seasons integer[],
            p_stat text,
            p_pos_group text
        )
        RETURNS TABLE (
            defense text,
            avg_allowed numeric,
            player_games integer,
            season_team_games integer,
            window_team_games integer,
            blended boolean,
            rank_most_allowed integer,
            teams_ranked integer
        )
        LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
        WITH current_season AS (
            SELECT max(s) AS season FROM unnest(p_seasons) AS s
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
            WHERE n.season = ANY(p_seasons)
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
        q AS (
            SELECT * FROM role
            WHERE has_role AND val IS NOT NULL AND opponent IS NOT NULL
        ),
        season_games AS (
            SELECT upper(n.opponent) AS defense,
                   count(DISTINCT n.game_id)::int AS team_games
            FROM nfl_player_game_log n
            JOIN current_season c ON n.season = c.season
            WHERE COALESCE(n.season_type, 'REG') <> 'PRE'
              AND n.opponent IS NOT NULL
            GROUP BY upper(n.opponent)
        ),
        used AS (
            SELECT q.*,
                   COALESCE(sg.team_games, 0) AS season_team_games,
                   (COALESCE(sg.team_games, 0) < 8) AS blended
            FROM q
            LEFT JOIN season_games sg ON sg.defense = upper(q.opponent)
            JOIN current_season c ON TRUE
            WHERE (COALESCE(sg.team_games, 0) >= 8 AND q.season = c.season)
               OR (COALESCE(sg.team_games, 0) < 8)
        ),
        defense AS (
            SELECT upper(u.opponent) AS defense,
                   avg(u.val) AS avg_allowed,
                   count(*)::int AS player_games,
                   count(DISTINCT u.game_id)::int AS window_team_games,
                   max(u.season_team_games)::int AS season_team_games,
                   bool_or(u.blended) AS blended
            FROM used u
            GROUP BY upper(u.opponent)
        ),
        ranked AS (
            SELECT d.*,
                   rank() OVER (ORDER BY d.avg_allowed DESC)::int AS rank_most_allowed,
                   count(*) OVER ()::int AS teams_ranked
            FROM defense d
        )
        SELECT r.defense,
               round(r.avg_allowed, 3),
               r.player_games,
               r.season_team_games,
               r.window_team_games,
               r.blended,
               r.rank_most_allowed,
               r.teams_ranked
        FROM ranked r
        $fn$
        $ddl$;

        EXECUTE 'REVOKE ALL ON FUNCTION public.position_defense_ranks_nfl(integer[], text, text) FROM PUBLIC';
        EXECUTE 'GRANT EXECUTE ON FUNCTION public.position_defense_ranks_nfl(integer[], text, text) TO anon, authenticated';
        RAISE NOTICE 'position_defense_ranks_nfl created';
    ELSE
        RAISE NOTICE 'position_defense_ranks_nfl already present — skipping';
    END IF;

    -- Season read gains pos. Guarded on the result type, not on the function
    -- existing: the original create is not in ACTIVE_MIGRATIONS, and a later
    -- pass must not drop a function that already returns pos.
    IF NOT EXISTS (SELECT 1
                     FROM pg_proc p
                     JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public'
                      AND p.proname = 'player_season_stat_values_nfl'
                      AND pg_get_function_identity_arguments(p.oid) = 'integer, text'
                      AND pg_get_function_result(p.oid) ILIKE '%pos text%') THEN
        EXECUTE 'DROP FUNCTION IF EXISTS public.player_season_stat_values_nfl(integer, text)';
        EXECUTE $ddl$
        CREATE FUNCTION public.player_season_stat_values_nfl(
            p_season integer,
            p_stat text
        )
        RETURNS TABLE (
            player_id text, player_name text, team text, pos text,
            games integer, "values" numeric[]
        )
        LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
            WITH vals AS (
                SELECT
                    n.player_id, n.player_name, n.team, n.pos, n.game_date, n.game_id,
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
                (array_agg(v.pos ORDER BY v.game_date DESC, v.game_id DESC)
                     FILTER (WHERE v.pos IS NOT NULL AND btrim(v.pos) <> ''))[1] AS pos,
                count(v.val)::int AS games,
                (array_agg(v.val ORDER BY v.game_date DESC, v.game_id DESC)
                     FILTER (WHERE v.val IS NOT NULL)) AS "values"
            FROM vals v
            GROUP BY v.player_id
            HAVING count(v.val) > 0
        $fn$
        $ddl$;
        EXECUTE 'REVOKE ALL ON FUNCTION public.player_season_stat_values_nfl(integer, text) FROM PUBLIC';
        EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_season_stat_values_nfl(integer, text) TO anon, authenticated';
        RAISE NOTICE 'player_season_stat_values_nfl now returns pos';
    ELSE
        RAISE NOTICE 'player_season_stat_values_nfl already returns pos — skipping';
    END IF;

    IF NOT EXISTS (SELECT 1
                     FROM pg_proc p
                     JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public'
                      AND p.proname = 'player_h2h_stat_values_nfl'
                      AND pg_get_function_identity_arguments(p.oid) = 'integer[], text, text[], text[]'
                      AND pg_get_function_result(p.oid) ILIKE '%pos text%') THEN
        EXECUTE 'DROP FUNCTION IF EXISTS public.player_h2h_stat_values_nfl(integer[], text, text[], text[])';
        EXECUTE $ddl$
        CREATE FUNCTION public.player_h2h_stat_values_nfl(
            p_seasons integer[],
            p_stat text,
            p_teams text[],
            p_opponents text[]
        )
        RETURNS TABLE (
            player_id text, player_name text, team text, pos text,
            opponent text, games integer, "values" numeric[], dates text[]
        )
        LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
        WITH pairs AS (
            SELECT DISTINCT t.team, o.opp
            FROM unnest(p_teams)     WITH ORDINALITY AS t(team, i)
            JOIN unnest(p_opponents) WITH ORDINALITY AS o(opp, i) USING (i)
        ),
        latest AS (
            SELECT DISTINCT ON (n.player_id) n.player_id, n.player_name, n.team
            FROM nfl_player_game_log n
            WHERE n.season = ANY(p_seasons)
            ORDER BY n.player_id, n.game_date DESC, n.game_id DESC
        ),
        sel AS (
            SELECT l.player_id, l.player_name, l.team, p.opp
            FROM latest l JOIN pairs p ON p.team = l.team
        ),
        vals AS (
            SELECT s.player_id, s.player_name, s.team, s.opp, n.pos, n.game_date, n.game_id,
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
            FROM sel s
            JOIN nfl_player_game_log n
              ON n.player_id = s.player_id
             AND n.opponent = s.opp
             AND n.season = ANY(p_seasons)
        )
        SELECT
            v.player_id,
            (array_agg(v.player_name ORDER BY v.game_date DESC, v.game_id DESC))[1] AS player_name,
            (array_agg(v.team        ORDER BY v.game_date DESC, v.game_id DESC))[1] AS team,
            (array_agg(v.pos ORDER BY v.game_date DESC, v.game_id DESC)
                 FILTER (WHERE v.pos IS NOT NULL AND btrim(v.pos) <> ''))[1] AS pos,
            v.opp AS opponent,
            count(v.val)::int AS games,
            (array_agg(v.val       ORDER BY v.game_date DESC, v.game_id DESC)
                 FILTER (WHERE v.val IS NOT NULL)) AS "values",
            (array_agg(v.game_date ORDER BY v.game_date DESC, v.game_id DESC)
                 FILTER (WHERE v.val IS NOT NULL)) AS dates
        FROM vals v
        GROUP BY v.player_id, v.opp
        HAVING count(v.val) > 0
        $fn$
        $ddl$;
        EXECUTE 'REVOKE ALL ON FUNCTION public.player_h2h_stat_values_nfl(integer[], text, text[], text[]) FROM PUBLIC';
        EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_nfl(integer[], text, text[], text[]) TO anon, authenticated';
        RAISE NOTICE 'player_h2h_stat_values_nfl now returns pos';
    ELSE
        RAISE NOTICE 'player_h2h_stat_values_nfl already returns pos — skipping';
    END IF;
END
$mig$;
