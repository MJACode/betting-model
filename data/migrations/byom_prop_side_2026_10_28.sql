-- One prop direction on byom_backtest, and a prop save requires it.
--
-- Production already stakes prop legs at over_price and under_price
-- (byom_backtest_prop_dk_prices_2026_10_28.sql). That function counts
-- the over and the under together. This file keeps that stake and
-- adds prop_side. "over" keeps the over leg. "under" keeps the under
-- leg. A missing prop_side still counts both, so an older caller is
-- unchanged. The player's team stays on side: home or away. A prop
-- leg with no American price on the chosen side stays out of the
-- record and in skipped. Anytime TD Yes is the over leg. This file
-- does not hide the under leg from a caller that asks for it.
--
-- byom_save_model keeps prop_side. One of the twelve NFL prop markets
-- with no over or under is refused. A filter with no prop market
-- drops prop_side, so a game bet does not store it. Game-market side
-- refusals stay. byom_saved_models_v1 stays in the save body.
-- byom_backtest_v1, byom_dk_start_price, byom_dk_price_fallback,
-- byom_total_side, and byom_prop_dk_prices stay in the backtest body.
--
-- NOT in data/view_migrations.ACTIVE_MIGRATIONS. The worker re-runs
-- that list against production. Apply this file by hand, after
-- byom_prop_facts_dk_prices_2026_10_28.sql and after
-- byom_total_side_2026_10_25.sql. Do not re-apply the older backtest
-- files after this one. They replace the function. It is idempotent:
-- both functions are CREATE OR REPLACE. It does not DROP either
-- function. It does not write picks.
--
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

  IF to_regprocedure('public.byom_save_model(text, jsonb, integer)') IS NULL THEN
    RAISE EXCEPTION 'byom_save_model is not present; apply byom_saved_models_2026_10_16.sql first';
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
    -- byom_prop_side
    v_season integer;
    v_side text;
    v_prop_side text;
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
       'primetime', 'markets', 'prop_side')
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
    v_prop_side := NULLIF(p_filters->>'prop_side', '');
    IF v_prop_side IS NOT NULL AND v_prop_side NOT IN ('over', 'under') THEN
      RAISE EXCEPTION 'Choose over or under.';
    END IF;
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
                  AND abs(g.dk_spread_home_price) >= 100))) AS no_line,
             NULL::text AS leg_ou
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
             , NULL::text
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
             , NULL::text
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
             , NULL::text
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
             , NULL::text
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
             , NULL::text
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
                AND abs(p.over_price) >= 100)),
             'over'::text
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
                AND abs(p.under_price) >= 100)),
             'under'::text
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
         AND (v_prop_side IS NULL OR leg_ou = v_prop_side)
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

  EXECUTE $save$
    CREATE OR REPLACE FUNCTION public.byom_save_model(
      p_name text,
      p_filters jsonb,
      p_season integer DEFAULT NULL
    )
    RETURNS TABLE (
      model_id uuid,
      name text,
      season integer,
      bets bigint,
      wins bigint,
      losses bigint,
      pushes bigint,
      ties bigint
    )
    LANGUAGE plpgsql
    VOLATILE
    SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $body$
    #variable_conflict use_column
    DECLARE
      -- byom_saved_models_v1
      -- byom_prop_side
      v_uid uuid;
      v_name text;
      v_filters jsonb;
      v_season integer;
      v_month integer;
      v_year integer;
      v_model uuid;
      v_count integer;
      v_bets bigint;
      v_wins bigint;
      v_losses bigint;
      v_pushes bigint;
      v_ties bigint;
      v_summary jsonb;
    BEGIN
      v_uid := auth.uid();
      IF v_uid IS NULL THEN
        RAISE EXCEPTION 'sign-in required';
      END IF;
      PERFORM pg_advisory_xact_lock(hashtext(v_uid::text));

      v_name := btrim(p_name);
      IF v_name IS NULL OR v_name = '' OR char_length(v_name) > 80 THEN
        RAISE EXCEPTION 'model name must be 1 to 80 characters';
      END IF;

      v_filters := COALESCE(p_filters, '{}'::jsonb);
      IF jsonb_typeof(v_filters) <> 'object' THEN
        RAISE EXCEPTION 'filters must be an object';
      END IF;
      IF EXISTS (
        SELECT 1 FROM jsonb_object_keys(v_filters) AS k(key)
         WHERE lower(k.key) IN (
           'minodds', 'maxodds', 'min_odds', 'max_odds',
           'minline', 'maxline', 'min_line', 'max_line',
           'spread_size', 'price_band', 'stake', 'kelly'))
      THEN
        RAISE EXCEPTION 'price, line, and stake filters are not accepted';
      END IF;
      IF EXISTS (
        SELECT 1 FROM jsonb_object_keys(v_filters) AS k(key)
         WHERE lower(k.key) IN (
           'side', 'role', 'weeks', 'min_rest_days', 'max_rest_days',
           'primetime', 'markets', 'prop_side')
           AND k.key NOT IN (
           'side', 'role', 'weeks', 'min_rest_days', 'max_rest_days',
           'primetime', 'markets', 'prop_side'))
      THEN
        RAISE EXCEPTION 'filter keys must be lowercase';
      END IF;
      SELECT COALESCE(jsonb_object_agg(e.key, e.value), '{}'::jsonb)
        INTO v_filters
        FROM jsonb_each(v_filters) AS e
       WHERE e.key IN (
         'side', 'role', 'weeks', 'min_rest_days', 'max_rest_days',
         'primetime', 'markets', 'prop_side');

      -- One game market needs a side. A missing side is not both sides.
      IF jsonb_typeof(v_filters->'markets') = 'array' THEN
        IF jsonb_array_length(v_filters->'markets') = 1
           AND (v_filters->'markets'->>0) IN ('h2h', 'spreads')
           AND COALESCE(v_filters->>'side', '') NOT IN ('home', 'away')
           AND COALESCE(v_filters->>'role', '') NOT IN ('favorite', 'underdog', 'pickem')
        THEN
          RAISE EXCEPTION 'Choose a team, or a favorite or underdog.';
        END IF;
        IF jsonb_array_length(v_filters->'markets') = 1
           AND (v_filters->'markets'->>0) = 'totals'
           AND COALESCE(v_filters->>'side', '') NOT IN ('over', 'under')
        THEN
          RAISE EXCEPTION 'Choose over or under.';
        END IF;
        IF jsonb_array_length(v_filters->'markets') = 1
           AND (v_filters->'markets'->>0) IN (
             'player_pass_yds', 'player_pass_attempts', 'player_pass_completions',
             'player_pass_tds', 'player_rush_yds', 'player_rush_attempts',
             'player_reception_yds', 'player_receptions',
             'player_rush_reception_yds', 'player_anytime_td',
             'player_tackles_assists', 'player_sacks')
           AND COALESCE(v_filters->>'prop_side', '') NOT IN ('over', 'under')
        THEN
          RAISE EXCEPTION 'Choose over or under.';
        END IF;
      END IF;
      IF NOT (
        jsonb_typeof(v_filters->'markets') = 'array'
        AND EXISTS (
          SELECT 1
            FROM jsonb_array_elements_text(v_filters->'markets') AS m(mkt)
           WHERE m.mkt IN (
             'player_pass_yds', 'player_pass_attempts', 'player_pass_completions',
             'player_pass_tds', 'player_rush_yds', 'player_rush_attempts',
             'player_reception_yds', 'player_receptions',
             'player_rush_reception_yds', 'player_anytime_td',
             'player_tackles_assists', 'player_sacks'))
      ) THEN
        v_filters := v_filters - 'prop_side';
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

      -- One function call. The sums and the summary are that same row set.
      SELECT coalesce(sum(b.bets), 0)::bigint,
             coalesce(sum(b.wins), 0)::bigint,
             coalesce(sum(b.losses), 0)::bigint,
             coalesce(sum(b.pushes), 0)::bigint,
             coalesce(sum(b.ties), 0)::bigint,
             coalesce(jsonb_agg(jsonb_build_object(
               'market', b.market,
               'bets', b.bets,
               'wins', b.wins,
               'losses', b.losses,
               'pushes', b.pushes,
               'ties', b.ties
             ) ORDER BY b.market), '[]'::jsonb)
        INTO v_bets, v_wins, v_losses, v_pushes, v_ties,
             v_summary
        FROM byom_backtest(v_season, v_filters) AS b;

      SELECT m.model_id INTO v_model
        FROM byom_models m
       WHERE m.user_id = v_uid AND m.name = v_name;

      IF v_model IS NULL THEN
        SELECT count(*) INTO v_count
          FROM byom_models m
         WHERE m.user_id = v_uid;
        IF v_count >= 25 THEN
          RAISE EXCEPTION 'byom model cap is 25';
        END IF;
        INSERT INTO byom_models (user_id, name, sport, filters)
        VALUES (v_uid, v_name, 'NFL', v_filters)
        RETURNING byom_models.model_id INTO v_model;
      ELSE
        UPDATE byom_models m
           SET filters = v_filters, updated_at = now()
         WHERE m.model_id = v_model AND m.user_id = v_uid;
      END IF;

      INSERT INTO byom_model_snapshots (
        model_id, user_id, season, filters, summary,
        bets, wins, losses, pushes, ties)
      VALUES (
        v_model, v_uid, v_season, v_filters, v_summary,
        v_bets, v_wins, v_losses, v_pushes, v_ties);

      RETURN QUERY
      SELECT v_model, v_name, v_season, v_bets, v_wins, v_losses,
             v_pushes, v_ties;
    END
    $body$;
  $save$;

  REVOKE ALL ON FUNCTION public.byom_save_model(text, jsonb, integer)
    FROM PUBLIC, anon;
  GRANT EXECUTE ON FUNCTION public.byom_save_model(text, jsonb, integer)
    TO authenticated;
  REVOKE ALL ON FUNCTION public.byom_save_model(text, jsonb, integer)
    FROM PUBLIC, anon;
  GRANT EXECUTE ON FUNCTION public.byom_save_model(text, jsonb, integer)
    TO authenticated;
END $mig$;
