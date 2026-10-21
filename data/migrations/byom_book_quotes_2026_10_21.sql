-- Per-book quotes, and best-line units on byom_backtest.
--
-- UNAPPLIED. This file is NOT in data/view_migrations.ACTIVE_MIGRATIONS.
-- The worker must not run it. Matt applies it by hand.
--
-- It does not edit byom_facts_schema_2026_10_16.sql or
-- byom_saved_models_2026_10_16.sql. It does not touch picks.
--
-- Apply after the facts schema, byom_backtest_rpc_2026_10_16.sql, and
-- published_pick_units_2026_10_17.sql. Apply byom_saved_models_2026_10_16.sql
-- first when this pass should fill result_version. If that file is applied
-- later, run this file again: the second pass adds the snapshot columns
-- and replaces save and list. The replaced save keeps byom_saved_models_v1
-- and byom_save_model(text, jsonb, integer), so the saved-models file does
-- not put the old function back.
--
-- byom_game_book_quotes and byom_prop_book_quotes hold one row per book,
-- market, and side. fact_id is the game canonical_key or the prop_key.
-- market and side are on the row because one book posts a spread, a total,
-- and a moneyline, and each side has its own number. The unique key is
-- (fact_id, book, market, side). A key of (fact_id, book) collides a
-- spread with a total, and an over with an under, on upsert.
--
-- byom_backtest(season, filters) is the DraftKings record: the same counts,
-- and units, roi, and risked are NULL. byom_backtest(season, filters, books)
-- grades the best line among those books. No selected line excludes the
-- leg. A prop that is not logged stays out. Units call
-- published_pick_unit_profit and published_pick_unit_risked. A push is 0.
--
-- The in-function 3s timeout does not apply. Postgres arms
-- statement_timeout when the top-level statement starts, so the SET below
-- does not bound the running call. The role timeouts govern: anon 3s,
-- authenticated 8s.
--
-- result_version NULL is a snapshot written before the column. 1 is a
-- DraftKings save. 2 is a best-line save, with units, roi, and the books.
--
-- The replaced byom_backtest keeps the text byom_backtest_v1, so
-- byom_backtest_rpc_2026_10_16.sql does not recreate the two-argument
-- function. It also carries byom_best_line_v1.
--
-- One DO block. No CONCURRENTLY.

DO $mig$
BEGIN
  IF to_regclass('public.byom_game_book_quotes') IS NOT NULL
     AND to_regclass('public.byom_prop_book_quotes') IS NOT NULL
     AND EXISTS (
       SELECT 1 FROM pg_proc p
         JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'byom_backtest'
          AND p.prosrc LIKE '%byom_best_line_v1%'
          AND p.prosrc LIKE '%byom_backtest_v1%'
          AND pg_get_function_identity_arguments(p.oid)
              = 'p_season integer, p_filters jsonb, p_books text[]')
     AND NOT EXISTS (
       SELECT 1 FROM pg_proc p
         JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'byom_backtest'
          AND pg_get_function_identity_arguments(p.oid)
              = 'p_season integer, p_filters jsonb')
     AND (
       to_regclass('public.byom_model_snapshots') IS NULL
       OR (
         EXISTS (
           SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'byom_model_snapshots'
              AND column_name = 'result_version')
         AND EXISTS (
           SELECT 1 FROM pg_proc p
             JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND p.proname = 'byom_save_model'
              AND p.prosrc LIKE '%byom_best_line_v1%'
              AND p.prosrc LIKE '%byom_saved_models_v1%')
         AND EXISTS (
           SELECT 1 FROM pg_proc p
             JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND p.proname = 'byom_list_models'
              AND p.prosrc LIKE '%byom_best_line_v1%'
              AND p.prosrc LIKE '%byom_saved_models_v1%')
       )
     )
     AND to_regclass('public.idx_byom_game_book_quotes_fact_book') IS NULL
     AND to_regclass('public.idx_byom_prop_book_quotes_fact_book') IS NULL
     AND to_regclass('public.idx_byom_game_book_quotes_fact_book_market_side') IS NOT NULL
     AND to_regclass('public.idx_byom_prop_book_quotes_fact_book_market_side') IS NOT NULL
  THEN
    RAISE NOTICE 'byom book quotes already present - skipping';
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.byom_game_book_quotes (
    fact_id      TEXT NOT NULL,
    book         TEXT NOT NULL,
    -- One book posts spreads, totals, and h2h. Each side has its own
    -- number, so market and side sit on the row with the line.
    market       TEXT NOT NULL,
    side         TEXT NOT NULL,
    line         NUMERIC,
    price        NUMERIC,
    captured_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (fact_id, book, market, side)
  );

  CREATE TABLE IF NOT EXISTS public.byom_prop_book_quotes (
    fact_id      TEXT NOT NULL,
    book         TEXT NOT NULL,
    market       TEXT NOT NULL,
    side         TEXT NOT NULL,
    line         NUMERIC,
    price        NUMERIC,
    captured_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (fact_id, book, market, side)
  );

  -- A previous pass indexed (fact_id, book) only. That key collides
  -- the spread and the total, and the two sides, from one book.
  DROP INDEX IF EXISTS public.idx_byom_game_book_quotes_fact_book;
  DROP INDEX IF EXISTS public.idx_byom_prop_book_quotes_fact_book;
  CREATE UNIQUE INDEX IF NOT EXISTS idx_byom_game_book_quotes_fact_book_market_side
    ON public.byom_game_book_quotes (fact_id, book, market, side);
  CREATE UNIQUE INDEX IF NOT EXISTS idx_byom_prop_book_quotes_fact_book_market_side
    ON public.byom_prop_book_quotes (fact_id, book, market, side);

  REVOKE ALL ON public.byom_game_book_quotes FROM PUBLIC, anon, authenticated;
  REVOKE ALL ON public.byom_prop_book_quotes FROM PUBLIC, anon, authenticated;
  GRANT SELECT ON public.byom_game_book_quotes TO anon, authenticated;
  GRANT SELECT ON public.byom_prop_book_quotes TO anon, authenticated;
  ALTER TABLE public.byom_game_book_quotes ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.byom_prop_book_quotes ENABLE ROW LEVEL SECURITY;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
     WHERE polrelid = 'public.byom_game_book_quotes'::regclass
       AND polname = 'anon read byom_game_book_quotes') THEN
    CREATE POLICY "anon read byom_game_book_quotes"
      ON public.byom_game_book_quotes
      FOR SELECT TO anon, authenticated
      USING (true);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
     WHERE polrelid = 'public.byom_prop_book_quotes'::regclass
       AND polname = 'anon read byom_prop_book_quotes') THEN
    CREATE POLICY "anon read byom_prop_book_quotes"
      ON public.byom_prop_book_quotes
      FOR SELECT TO anon, authenticated
      USING (true);
  END IF;

  DROP FUNCTION IF EXISTS public.byom_backtest(integer, jsonb);
  DROP FUNCTION IF EXISTS public.byom_backtest(integer, jsonb, text[]);

  EXECUTE $fn$
    CREATE FUNCTION public.byom_backtest(
      p_season integer,
      p_filters jsonb DEFAULT '{}'::jsonb,
      p_books text[] DEFAULT NULL
    )
    RETURNS TABLE (
      market text,
      bets bigint,
      wins bigint,
      losses bigint,
      pushes bigint,
      ties bigint,
      units numeric,
      roi numeric,
      risked numeric
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
      -- byom_best_line_v1
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
      v_books text[];
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

      -- No book list: the stored DraftKings results. Units stay NULL.
      IF p_books IS NULL THEN
        RETURN QUERY
        WITH legs AS (
          SELECT 'spreads'::text AS mkt,
                 g.ats_home_result AS res,
                 g.week AS wk, g.home_rest_days AS rest_days, g.is_primetime AS prime,
                 g.home_role AS leg_role, 'home'::text AS leg_side
            FROM byom_game_facts g
           WHERE g.sport = 'NFL' AND g.season = v_season
          UNION ALL
          SELECT 'spreads', g.ats_away_result, g.week, g.away_rest_days,
                 g.is_primetime, g.away_role, 'away'
            FROM byom_game_facts g
           WHERE g.sport = 'NFL' AND g.season = v_season
          UNION ALL
          SELECT 'h2h', g.ml_home_result, g.week, g.home_rest_days,
                 g.is_primetime, g.home_role, 'home'
            FROM byom_game_facts g
           WHERE g.sport = 'NFL' AND g.season = v_season
          UNION ALL
          SELECT 'h2h', g.ml_away_result, g.week, g.away_rest_days,
                 g.is_primetime, g.away_role, 'away'
            FROM byom_game_facts g
           WHERE g.sport = 'NFL' AND g.season = v_season
          UNION ALL
          SELECT 'totals', g.ou_over_result, g.week, NULL::integer,
                 g.is_primetime, NULL::text, NULL::text
            FROM byom_game_facts g
           WHERE g.sport = 'NFL' AND g.season = v_season
          UNION ALL
          SELECT 'totals', g.ou_under_result, g.week, NULL::integer,
                 g.is_primetime, NULL::text, NULL::text
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
                      ELSE NULL END
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
               NULL::numeric,
               NULL::numeric,
               NULL::numeric
          FROM kept
         GROUP BY kept.mkt
         ORDER BY kept.mkt;
        RETURN;
      END IF;

      IF cardinality(p_books) > 32
         OR EXISTS (
           SELECT 1 FROM unnest(p_books) AS b(book)
            WHERE b.book IS NULL
               OR lower(btrim(b.book)) !~ '^[a-z0-9_]{2,40}$')
      THEN
        RAISE EXCEPTION 'books must be 1 to 32 sportsbook slugs';
      END IF;
      v_books := ARRAY(
        SELECT DISTINCT lower(btrim(b.book))
          FROM unnest(p_books) AS b(book));
      IF cardinality(v_books) = 0 THEN
        RETURN;
      END IF;

      -- Best line among the selected books. Spreads: higher line. Over:
      -- lower line. Under: higher line. Moneyline: higher American price.
      -- Grade that line. A push is 0 via published_pick_unit_profit.
      RETURN QUERY
      WITH game_best AS (
        SELECT DISTINCT ON (q.fact_id, q.market, q.side)
               q.fact_id, q.market, q.side, q.line, q.price
          FROM byom_game_book_quotes q
          JOIN byom_game_facts g ON g.canonical_key = q.fact_id
         WHERE g.sport = 'NFL' AND g.season = v_season
           AND q.book = ANY (v_books)
           AND (
             (q.market = 'h2h' AND q.price IS NOT NULL)
             OR (q.market IN ('spreads', 'totals') AND q.line IS NOT NULL)
           )
         ORDER BY q.fact_id, q.market, q.side,
           CASE
             WHEN q.market = 'spreads' THEN q.line
             WHEN q.market = 'h2h' THEN q.price
             WHEN q.market = 'totals' AND q.side = 'under' THEN q.line
             ELSE NULL
           END DESC NULLS LAST,
           CASE
             WHEN q.market = 'totals' AND q.side = 'over' THEN q.line
             ELSE NULL
           END ASC NULLS LAST,
           q.price DESC NULLS LAST,
           q.book
      ),
      spread_role AS (
        SELECT fact_id, side,
               CASE WHEN line < 0 THEN 'favorite'
                    WHEN line > 0 THEN 'underdog'
                    ELSE 'pickem' END AS leg_role
          FROM game_best
         WHERE game_best.market = 'spreads' AND game_best.line IS NOT NULL
      ),
      prop_best AS (
        SELECT DISTINCT ON (q.fact_id, q.side)
               q.fact_id, q.side, q.line, q.price
          FROM byom_prop_book_quotes q
          JOIN byom_prop_facts p ON p.prop_key = q.fact_id
         WHERE p.sport = 'NFL' AND p.season = v_season
           AND p.log_status = 'logged'
           AND p.actual IS NOT NULL
           AND q.book = ANY (v_books)
           AND q.line IS NOT NULL
         ORDER BY q.fact_id, q.side,
           CASE WHEN q.side = 'under' THEN q.line ELSE NULL END DESC NULLS LAST,
           CASE WHEN q.side = 'over' THEN q.line ELSE NULL END ASC NULLS LAST,
           q.price DESC NULLS LAST,
           q.book
      ),
      legs AS (
        SELECT 'spreads'::text AS mkt,
               CASE
                 WHEN q.side = 'home'
                      AND (g.home_score - g.away_score + q.line) > 0 THEN 'win'
                 WHEN q.side = 'home'
                      AND (g.home_score - g.away_score + q.line) < 0 THEN 'loss'
                 WHEN q.side = 'away'
                      AND (g.away_score - g.home_score + q.line) > 0 THEN 'win'
                 WHEN q.side = 'away'
                      AND (g.away_score - g.home_score + q.line) < 0 THEN 'loss'
                 ELSE 'push'
               END AS res,
               g.week AS wk,
               CASE q.side WHEN 'home' THEN g.home_rest_days
                           ELSE g.away_rest_days END AS rest_days,
               g.is_primetime AS prime,
               CASE WHEN q.line < 0 THEN 'favorite'
                    WHEN q.line > 0 THEN 'underdog'
                    ELSE 'pickem' END AS leg_role,
               q.side AS leg_side,
               q.price AS px
          FROM byom_game_facts g
          JOIN game_best q
            ON q.fact_id = g.canonical_key AND q.market = 'spreads'
         WHERE g.sport = 'NFL' AND g.season = v_season
           AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
        UNION ALL
        SELECT 'h2h',
               CASE
                 WHEN g.home_score = g.away_score THEN 'tie'
                 WHEN q.side = 'home' AND g.home_score > g.away_score THEN 'win'
                 WHEN q.side = 'away' AND g.away_score > g.home_score THEN 'win'
                 ELSE 'loss'
               END,
               g.week,
               CASE q.side WHEN 'home' THEN g.home_rest_days
                           ELSE g.away_rest_days END,
               g.is_primetime,
               sr.leg_role,
               q.side,
               q.price
          FROM byom_game_facts g
          JOIN game_best q
            ON q.fact_id = g.canonical_key AND q.market = 'h2h'
          LEFT JOIN spread_role sr
            ON sr.fact_id = g.canonical_key AND sr.side = q.side
         WHERE g.sport = 'NFL' AND g.season = v_season
           AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
        UNION ALL
        SELECT 'totals',
               CASE
                 WHEN q.side = 'over'
                      AND (g.home_score + g.away_score) > q.line THEN 'win'
                 WHEN q.side = 'over'
                      AND (g.home_score + g.away_score) < q.line THEN 'loss'
                 WHEN q.side = 'under'
                      AND (g.home_score + g.away_score) < q.line THEN 'win'
                 WHEN q.side = 'under'
                      AND (g.home_score + g.away_score) > q.line THEN 'loss'
                 ELSE 'push'
               END,
               g.week,
               NULL::integer,
               g.is_primetime,
               NULL::text,
               NULL::text,
               q.price
          FROM byom_game_facts g
          JOIN game_best q
            ON q.fact_id = g.canonical_key AND q.market = 'totals'
         WHERE g.sport = 'NFL' AND g.season = v_season
           AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
        UNION ALL
        SELECT p.market,
               CASE
                 WHEN q.side = 'over' AND p.actual > q.line THEN 'win'
                 WHEN q.side = 'over' AND p.actual < q.line THEN 'loss'
                 WHEN q.side = 'under' AND p.actual < q.line THEN 'win'
                 WHEN q.side = 'under' AND p.actual > q.line THEN 'loss'
                 ELSE 'push'
               END,
               p.week,
               CASE WHEN p.team = g.home_team THEN g.home_rest_days
                    WHEN p.team = g.away_team THEN g.away_rest_days
                    ELSE NULL END,
               g.is_primetime,
               sr.leg_role,
               CASE WHEN p.team = g.home_team THEN 'home'
                    WHEN p.team = g.away_team THEN 'away'
                    ELSE NULL END,
               q.price
          FROM byom_prop_facts p
          JOIN prop_best q ON q.fact_id = p.prop_key
          LEFT JOIN byom_game_facts g ON g.canonical_key = p.canonical_key
          LEFT JOIN spread_role sr
            ON sr.fact_id = p.canonical_key
           AND sr.side = CASE WHEN p.team = g.home_team THEN 'home'
                              WHEN p.team = g.away_team THEN 'away'
                              ELSE NULL END
         WHERE p.sport = 'NFL' AND p.season = v_season
           AND p.log_status = 'logged'
           AND p.actual IS NOT NULL
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
      ),
      rolled AS (
        SELECT kept.mkt,
               count(*)::bigint AS n_bets,
               count(*) FILTER (WHERE kept.res = 'win')::bigint AS n_wins,
               count(*) FILTER (WHERE kept.res = 'loss')::bigint AS n_losses,
               count(*) FILTER (WHERE kept.res = 'push')::bigint AS n_pushes,
               count(*) FILTER (WHERE kept.res = 'tie')::bigint AS n_ties,
               coalesce(sum(public.published_pick_unit_profit(
                 kept.px, upper(kept.res))), 0) AS u,
               coalesce(sum(public.published_pick_unit_risked(
                 kept.px, upper(kept.res))), 0) AS r
          FROM kept
         GROUP BY kept.mkt
      )
      SELECT rolled.mkt, rolled.n_bets, rolled.n_wins, rolled.n_losses,
             rolled.n_pushes, rolled.n_ties,
             rolled.u,
             rolled.u / nullif(rolled.r, 0),
             rolled.r
        FROM rolled
       ORDER BY rolled.mkt;
    END
    $body$
  $fn$;

  REVOKE ALL ON FUNCTION public.byom_backtest(integer, jsonb, text[]) FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION public.byom_backtest(integer, jsonb, text[])
    TO anon, authenticated;

  IF to_regclass('public.byom_model_snapshots') IS NULL THEN
    RETURN;
  END IF;

  ALTER TABLE public.byom_model_snapshots
    ADD COLUMN IF NOT EXISTS result_version integer,
    ADD COLUMN IF NOT EXISTS units numeric,
    ADD COLUMN IF NOT EXISTS roi numeric,
    ADD COLUMN IF NOT EXISTS books text[];

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
      -- byom_best_line_v1
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
      v_units numeric;
      v_risked numeric;
      v_roi numeric;
      v_version integer;
      v_books text[];
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
           'primetime', 'markets', 'books')
           AND k.key NOT IN (
           'side', 'role', 'weeks', 'min_rest_days', 'max_rest_days',
           'primetime', 'markets', 'books'))
      THEN
        RAISE EXCEPTION 'filter keys must be lowercase';
      END IF;

      v_books := NULL;
      v_version := 1;
      IF v_filters ? 'books' THEN
        IF jsonb_typeof(v_filters->'books') <> 'array'
           OR jsonb_array_length(v_filters->'books') < 1
           OR jsonb_array_length(v_filters->'books') > 32
           OR EXISTS (
             SELECT 1 FROM jsonb_array_elements(v_filters->'books') AS e(val)
              WHERE jsonb_typeof(e.val) <> 'string'
                 OR lower(btrim(e.val #>> '{}')) !~ '^[a-z0-9_]{2,40}$')
        THEN
          RAISE EXCEPTION 'books must be 1 to 32 sportsbook slugs';
        END IF;
        v_books := ARRAY(
          SELECT DISTINCT lower(btrim(e.val #>> '{}'))
            FROM jsonb_array_elements(v_filters->'books') AS e(val));
        v_version := 2;
      END IF;

      SELECT COALESCE(jsonb_object_agg(e.key, e.value), '{}'::jsonb)
        INTO v_filters
        FROM jsonb_each(v_filters) AS e
       WHERE e.key IN (
         'side', 'role', 'weeks', 'min_rest_days', 'max_rest_days',
         'primetime', 'markets');

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
               'ties', b.ties,
               'units', b.units,
               'roi', b.roi
             ) ORDER BY b.market), '[]'::jsonb),
             sum(b.units),
             sum(b.risked)
        INTO v_bets, v_wins, v_losses, v_pushes, v_ties,
             v_summary, v_units, v_risked
        FROM byom_backtest(v_season, v_filters, v_books) AS b;
      IF v_risked IS NULL OR v_risked = 0 THEN
        v_roi := NULL;
      ELSE
        v_roi := v_units / v_risked;
      END IF;

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
        bets, wins, losses, pushes, ties,
        result_version, units, roi, books)
      VALUES (
        v_model, v_uid, v_season, v_filters, v_summary,
        v_bets, v_wins, v_losses, v_pushes, v_ties,
        v_version, v_units, v_roi, v_books);

      RETURN QUERY
      SELECT v_model, v_name, v_season, v_bets, v_wins, v_losses,
             v_pushes, v_ties;
    END
    $body$
  $save$;

  EXECUTE $list$
    CREATE OR REPLACE FUNCTION public.byom_list_models()
    RETURNS TABLE (
      model_id uuid,
      name text,
      sport text,
      filters jsonb,
      created_at timestamptz,
      updated_at timestamptz,
      snapshots jsonb
    )
    LANGUAGE plpgsql
    STABLE
    SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $body$
    #variable_conflict use_column
    DECLARE
      -- byom_saved_models_v1
      -- byom_best_line_v1
      v_uid uuid;
    BEGIN
      v_uid := auth.uid();
      IF v_uid IS NULL THEN
        RAISE EXCEPTION 'sign-in required';
      END IF;
      RETURN QUERY
      SELECT m.model_id, m.name, m.sport, m.filters, m.created_at, m.updated_at,
             COALESCE((
               SELECT jsonb_agg(jsonb_build_object(
                        'snapshot_id', s.snapshot_id,
                        'saved_at', s.saved_at,
                        'season', s.season,
                        'filters', s.filters,
                        'bets', s.bets,
                        'wins', s.wins,
                        'losses', s.losses,
                        'pushes', s.pushes,
                        'ties', s.ties,
                        'summary', s.summary,
                        'result_version', s.result_version,
                        'units', s.units,
                        'roi', s.roi,
                        'books', s.books
                      ) ORDER BY s.saved_at DESC)
                 FROM byom_model_snapshots s
                WHERE s.model_id = m.model_id AND s.user_id = v_uid
             ), '[]'::jsonb)
        FROM byom_models m
       WHERE m.user_id = v_uid
       ORDER BY m.updated_at DESC;
    END
    $body$
  $list$;
END $mig$;
