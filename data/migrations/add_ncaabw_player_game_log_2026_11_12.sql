-- Women's college basketball player stats for the Stats tab. The men's board
-- shipped 2026-11-03 (add_ncaab_player_game_log_2026_11_03.sql); this is that
-- table, view and four functions on the women's log.
--
-- ncaabw_player_game_log: one row per player per game, from sportsdataverse's
-- ncaa_wbb_player_box file (data/ingestors/ncaabw_sdv_import.py). ESPN's
-- women's player box is not ingested. `team` is the school name the games row
-- carries (the writer joins ncaabw_events on the ESPN game id), so the H2H
-- join matches games.home_team / away_team. player_id is the team ESPN id
-- plus the folded name, because NCAA's own player id changes every season.
-- Display only: no model reads it, and there is no player-prop market
-- (Matt, 2026-11-03: college hoops has no props).
--
-- NOT in data/view_migrations.ACTIVE_MIGRATIONS. Apply by hand once Matt
-- says so, and before this app build reaches users. A merge to master ships
-- the Stats tab over the air, and from then the board reads this view. An
-- empty table in November shows the tip-off sentence. The worker does not
-- have to be this build first: a worker that does not know the table never
-- writes it. The grants in this file (SELECT on the table and the view,
-- EXECUTE on the four functions) are what the app needs.
--
-- The view and the four functions are the men's set with the table swapped
-- and the same column names, so the app's basketball stat keys read one
-- column per stat. The H2H join filters g.sport = 'NCAABW'.
--
-- Once the table, the policy and the view's marker comment exist, this
-- returns on a catalog read (data/ddl_guard.py: a no-op CREATE OR REPLACE
-- still reloads PostgREST's schema cache).
DO $$
BEGIN
  IF to_regclass('public.ncaabw_player_game_log') IS NOT NULL
     AND to_regclass('public.v_player_season_totals_ncaabw') IS NOT NULL
     AND COALESCE(obj_description(to_regclass('public.v_player_season_totals_ncaabw'), 'pg_class'), '')
         = 'ncaabw_player_game_log v1'
     AND EXISTS (
       SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'ncaabw_player_game_log'
          AND policyname = 'anon read ncaabw_player_game_log')
  THEN
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.ncaabw_player_game_log (
    game_id        TEXT    NOT NULL,
    player_id      TEXT    NOT NULL,
    player_name    TEXT    NOT NULL,
    team           TEXT    NOT NULL,
    team_espn_id   BIGINT  NOT NULL,
    espn_event_id  BIGINT  NOT NULL,
    season         INTEGER NOT NULL,
    game_date      TEXT    NOT NULL,
    position       TEXT,
    is_starter     INTEGER,
    minutes        NUMERIC,
    points         INTEGER,
    rebounds       INTEGER,
    offensive_reb  INTEGER,
    defensive_reb  INTEGER,
    assists        INTEGER,
    steals         INTEGER,
    blocks         INTEGER,
    turnovers      INTEGER,
    fouls          INTEGER,
    fg_made        INTEGER,
    fg_att         INTEGER,
    fg3_made       INTEGER,
    fg3_att        INTEGER,
    ft_made        INTEGER,
    ft_att         INTEGER,
    source         TEXT    NOT NULL,
    loaded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, player_id)
  );
  CREATE INDEX IF NOT EXISTS idx_ncaabw_plog_player
    ON public.ncaabw_player_game_log (player_id, game_date DESC);
  CREATE INDEX IF NOT EXISTS idx_ncaabw_plog_season
    ON public.ncaabw_player_game_log (season);
  CREATE INDEX IF NOT EXISTS idx_ncaabw_plog_event
    ON public.ncaabw_player_game_log (espn_event_id);

  ALTER TABLE public.ncaabw_player_game_log ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.ncaabw_player_game_log FROM anon, authenticated;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'ncaabw_player_game_log'
       AND policyname = 'anon read ncaabw_player_game_log'
  ) THEN
    CREATE POLICY "anon read ncaabw_player_game_log"
      ON public.ncaabw_player_game_log
      FOR SELECT
      TO anon, authenticated
      USING (true);
  END IF;
  GRANT SELECT ON public.ncaabw_player_game_log TO anon, authenticated;

  -- ── Season totals per (player, season): the leaderboard ─────────────────
  EXECUTE $view$
    CREATE OR REPLACE VIEW public.v_player_season_totals_ncaabw
    WITH (security_invoker = on) AS
    SELECT player_id,
           (array_agg(player_name ORDER BY game_date DESC))[1] AS player_name,
           season,
           (array_agg(team ORDER BY game_date DESC))[1] AS team,
           count(DISTINCT game_id) AS games_played,
           COALESCE(sum(minutes), 0::numeric) AS minutes,
           COALESCE(sum(points), 0::bigint) AS points,
           COALESCE(sum(rebounds), 0::bigint) AS rebounds,
           COALESCE(sum(assists), 0::bigint) AS assists,
           COALESCE(sum(fg3_made), 0::bigint) AS threes,
           COALESCE(sum(steals), 0::bigint) AS steals,
           COALESCE(sum(blocks), 0::bigint) AS blocks,
           COALESCE(sum(turnovers), 0::bigint) AS turnovers,
           COALESCE(sum(COALESCE(points, 0) + COALESCE(rebounds, 0) + COALESCE(assists, 0)), 0::bigint) AS pra
      FROM public.ncaabw_player_game_log
     GROUP BY player_id, season
  $view$;
  EXECUTE $c$COMMENT ON VIEW public.v_player_season_totals_ncaabw IS 'ncaabw_player_game_log v1'$c$;
  REVOKE ALL ON public.v_player_season_totals_ncaabw FROM anon, authenticated;
  GRANT SELECT ON public.v_player_season_totals_ncaabw TO anon, authenticated;

  -- ── Last-N-games totals (the L3/L5/L10 chips on Averages) ───────────────
  EXECUTE $f$
    CREATE OR REPLACE FUNCTION public.player_window_totals_ncaabw(p_season integer, p_window integer DEFAULT NULL::integer)
     RETURNS TABLE(player_id text, player_name text, season integer, team text, games_played bigint,
                   minutes numeric, points bigint, rebounds bigint, assists bigint, threes bigint,
                   steals bigint, blocks bigint, turnovers bigint, pra bigint)
     LANGUAGE sql STABLE SECURITY INVOKER
     SET search_path TO 'public', 'pg_temp'
    AS $body$
        WITH ranked AS (
            SELECT w.*,
                   ROW_NUMBER() OVER (PARTITION BY w.player_id
                                      ORDER BY w.game_date DESC, w.game_id DESC) AS rn
            FROM ncaabw_player_game_log w
            WHERE w.season = p_season
        )
        SELECT
            player_id,
            (array_agg(player_name ORDER BY game_date DESC))[1] AS player_name,
            p_season AS season,
            (array_agg(team ORDER BY game_date DESC))[1] AS team,
            COUNT(DISTINCT game_id) AS games_played,
            COALESCE(SUM(minutes),0), COALESCE(SUM(points),0), COALESCE(SUM(rebounds),0),
            COALESCE(SUM(assists),0), COALESCE(SUM(fg3_made),0), COALESCE(SUM(steals),0),
            COALESCE(SUM(blocks),0), COALESCE(SUM(turnovers),0),
            COALESCE(SUM(COALESCE(points,0)+COALESCE(rebounds,0)+COALESCE(assists,0)),0) AS pra
        FROM ranked
        WHERE p_window IS NULL OR rn <= p_window
        GROUP BY player_id;
    $body$
  $f$;

  -- ── Raw last-N per-game rows (Hit Rates L3/L5/L10) ──────────────────────
  EXECUTE $f$
    CREATE OR REPLACE FUNCTION public.player_recent_games_ncaabw(p_season integer, p_window integer DEFAULT 10, p_teams text[] DEFAULT NULL::text[])
     RETURNS TABLE(player_id text, player_name text, team text, game_id text, game_date text, season integer,
                   rn integer, minutes numeric, points integer, rebounds integer, assists integer, threes integer,
                   steals integer, blocks integer, turnovers integer, pra integer)
     LANGUAGE sql STABLE SECURITY INVOKER
     SET search_path TO 'public', 'pg_temp'
    AS $body$
        WITH ranked AS (
            SELECT w.*,
                   ROW_NUMBER() OVER (PARTITION BY w.player_id
                                      ORDER BY w.game_date DESC, w.game_id DESC) AS rn
            FROM ncaabw_player_game_log w
            WHERE w.season = p_season
        ),
        keep AS (
            SELECT r.player_id FROM ranked r
            WHERE r.rn = 1 AND (p_teams IS NULL OR r.team = ANY(p_teams))
        )
        SELECT
            r.player_id, r.player_name, r.team, r.game_id, r.game_date, r.season,
            r.rn::int, r.minutes, r.points, r.rebounds, r.assists,
            r.fg3_made AS threes, r.steals, r.blocks, r.turnovers,
            (COALESCE(r.points,0) + COALESCE(r.rebounds,0) + COALESCE(r.assists,0))::int AS pra
        FROM ranked r
        JOIN keep k ON k.player_id = r.player_id
        WHERE r.rn <= LEAST(COALESCE(p_window, 10), 25)
        ORDER BY r.player_id, r.rn;
    $body$
  $f$;

  -- ── Every game's value for one stat (Hit Rates, season) ─────────────────
  EXECUTE $f$
    CREATE OR REPLACE FUNCTION public.player_season_stat_values_ncaabw(p_season integer, p_stat text)
     RETURNS TABLE(player_id text, player_name text, team text, games integer, "values" numeric[])
     LANGUAGE sql STABLE SECURITY INVOKER
     SET search_path TO 'public', 'pg_temp'
    AS $body$
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
            FROM ncaabw_player_game_log w
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
    $body$
  $f$;

  -- ── H2H: a slate player's values against tonight's opponent ─────────────
  EXECUTE $f$
    CREATE OR REPLACE FUNCTION public.player_h2h_stat_values_ncaabw(p_seasons integer[], p_stat text, p_teams text[], p_opponents text[])
     RETURNS TABLE(player_id text, player_name text, team text, opponent text, games integer, "values" numeric[], dates text[])
     LANGUAGE sql STABLE SECURITY INVOKER
     SET search_path TO 'public', 'pg_temp'
    AS $body$
        WITH pairs AS (
            SELECT DISTINCT t.team, o.opp
            FROM unnest(p_teams)     WITH ORDINALITY AS t(team, i)
            JOIN unnest(p_opponents) WITH ORDINALITY AS o(opp, i) USING (i)
        ),
        latest AS (
            SELECT DISTINCT ON (w.player_id) w.player_id, w.player_name, w.team
            FROM ncaabw_player_game_log w
            WHERE w.season = ANY(p_seasons)
            ORDER BY w.player_id, w.game_date DESC, w.game_id DESC
        ),
        sel AS (
            SELECT l.player_id, l.player_name, l.team, p.opp
            FROM latest l JOIN pairs p ON p.team = l.team
        ),
        vals AS (
            SELECT s.player_id, s.player_name, s.team, s.opp, w.game_date, w.game_id,
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
            FROM sel s
            JOIN ncaabw_player_game_log w
              ON w.player_id = s.player_id AND w.season = ANY(p_seasons)
            JOIN games g
              ON g.game_id = w.game_id AND g.sport = 'NCAABW'
             AND CASE WHEN g.home_team = w.team THEN g.away_team ELSE g.home_team END = s.opp
        )
        SELECT
            v.player_id,
            (array_agg(v.player_name ORDER BY v.game_date DESC, v.game_id DESC))[1] AS player_name,
            (array_agg(v.team        ORDER BY v.game_date DESC, v.game_id DESC))[1] AS team,
            v.opp AS opponent,
            count(v.val)::int AS games,
            (array_agg(v.val       ORDER BY v.game_date DESC, v.game_id DESC)
                 FILTER (WHERE v.val IS NOT NULL)) AS "values",
            (array_agg(v.game_date ORDER BY v.game_date DESC, v.game_id DESC)
                 FILTER (WHERE v.val IS NOT NULL)) AS dates
        FROM vals v
        GROUP BY v.player_id, v.opp
        HAVING count(v.val) > 0;
    $body$
  $f$;

  -- Default privileges hand anon ALL on anything new; REVOKE FROM PUBLIC alone
  -- does nothing, so the roles are named.
  REVOKE ALL ON FUNCTION public.player_window_totals_ncaabw(integer, integer) FROM PUBLIC, anon, authenticated;
  REVOKE ALL ON FUNCTION public.player_recent_games_ncaabw(integer, integer, text[]) FROM PUBLIC, anon, authenticated;
  REVOKE ALL ON FUNCTION public.player_season_stat_values_ncaabw(integer, text) FROM PUBLIC, anon, authenticated;
  REVOKE ALL ON FUNCTION public.player_h2h_stat_values_ncaabw(integer[], text, text[], text[]) FROM PUBLIC, anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.player_window_totals_ncaabw(integer, integer) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.player_recent_games_ncaabw(integer, integer, text[]) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.player_season_stat_values_ncaabw(integer, text) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_ncaabw(integer[], text, text[], text[]) TO anon, authenticated;
END $$;
