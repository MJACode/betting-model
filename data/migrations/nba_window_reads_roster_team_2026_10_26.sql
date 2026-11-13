-- NBA last-N reads: a player who has not played yet this season is listed
-- under his CURRENT roster team (Matt, 2026-10-26). Supersedes
-- nba_window_reads_span_seasons_2026_10_23.sql, which this replaces in
-- ACTIVE_MIGRATIONS (it is deleted, so the two never fight on a pass).
--
-- WHY. The 10-23 fix made a last-N window span into last season, and to keep
-- a summer trade off his OLD team it listed only players with a game THIS
-- season. Measured 2026-10-25: that hid 243 players from L3-L20, 146 of them
-- on a current roster (injured, not yet used), and on opening night every
-- year the board would be empty. Matt chose option (a): bring them back,
-- with the team from ESPN's roster feed.
--
-- THE TEAM, IN ORDER:
--   1. newest game is THIS season -> that game's team (the log is the truth
--      once he has played);
--   2. otherwise, his team in `player_positions`, if that row was seen on an
--      ESPN roster in the last 3 days (`roster_seen_at`, stamped each morning
--      by the roster job with his current team — so a waived or retired
--      player drops off and a trade shows the next morning; 3 days rides out
--      two failed mornings);
--   3. neither -> not listed (retired, unsigned).
-- It is written on the rn = 1 row, which is the row the board takes a
-- player's team from (StatsScreen groups by player, head = games[0]).
-- Older rows keep the team that game was played for.
--
-- ESPN codes six teams differently from our logs; mapped here. Measured
-- 2026-10-26: GS, NO, NY, SA, UTAH, WSH -> GSW, NOP, NYK, SAS, UTA, WAS. The
-- other 24 match.
--
-- p_teams narrows on the RESOLVED team, so a slate board admits exactly the
-- players it would show. Same signatures: CREATE OR REPLACE, grants kept.
-- Guarded on the property (the body reads roster_seen_at), so it fires once.

DO $mig$
BEGIN
    -- The roster stamp (2026-10-27, Matt). player_positions_ingestor writes it
    -- each morning on every athlete listed on a roster, with his current team.
    -- Before it existed a player off every roster kept his row forever, and a
    -- traded player kept his old team until his 7-13 day position refresh.
    -- Guarded on the column; it must exist before the functions below, which
    -- are validated against it at CREATE.
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = 'player_positions'
           AND column_name = 'roster_seen_at') THEN
        ALTER TABLE public.player_positions ADD COLUMN roster_seen_at TIMESTAMPTZ;
    END IF;

    IF (SELECT count(*)
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'public'
           AND p.proname IN ('player_recent_games_nba', 'player_window_totals_nba')
           AND position('p_season - 1' in pg_get_functiondef(p.oid)) > 0
           AND position('roster_seen_at' in pg_get_functiondef(p.oid)) > 0) >= 2 THEN
        RAISE NOTICE 'NBA window reads already resolve the roster team — skipping';
        RETURN;
    END IF;

    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_recent_games_nba(
        p_season integer, p_window integer DEFAULT 10, p_teams text[] DEFAULT NULL)
    RETURNS TABLE(player_id text, player_name text, team text, game_id text,
                  game_date text, season integer, rn integer, minutes numeric,
                  points integer, rebounds integer, assists integer, threes integer,
                  steals integer, blocks integer, turnovers integer, pra integer)
    LANGUAGE sql STABLE SET search_path TO 'public', 'pg_temp'
    AS $fn$
        WITH ranked AS (
            SELECT n.*,
                   ROW_NUMBER() OVER (PARTITION BY n.player_id
                                      ORDER BY n.game_date DESC, n.game_id DESC) AS rn
            FROM nba_player_game_log n
            WHERE n.season IN (p_season, p_season - 1)
        ),
        roster AS (
            SELECT pp.player_id,
                   CASE pp.team WHEN 'GS' THEN 'GSW' WHEN 'NO' THEN 'NOP'
                                WHEN 'NY' THEN 'NYK' WHEN 'SA' THEN 'SAS'
                                WHEN 'UTAH' THEN 'UTA' WHEN 'WSH' THEN 'WAS'
                                ELSE pp.team END AS team
            FROM player_positions pp
            WHERE pp.sport = 'NBA'
              AND pp.roster_seen_at >= now() - interval '3 days'
        ),
        keep AS (
            SELECT r.player_id,
                   CASE WHEN r.season = p_season THEN r.team ELSE ro.team END AS cur_team
            FROM ranked r
            LEFT JOIN roster ro ON ro.player_id = r.player_id
            WHERE r.rn = 1 AND (r.season = p_season OR ro.team IS NOT NULL)
        )
        SELECT
            r.player_id, r.player_name,
            CASE WHEN r.rn = 1 THEN k.cur_team ELSE r.team END AS team,
            r.game_id, r.game_date, r.season,
            r.rn::int, r.minutes, r.points, r.rebounds, r.assists,
            r.fg3_made AS threes, r.steals, r.blocks, r.turnovers,
            (COALESCE(r.points,0) + COALESCE(r.rebounds,0) + COALESCE(r.assists,0))::int AS pra
        FROM ranked r
        JOIN keep k ON k.player_id = r.player_id
        WHERE r.rn <= LEAST(COALESCE(p_window, 10), 25)
          AND (p_teams IS NULL OR k.cur_team = ANY(p_teams))
        ORDER BY r.player_id, r.rn;
    $fn$
    $ddl$;

    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_window_totals_nba(
        p_season integer, p_window integer DEFAULT NULL)
    RETURNS TABLE(player_id text, player_name text, season integer, team text,
                  games_played bigint, minutes numeric, points bigint, rebounds bigint,
                  assists bigint, threes bigint, steals bigint, blocks bigint,
                  turnovers bigint, pra bigint)
    LANGUAGE sql STABLE SET search_path TO 'public', 'pg_temp'
    AS $fn$
        WITH ranked AS (
            SELECT n.*,
                   ROW_NUMBER() OVER (PARTITION BY n.player_id
                                      ORDER BY n.game_date DESC, n.game_id DESC) AS rn
            FROM nba_player_game_log n
            WHERE n.season = p_season
               OR (p_window IS NOT NULL AND n.season = p_season - 1)
        ),
        roster AS (
            SELECT pp.player_id,
                   CASE pp.team WHEN 'GS' THEN 'GSW' WHEN 'NO' THEN 'NOP'
                                WHEN 'NY' THEN 'NYK' WHEN 'SA' THEN 'SAS'
                                WHEN 'UTAH' THEN 'UTA' WHEN 'WSH' THEN 'WAS'
                                ELSE pp.team END AS team
            FROM player_positions pp
            WHERE pp.sport = 'NBA'
              AND pp.roster_seen_at >= now() - interval '3 days'
        ),
        agg AS (
            SELECT
                player_id,
                (array_agg(player_name ORDER BY game_date DESC))[1] AS player_name,
                (array_agg(team ORDER BY game_date DESC))[1] AS last_team,
                bool_or(season = p_season) AS played_this_season,
                COUNT(DISTINCT game_id) AS games_played,
                COALESCE(SUM(minutes),0) AS minutes, COALESCE(SUM(points),0) AS points,
                COALESCE(SUM(rebounds),0) AS rebounds, COALESCE(SUM(assists),0) AS assists,
                COALESCE(SUM(fg3_made),0) AS threes, COALESCE(SUM(steals),0) AS steals,
                COALESCE(SUM(blocks),0) AS blocks, COALESCE(SUM(turnovers),0) AS turnovers,
                COALESCE(SUM(COALESCE(points,0)+COALESCE(rebounds,0)+COALESCE(assists,0)),0) AS pra
            FROM ranked
            WHERE p_window IS NULL OR rn <= p_window
            GROUP BY player_id
        )
        SELECT a.player_id, a.player_name, p_season AS season,
               CASE WHEN a.played_this_season THEN a.last_team ELSE ro.team END AS team,
               a.games_played, a.minutes, a.points, a.rebounds, a.assists, a.threes,
               a.steals, a.blocks, a.turnovers, a.pra
        FROM agg a
        LEFT JOIN roster ro ON ro.player_id = a.player_id
        WHERE a.played_this_season OR ro.team IS NOT NULL;
    $fn$
    $ddl$;
END
$mig$;
