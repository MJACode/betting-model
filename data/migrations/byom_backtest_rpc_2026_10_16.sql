-- byom_backtest: one season of byom_game_facts and byom_prop_facts.
--
-- UNAPPLIED. Registered for the worker. A second pass returns when the
-- function body already carries the marker below, so it does not replace
-- the function again.
--
-- SECURITY INVOKER. The caller reads the facts tables under its own RLS.
-- plpgsql locals, not a filter CTE over the jsonb argument.
--
-- p_season NULL is the current NFL season only: the year the season
-- starts, in America/New_York, and January through August stay on the
-- previous year's label. A later caller can pass an older season.
--
-- p_filters, all optional, AND'd:
--   side: "home" | "away"
--   role: "favorite" | "underdog" | "pickem"
--   weeks: [1, 2]
--   min_rest_days / max_rest_days
--   primetime: true | false
--   markets: ["spreads", "totals", "h2h", "player_pass_yds"]
-- A missing datum on a leg is excluded once that filter is set.
-- There is no spread-size, price, or line filter. Both unit columns are
-- summed. They are the stored DraftKings-lock results, not a stake.
--
-- Game markets contribute the home leg and the away leg. Prop markets
-- contribute the over and the under. A side or role filter uses the
-- player's team on the game fact.
--
-- An empty filter object is the whole season. It is not a model record.
-- The UI must not present that unfiltered result as a saved model.
--
-- The 120h and 24h windows are UNCONFIRMED and are not in this file.
-- One DO block. No CONCURRENTLY.

DO $mig$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public' AND p.proname = 'byom_backtest'
       AND p.prosrc LIKE '%byom_backtest_v1%')
  THEN
    RAISE NOTICE 'byom_backtest already present - skipping';
    RETURN;
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
      units_uncapped numeric,
      units_capped numeric
    )
    LANGUAGE plpgsql
    STABLE
    SECURITY INVOKER
    SET search_path = public, pg_temp
    SET statement_timeout = '3s'
    AS $body$
    DECLARE
      -- byom_backtest_v1
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
    BEGIN
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
      -- other names so `market` is not ambiguous. statement_timeout is
      -- set on the function (STABLE cannot SET LOCAL).
      RETURN QUERY
      WITH legs AS (
        SELECT 'spreads'::text AS mkt,
               g.ats_home_result AS res,
               g.ats_home_units_uncapped AS unc,
               g.ats_home_units_capped AS cap,
               g.week AS wk, g.home_rest_days AS rest_days, g.is_primetime AS prime,
               g.home_role AS leg_role, 'home'::text AS leg_side
          FROM byom_game_facts g
         WHERE g.sport = 'NFL' AND g.season = v_season
        UNION ALL
        SELECT 'spreads', g.ats_away_result, g.ats_away_units_uncapped,
               g.ats_away_units_capped, g.week, g.away_rest_days,
               g.is_primetime, g.away_role, 'away'
          FROM byom_game_facts g
         WHERE g.sport = 'NFL' AND g.season = v_season
        UNION ALL
        SELECT 'h2h', g.ml_home_result, g.ml_home_units_uncapped,
               g.ml_home_units_capped, g.week, g.home_rest_days,
               g.is_primetime, g.home_role, 'home'
          FROM byom_game_facts g
         WHERE g.sport = 'NFL' AND g.season = v_season
        UNION ALL
        SELECT 'h2h', g.ml_away_result, g.ml_away_units_uncapped,
               g.ml_away_units_capped, g.week, g.away_rest_days,
               g.is_primetime, g.away_role, 'away'
          FROM byom_game_facts g
         WHERE g.sport = 'NFL' AND g.season = v_season
        UNION ALL
        SELECT 'totals', g.ou_over_result, g.ou_over_units_uncapped,
               g.ou_over_units_capped, g.week, NULL::integer,
               g.is_primetime, NULL::text, NULL::text
          FROM byom_game_facts g
         WHERE g.sport = 'NFL' AND g.season = v_season
        UNION ALL
        SELECT 'totals', g.ou_under_result, g.ou_under_units_uncapped,
               g.ou_under_units_capped, g.week, NULL::integer,
               g.is_primetime, NULL::text, NULL::text
          FROM byom_game_facts g
         WHERE g.sport = 'NFL' AND g.season = v_season
        UNION ALL
        SELECT p.market, p.over_result, p.over_units_uncapped,
               p.over_units_capped, p.week,
               CASE WHEN p.team = g.home_team THEN g.home_rest_days
                    WHEN p.team = g.away_team THEN g.away_rest_days
                    ELSE NULL END,
               g.is_primetime,
               CASE WHEN p.team = g.home_team THEN g.home_role
                    WHEN p.team = g.away_team THEN g.away_role
                    ELSE NULL END,
               CASE WHEN p.team = g.home_team THEN 'home'
                    WHEN p.team = g.away_team THEN 'away'
                    ELSE NULL END
          FROM byom_prop_facts p
          LEFT JOIN byom_game_facts g ON g.canonical_key = p.canonical_key
         WHERE p.sport = 'NFL' AND p.season = v_season
        UNION ALL
        SELECT p.market, p.under_result, p.under_units_uncapped,
               p.under_units_capped, p.week,
               CASE WHEN p.team = g.home_team THEN g.home_rest_days
                    WHEN p.team = g.away_team THEN g.away_rest_days
                    ELSE NULL END,
               g.is_primetime,
               CASE WHEN p.team = g.home_team THEN g.home_role
                    WHEN p.team = g.away_team THEN g.away_role
                    ELSE NULL END,
               CASE WHEN p.team = g.home_team THEN 'home'
                    WHEN p.team = g.away_team THEN 'away'
                    ELSE NULL END
          FROM byom_prop_facts p
          LEFT JOIN byom_game_facts g ON g.canonical_key = p.canonical_key
         WHERE p.sport = 'NFL' AND p.season = v_season
      ),
      kept AS (
        SELECT * FROM legs
         WHERE res IS NOT NULL
           AND (v_markets IS NULL OR mkt = ANY (v_markets))
           AND (v_weeks IS NULL OR wk = ANY (v_weeks))
           AND (v_side IS NULL OR leg_side = v_side)
           AND (v_role IS NULL OR leg_role = v_role)
           AND (v_min_rest IS NULL OR rest_days >= v_min_rest)
           AND (v_max_rest IS NULL OR rest_days <= v_max_rest)
           AND (v_primetime IS NULL OR prime = v_primetime)
      )
      SELECT kept.mkt,
             count(*)::bigint,
             count(*) FILTER (WHERE kept.res = 'win')::bigint,
             count(*) FILTER (WHERE kept.res = 'loss')::bigint,
             count(*) FILTER (WHERE kept.res = 'push')::bigint,
             count(*) FILTER (WHERE kept.res = 'tie')::bigint,
             COALESCE(sum(kept.unc), 0),
             COALESCE(sum(kept.cap), 0)
        FROM kept
       GROUP BY kept.mkt
       ORDER BY kept.mkt;
    END
    $body$
  $fn$;

  REVOKE ALL ON FUNCTION public.byom_backtest(integer, jsonb) FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION public.byom_backtest(integer, jsonb)
    TO anon, authenticated;
END $mig$;
