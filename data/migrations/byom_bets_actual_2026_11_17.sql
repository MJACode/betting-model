-- Build Your Own Model: the bet list carries what actually happened.
--
-- 2026-11-17 (Matt): "we should definitely show actual on the win or
-- loss". A row read "Jordan Mason Over 0.5 · Won" with no number, so a
-- 0.5 receiving-yards line looked like a bug. byom_bets gains three
-- columns:
--
--   actual      a prop's stat (byom_prop_facts.actual, log_status
--               'logged'). One value per game, market and player: measured
--               2026-11-17, 474,468 (canonical_key, market, player_name)
--               groups, 0 with two different actuals.
--   home_score  the final score (byom_game_facts, one row per
--   away_score  canonical_key: 91,044 rows, 91,044 keys).
--
-- The 500 counted rows are chosen exactly as before (same filter, order
-- and LIMIT), then joined. A row with no stored actual returns NULL.
--
-- The return type changes, so the function is dropped and re-created,
-- and EXECUTE is granted again to the same roles it held (anon,
-- authenticated, service_role). The body keeps byom_official_legs_v1, so
-- byom_official_legs_2026_11_04.sql still counts five marked functions
-- and skips. Skips once byom_bets carries byom_bets_actual_v1.
-- Reads facts only. Does not write picks.

DO $mig$
BEGIN
  IF EXISTS (
       SELECT 1 FROM pg_proc p
        WHERE p.oid = to_regprocedure('public.byom_bets(integer, jsonb, text)')
          AND position('byom_bets_actual_v1' in p.prosrc) > 0)
  THEN
    RAISE NOTICE 'byom_bets actual already present - skipping';
    RETURN;
  END IF;

  DROP FUNCTION IF EXISTS public.byom_bets(integer, jsonb, text);

  EXECUTE $fn$
  CREATE FUNCTION public.byom_bets(
    p_season integer,
    p_filters jsonb DEFAULT '{}'::jsonb,
    p_timing text DEFAULT 'official'
  )
  RETURNS TABLE (
    canonical_key text, commence_time timestamptz, market text,
    leg_side text, label text, home_team text, away_team text,
    player_name text, point numeric, price numeric, result text,
    units numeric, locked_at timestamptz, total_bets bigint,
    actual numeric, home_score numeric, away_score numeric
  )
  LANGUAGE sql
  STABLE
  SECURITY INVOKER
  SET search_path = public, pg_temp
  AS $body$
    -- byom_official_legs_v1
    -- byom_bets_actual_v1
    -- Only the counted bets: graded and priced. Newest first. At most
    -- 500 rows; total_bets is the full count, so a screen can say so.
    -- actual is the prop's stat; home/away_score the final score.
    WITH b AS (
      SELECT l.canonical_key, l.commence_time, l.market, l.leg_side,
             byom_leg_label(l.market, l.leg_side, l.team, l.point,
                            l.player_name) AS label,
             l.home_team, l.away_team, l.player_name, l.point, l.price,
             l.result, l.units, l.locked_at, count(*) OVER () AS total_bets
        FROM byom_legs(p_season, p_filters, COALESCE(p_timing, 'official')) l
       WHERE l.units IS NOT NULL
       ORDER BY l.commence_time DESC NULLS LAST, l.canonical_key, l.market,
                l.player_name NULLS FIRST, l.leg_side
       LIMIT 500
    )
    SELECT b.canonical_key, b.commence_time, b.market, b.leg_side, b.label,
           b.home_team, b.away_team, b.player_name, b.point, b.price,
           b.result, b.units, b.locked_at, b.total_bets,
           pf.actual, g.home_score::numeric, g.away_score::numeric
      FROM b
      LEFT JOIN byom_game_facts g ON g.canonical_key = b.canonical_key
      LEFT JOIN LATERAL (
        SELECT p.actual
          FROM byom_prop_facts p
         WHERE b.player_name IS NOT NULL
           AND p.canonical_key = b.canonical_key
           AND p.market = b.market
           AND p.player_name = b.player_name
           AND p.log_status = 'logged'
           AND p.actual IS NOT NULL
         LIMIT 1
      ) pf ON true
     ORDER BY b.commence_time DESC NULLS LAST, b.canonical_key, b.market,
              b.player_name NULLS FIRST, b.leg_side
  $body$;
  $fn$;

  REVOKE ALL ON FUNCTION public.byom_bets(integer, jsonb, text) FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION public.byom_bets(integer, jsonb, text)
    TO authenticated;
  IF to_regclass('public.picks') IS NULL
     OR has_table_privilege('anon', 'public.picks', 'SELECT') THEN
    GRANT EXECUTE ON FUNCTION public.byom_bets(integer, jsonb, text)
      TO anon;
  END IF;
  -- service_role exists on Supabase, not on a scratch database.
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    GRANT EXECUTE ON FUNCTION public.byom_bets(integer, jsonb, text)
      TO service_role;
  END IF;
END
$mig$;
