-- Migration: add_position_vs_opponent_nfl
--
-- Backs the player page's "WRs vs ATL" card (Matt, 2026-10-05: "When you click
-- into a user stat. We should show how other players at the same position have
-- done against that team"). Phase 1 of 3: NFL only, because nfl_player_game_log
-- is the one log carrying BOTH `pos` and `opponent` on every row (measured
-- 2026-10-03: 0 NULL pos, 0 NULL opponent across seasons 2024-2026). MLB
-- (lineup spot / starter) and NBA, WNBA, NCAAF (need a position ingest) follow.
--
-- ONE ROW PER QUALIFYING PLAYER-GAME AGAINST `p_opponent`, each carrying the
-- defence's league standing for that season on the same row. The card lists
-- the games (player name, date, value), computes the hit rate at the page's
-- line client-side (so a line change never refetches), and prints the rank.
-- Repeating three numbers on ~50 rows is cheaper than a second round trip.
--
-- "REAL ROLE ONLY" (Matt, 2026-10-05). A player-game counts only when the
-- player had a meaningful share of the work, so a WR5's 0 yards on one target
-- does not read as a "miss" for the defence:
--   QB  attempts >= 10       RB  carries + targets >= 6
--   WR  targets  >= 3        TE  targets >= 2
--   DL / LB / DB  solo + assisted tackles + sacks + QB hits >= 2
-- The same cut feeds the rank, so the list and the rank describe one
-- population. Measured 2026-10-05, WR receiving_yards vs ATL: 10 player-games
-- in 2026 (avg 60.4, 9th most allowed of 32), 45 in 2025 (avg 48.3, 16th).
--
-- RANK 1 = ALLOWS THE MOST per qualifying player-game. That is the bettor's
-- reading of a "good matchup" for an over; the card says it in words.
--
-- SAME DDL DISCIPLINE AS add_player_h2h_stat_values_rpcs.sql: one DO block,
-- guarded on the function existing, because data/view_migrations runs this on
-- every refresh pass and each DDL statement makes PostgREST 503 the app while
-- it reloads (tests/test_ddl_guard.py). PUBLIC revoked before the named grant.

DO $mig$
BEGIN
    IF EXISTS (SELECT 1
                 FROM pg_proc p
                 JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public'
                  AND p.proname = 'position_vs_opponent_nfl') THEN
        RAISE NOTICE 'position_vs_opponent_nfl already present — skipping';
        RETURN;
    END IF;

    EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.position_vs_opponent_nfl(
    p_seasons integer[],
    p_stat text,
    p_pos_group text,
    p_opponent text
    )
    RETURNS TABLE (
    season integer, player_id text, player_name text, team text, pos text,
    game_id text, game_date text, week integer, value numeric,
    avg_allowed numeric, player_games integer,
    rank_most_allowed integer, teams_ranked integer
    )
    LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
    WITH grp AS (
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
        SELECT * FROM role WHERE has_role AND val IS NOT NULL
    ),
    defense AS (
        SELECT q.season, q.opponent AS defense,
               avg(q.val) AS avg_allowed,
               count(*)::int AS player_games
        FROM q
        GROUP BY q.season, q.opponent
    ),
    ranked AS (
        SELECT d.*,
               rank() OVER (PARTITION BY d.season ORDER BY d.avg_allowed DESC)::int AS rank_most_allowed,
               count(*) OVER (PARTITION BY d.season)::int AS teams_ranked
        FROM defense d
    )
    SELECT q.season::int, q.player_id::text, q.player_name::text, q.team::text, q.pos::text,
           q.game_id::text, q.game_date::text, q.week::int, q.val,
           round(r.avg_allowed, 2), r.player_games, r.rank_most_allowed, r.teams_ranked
    FROM q
    JOIN ranked r ON r.season = q.season AND r.defense = q.opponent
    WHERE q.opponent = p_opponent
    $fn$
    $ddl$;

    EXECUTE 'REVOKE ALL ON FUNCTION public.position_vs_opponent_nfl(integer[], text, text, text) FROM PUBLIC';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.position_vs_opponent_nfl(integer[], text, text, text) TO anon, authenticated';

    RAISE NOTICE 'position_vs_opponent_nfl created';
END
$mig$;
