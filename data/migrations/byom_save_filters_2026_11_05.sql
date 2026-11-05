-- Build Your Own Model: a saved model keeps every filter the preview grades.
--
-- Matt, 2026-11-05 ("Yes continue on your next steps recommendation").
-- The live byom_save_model (byom_nhl_2026_11_05.sql) kept 9 keys: side,
-- role, weeks, rest, primetime, markets, prop_side and sport. It refused
-- min_line / max_line ("price, line, and stake filters are not accepted")
-- and silently dropped min/max_price, team spread, game total, months,
-- weekdays, kick_slots, opponents and player, so a saved prop model
-- graded a different set of bets than the preview it was saved from.
-- Measured 2026-11-05: byom_models held 0 rows, so nothing stored changes.
--
-- Now the save accepts the 22 keys byom_legs grades. An unknown key is
-- refused by name (it was dropped). A null value is not stored. The
-- values are checked by the same parser as the preview: the save grades
-- through byom_backtest, which raises on a bad month, weekday, slot,
-- player or prop side before any row is written. Stake and kelly are
-- still refused. An NHL model cannot be a pick'em (a puck line is 1.5).
--
-- The body is byom_nhl_2026_11_05.sql's with those changes; the markers
-- byom_saved_models_v1, byom_prop_side, byom_nba_props and byom_nhl_v1
-- are kept, so the NHL file still skips. Skips once the body carries
-- byom_save_filters_v1. CREATE OR REPLACE keeps the grants. Does not
-- write picks.

DO $mig$
BEGIN
  IF to_regprocedure('public.byom_save_model(text, jsonb, integer)') IS NULL THEN
    RAISE EXCEPTION 'byom_save_model is not present; apply byom_nhl_2026_11_05.sql first';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_proc p
     WHERE p.oid = to_regprocedure('public.byom_save_model(text, jsonb, integer)')
       AND position('byom_save_filters_v1' in p.prosrc) > 0
       AND position('byom_nhl_v1' in p.prosrc) > 0
  ) THEN
    RAISE NOTICE 'byom save filters already present - skipping';
    RETURN;
  END IF;

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
      -- byom_prop_side
      -- byom_nba_props
      -- byom_nhl_v1
      -- byom_save_filters_v1
      v_uid uuid;
      v_sport text;
      v_grade jsonb;
      v_name text;
      v_filters jsonb;
      v_season integer;
      v_month integer;
      v_year integer;
      v_model uuid;
      v_saved_sport text;
      v_count integer;
      v_bets bigint;
      v_wins bigint;
      v_losses bigint;
      v_pushes bigint;
      v_ties bigint;
      v_summary jsonb;
      v_bad text;
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
         WHERE lower(k.key) IN ('stake', 'kelly'))
      THEN
        RAISE EXCEPTION 'stake filters are not accepted';
      END IF;
      -- Every key the preview grades (byom_legs), and only those. An
      -- unknown key is refused, never dropped (Matt, 2026-11-05: a saved
      -- model kept 9 of the builder's 22 keys and lost the rest silently).
      IF EXISTS (
        SELECT 1 FROM jsonb_object_keys(v_filters) AS k(key)
         WHERE lower(k.key) IN (
           'side', 'role', 'weeks', 'min_rest_days', 'max_rest_days',
           'primetime', 'markets', 'prop_side', 'sport', 'min_line', 'max_line',
           'min_price', 'max_price', 'min_team_spread', 'max_team_spread',
           'min_game_total', 'max_game_total', 'months', 'weekdays',
           'kick_slots', 'opponents', 'player')
           AND k.key NOT IN (
           'side', 'role', 'weeks', 'min_rest_days', 'max_rest_days',
           'primetime', 'markets', 'prop_side', 'sport', 'min_line', 'max_line',
           'min_price', 'max_price', 'min_team_spread', 'max_team_spread',
           'min_game_total', 'max_game_total', 'months', 'weekdays',
           'kick_slots', 'opponents', 'player'))
      THEN
        RAISE EXCEPTION 'filter keys must be lowercase';
      END IF;
      SELECT k.key INTO v_bad
        FROM jsonb_object_keys(v_filters) AS k(key)
       WHERE k.key NOT IN (
         'side', 'role', 'weeks', 'min_rest_days', 'max_rest_days',
         'primetime', 'markets', 'prop_side', 'sport', 'min_line', 'max_line',
         'min_price', 'max_price', 'min_team_spread', 'max_team_spread',
         'min_game_total', 'max_game_total', 'months', 'weekdays',
         'kick_slots', 'opponents', 'player')
       LIMIT 1;
      IF v_bad IS NOT NULL THEN
        RAISE EXCEPTION 'unknown filter key: %', v_bad;
      END IF;
      -- A null value is the same as no filter, so it is not stored.
      v_filters := jsonb_strip_nulls(v_filters);

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
             'player_tackles_assists', 'player_sacks',
             'player_points', 'player_rebounds', 'player_assists', 'player_threes',
             'player_points_rebounds_assists', 'player_points_rebounds',
             'player_points_assists', 'player_rebounds_assists',
             'player_blocks', 'player_steals', 'player_blocks_steals',
             'player_turnovers', 'player_double_double', 'player_triple_double')
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
             'player_tackles_assists', 'player_sacks',
             'player_points', 'player_rebounds', 'player_assists', 'player_threes',
             'player_points_rebounds_assists', 'player_points_rebounds',
             'player_points_assists', 'player_rebounds_assists',
             'player_blocks', 'player_steals', 'player_blocks_steals',
             'player_turnovers', 'player_double_double', 'player_triple_double'))
      ) THEN
        v_filters := v_filters - 'prop_side';
      END IF;

      v_sport := COALESCE(NULLIF(v_filters->>'sport', ''), 'NFL');
      IF v_sport NOT IN ('NFL', 'NBA', 'NHL') THEN
        RAISE EXCEPTION 'unknown sport';
      END IF;
      -- An NHL puck line is always 1.5, so no game is a pick'em.
      IF v_sport = 'NHL' AND v_filters->>'role' = 'pickem' THEN
        RAISE EXCEPTION 'Pick''em is not an NHL role.';
      END IF;
      v_grade := v_filters;
      v_filters := v_filters - 'sport';

      IF p_season IS NULL THEN
        v_month := EXTRACT(MONTH FROM (now() AT TIME ZONE 'America/New_York'))::integer;
        v_year := EXTRACT(YEAR FROM (now() AT TIME ZONE 'America/New_York'))::integer;
        IF v_sport IN ('NBA', 'NHL') THEN
          IF v_month >= 10 THEN
            v_season := v_year + 1;
          ELSE
            v_season := v_year;
          END IF;
        ELSIF v_month >= 9 THEN
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
        FROM byom_backtest(v_season, v_grade) AS b;

      SELECT m.model_id, m.sport INTO v_model, v_saved_sport
        FROM byom_models m
       WHERE m.user_id = v_uid AND m.name = v_name;

      -- Same name on the other sport must not flip that row. The
      -- unique key is still (user_id, name), so this refuses instead
      -- of inserting a second row.
      IF v_model IS NOT NULL AND v_saved_sport IS DISTINCT FROM v_sport THEN
        RAISE EXCEPTION 'name is saved on another sport';
      END IF;

      IF v_model IS NULL THEN
        SELECT count(*) INTO v_count
          FROM byom_models m
         WHERE m.user_id = v_uid;
        IF v_count >= 25 THEN
          RAISE EXCEPTION 'byom model cap is 25';
        END IF;
        INSERT INTO byom_models (user_id, name, sport, filters)
        VALUES (v_uid, v_name, v_sport, v_filters)
        RETURNING byom_models.model_id INTO v_model;
      ELSE
        UPDATE byom_models m
           SET filters = v_filters, sport = v_sport, updated_at = now()
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
  $fn$;
END
$mig$;
