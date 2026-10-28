-- Prop legs in byom_backtest use the stored DraftKings prices.
--
-- Production already has byom_backtest with units and skipped:
--   byom_dk_start_price_2026_10_23     version 20261023131032
--   byom_dk_price_fallback_2026_10_23  version 20261023225630
-- byom_total_side_2026_10_25.sql labels total legs over and under.
-- Those files stay as applied. Do not edit them. Do not re-apply
-- them after this file: each one replaces this function.
--
-- This file is the total-side body, plus prop prices. A prop over
-- uses p.over_price. A prop under uses p.under_price. The price is
-- the American price on the same quote as the line. The exemption
-- that hard-coded NULL and treated a non-game market as priced is
-- gone. A graded prop side whose price is missing, fractional, or
-- under 100 in absolute value is left out of wins, losses, pushes,
-- ties, and units, and counted in skipped. A null prop result stays
-- out of the record and out of skipped. Staking is the same 1u to
-- win rule the game legs use.
--
-- Return columns stay market, bets, wins, losses, pushes, ties,
-- units, skipped. byom_backtest_v1 stays in the body, so the
-- registered byom_backtest_rpc_2026_10_16.sql still skips.
-- byom_dk_start_price, byom_dk_price_fallback, byom_total_side, and
-- byom_prop_dk_prices stay in the body too. This file does not
-- replace byom_save_model.
--
-- NOT in data/view_migrations.ACTIVE_MIGRATIONS. The worker re-runs
-- that list against production. Apply this file by hand, after
-- byom_prop_facts_dk_prices_2026_10_28.sql. It is idempotent:
-- CREATE OR REPLACE. It does not DROP the function. It does not
-- write picks.
--
-- Requires byom_game_facts, the DraftKings game price columns from
-- byom_dk_start_price_2026_10_23.sql, and over_price / under_price
-- on byom_prop_facts.
-- One DO block. No CONCURRENTLY.

DO $mig$
BEGIN
  IF to_regclass('public.byom_game_facts') IS NULL THEN
    RAISE EXCEPTION 'byom_game_facts is not present; apply byom_facts_schema_2026_10_16.sql first';
  END IF;
  IF to_regclass('public.byom_prop_facts') IS NULL THEN
    RAISE EXCEPTION 'byom_prop_facts is not present; apply byom_facts_schema_2026_10_16.sql first';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = 'byom_game_facts'
       AND column_name = 'dk_spread_home_price')
  THEN
    RAISE EXCEPTION 'apply byom_dk_start_price_2026_10_23.sql first';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = 'byom_prop_facts'
       AND column_name = 'over_price')
     OR NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = 'byom_prop_facts'
       AND column_name = 'under_price')
  THEN
    RAISE EXCEPTION 'apply byom_prop_facts_dk_prices_2026_10_28.sql first';
  END IF;

  EXECUTE $fn$
  CREATE OR REPLACE FUNCTION public.byom_backtest(
    p_season integer,
    p_filters jsonb DEFAULT '{}'::jsonb
  )
  RETURNS TABLE (
    market text,
    bets bigint,
    wins bigint,
    losses bigint,
    pushes bigint,
    ties bigint,
    units numeric,
    skipped bigint
  )
  LANGUAGE plpgsql
  STABLE
  SECURITY INVOKER
  SET search_path = public, pg_temp
  -- The in-function 3s timeout does not apply. Postgres arms
  -- statement_timeout when the top-level statement starts, so this
  -- SET does not bound the running call. The role timeouts govern:
  -- anon 3s, authenticated 8s.
  SET statement_timeout = '3s'
  AS $body$
  DECLARE
    -- byom_backtest_v1
    -- byom_dk_start_price
    -- byom_dk_price_fallback
    -- byom_total_side
    -- byom_prop_dk_prices
    v_season integer;
    v_side text;
    v_role text;
    v_weeks integer[];
    v_min_rest integer;
    v_max_rest integer;
    v_primetime boolean;
    v_markets text[];
    v_month integer;
    v_year integer;
    v_bad text;
  BEGIN
    IF p_filters IS NULL OR p_filters = 'null'::jsonb THEN
      p_filters := '{}'::jsonb;
    END IF;
    IF jsonb_typeof(p_filters) <> 'object' THEN
      RAISE EXCEPTION 'unknown filter key: filters must be an object';
    END IF;
    v_bad := NULL;
    SELECT k.key INTO v_bad
      FROM jsonb_object_keys(p_filters) AS k(key)
     WHERE k.key NOT IN (
       'side', 'role', 'weeks', 'min_rest_days', 'max_rest_days',
       'primetime', 'markets')
     LIMIT 1;
    IF v_bad IS NOT NULL THEN
      RAISE EXCEPTION 'unknown filter key: %', v_bad;
    END IF;

    IF p_season IS NULL THEN
      v_month := EXTRACT(MONTH FROM (now() AT TIME ZONE 'America/New_York'))::integer;
      v_year := EXTRACT(YEAR FROM (now() AT TIME ZONE 'America/New_York'))::integer;
      IF v_month >= 9 THEN
        v_season := v_year;
      ELSE
        v_season := v_year - 1;
      END IF;
    ELSE
      v_season := p_season;
    END IF;

    v_side := NULLIF(p_filters->>'side', '');
    v_role := NULLIF(p_filters->>'role', '');
    v_min_rest := (p_filters->>'min_rest_days')::integer;
    v_max_rest := (p_filters->>'max_rest_days')::integer;
    IF p_filters ? 'primetime' AND p_filters->>'primetime' IS NOT NULL
       AND p_filters->>'primetime' <> '' THEN
      v_primetime := (p_filters->>'primetime')::boolean;
    ELSE
      v_primetime := NULL;
    END IF;
    IF p_filters->'weeks' IS NULL
       OR jsonb_typeof(p_filters->'weeks') <> 'array'
       OR jsonb_array_length(p_filters->'weeks') = 0 THEN
      v_weeks := NULL;
    ELSE
      v_weeks := ARRAY(
        SELECT (jsonb_array_elements_text(p_filters->'weeks'))::integer);
    END IF;
    IF p_filters->'markets' IS NULL
       OR jsonb_typeof(p_filters->'markets') <> 'array'
       OR jsonb_array_length(p_filters->'markets') = 0 THEN
      v_markets := NULL;
    ELSE
      v_markets := ARRAY(SELECT jsonb_array_elements_text(p_filters->'markets'));
    END IF;

    -- Output names are also plpgsql variables. The leg columns use
    -- other names so `market` is not ambiguous. The function-level
    -- statement_timeout above does not apply; the role timeouts govern.
    -- no_line is a played bet with no DraftKings line, or a played bet
    -- whose stored price is not American. skipped counts both. Null
    -- scores are an unplayed game, so that game is not no_line.
    -- A prop leg is the same rule on that side's price. A null prop
    -- result is ungraded, so that leg is not no_line.
    RETURN QUERY
    WITH legs AS (
      SELECT 'spreads'::text AS mkt,
             g.ats_home_result AS res,
             g.week AS wk, g.home_rest_days AS rest_days, g.is_primetime AS prime,
             g.home_role AS leg_role, 'home'::text AS leg_side,
             g.dk_spread_home_price AS px,
             (g.home_score IS NOT NULL AND g.away_score IS NOT NULL
              AND (
                g.dk_spread_home IS NULL
                OR NOT (
                  g.dk_spread_home_price IS NOT NULL
                  AND g.dk_spread_home_price = trunc(g.dk_spread_home_price)
                  AND abs(g.dk_spread_home_price) >= 100))) AS no_line
        FROM byom_game_facts g
       WHERE g.sport = 'NFL' AND g.season = v_season
      UNION ALL
      SELECT 'spreads', g.ats_away_result, g.week, g.away_rest_days,
             g.is_primetime, g.away_role, 'away', g.dk_spread_away_price,
             (g.home_score IS NOT NULL AND g.away_score IS NOT NULL
              AND (
                g.dk_spread_home IS NULL
                OR NOT (
                  g.dk_spread_away_price IS NOT NULL
                  AND g.dk_spread_away_price = trunc(g.dk_spread_away_price)
                  AND abs(g.dk_spread_away_price) >= 100)))
        FROM byom_game_facts g
       WHERE g.sport = 'NFL' AND g.season = v_season
      UNION ALL
      SELECT 'h2h', g.ml_home_result, g.week, g.home_rest_days,
             g.is_primetime, g.home_role, 'home', g.dk_ml_home_price,
             (g.home_score IS NOT NULL AND g.away_score IS NOT NULL
              AND NOT (
                g.dk_ml_home_price IS NOT NULL
                AND g.dk_ml_home_price = trunc(g.dk_ml_home_price)
                AND abs(g.dk_ml_home_price) >= 100))
        FROM byom_game_facts g
       WHERE g.sport = 'NFL' AND g.season = v_season
      UNION ALL
      SELECT 'h2h', g.ml_away_result, g.week, g.away_rest_days,
             g.is_primetime, g.away_role, 'away', g.dk_ml_away_price,
             (g.home_score IS NOT NULL AND g.away_score IS NOT NULL
              AND NOT (
                g.dk_ml_away_price IS NOT NULL
                AND g.dk_ml_away_price = trunc(g.dk_ml_away_price)
                AND abs(g.dk_ml_away_price) >= 100))
        FROM byom_game_facts g
       WHERE g.sport = 'NFL' AND g.season = v_season
      UNION ALL
      SELECT 'totals', g.ou_over_result, g.week, NULL::integer,
             g.is_primetime, NULL::text, 'over'::text, g.dk_total_over_price,
             (g.home_score IS NOT NULL AND g.away_score IS NOT NULL
              AND (
                g.dk_total IS NULL
                OR NOT (
                  g.dk_total_over_price IS NOT NULL
                  AND g.dk_total_over_price = trunc(g.dk_total_over_price)
                  AND abs(g.dk_total_over_price) >= 100)))
        FROM byom_game_facts g
       WHERE g.sport = 'NFL' AND g.season = v_season
      UNION ALL
      SELECT 'totals', g.ou_under_result, g.week, NULL::integer,
             g.is_primetime, NULL::text, 'under'::text, g.dk_total_under_price,
             (g.home_score IS NOT NULL AND g.away_score IS NOT NULL
              AND (
                g.dk_total IS NULL
                OR NOT (
                  g.dk_total_under_price IS NOT NULL
                  AND g.dk_total_under_price = trunc(g.dk_total_under_price)
                  AND abs(g.dk_total_under_price) >= 100)))
        FROM byom_game_facts g
       WHERE g.sport = 'NFL' AND g.season = v_season
      UNION ALL
      SELECT p.market, p.over_result, p.week,
             CASE WHEN p.team = g.home_team THEN g.home_rest_days
                  WHEN p.team = g.away_team THEN g.away_rest_days
                  ELSE NULL END,
             g.is_primetime,
             CASE WHEN p.team = g.home_team THEN g.home_role
                  WHEN p.team = g.away_team THEN g.away_role
                  ELSE NULL END,
             CASE WHEN p.team = g.home_team THEN 'home'
                  WHEN p.team = g.away_team THEN 'away'
                  ELSE NULL END,
             p.over_price,
             (p.over_result IS NOT NULL
              AND NOT (
                p.over_price IS NOT NULL
                AND p.over_price = trunc(p.over_price)
                AND abs(p.over_price) >= 100))
        FROM byom_prop_facts p
        LEFT JOIN byom_game_facts g ON g.canonical_key = p.canonical_key
       WHERE p.sport = 'NFL' AND p.season = v_season
      UNION ALL
      SELECT p.market, p.under_result, p.week,
             CASE WHEN p.team = g.home_team THEN g.home_rest_days
                  WHEN p.team = g.away_team THEN g.away_rest_days
                  ELSE NULL END,
             g.is_primetime,
             CASE WHEN p.team = g.home_team THEN g.home_role
                  WHEN p.team = g.away_team THEN g.away_role
                  ELSE NULL END,
             CASE WHEN p.team = g.home_team THEN 'home'
                  WHEN p.team = g.away_team THEN 'away'
                  ELSE NULL END,
             p.under_price,
             (p.under_result IS NOT NULL
              AND NOT (
                p.under_price IS NOT NULL
                AND p.under_price = trunc(p.under_price)
                AND abs(p.under_price) >= 100))
        FROM byom_prop_facts p
        LEFT JOIN byom_game_facts g ON g.canonical_key = p.canonical_key
       WHERE p.sport = 'NFL' AND p.season = v_season
    ),
    kept AS (
      SELECT legs.*,
             -- Every market, including a prop. American odds only:
             -- a whole number with absolute value at least 100.
             -- 1.91 is not a price. A prop market is not exempt.
             (
               legs.px IS NOT NULL
               AND legs.px = trunc(legs.px)
               AND abs(legs.px) >= 100
             ) AS priced
        FROM legs
       WHERE (res IS NOT NULL OR no_line)
         AND (v_markets IS NULL OR mkt = ANY (v_markets))
         AND (v_weeks IS NULL OR wk = ANY (v_weeks))
         AND (v_side IS NULL OR leg_side = v_side)
         AND (v_role IS NULL OR leg_role = v_role)
         AND (v_min_rest IS NULL OR rest_days >= v_min_rest)
         AND (v_max_rest IS NULL OR rest_days <= v_max_rest)
         AND (v_primetime IS NULL OR prime = v_primetime)
    )
    SELECT kept.mkt,
           count(*) FILTER (WHERE kept.priced)::bigint,
           count(*) FILTER (WHERE kept.priced AND kept.res = 'win')::bigint,
           count(*) FILTER (WHERE kept.priced AND kept.res = 'loss')::bigint,
           count(*) FILTER (WHERE kept.priced AND kept.res = 'push')::bigint,
           count(*) FILTER (WHERE kept.priced AND kept.res = 'tie')::bigint,
           coalesce(sum(
             CASE
               WHEN kept.res = 'win' THEN 1
               WHEN kept.res IN ('push', 'tie') THEN 0
               WHEN kept.res = 'loss' AND kept.px < 0 THEN -abs(kept.px) / 100
               WHEN kept.res = 'loss' AND kept.px > 0 THEN -(100 / kept.px)
               ELSE 0
             END
           ) FILTER (WHERE kept.priced), 0)::numeric,
           count(*) FILTER (WHERE kept.no_line AND NOT kept.priced)::bigint
      FROM kept
     GROUP BY kept.mkt
     ORDER BY kept.mkt;
  END
  $body$;
  $fn$;

  REVOKE ALL ON FUNCTION public.byom_backtest(integer, jsonb) FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION public.byom_backtest(integer, jsonb)
    TO anon, authenticated;

END $mig$;
