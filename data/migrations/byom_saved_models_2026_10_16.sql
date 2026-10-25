-- Saved BYOM models, keyed to the signed-in user.
--
-- UNAPPLIED. This file is NOT in data/view_migrations.ACTIVE_MIGRATIONS.
-- The worker must not run it. It cannot be used until sign-in is on.
-- Turning sign-in on is Matt's step. This file does not set AUTH_ENABLED
-- and does not change a sign-in screen.
--
-- byom_models and byom_model_snapshots are not granted to anon or to
-- authenticated. The grant sweep must not name them: GRANT on a missing
-- relation raises and rolls the sweep back. The RPCs are SECURITY DEFINER.
-- They take the user id from auth.uid() and never from an argument.
-- RLS policies are there for a later table grant. DEFINER bypasses RLS,
-- so each function filters on auth.uid() itself.
--
-- A save stores the byom_backtest result at that moment. A later rebuild
-- of the facts does not change a snapshot already stored.
--
-- Cap is 25 models per user. Saving an existing name updates that model
-- and appends a snapshot. It does not count as a new model.
--
-- There is no spread-size, price, or line filter. A stake or kelly
-- filter key is rejected. An allowlisted key in the wrong case is
-- rejected too; it is not stored under a different spelling. A single
-- moneyline or spread with no team and no favorite, underdog, or
-- pick'em is rejected. A single total whose side is not over or under
-- is rejected. A missing side is not stored as both sides. The
-- snapshot totals and the per-market summary come from one
-- byom_backtest read. A snapshot stores wins, losses, pushes, and ties.
--
-- One DO block. No CONCURRENTLY. Does not touch picks or the record views.

DO $mig$
BEGIN
  -- to_regclass only. A ::regclass cast in this same condition throws
  -- when the table is not there yet, and PL/pgSQL sends the whole
  -- condition as one query.
  IF to_regclass('public.byom_models') IS NOT NULL
     AND to_regclass('public.byom_model_snapshots') IS NOT NULL
     AND EXISTS (
       SELECT 1 FROM pg_proc p
         JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'byom_save_model'
          AND p.prosrc LIKE '%byom_saved_models_v1%')
     AND EXISTS (
       SELECT 1 FROM pg_proc p
         JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'byom_list_models'
          AND p.prosrc LIKE '%byom_saved_models_v1%')
     AND EXISTS (
       SELECT 1 FROM pg_proc p
         JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'byom_delete_model'
          AND p.prosrc LIKE '%byom_saved_models_v1%')
  THEN
    IF (SELECT relrowsecurity FROM pg_class
         WHERE oid = 'public.byom_models'::regclass)
       AND (SELECT relrowsecurity FROM pg_class
             WHERE oid = 'public.byom_model_snapshots'::regclass)
       AND EXISTS (
         SELECT 1 FROM pg_policy
          WHERE polrelid = 'public.byom_models'::regclass
            AND polname = 'own byom_models')
       AND EXISTS (
         SELECT 1 FROM pg_policy
          WHERE polrelid = 'public.byom_model_snapshots'::regclass
            AND polname = 'own byom_model_snapshots')
       AND has_function_privilege(
         'authenticated', 'public.byom_save_model(text, jsonb, integer)', 'EXECUTE')
       AND has_function_privilege(
         'authenticated', 'public.byom_list_models()', 'EXECUTE')
       AND has_function_privilege(
         'authenticated', 'public.byom_delete_model(uuid)', 'EXECUTE')
       AND NOT has_function_privilege(
         'anon', 'public.byom_save_model(text, jsonb, integer)', 'EXECUTE')
       AND NOT has_function_privilege(
         'anon', 'public.byom_list_models()', 'EXECUTE')
       AND NOT has_function_privilege(
         'anon', 'public.byom_delete_model(uuid)', 'EXECUTE')
       AND NOT has_table_privilege('anon', 'public.byom_models', 'SELECT')
       AND NOT has_table_privilege(
         'authenticated', 'public.byom_models', 'SELECT')
       AND NOT has_table_privilege(
         'anon', 'public.byom_model_snapshots', 'SELECT')
       AND NOT has_table_privilege(
         'authenticated', 'public.byom_model_snapshots', 'SELECT')
    THEN
      RAISE NOTICE 'byom saved models already present - skipping';
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.byom_models (
    model_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    name        TEXT NOT NULL,
    sport       TEXT NOT NULL DEFAULT 'NFL',
    filters     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT byom_models_user_name UNIQUE (user_id, name)
  );

  CREATE TABLE IF NOT EXISTS public.byom_model_snapshots (
    snapshot_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        UUID NOT NULL REFERENCES public.byom_models (model_id)
                      ON DELETE CASCADE,
    user_id         UUID NOT NULL,
    saved_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    season          INTEGER NOT NULL,
    filters         JSONB NOT NULL,
    summary         JSONB NOT NULL,
    bets            BIGINT NOT NULL,
    wins            BIGINT NOT NULL,
    losses          BIGINT NOT NULL,
    pushes          BIGINT NOT NULL,
    ties            BIGINT NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_byom_models_user
    ON public.byom_models (user_id);
  CREATE INDEX IF NOT EXISTS idx_byom_model_snapshots_model
    ON public.byom_model_snapshots (model_id, saved_at DESC);

  REVOKE ALL ON public.byom_models FROM PUBLIC, anon, authenticated;
  REVOKE ALL ON public.byom_model_snapshots FROM PUBLIC, anon, authenticated;
  ALTER TABLE public.byom_models ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.byom_model_snapshots ENABLE ROW LEVEL SECURITY;

  DROP POLICY IF EXISTS "own byom_models" ON public.byom_models;
  CREATE POLICY "own byom_models"
    ON public.byom_models
    FOR ALL
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

  DROP POLICY IF EXISTS "own byom_model_snapshots" ON public.byom_model_snapshots;
  CREATE POLICY "own byom_model_snapshots"
    ON public.byom_model_snapshots
    FOR ALL
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

  EXECUTE $fn$
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
           'primetime', 'markets')
           AND k.key NOT IN (
           'side', 'role', 'weeks', 'min_rest_days', 'max_rest_days',
           'primetime', 'markets'))
      THEN
        RAISE EXCEPTION 'filter keys must be lowercase';
      END IF;
      SELECT COALESCE(jsonb_object_agg(e.key, e.value), '{}'::jsonb)
        INTO v_filters
        FROM jsonb_each(v_filters) AS e
       WHERE e.key IN (
         'side', 'role', 'weeks', 'min_rest_days', 'max_rest_days',
         'primetime', 'markets');

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
    $body$
  $fn$;

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
                        'summary', s.summary
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

  EXECUTE $del$
    CREATE OR REPLACE FUNCTION public.byom_delete_model(p_model_id uuid)
    RETURNS uuid
    LANGUAGE plpgsql
    VOLATILE
    SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $body$
    DECLARE
      -- byom_saved_models_v1
      v_uid uuid;
      v_id uuid;
    BEGIN
      v_uid := auth.uid();
      IF v_uid IS NULL THEN
        RAISE EXCEPTION 'sign-in required';
      END IF;
      DELETE FROM byom_models m
       WHERE m.model_id = p_model_id AND m.user_id = v_uid
       RETURNING m.model_id INTO v_id;
      IF v_id IS NULL THEN
        RAISE EXCEPTION 'model not found';
      END IF;
      RETURN v_id;
    END
    $body$
  $del$;

  REVOKE ALL ON FUNCTION public.byom_save_model(text, jsonb, integer)
    FROM PUBLIC, anon;
  REVOKE ALL ON FUNCTION public.byom_list_models() FROM PUBLIC, anon;
  REVOKE ALL ON FUNCTION public.byom_delete_model(uuid) FROM PUBLIC, anon;
  GRANT EXECUTE ON FUNCTION public.byom_save_model(text, jsonb, integer)
    TO authenticated;
  GRANT EXECUTE ON FUNCTION public.byom_list_models() TO authenticated;
  GRANT EXECUTE ON FUNCTION public.byom_delete_model(uuid) TO authenticated;
END $mig$;
