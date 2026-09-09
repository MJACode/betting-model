-- player_recent_games_*: filter by the player's CURRENT team, server-side.
--
-- WHY THIS EXISTS. The Stats board's last-N read is over the row cap in every
-- sport (54,687 rows for NCAAF, 12,850 for the NFL against a silent 1,000-row
-- max-rows), so the board drew an arbitrary first 1,000 and the NFL slate — six
-- of tonight's 110 players, none a quarterback — rendered empty. Paging drains
-- the cap; narrowing to the slate's teams is what keeps the paged read from
-- being 55 round trips and 25 MB onto a phone.
--
-- AND WHY IT IS A PARAMETER RATHER THAN A CLIENT FILTER. These functions return
-- one row PER GAME, each carrying the team the player played that game FOR, so
-- `.in('team', …)` on the request filters GAMES where the board filters PLAYERS
-- (StatsScreen groups by player_id and takes the rn=1 row's team). The two
-- disagree for exactly the traded population, in both directions, and measured
-- on tonight's SEA-NE slate that is 5 players whose last-10 window would be
-- silently cut to only the games played for tonight's team, and 5 more who have
-- LEFT those teams and would appear on the board as though they were on it.
-- Neither is visible on screen: the row prints "3 of 5" under an L10 chip.
--
-- So the filter belongs where the ranking already is — on rn = 1, the same row
-- the client groups to. `player_window_totals_*` and `player_season_stat_values_*`
-- need no change: both already emit one row per player with
-- team = (array_agg(team ORDER BY game_date DESC))[1], which IS the rn=1 team.
--
-- DROP-then-CREATE, not CREATE OR REPLACE, because the added parameter makes a
-- NEW function rather than replacing the old one — and two overloads is worse
-- than either: a call carrying exactly {p_season, p_window} matches the 2-arg
-- form exactly AND the 3-arg form by default, which PostgREST answers with 300
-- Multiple Choices. That would break every app build already in the field. One
-- DO block so the drop and the create are atomic, and old builds resolve to the
-- new function through the default.
--
-- GUARDED ON THE PROPERTY IT ESTABLISHES (all five functions carry p_teams), not
-- on the shape of its own output, and it must skip after the first pass: every
-- DDL statement fires Supabase's pgrst_ddl_watch and answers 503 to the whole
-- app while PostgREST rebuilds its schema cache, and this file is executed on
-- all ~54 refresh passes a day.
--
-- Grants are re-issued because DROP takes them with it and
-- ALTER DEFAULT PRIVILEGES ... REVOKE ALL ON FUNCTIONS (scripts/apply_anon_grants.py)
-- means the recreated function arrives callable by nobody. PUBLIC off first,
-- then the two named grants — the end state that script maintains.

DO $mig$
BEGIN
    IF (SELECT count(*)
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'public'
           AND p.proname LIKE 'player_recent_games_%'
           AND pg_get_function_arguments(p.oid) LIKE '%p_teams%') >= 5 THEN
        RAISE NOTICE 'player_recent_games_* already take p_teams — skipping';
        RETURN;
    END IF;

    -- ── MLB ──────────────────────────────────────────────────────────────────
    EXECUTE 'DROP FUNCTION IF EXISTS public.player_recent_games_mlb(integer, text, integer)';
    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_recent_games_mlb(
        p_season integer, p_player_type text, p_window integer DEFAULT 10,
        p_teams text[] DEFAULT NULL)
    RETURNS TABLE(player_id text, player_name text, team text, player_type text,
                  game_id text, game_date text, season integer, rn integer,
                  at_bats integer, hits integer, doubles integer, triples integer,
                  home_runs integer, total_bases integer, rbi integer, runs integer,
                  walks integer, strikeouts integer, stolen_bases integer,
                  p_strikeouts integer, p_walks integer, p_hits_allowed integer,
                  p_earned_runs integer, p_home_runs integer,
                  innings_pitched numeric, pitches integer)
    LANGUAGE sql STABLE SET search_path TO 'public', 'pg_temp'
    AS $fn$
        WITH ranked AS (
            SELECT pgl.*,
                   ROW_NUMBER() OVER (PARTITION BY pgl.player_id
                                      ORDER BY pgl.game_date DESC, pgl.game_id DESC) AS rn
            FROM player_game_log pgl
            WHERE pgl.season = p_season AND pgl.player_type = p_player_type
        ),
        keep AS (
            SELECT r.player_id FROM ranked r
            WHERE r.rn = 1
              AND (p_teams IS NULL OR r.team = ANY(p_teams))
        )
        SELECT
            r.player_id, r.player_name, r.team, r.player_type, r.game_id, r.game_date,
            r.season, r.rn::int,
            r.at_bats, r.hits, r.doubles, r.triples, r.home_runs, r.total_bases,
            r.rbi, r.runs, r.walks, r.strikeouts, r.stolen_bases, r.p_strikeouts,
            r.p_walks, r.p_hits_allowed, r.p_earned_runs, r.p_home_runs,
            r.innings_pitched, r.pitches
        FROM ranked r
        JOIN keep k ON k.player_id = r.player_id
        WHERE r.rn <= LEAST(COALESCE(p_window, 10), 25)
        ORDER BY r.player_id, r.rn;
    $fn$
    $ddl$;

    -- ── NBA ──────────────────────────────────────────────────────────────────
    EXECUTE 'DROP FUNCTION IF EXISTS public.player_recent_games_nba(integer, integer)';
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
            WHERE n.season = p_season
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
    $fn$
    $ddl$;

    -- ── WNBA ─────────────────────────────────────────────────────────────────
    EXECUTE 'DROP FUNCTION IF EXISTS public.player_recent_games_wnba(integer, integer)';
    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_recent_games_wnba(
        p_season integer, p_window integer DEFAULT 10, p_teams text[] DEFAULT NULL)
    RETURNS TABLE(player_id text, player_name text, team text, game_id text,
                  game_date text, season integer, rn integer, minutes numeric,
                  points integer, rebounds integer, assists integer, threes integer,
                  steals integer, blocks integer, turnovers integer, pra integer)
    LANGUAGE sql STABLE SET search_path TO 'public', 'pg_temp'
    AS $fn$
        WITH ranked AS (
            SELECT w.*,
                   ROW_NUMBER() OVER (PARTITION BY w.player_id
                                      ORDER BY w.game_date DESC, w.game_id DESC) AS rn
            FROM wnba_player_game_log w
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
    $fn$
    $ddl$;

    -- ── NFL ──────────────────────────────────────────────────────────────────
    EXECUTE 'DROP FUNCTION IF EXISTS public.player_recent_games_nfl(integer, integer)';
    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_recent_games_nfl(
        p_season integer, p_window integer DEFAULT 10, p_teams text[] DEFAULT NULL)
    RETURNS TABLE(player_id text, player_name text, team text, pos text,
                  game_id text, game_date text, season integer, rn integer,
                  completions integer, attempts integer, passing_yards numeric,
                  passing_tds integer, interceptions integer, carries integer,
                  rushing_yards numeric, rushing_tds integer, receptions integer,
                  targets integer, receiving_yards numeric, receiving_tds integer,
                  rush_rec_tds integer, def_sacks numeric, def_interceptions integer)
    LANGUAGE sql STABLE SET search_path TO 'public', 'pg_temp'
    AS $fn$
        WITH ranked AS (
            SELECT n.*,
                   ROW_NUMBER() OVER (PARTITION BY n.player_id
                                      ORDER BY n.game_date DESC, n.game_id DESC) AS rn
            FROM nfl_player_game_log n
            WHERE n.season = p_season
        ),
        keep AS (
            SELECT r.player_id FROM ranked r
            WHERE r.rn = 1 AND (p_teams IS NULL OR r.team = ANY(p_teams))
        )
        SELECT
            r.player_id, r.player_name, r.team, r.pos, r.game_id, r.game_date,
            r.season, r.rn::int,
            r.completions, r.attempts, r.passing_yards, r.passing_tds,
            r.interceptions, r.carries, r.rushing_yards, r.rushing_tds,
            r.receptions, r.targets, r.receiving_yards, r.receiving_tds,
            (COALESCE(r.rushing_tds,0) + COALESCE(r.receiving_tds,0))::int AS rush_rec_tds,
            r.def_sacks, r.def_interceptions
        FROM ranked r
        JOIN keep k ON k.player_id = r.player_id
        WHERE r.rn <= LEAST(COALESCE(p_window, 10), 25)
        ORDER BY r.player_id, r.rn;
    $fn$
    $ddl$;

    -- ── NCAAF ────────────────────────────────────────────────────────────────
    EXECUTE 'DROP FUNCTION IF EXISTS public.player_recent_games_ncaaf(integer, integer)';
    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_recent_games_ncaaf(
        p_season integer, p_window integer DEFAULT 10, p_teams text[] DEFAULT NULL)
    RETURNS TABLE(player_id text, player_name text, team text, game_id text,
                  game_date text, season integer, week integer, opponent text,
                  rn integer, completions integer, attempts integer,
                  passing_yards integer, passing_tds integer, interceptions integer,
                  carries integer, rushing_yards integer, rushing_tds integer,
                  receptions integer, receiving_yards integer, receiving_tds integer,
                  rush_rec_tds integer, def_tackles numeric, def_solo numeric,
                  def_sacks numeric, def_tfl numeric, def_pd integer,
                  def_interceptions integer)
    LANGUAGE sql STABLE SET search_path TO 'public', 'pg_temp'
    AS $fn$
        WITH ranked AS (
            SELECT n.*,
                   ROW_NUMBER() OVER (PARTITION BY n.player_id
                                      ORDER BY n.game_date DESC, n.game_id DESC) AS rn
            FROM ncaaf_player_game_log n
            WHERE n.season = p_season
        ),
        keep AS (
            SELECT r.player_id FROM ranked r
            WHERE r.rn = 1 AND (p_teams IS NULL OR r.team = ANY(p_teams))
        )
        SELECT
            r.player_id, r.player_name, r.team, r.game_id, r.game_date, r.season,
            r.week, r.opponent, r.rn::int,
            r.completions, r.attempts, r.passing_yards, r.passing_tds,
            r.interceptions, r.carries, r.rushing_yards, r.rushing_tds,
            r.receptions, r.receiving_yards, r.receiving_tds,
            (COALESCE(r.rushing_tds,0) + COALESCE(r.receiving_tds,0))::int AS rush_rec_tds,
            r.def_tackles, r.def_solo, r.def_sacks, r.def_tfl, r.def_pd,
            r.def_interceptions
        FROM ranked r
        JOIN keep k ON k.player_id = r.player_id
        WHERE r.rn <= LEAST(COALESCE(p_window, 10), 25)
        ORDER BY r.player_id, r.rn;
    $fn$
    $ddl$;

    -- The grants DROP took with it. PUBLIC off first: Postgres grants EXECUTE
    -- to PUBLIC on a new function and anon is a member, so a named revoke alone
    -- leaves it callable and reports success (measured 2026-09-04).
        EXECUTE 'REVOKE ALL ON FUNCTION public.player_recent_games_mlb(integer, text, integer, text[]) FROM PUBLIC';
        EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_recent_games_mlb(integer, text, integer, text[]) TO anon, authenticated';
        EXECUTE 'REVOKE ALL ON FUNCTION public.player_recent_games_nba(integer, integer, text[]) FROM PUBLIC';
        EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_recent_games_nba(integer, integer, text[]) TO anon, authenticated';
        EXECUTE 'REVOKE ALL ON FUNCTION public.player_recent_games_wnba(integer, integer, text[]) FROM PUBLIC';
        EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_recent_games_wnba(integer, integer, text[]) TO anon, authenticated';
        EXECUTE 'REVOKE ALL ON FUNCTION public.player_recent_games_nfl(integer, integer, text[]) FROM PUBLIC';
        EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_recent_games_nfl(integer, integer, text[]) TO anon, authenticated';
        EXECUTE 'REVOKE ALL ON FUNCTION public.player_recent_games_ncaaf(integer, integer, text[]) FROM PUBLIC';
        EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_recent_games_ncaaf(integer, integer, text[]) TO anon, authenticated';

    RAISE NOTICE 'player_recent_games_* now take p_teams (filtered on the rn=1 team)';
END
$mig$;
