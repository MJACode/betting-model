-- NHL Stats-tab reads. Display only: no scorer, no card, and no record view
-- reads these names. NOT applied from a development session. The worker runs
-- this file because it is in data/view_migrations.ACTIVE_MIGRATIONS. Merging
-- is the approval to open the three log tables to anon SELECT.
--
-- The logs were created with RLS on, privileges revoked, and no policy
-- (add_nhl_game_logs.sql). A security_invoker view runs as the caller, so
-- anon needs SELECT and a SELECT policy or the future screen is empty.
-- postgres and service_role bypass RLS; the worker's writes are unchanged.
-- RLS is not forced.
--
-- ONE statement, and it returns once the objects and the three policies
-- exist. Every DDL fires pgrst_ddl_watch. This file runs on every refresh.
--
-- Season is the ENDING year. game_type 2 is the regular season, the same
-- cut the prop cards use. player_id is text here because the other season
-- views expose text ids; the logs store bigint.
--
-- GAA is goals against per 60 minutes: goals_against * 3600 / toi_seconds.
-- Save% is saves / shots_against. Skater TOI minutes are toi_seconds / 60.
--
-- player_stat_values_nhl(p_season, p_kind, p_stat, p_window) returns one row
-- per player and a newest-first array of per-game values. p_window NULL is
-- the season, 5 is the last five games, 10 is the last ten. The array
-- elements are the per-game series the hit rate is counted from. An unknown
-- p_stat or p_kind yields no rows.
--
-- v_nhl_player_prop_odds is the newest pre-game quote per
-- (game, market, player, book, line) for games.sport = 'NHL', bounded at
-- commence_time, in-play snapshots excluded. player_id is set only when
-- exactly one regular-season log id on the home or away team, this season
-- or last, matches the book's name. Zero or several leave it null.
-- FILTER IT. A read with no game_id and no game_date scans player_prop_odds
-- and hits statement_timeout. Every caller passes one game or one date.

DO $mig$
BEGIN
    SET LOCAL lock_timeout = '10s';

    IF to_regclass('public.v_player_season_totals_nhl') IS NOT NULL
       AND to_regclass('public.v_team_season_totals_nhl') IS NOT NULL
       AND to_regclass('public.v_nhl_player_prop_odds') IS NOT NULL
       AND EXISTS (
            SELECT 1
              FROM pg_proc p
              JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'public'
               AND p.proname = 'player_stat_values_nhl')
       AND EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public'
               AND tablename = 'nhl_skater_game_log'
               AND policyname = 'anon read nhl_skater_game_log')
       AND EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public'
               AND tablename = 'nhl_goalie_game_log'
               AND policyname = 'anon read nhl_goalie_game_log')
       AND EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public'
               AND tablename = 'nhl_team_game_log'
               AND policyname = 'anon read nhl_team_game_log')
    THEN
        RAISE NOTICE 'nhl stats views already present — skipping';
        RETURN;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'nhl_skater_game_log'
           AND policyname = 'anon read nhl_skater_game_log') THEN
        CREATE POLICY "anon read nhl_skater_game_log"
            ON public.nhl_skater_game_log
            FOR SELECT TO anon, authenticated
            USING (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'nhl_goalie_game_log'
           AND policyname = 'anon read nhl_goalie_game_log') THEN
        CREATE POLICY "anon read nhl_goalie_game_log"
            ON public.nhl_goalie_game_log
            FOR SELECT TO anon, authenticated
            USING (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'nhl_team_game_log'
           AND policyname = 'anon read nhl_team_game_log') THEN
        CREATE POLICY "anon read nhl_team_game_log"
            ON public.nhl_team_game_log
            FOR SELECT TO anon, authenticated
            USING (true);
    END IF;

    EXECUTE $ddl$
    CREATE OR REPLACE VIEW public.v_player_season_totals_nhl
    WITH (security_invoker = on) AS
    SELECT
        s.player_id::text AS player_id,
        (array_agg(s.player_name ORDER BY s.game_date DESC, s.nhl_game_id DESC))[1] AS player_name,
        'skater'::text AS kind,
        s.season,
        (array_agg(s.team ORDER BY s.game_date DESC, s.nhl_game_id DESC))[1] AS team,
        (array_agg(s.position ORDER BY s.game_date DESC, s.nhl_game_id DESC))[1] AS position,
        COUNT(DISTINCT s.nhl_game_id) AS games_played,
        COALESCE(SUM(s.points), 0) AS points,
        COALESCE(SUM(s.goals), 0) AS goals,
        COALESCE(SUM(s.assists), 0) AS assists,
        COALESCE(SUM(s.shots), 0) AS shots,
        COALESCE(SUM(s.hits), 0) AS hits,
        COALESCE(SUM(s.blocked_shots), 0) AS blocks,
        COALESCE(SUM(s.pp_points), 0) AS pp_points,
        COALESCE(SUM(s.toi_seconds), 0)::numeric / 60.0 AS toi_minutes,
        COALESCE(SUM(s.toi_seconds), 0) AS toi_seconds,
        NULL::bigint AS saves,
        NULL::bigint AS shots_against,
        NULL::bigint AS goals_against,
        NULL::numeric AS save_pct,
        NULL::numeric AS gaa
    FROM public.nhl_skater_game_log s
    WHERE s.game_type = 2
    GROUP BY s.player_id, s.season
    UNION ALL
    SELECT
        g.player_id::text,
        (array_agg(g.player_name ORDER BY g.game_date DESC, g.nhl_game_id DESC))[1],
        'goalie'::text,
        g.season,
        (array_agg(g.team ORDER BY g.game_date DESC, g.nhl_game_id DESC))[1],
        'G'::text,
        COUNT(DISTINCT g.nhl_game_id),
        NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint,
        NULL::bigint, NULL::bigint, NULL::bigint,
        COALESCE(SUM(g.toi_seconds), 0)::numeric / 60.0,
        COALESCE(SUM(g.toi_seconds), 0),
        COALESCE(SUM(g.saves), 0),
        COALESCE(SUM(g.shots_against), 0),
        COALESCE(SUM(g.goals_against), 0),
        SUM(g.saves)::numeric / NULLIF(SUM(g.shots_against), 0),
        SUM(g.goals_against)::numeric * 3600.0 / NULLIF(SUM(g.toi_seconds), 0)
    FROM public.nhl_goalie_game_log g
    WHERE g.game_type = 2
    GROUP BY g.player_id, g.season
    $ddl$;

    EXECUTE $ddl$
    CREATE OR REPLACE VIEW public.v_team_season_totals_nhl
    WITH (security_invoker = on) AS
    SELECT
        t.team,
        t.season,
        COUNT(DISTINCT t.nhl_game_id) AS games_played,
        COALESCE(SUM(t.goals_for), 0) AS goals_for,
        COALESCE(SUM(t.goals_against), 0) AS goals_against,
        COALESCE(SUM(t.shots_for), 0) AS shots_for,
        COALESCE(SUM(t.shots_against), 0) AS shots_against,
        COALESCE(SUM(t.hits), 0) AS hits,
        COALESCE(SUM(t.blocked_shots), 0) AS blocked_shots,
        COALESCE(SUM(t.pp_goals), 0) AS pp_goals,
        COALESCE(SUM(t.pp_opportunities), 0) AS pp_opportunities,
        COALESCE(SUM(t.pp_goals_against), 0) AS pp_goals_against,
        COALESCE(SUM(t.times_shorthanded), 0) AS times_shorthanded,
        COALESCE(SUM(t.sat_for_5v5), 0) AS sat_for_5v5,
        COALESCE(SUM(t.sat_against_5v5), 0) AS sat_against_5v5,
        AVG(t.faceoff_win_pct) AS faceoff_win_pct
    FROM public.nhl_team_game_log t
    WHERE t.game_type = 2
    GROUP BY t.team, t.season
    $ddl$;

    -- Callers filter on game_id or game_date. Unfiltered, this view scans
    -- player_prop_odds and hits statement_timeout.
    EXECUTE $ddl$
    CREATE OR REPLACE VIEW public.v_nhl_player_prop_odds
    WITH (security_invoker = on) AS
    WITH nhl_games AS (
        SELECT game_id, game_date, season, home_team, away_team, commence_time
        FROM public.games
        WHERE sport = 'NHL'
    ),
    quotes AS (
        SELECT DISTINCT ON (p.game_id, p.market, p.player_name, p.bookmaker, p.line)
               p.game_id,
               p.game_date,
               p.market,
               p.player_name,
               p.bookmaker,
               p.line,
               p.over_price,
               p.under_price,
               p.snapshot_at,
               p.snapshot_type,
               g.season,
               g.home_team,
               g.away_team,
               g.commence_time
        FROM public.player_prop_odds p
        JOIN nhl_games g ON g.game_id = p.game_id
        WHERE (p.snapshot_type IS NULL OR p.snapshot_type <> 'in_play')
          AND g.commence_time IS NOT NULL
          AND p.snapshot_at::timestamptz <= g.commence_time::timestamptz
        ORDER BY p.game_id, p.market, p.player_name, p.bookmaker, p.line,
                 p.snapshot_at::timestamptz DESC
    )
    SELECT
        q.game_id,
        q.game_date,
        q.commence_time,
        q.home_team,
        q.away_team,
        q.market,
        q.player_name,
        CASE WHEN ids.n = 1 THEN ids.player_id ELSE NULL END AS player_id,
        q.bookmaker,
        q.line,
        q.over_price,
        q.under_price,
        q.snapshot_at,
        q.snapshot_type
    FROM quotes q
    LEFT JOIN LATERAL (
        SELECT COUNT(DISTINCT u.player_id)::int AS n,
               MIN(u.player_id) AS player_id
        FROM (
            SELECT s.player_id::text AS player_id
            FROM public.nhl_skater_game_log s
            WHERE s.game_type = 2
              AND s.season IN (q.season, q.season - 1)
              AND s.team IN (q.home_team, q.away_team)
              AND lower(s.player_name) = lower(q.player_name)
            UNION
            SELECT gl.player_id::text
            FROM public.nhl_goalie_game_log gl
            WHERE gl.game_type = 2
              AND gl.season IN (q.season, q.season - 1)
              AND gl.team IN (q.home_team, q.away_team)
              AND lower(gl.player_name) = lower(q.player_name)
        ) u
    ) ids ON true
    $ddl$;

    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_stat_values_nhl(
        p_season integer,
        p_kind text,
        p_stat text,
        p_window integer
    )
    RETURNS TABLE (
        player_id text,
        player_name text,
        team text,
        kind text,
        games integer,
        "values" numeric[]
    )
    LANGUAGE sql
    STABLE
    SECURITY INVOKER
    SET search_path = public, pg_temp
    AS $fn$
        WITH sk AS (
            SELECT s.player_id::text AS player_id,
                   s.player_name,
                   s.team,
                   s.game_date,
                   s.nhl_game_id,
                   'skater'::text AS kind,
                   CASE p_stat
                       WHEN 'points' THEN s.points::numeric
                       WHEN 'goals' THEN s.goals::numeric
                       WHEN 'assists' THEN s.assists::numeric
                       WHEN 'shots' THEN s.shots::numeric
                       WHEN 'hits' THEN s.hits::numeric
                       WHEN 'blocks' THEN s.blocked_shots::numeric
                       WHEN 'pp_points' THEN s.pp_points::numeric
                       WHEN 'toi' THEN s.toi_seconds::numeric / 60.0
                       WHEN 'toi_seconds' THEN s.toi_seconds::numeric
                       ELSE NULL
                   END AS val
            FROM public.nhl_skater_game_log s
            WHERE p_kind = 'skater'
              AND s.season = p_season
              AND s.game_type = 2
        ),
        gl AS (
            SELECT g.player_id::text,
                   g.player_name,
                   g.team,
                   g.game_date,
                   g.nhl_game_id,
                   'goalie'::text,
                   CASE p_stat
                       WHEN 'saves' THEN g.saves::numeric
                       WHEN 'save_pct' THEN g.saves::numeric / NULLIF(g.shots_against, 0)
                       WHEN 'gaa' THEN g.goals_against::numeric * 3600.0 / NULLIF(g.toi_seconds, 0)
                       WHEN 'shots_against' THEN g.shots_against::numeric
                       WHEN 'goals_against' THEN g.goals_against::numeric
                       WHEN 'toi' THEN g.toi_seconds::numeric / 60.0
                       WHEN 'toi_seconds' THEN g.toi_seconds::numeric
                       ELSE NULL
                   END
            FROM public.nhl_goalie_game_log g
            WHERE p_kind = 'goalie'
              AND g.season = p_season
              AND g.game_type = 2
        ),
        raw AS (
            SELECT * FROM sk
            UNION ALL
            SELECT * FROM gl
        ),
        ranked AS (
            SELECT raw.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY raw.player_id
                       ORDER BY raw.game_date DESC, raw.nhl_game_id DESC
                   ) AS rn
            FROM raw
            WHERE raw.val IS NOT NULL
        )
        SELECT
            r.player_id,
            (array_agg(r.player_name ORDER BY r.game_date DESC, r.nhl_game_id DESC))[1],
            (array_agg(r.team ORDER BY r.game_date DESC, r.nhl_game_id DESC))[1],
            (array_agg(r.kind ORDER BY r.game_date DESC, r.nhl_game_id DESC))[1],
            count(r.val)::int,
            (array_agg(r.val ORDER BY r.game_date DESC, r.nhl_game_id DESC)
                 FILTER (WHERE r.val IS NOT NULL))
        FROM ranked r
        WHERE p_window IS NULL OR (p_window > 0 AND r.rn <= p_window)
        GROUP BY r.player_id
        HAVING count(r.val) > 0
    $fn$
    $ddl$;

    EXECUTE 'GRANT SELECT ON public.nhl_skater_game_log TO anon, authenticated';
    EXECUTE 'GRANT SELECT ON public.nhl_goalie_game_log TO anon, authenticated';
    EXECUTE 'GRANT SELECT ON public.nhl_team_game_log TO anon, authenticated';
    EXECUTE 'GRANT SELECT ON public.v_player_season_totals_nhl TO anon, authenticated';
    EXECUTE 'GRANT SELECT ON public.v_team_season_totals_nhl TO anon, authenticated';
    EXECUTE 'GRANT SELECT ON public.v_nhl_player_prop_odds TO anon, authenticated';
    EXECUTE 'REVOKE ALL ON FUNCTION public.player_stat_values_nhl(integer, text, text, integer) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_stat_values_nhl(integer, text, text, integer) TO anon, authenticated';
END
$mig$;
