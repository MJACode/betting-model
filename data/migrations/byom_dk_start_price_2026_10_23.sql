-- DraftKings game-start prices on byom_game_facts, and units on byom_backtest.
--
-- NOT in data/view_migrations.ACTIVE_MIGRATIONS. The worker re-runs that
-- list against production. Apply this file by hand. It is idempotent:
-- ADD COLUMN IF NOT EXISTS, DROP NOT NULL (already nullable is a no-op),
-- DROP FUNCTION IF EXISTS, CREATE OR REPLACE.
--
-- A price is the last DraftKings quote at or before commence_time for
-- that market and side. The columns are nullable. A missing price is
-- not filled in. Another book is not stored here.
--
-- week stays the NFL week parsed from the id. Other sports have no week
-- on games (measured 2026-10-23: only NCAAF has games.week populated,
-- and not on every row), so week may be null. NFL rows keep their week.
--
-- byom_backtest gains units and skipped and keeps market, bets, wins,
-- losses, pushes, ties in that order. Staking is 1u to win at the stored
-- DraftKings price: a win is +1, a loss is -abs(price)/100 on minus odds
-- and -100/price on plus odds, a push or a tie is 0. A graded game leg
-- with no price is left out of those counts and added to skipped.
-- Graded prop legs have no price column in this file. They stay in the
-- win-loss counts, add 0 to units, and are not skipped. An ungraded row
-- (null result: non_participant, missing_log, unplayed, ambiguous, or
-- no result) stays out of the record and out of skipped.
--
-- The function body still carries byom_backtest_v1. The registered
-- migration byom_backtest_rpc_2026_10_16.sql skips when that marker is
-- present, so a later worker pass does not replace this function with
-- the old return type.
--
-- SECURITY INVOKER. The in-function 3s timeout does not apply. Postgres
-- arms statement_timeout when the top-level statement starts, so this
-- SET does not bound the running call. The role timeouts govern:
-- anon 3s, authenticated 8s (measured on pg_roles 2026-10-23).
--
-- Unknown filter keys are rejected. The known keys are unchanged.
--
-- Does not apply data/migrations/byom_book_quotes_2026_10_21.sql.
-- One DO block. No CONCURRENTLY.

DO $mig$
DECLARE
  dep text;
BEGIN
  IF to_regclass('public.byom_game_facts') IS NULL THEN
    RAISE EXCEPTION 'byom_game_facts is not present; apply byom_facts_schema_2026_10_16.sql first';
  END IF;

  ALTER TABLE public.byom_game_facts
    ADD COLUMN IF NOT EXISTS dk_ml_home_price NUMERIC;
  ALTER TABLE public.byom_game_facts
    ADD COLUMN IF NOT EXISTS dk_ml_away_price NUMERIC;
  ALTER TABLE public.byom_game_facts
    ADD COLUMN IF NOT EXISTS dk_spread_home_price NUMERIC;
  ALTER TABLE public.byom_game_facts
    ADD COLUMN IF NOT EXISTS dk_spread_away_price NUMERIC;
  ALTER TABLE public.byom_game_facts
    ADD COLUMN IF NOT EXISTS dk_total_over_price NUMERIC;
  ALTER TABLE public.byom_game_facts
    ADD COLUMN IF NOT EXISTS dk_total_under_price NUMERIC;

  ALTER TABLE public.byom_game_facts ALTER COLUMN week DROP NOT NULL;

  SELECT p.proname INTO dep
    FROM pg_depend d
    JOIN pg_proc p ON p.oid = d.objid
    JOIN pg_proc ref ON ref.oid = d.refobjid
   WHERE ref.proname = 'byom_backtest'
     AND ref.pronamespace = 'public'::regnamespace
     AND d.deptype = 'n'
     AND p.oid <> ref.oid
   LIMIT 1;
  IF dep IS NOT NULL THEN
    RAISE EXCEPTION 'byom_backtest is used by %; refusing to drop it', dep;
  END IF;

  DROP FUNCTION IF EXISTS public.byom_backtest(integer, jsonb);

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
      RETURN QUERY
      WITH legs AS (
        SELECT 'spreads'::text AS mkt,
               g.ats_home_result AS res,
               g.week AS wk, g.home_rest_days AS rest_days, g.is_primetime AS prime,
               g.home_role AS leg_role, 'home'::text AS leg_side,
               g.dk_spread_home_price AS px
          FROM byom_game_facts g
         WHERE g.sport = 'NFL' AND g.season = v_season
        UNION ALL
        SELECT 'spreads', g.ats_away_result, g.week, g.away_rest_days,
               g.is_primetime, g.away_role, 'away', g.dk_spread_away_price
          FROM byom_game_facts g
         WHERE g.sport = 'NFL' AND g.season = v_season
        UNION ALL
        SELECT 'h2h', g.ml_home_result, g.week, g.home_rest_days,
               g.is_primetime, g.home_role, 'home', g.dk_ml_home_price
          FROM byom_game_facts g
         WHERE g.sport = 'NFL' AND g.season = v_season
        UNION ALL
        SELECT 'h2h', g.ml_away_result, g.week, g.away_rest_days,
               g.is_primetime, g.away_role, 'away', g.dk_ml_away_price
          FROM byom_game_facts g
         WHERE g.sport = 'NFL' AND g.season = v_season
        UNION ALL
        SELECT 'totals', g.ou_over_result, g.week, NULL::integer,
               g.is_primetime, NULL::text, NULL::text, g.dk_total_over_price
          FROM byom_game_facts g
         WHERE g.sport = 'NFL' AND g.season = v_season
        UNION ALL
        SELECT 'totals', g.ou_under_result, g.week, NULL::integer,
               g.is_primetime, NULL::text, NULL::text, g.dk_total_under_price
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
               NULL::numeric
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
               NULL::numeric
          FROM byom_prop_facts p
          LEFT JOIN byom_game_facts g ON g.canonical_key = p.canonical_key
         WHERE p.sport = 'NFL' AND p.season = v_season
      ),
      kept AS (
        SELECT legs.*,
               (
                 legs.mkt NOT IN ('h2h', 'spreads', 'totals')
                 OR (legs.px IS NOT NULL AND legs.px <> 0)
               ) AS priced
          FROM legs
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
             count(*) FILTER (WHERE kept.priced)::bigint,
             count(*) FILTER (WHERE kept.priced AND kept.res = 'win')::bigint,
             count(*) FILTER (WHERE kept.priced AND kept.res = 'loss')::bigint,
             count(*) FILTER (WHERE kept.priced AND kept.res = 'push')::bigint,
             count(*) FILTER (WHERE kept.priced AND kept.res = 'tie')::bigint,
             coalesce(sum(
               CASE
                 WHEN kept.mkt NOT IN ('h2h', 'spreads', 'totals') THEN 0
                 WHEN kept.res = 'win' THEN 1
                 WHEN kept.res IN ('push', 'tie') THEN 0
                 WHEN kept.res = 'loss' AND kept.px < 0 THEN -abs(kept.px) / 100
                 WHEN kept.res = 'loss' AND kept.px > 0 THEN -(100 / kept.px)
                 ELSE 0
               END
             ) FILTER (WHERE kept.priced), 0)::numeric,
             count(*) FILTER (WHERE NOT kept.priced)::bigint
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
