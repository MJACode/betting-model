-- Migration: add_player_h2h_stat_values_rpcs
--
-- Backs the Stats tab's H2H window (Matt, 2026-09-20: "I want to add the
-- ability to show how a player or team has done against an opponent … the last
-- 2 years"). One row per player on the slate, carrying that player's per-game
-- values for ONE stat IN THE MEETINGS WITH THE TEAM HE IS ABOUT TO PLAY, over
-- the seasons the caller names (the app names two: this season and last).
--
-- SAME SHAPE AS player_season_stat_values_* ON PURPOSE. The board's Season
-- window already renders a `values numeric[]` per player and computes the hit
-- rate for any line client-side (add_player_season_stat_values_rpcs.sql), so
-- H2H reuses that branch whole rather than adding a second rendering path.
-- `dates` is the one addition — the player page lists the meetings themselves,
-- and a list of numbers with no dates cannot say WHEN he did it. `dates` and
-- `values` carry the SAME filter (val IS NOT NULL) so index i of one is index
-- i of the other; filtering only one would silently pair a value with another
-- game's date.
--
-- WHY A MATCHUP LIST AND NOT A TEAM LIST. H2H is a question about a PAIR, and
-- the pair is decided by the fixture: the caller already knows that IND play
-- KC, so it sends that pair and gets back only IND players' games against KC.
-- Reading "every slate team's players against every slate opponent" instead
-- would be the cross product — measured on the 2026-09-20 NFL slate, 30 games:
-- 3,724 players on the slate, 1,406 (player, opponent) rows once paired, and
-- roughly 32x that unpaired.
--
-- TWO PARALLEL ARRAYS, NOT 'TEAM|OPP' STRINGS. An NCAAF team id is a school
-- NAME (CLAUDE.md §4), so any separator is a character that can occur inside a
-- key; `unnest(...) WITH ORDINALITY` pairs them positionally and cannot be
-- confused by one.
--
-- THE PLAYER'S LATEST TEAM DECIDES HIS FIXTURE; HIS WHOLE HISTORY ANSWERS IT.
-- A player is matched to a pair by the team he most recently played for inside
-- the season window, and then EVERY meeting with that opponent counts — games
-- played for a previous team included. "How has he done against KC" is a
-- question about the player, not about the jersey he wore in 2025.
--
-- MLB / NBA / WNBA CARRY NO OPPONENT COLUMN, so theirs is derived by joining
-- `games` on game_id (measured 2026-09-20: every distinct (game_id) on each of
-- the three logs for seasons 2025-2026 joins — MLB 7,852/7,852, NBA 4,900/4,900,
-- WNBA 1,198/1,198). NFL and NCAAF store `opponent` on the log row itself.
--
-- security_invoker + anon GRANTs, matching player_season_stat_values_*. NOTE:
-- "values" is a reserved word, hence the quoted column name — PostgREST still
-- serializes the JSON key as `values`.

-- ONE `DO` BLOCK, GUARDED ON THE PROPERTY IT ESTABLISHES. data/view_migrations
-- executes this file with conn.execute() on every refresh pass, which shreds a
-- multi-statement file at its semicolons — so everything is one statement, and
-- the function bodies are re-tagged $fn$ because $$ cannot nest inside $mig$.
--
-- The guard is not politeness: every DDL statement fires Supabase's
-- `pgrst_ddl_watch`, and PostgREST answers 503 to the WHOLE APP while it
-- rebuilds its schema cache. On 2026-09-01 that is exactly how the Stats tab
-- went dark for every sport (tests/test_ddl_guard.py). This file runs ~54 times
-- a day, so it must do its DDL once and skip silently forever after.
--
-- Grants are issued here as well as by scripts/apply_anon_grants.py, and PUBLIC
-- is revoked FIRST: Postgres grants EXECUTE to PUBLIC on a new function and anon
-- is a member, so a named grant alone leaves a wider surface than intended, and
-- ALTER DEFAULT PRIVILEGES ... REVOKE ALL ON FUNCTIONS means a new function
-- otherwise arrives callable by nobody at all.

DO $mig$
BEGIN
    IF (SELECT count(*)
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'public'
           AND p.proname LIKE 'player_h2h_stat_values_%') >= 5 THEN
        RAISE NOTICE 'player_h2h_stat_values_* already present — skipping';
        RETURN;
    END IF;

    -- ── MLB ──────────────────────────────────────────────────────────────────────
    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_h2h_stat_values_mlb(
    p_seasons integer[],
    p_player_type text,
    p_stat text,
    p_teams text[],
    p_opponents text[]
    )
    RETURNS TABLE (
    player_id text, player_name text, team text, player_type text,
    opponent text, games integer, "values" numeric[], dates text[]
    )
    LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
    WITH pairs AS (
        SELECT DISTINCT t.team, o.opp
        FROM unnest(p_teams)     WITH ORDINALITY AS t(team, i)
        JOIN unnest(p_opponents) WITH ORDINALITY AS o(opp, i) USING (i)
    ),
    latest AS (
        SELECT DISTINCT ON (pgl.player_id, pgl.player_type)
               pgl.player_id, pgl.player_name, pgl.team, pgl.player_type
        FROM player_game_log pgl
        WHERE pgl.season = ANY(p_seasons) AND pgl.player_type = p_player_type
        ORDER BY pgl.player_id, pgl.player_type, pgl.game_date DESC, pgl.game_id DESC
    ),
    sel AS (
        SELECT l.player_id, l.player_name, l.team, l.player_type, p.opp
        FROM latest l JOIN pairs p ON p.team = l.team
    ),
    vals AS (
        SELECT s.player_id, s.player_name, s.team, s.player_type, s.opp,
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
        FROM sel s
        JOIN player_game_log pgl
          ON pgl.player_id = s.player_id
         AND pgl.player_type = s.player_type
         AND pgl.season = ANY(p_seasons)
        JOIN games g
          ON g.game_id = pgl.game_id AND g.sport = 'MLB'
         AND CASE WHEN g.home_team = pgl.team THEN g.away_team ELSE g.home_team END = s.opp
    )
    SELECT
        v.player_id,
        (array_agg(v.player_name  ORDER BY v.game_date DESC, v.game_id DESC))[1] AS player_name,
        (array_agg(v.team         ORDER BY v.game_date DESC, v.game_id DESC))[1] AS team,
        (array_agg(v.player_type  ORDER BY v.game_date DESC, v.game_id DESC))[1] AS player_type,
        v.opp AS opponent,
        count(v.val)::int AS games,
        (array_agg(v.val       ORDER BY v.game_date DESC, v.game_id DESC)
             FILTER (WHERE v.val IS NOT NULL)) AS "values",
        (array_agg(v.game_date ORDER BY v.game_date DESC, v.game_id DESC)
             FILTER (WHERE v.val IS NOT NULL)) AS dates
    FROM vals v
    GROUP BY v.player_id, v.opp
    HAVING count(v.val) > 0;
    $fn$
    $ddl$;

    -- ── WNBA ─────────────────────────────────────────────────────────────────────
    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_h2h_stat_values_wnba(
    p_seasons integer[],
    p_stat text,
    p_teams text[],
    p_opponents text[]
    )
    RETURNS TABLE (
    player_id text, player_name text, team text,
    opponent text, games integer, "values" numeric[], dates text[]
    )
    LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
    WITH pairs AS (
        SELECT DISTINCT t.team, o.opp
        FROM unnest(p_teams)     WITH ORDINALITY AS t(team, i)
        JOIN unnest(p_opponents) WITH ORDINALITY AS o(opp, i) USING (i)
    ),
    latest AS (
        SELECT DISTINCT ON (w.player_id) w.player_id, w.player_name, w.team
        FROM wnba_player_game_log w
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
        JOIN wnba_player_game_log w
          ON w.player_id = s.player_id AND w.season = ANY(p_seasons)
        JOIN games g
          ON g.game_id = w.game_id AND g.sport = 'WNBA'
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
    $fn$
    $ddl$;

    -- ── NBA ──────────────────────────────────────────────────────────────────────
    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_h2h_stat_values_nba(
    p_seasons integer[],
    p_stat text,
    p_teams text[],
    p_opponents text[]
    )
    RETURNS TABLE (
    player_id text, player_name text, team text,
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
        FROM nba_player_game_log n
        WHERE n.season = ANY(p_seasons)
        ORDER BY n.player_id, n.game_date DESC, n.game_id DESC
    ),
    sel AS (
        SELECT l.player_id, l.player_name, l.team, p.opp
        FROM latest l JOIN pairs p ON p.team = l.team
    ),
    vals AS (
        SELECT s.player_id, s.player_name, s.team, s.opp, n.game_date, n.game_id,
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
        FROM sel s
        JOIN nba_player_game_log n
          ON n.player_id = s.player_id AND n.season = ANY(p_seasons)
        JOIN games g
          ON g.game_id = n.game_id AND g.sport = 'NBA'
         AND CASE WHEN g.home_team = n.team THEN g.away_team ELSE g.home_team END = s.opp
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
    $fn$
    $ddl$;

    -- ── NFL ──────────────────────────────────────────────────────────────────────
    -- `opponent` is stored on the log row, so no join to `games` is needed.
    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_h2h_stat_values_nfl(
    p_seasons integer[],
    p_stat text,
    p_teams text[],
    p_opponents text[]
    )
    RETURNS TABLE (
    player_id text, player_name text, team text,
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
        SELECT s.player_id, s.player_name, s.team, s.opp, n.game_date, n.game_id,
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
        v.opp AS opponent,
        count(v.val)::int AS games,
        (array_agg(v.val       ORDER BY v.game_date DESC, v.game_id DESC)
             FILTER (WHERE v.val IS NOT NULL)) AS "values",
        (array_agg(v.game_date ORDER BY v.game_date DESC, v.game_id DESC)
             FILTER (WHERE v.val IS NOT NULL)) AS dates
    FROM vals v
    GROUP BY v.player_id, v.opp
    HAVING count(v.val) > 0;
    $fn$
    $ddl$;

    -- ── NCAAF ────────────────────────────────────────────────────────────────────
    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.player_h2h_stat_values_ncaaf(
    p_seasons integer[],
    p_stat text,
    p_teams text[],
    p_opponents text[]
    )
    RETURNS TABLE (
    player_id text, player_name text, team text,
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
        FROM ncaaf_player_game_log n
        WHERE n.season = ANY(p_seasons)
        ORDER BY n.player_id, n.game_date DESC, n.game_id DESC
    ),
    sel AS (
        SELECT l.player_id, l.player_name, l.team, p.opp
        FROM latest l JOIN pairs p ON p.team = l.team
    ),
    vals AS (
        SELECT s.player_id, s.player_name, s.team, s.opp, n.game_date, n.game_id,
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
                   WHEN 'def_tackles'       THEN n.def_tackles::numeric
                   WHEN 'def_solo'          THEN n.def_solo::numeric
                   WHEN 'def_sacks'         THEN n.def_sacks::numeric
                   WHEN 'def_tfl'           THEN n.def_tfl::numeric
                   WHEN 'def_pd'            THEN n.def_pd::numeric
                   WHEN 'def_interceptions' THEN n.def_interceptions::numeric
                   ELSE NULL
               END AS val
        FROM sel s
        JOIN ncaaf_player_game_log n
          ON n.player_id = s.player_id
         AND n.opponent = s.opp
         AND n.season = ANY(p_seasons)
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
    $fn$
    $ddl$;

    EXECUTE 'REVOKE ALL ON FUNCTION public.player_h2h_stat_values_mlb(integer[], text, text, text[], text[]) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_mlb(integer[], text, text, text[], text[]) TO anon, authenticated';
    EXECUTE 'REVOKE ALL ON FUNCTION public.player_h2h_stat_values_wnba(integer[], text, text[], text[]) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_wnba(integer[], text, text[], text[]) TO anon, authenticated';
    EXECUTE 'REVOKE ALL ON FUNCTION public.player_h2h_stat_values_nba(integer[], text, text[], text[]) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_nba(integer[], text, text[], text[]) TO anon, authenticated';
    EXECUTE 'REVOKE ALL ON FUNCTION public.player_h2h_stat_values_nfl(integer[], text, text[], text[]) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_nfl(integer[], text, text[], text[]) TO anon, authenticated';
    EXECUTE 'REVOKE ALL ON FUNCTION public.player_h2h_stat_values_ncaaf(integer[], text, text[], text[]) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_ncaaf(integer[], text, text[], text[]) TO anon, authenticated';

    RAISE NOTICE 'player_h2h_stat_values_* created for MLB, WNBA, NBA, NFL, NCAAF';
END
$mig$;
