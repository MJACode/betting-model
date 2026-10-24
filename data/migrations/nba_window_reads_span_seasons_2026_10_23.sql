-- NBA last-N reads reach back into the previous season (Matt, 2026-10-23).
--
-- WHY. The Stats board showed Jaylen Brown on BOS a week into 2026-27 — he was
-- traded to PHI in July. The app asked for season 2026 (the calendar year),
-- which for the NBA is LAST season (season = ending year, CLAUDE.md §4). The
-- app now asks for 2027. But two games into a season a 2027-only L10 reads
-- "2/2", so Matt chose: a last-N window spans seasons — the newest N games,
-- reaching into the previous season when this one is short. Team is still the
-- newest game's team (rn = 1), so a traded player shows his new team.
--
-- WHO IS LISTED. Only players with a game THIS season (rn = 1 is in
-- p_season). A player traded in the summer who has not debuted would
-- otherwise show under his OLD team — the bug this fixes — and retired players
-- would return. Same population as the Season chip.
--
-- SCOPE. Only the WINDOWED reads. `player_window_totals_nba` with
-- p_window NULL (the Season chip, the touch set) stays this season only.
--
-- Same signatures, so CREATE OR REPLACE: no overload, grants kept.
--
-- GUARDED ON THE PROPERTY (the body reads p_season - 1), so it fires once.
-- This file runs on every refresh pass and each DDL forces a PostgREST
-- schema reload.

DO $mig$
BEGIN
    IF (SELECT count(*)
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'public'
           AND p.proname IN ('player_recent_games_nba', 'player_window_totals_nba')
           AND position('p_season - 1' in pg_get_functiondef(p.oid)) > 0) >= 2 THEN
        RAISE NOTICE 'NBA window reads already span seasons — skipping';
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
        keep AS (
            SELECT r.player_id FROM ranked r
            WHERE r.rn = 1 AND r.season = p_season
              AND (p_teams IS NULL OR r.team = ANY(p_teams))
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
        GROUP BY player_id
        HAVING bool_or(season = p_season);
    $fn$
    $ddl$;
END
$mig$;
