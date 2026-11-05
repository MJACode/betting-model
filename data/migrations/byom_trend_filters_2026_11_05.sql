-- Build Your Own Model: trend filters on every bet (Matt, 2026-11-05:
-- "Add 1-3 for now"). Five new filter keys, graded by byom_legs and kept
-- by byom_save_model:
--
--   line_move     toward / against / none. The DraftKings line since the
--                 first stored quote (the opener), on this bet's side. A
--                 spread moves toward home when the home number falls, a
--                 total or a prop toward the over when the line rises, a
--                 moneyline toward a side when its implied chance rises.
--                 Official: the move up to the quote that became the bet,
--                 so the lock is the first quote where the move fits. The
--                 close is never used for an official bet (it is not known
--                 then). Close: the closing line against the opener.
--   prev_result   won / lost. The bet team's previous game this season.
--   prev_ats      covered / not_covered. The same game against its line.
--   prev_total    over / under. BOTH teams' previous games went over
--                 (or under). A team's first game has no previous game.
--   division_game true / false. Both teams in one division that season.
--
-- A last-game filter is not known until that game is over (4 hours after
-- the bet team's previous start; both teams' for prev_total). An official
-- lock is then the quote still in force at that moment, made official at
-- that moment: a candidate is stored only when the quote changes, so a
-- line that did not move after the previous game is not dropped. Divisions are byom_team_division, a fixed
-- list (NFL since 2002, NBA since 2004-05, NHL from 2013-14 with the
-- 2020-21 temporary divisions and the 2021-22 realignment). Team codes
-- are the ones byom_game_facts holds (measured 2026-11-05).
--
-- byom_legs is byom_nhl_2026_11_05.sql's body and byom_save_model is
-- byom_save_filters_2026_11_05.sql's, with these keys added. Every earlier
-- marker is kept, so those files still skip; plan_cache_mode stays forced.
-- byom_line_move and byom_team_division have no SET clause, so they can
-- inline. Skips once both bodies carry byom_trend_filters_v1. Does not
-- write picks.

DO $mig$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_proc p
     WHERE p.oid = to_regprocedure('public.byom_legs(integer, jsonb, text)')
       AND position('byom_trend_filters_v1' in p.prosrc) > 0
       AND position('p_filters %s' in p.prosrc) = 0
       AND 'plan_cache_mode=force_custom_plan' = ANY (p.proconfig)
  ) AND EXISTS (
    SELECT 1 FROM pg_proc p
     WHERE p.oid = to_regprocedure('public.byom_save_model(text, jsonb, integer)')
       AND position('byom_trend_filters_v1' in p.prosrc) > 0
  ) AND to_regprocedure('public.byom_line_move(text, text, numeric, numeric, numeric, numeric)') IS NOT NULL
    AND to_regprocedure('public.byom_team_division(text, integer, text)') IS NOT NULL
  THEN
    RAISE NOTICE 'byom trend filters already present - skipping';
    RETURN;
  END IF;

  EXECUTE $fn$
  CREATE OR REPLACE FUNCTION public.byom_team_division(
    p_sport text, p_season integer, p_team text)
  RETURNS text LANGUAGE sql IMMUTABLE
  AS $body$
    -- byom_trend_filters_v1. Fixed list; season is the label byom uses.
    SELECT d.division
      FROM (VALUES
      ('NFL', 'BUF', 'AFC East', 2000, 9999),
      ('NFL', 'MIA', 'AFC East', 2000, 9999),
      ('NFL', 'NE', 'AFC East', 2000, 9999),
      ('NFL', 'NYJ', 'AFC East', 2000, 9999),
      ('NFL', 'BAL', 'AFC North', 2000, 9999),
      ('NFL', 'CIN', 'AFC North', 2000, 9999),
      ('NFL', 'CLE', 'AFC North', 2000, 9999),
      ('NFL', 'PIT', 'AFC North', 2000, 9999),
      ('NFL', 'HOU', 'AFC South', 2000, 9999),
      ('NFL', 'IND', 'AFC South', 2000, 9999),
      ('NFL', 'JAX', 'AFC South', 2000, 9999),
      ('NFL', 'TEN', 'AFC South', 2000, 9999),
      ('NFL', 'DEN', 'AFC West', 2000, 9999),
      ('NFL', 'KC', 'AFC West', 2000, 9999),
      ('NFL', 'LAC', 'AFC West', 2000, 9999),
      ('NFL', 'LV', 'AFC West', 2000, 9999),
      ('NFL', 'DAL', 'NFC East', 2000, 9999),
      ('NFL', 'NYG', 'NFC East', 2000, 9999),
      ('NFL', 'PHI', 'NFC East', 2000, 9999),
      ('NFL', 'WAS', 'NFC East', 2000, 9999),
      ('NFL', 'CHI', 'NFC North', 2000, 9999),
      ('NFL', 'DET', 'NFC North', 2000, 9999),
      ('NFL', 'GB', 'NFC North', 2000, 9999),
      ('NFL', 'MIN', 'NFC North', 2000, 9999),
      ('NFL', 'ATL', 'NFC South', 2000, 9999),
      ('NFL', 'CAR', 'NFC South', 2000, 9999),
      ('NFL', 'NO', 'NFC South', 2000, 9999),
      ('NFL', 'TB', 'NFC South', 2000, 9999),
      ('NFL', 'ARI', 'NFC West', 2000, 9999),
      ('NFL', 'LA', 'NFC West', 2000, 9999),
      ('NFL', 'SEA', 'NFC West', 2000, 9999),
      ('NFL', 'SF', 'NFC West', 2000, 9999),
      ('NBA', 'BKN', 'Atlantic', 2005, 9999),
      ('NBA', 'BOS', 'Atlantic', 2005, 9999),
      ('NBA', 'NYK', 'Atlantic', 2005, 9999),
      ('NBA', 'PHI', 'Atlantic', 2005, 9999),
      ('NBA', 'TOR', 'Atlantic', 2005, 9999),
      ('NBA', 'CHI', 'Central', 2005, 9999),
      ('NBA', 'CLE', 'Central', 2005, 9999),
      ('NBA', 'DET', 'Central', 2005, 9999),
      ('NBA', 'IND', 'Central', 2005, 9999),
      ('NBA', 'MIL', 'Central', 2005, 9999),
      ('NBA', 'ATL', 'Southeast', 2005, 9999),
      ('NBA', 'CHA', 'Southeast', 2005, 9999),
      ('NBA', 'MIA', 'Southeast', 2005, 9999),
      ('NBA', 'ORL', 'Southeast', 2005, 9999),
      ('NBA', 'WAS', 'Southeast', 2005, 9999),
      ('NBA', 'DEN', 'Northwest', 2005, 9999),
      ('NBA', 'MIN', 'Northwest', 2005, 9999),
      ('NBA', 'OKC', 'Northwest', 2005, 9999),
      ('NBA', 'POR', 'Northwest', 2005, 9999),
      ('NBA', 'UTA', 'Northwest', 2005, 9999),
      ('NBA', 'GSW', 'Pacific', 2005, 9999),
      ('NBA', 'LAC', 'Pacific', 2005, 9999),
      ('NBA', 'LAL', 'Pacific', 2005, 9999),
      ('NBA', 'PHX', 'Pacific', 2005, 9999),
      ('NBA', 'SAC', 'Pacific', 2005, 9999),
      ('NBA', 'DAL', 'Southwest', 2005, 9999),
      ('NBA', 'HOU', 'Southwest', 2005, 9999),
      ('NBA', 'MEM', 'Southwest', 2005, 9999),
      ('NBA', 'NOP', 'Southwest', 2005, 9999),
      ('NBA', 'SAS', 'Southwest', 2005, 9999),
      ('NHL', 'BOS', 'Atlantic', 2014, 2020),
      ('NHL', 'BUF', 'Atlantic', 2014, 2020),
      ('NHL', 'DET', 'Atlantic', 2014, 2020),
      ('NHL', 'FLA', 'Atlantic', 2014, 2020),
      ('NHL', 'MTL', 'Atlantic', 2014, 2020),
      ('NHL', 'OTT', 'Atlantic', 2014, 2020),
      ('NHL', 'TBL', 'Atlantic', 2014, 2020),
      ('NHL', 'TOR', 'Atlantic', 2014, 2020),
      ('NHL', 'CAR', 'Metropolitan', 2014, 2020),
      ('NHL', 'CBJ', 'Metropolitan', 2014, 2020),
      ('NHL', 'NJD', 'Metropolitan', 2014, 2020),
      ('NHL', 'NYI', 'Metropolitan', 2014, 2020),
      ('NHL', 'NYR', 'Metropolitan', 2014, 2020),
      ('NHL', 'PHI', 'Metropolitan', 2014, 2020),
      ('NHL', 'PIT', 'Metropolitan', 2014, 2020),
      ('NHL', 'WSH', 'Metropolitan', 2014, 2020),
      ('NHL', 'CHI', 'Central', 2014, 2020),
      ('NHL', 'COL', 'Central', 2014, 2020),
      ('NHL', 'DAL', 'Central', 2014, 2020),
      ('NHL', 'MIN', 'Central', 2014, 2020),
      ('NHL', 'NSH', 'Central', 2014, 2020),
      ('NHL', 'STL', 'Central', 2014, 2020),
      ('NHL', 'WPG', 'Central', 2014, 2020),
      ('NHL', 'ANA', 'Pacific', 2014, 2020),
      ('NHL', 'CGY', 'Pacific', 2014, 2020),
      ('NHL', 'EDM', 'Pacific', 2014, 2020),
      ('NHL', 'LAK', 'Pacific', 2014, 2020),
      ('NHL', 'SJS', 'Pacific', 2014, 2020),
      ('NHL', 'UTA', 'Pacific', 2014, 2020),
      ('NHL', 'VAN', 'Pacific', 2014, 2020),
      ('NHL', 'VGK', 'Pacific', 2014, 2020),
      ('NHL', 'CGY', 'North', 2021, 2021),
      ('NHL', 'EDM', 'North', 2021, 2021),
      ('NHL', 'MTL', 'North', 2021, 2021),
      ('NHL', 'OTT', 'North', 2021, 2021),
      ('NHL', 'TOR', 'North', 2021, 2021),
      ('NHL', 'VAN', 'North', 2021, 2021),
      ('NHL', 'WPG', 'North', 2021, 2021),
      ('NHL', 'BOS', 'East', 2021, 2021),
      ('NHL', 'BUF', 'East', 2021, 2021),
      ('NHL', 'NJD', 'East', 2021, 2021),
      ('NHL', 'NYI', 'East', 2021, 2021),
      ('NHL', 'NYR', 'East', 2021, 2021),
      ('NHL', 'PHI', 'East', 2021, 2021),
      ('NHL', 'PIT', 'East', 2021, 2021),
      ('NHL', 'WSH', 'East', 2021, 2021),
      ('NHL', 'CAR', 'Central', 2021, 2021),
      ('NHL', 'CBJ', 'Central', 2021, 2021),
      ('NHL', 'CHI', 'Central', 2021, 2021),
      ('NHL', 'DAL', 'Central', 2021, 2021),
      ('NHL', 'DET', 'Central', 2021, 2021),
      ('NHL', 'FLA', 'Central', 2021, 2021),
      ('NHL', 'NSH', 'Central', 2021, 2021),
      ('NHL', 'TBL', 'Central', 2021, 2021),
      ('NHL', 'ANA', 'West', 2021, 2021),
      ('NHL', 'COL', 'West', 2021, 2021),
      ('NHL', 'LAK', 'West', 2021, 2021),
      ('NHL', 'MIN', 'West', 2021, 2021),
      ('NHL', 'SJS', 'West', 2021, 2021),
      ('NHL', 'STL', 'West', 2021, 2021),
      ('NHL', 'UTA', 'West', 2021, 2021),
      ('NHL', 'VGK', 'West', 2021, 2021),
      ('NHL', 'BOS', 'Atlantic', 2022, 9999),
      ('NHL', 'BUF', 'Atlantic', 2022, 9999),
      ('NHL', 'DET', 'Atlantic', 2022, 9999),
      ('NHL', 'FLA', 'Atlantic', 2022, 9999),
      ('NHL', 'MTL', 'Atlantic', 2022, 9999),
      ('NHL', 'OTT', 'Atlantic', 2022, 9999),
      ('NHL', 'TBL', 'Atlantic', 2022, 9999),
      ('NHL', 'TOR', 'Atlantic', 2022, 9999),
      ('NHL', 'CAR', 'Metropolitan', 2022, 9999),
      ('NHL', 'CBJ', 'Metropolitan', 2022, 9999),
      ('NHL', 'NJD', 'Metropolitan', 2022, 9999),
      ('NHL', 'NYI', 'Metropolitan', 2022, 9999),
      ('NHL', 'NYR', 'Metropolitan', 2022, 9999),
      ('NHL', 'PHI', 'Metropolitan', 2022, 9999),
      ('NHL', 'PIT', 'Metropolitan', 2022, 9999),
      ('NHL', 'WSH', 'Metropolitan', 2022, 9999),
      ('NHL', 'CHI', 'Central', 2022, 9999),
      ('NHL', 'COL', 'Central', 2022, 9999),
      ('NHL', 'DAL', 'Central', 2022, 9999),
      ('NHL', 'MIN', 'Central', 2022, 9999),
      ('NHL', 'NSH', 'Central', 2022, 9999),
      ('NHL', 'STL', 'Central', 2022, 9999),
      ('NHL', 'UTA', 'Central', 2022, 9999),
      ('NHL', 'WPG', 'Central', 2022, 9999),
      ('NHL', 'ANA', 'Pacific', 2022, 9999),
      ('NHL', 'CGY', 'Pacific', 2022, 9999),
      ('NHL', 'EDM', 'Pacific', 2022, 9999),
      ('NHL', 'LAK', 'Pacific', 2022, 9999),
      ('NHL', 'SEA', 'Pacific', 2022, 9999),
      ('NHL', 'SJS', 'Pacific', 2022, 9999),
      ('NHL', 'VAN', 'Pacific', 2022, 9999),
      ('NHL', 'VGK', 'Pacific', 2022, 9999)
      ) AS d(sport, team, division, first_season, last_season)
     WHERE d.sport = p_sport AND d.team = p_team
       AND p_season BETWEEN d.first_season AND d.last_season
  $body$;
  $fn$;

  EXECUTE $fn$
  CREATE OR REPLACE FUNCTION public.byom_line_move(
    p_market text, p_side text, p_open_point numeric, p_open_price numeric,
    p_point numeric, p_price numeric)
  RETURNS text LANGUAGE sql IMMUTABLE
  AS $body$
    -- byom_trend_filters_v1. A spread's point is the HOME number.
    SELECT CASE
      WHEN p_market = 'h2h' THEN
        CASE
          WHEN p_open_price IS NULL OR p_price IS NULL
               OR pg_catalog.abs(p_open_price) < 100 OR pg_catalog.abs(p_price) < 100 THEN NULL
          WHEN (CASE WHEN p_price < 0 THEN -p_price / (-p_price + 100) ELSE 100 / (p_price + 100) END)
             > (CASE WHEN p_open_price < 0 THEN -p_open_price / (-p_open_price + 100) ELSE 100 / (p_open_price + 100) END)
            THEN 'toward'
          WHEN (CASE WHEN p_price < 0 THEN -p_price / (-p_price + 100) ELSE 100 / (p_price + 100) END)
             < (CASE WHEN p_open_price < 0 THEN -p_open_price / (-p_open_price + 100) ELSE 100 / (p_open_price + 100) END)
            THEN 'against'
          ELSE 'none'
        END
      WHEN p_open_point IS NULL OR p_point IS NULL THEN NULL
      WHEN p_point = p_open_point THEN 'none'
      WHEN p_market = 'spreads' AND p_side = 'home' THEN
        CASE WHEN p_point < p_open_point THEN 'toward' ELSE 'against' END
      WHEN p_market = 'spreads' AND p_side = 'away' THEN
        CASE WHEN p_point > p_open_point THEN 'toward' ELSE 'against' END
      WHEN p_side = 'over' THEN
        CASE WHEN p_point > p_open_point THEN 'toward' ELSE 'against' END
      WHEN p_side = 'under' THEN
        CASE WHEN p_point < p_open_point THEN 'toward' ELSE 'against' END
    END
  $body$;
  $fn$;

  EXECUTE $fn$
  CREATE OR REPLACE FUNCTION public.byom_legs(
    p_season integer,
    p_filters jsonb DEFAULT '{}'::jsonb,
    p_timing text DEFAULT NULL
  )
  RETURNS TABLE (
    timing text, market text, leg_side text, canonical_key text,
    commence_time timestamptz, week integer, home_team text, away_team text,
    team text, player_name text, point numeric, price numeric,
    result text, locked_at timestamptz, leg_role text,
    priced boolean, no_line boolean, units numeric, risk numeric
  )
  LANGUAGE plpgsql
  STABLE
  SECURITY INVOKER
  SET search_path = public, pg_temp
  SET plan_cache_mode = force_custom_plan
  AS $body$
  DECLARE
    -- byom_official_legs_v1
    -- byom_official_lock_bands_v1
    -- byom_official_market_pushdown_v1
    -- byom_prop_lookup_v1
    -- byom_nhl_v1
    -- byom_trend_filters_v1
    v_season integer;
    v_sport text;
    v_side text;
    v_prop_side text;
    v_role text;
    v_weeks integer[];
    v_min_rest integer;
    v_max_rest integer;
    v_primetime boolean;
    v_markets text[];
    v_min_line numeric;
    v_max_line numeric;
    v_min_price numeric;
    v_max_price numeric;
    v_min_spread numeric;
    v_max_spread numeric;
    v_min_total numeric;
    v_max_total numeric;
    v_months integer[];
    v_weekdays integer[];
    v_slots text[];
    v_opponents text[];
    v_player text;
    v_month integer;
    v_year integer;
    v_bad text;
    v_line_move text;
    v_prev_result text;
    v_prev_ats text;
    v_prev_total text;
    v_division boolean;
    v_needs_prev boolean;
  BEGIN
    IF p_timing IS NOT NULL AND p_timing NOT IN ('official', 'close') THEN
      RAISE EXCEPTION 'timing is official or close';
    END IF;
    IF p_filters IS NULL OR p_filters = 'null'::jsonb THEN
      p_filters := '{}'::jsonb;
    END IF;
    IF jsonb_typeof(p_filters) <> 'object' THEN
      RAISE EXCEPTION 'unknown filter key: filters must be an object';
    END IF;
    SELECT k.key INTO v_bad
      FROM jsonb_object_keys(p_filters) AS k(key)
     WHERE k.key NOT IN (
       'side', 'role', 'weeks', 'min_rest_days', 'max_rest_days',
       'primetime', 'markets', 'prop_side', 'sport', 'min_line', 'max_line',
       'min_price', 'max_price', 'min_team_spread', 'max_team_spread',
       'min_game_total', 'max_game_total', 'months', 'weekdays',
       'kick_slots', 'opponents', 'player', 'line_move', 'prev_result',
       'prev_ats', 'prev_total', 'division_game')
     LIMIT 1;
    IF v_bad IS NOT NULL THEN
      RAISE EXCEPTION 'unknown filter key: %', v_bad;
    END IF;

    v_sport := COALESCE(NULLIF(p_filters->>'sport', ''), 'NFL');
    IF v_sport NOT IN ('NFL', 'NBA', 'NHL') THEN
      RAISE EXCEPTION 'unknown sport';
    END IF;

    IF p_season IS NULL THEN
      v_month := EXTRACT(MONTH FROM (now() AT TIME ZONE 'America/New_York'))::integer;
      v_year := EXTRACT(YEAR FROM (now() AT TIME ZONE 'America/New_York'))::integer;
      -- NBA and NHL seasons are the ending year; October on is next year.
      IF v_sport IN ('NBA', 'NHL') THEN
        v_season := CASE WHEN v_month >= 10 THEN v_year + 1 ELSE v_year END;
      ELSIF v_month >= 9 THEN
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
    IF v_role IS NOT NULL AND v_role NOT IN ('favorite', 'underdog', 'pickem') THEN
      RAISE EXCEPTION 'unknown filter key: role';
    END IF;
    v_min_rest := (p_filters->>'min_rest_days')::integer;
    v_max_rest := (p_filters->>'max_rest_days')::integer;
    IF jsonb_exists(p_filters, 'primetime') AND p_filters->>'primetime' IS NOT NULL
       AND p_filters->>'primetime' <> '' THEN
      v_primetime := (p_filters->>'primetime')::boolean;
    END IF;
    IF jsonb_typeof(p_filters->'weeks') = 'array'
       AND jsonb_array_length(p_filters->'weeks') > 0 THEN
      v_weeks := ARRAY(
        SELECT (jsonb_array_elements_text(p_filters->'weeks'))::integer);
    END IF;
    IF jsonb_typeof(p_filters->'markets') = 'array'
       AND jsonb_array_length(p_filters->'markets') > 0 THEN
      v_markets := ARRAY(SELECT jsonb_array_elements_text(p_filters->'markets'));
    END IF;
    v_min_line := NULLIF(p_filters->>'min_line', '')::numeric;
    v_max_line := NULLIF(p_filters->>'max_line', '')::numeric;
    v_min_price := NULLIF(p_filters->>'min_price', '')::numeric;
    v_max_price := NULLIF(p_filters->>'max_price', '')::numeric;
    v_min_spread := NULLIF(p_filters->>'min_team_spread', '')::numeric;
    v_max_spread := NULLIF(p_filters->>'max_team_spread', '')::numeric;
    v_min_total := NULLIF(p_filters->>'min_game_total', '')::numeric;
    v_max_total := NULLIF(p_filters->>'max_game_total', '')::numeric;
    v_player := NULLIF(btrim(COALESCE(p_filters->>'player', '')), '');
    IF v_player IS NOT NULL AND char_length(v_player) > 80 THEN
      RAISE EXCEPTION 'unknown filter key: player';
    END IF;
    IF jsonb_typeof(p_filters->'months') = 'array'
       AND jsonb_array_length(p_filters->'months') > 0 THEN
      v_months := ARRAY(
        SELECT (jsonb_array_elements_text(p_filters->'months'))::integer);
      IF EXISTS (SELECT 1 FROM unnest(v_months) AS m(m) WHERE m < 1 OR m > 12) THEN
        RAISE EXCEPTION 'unknown filter key: months';
      END IF;
    ELSIF jsonb_exists(p_filters, 'months') AND jsonb_typeof(p_filters->'months') NOT IN ('array', 'null') THEN
      RAISE EXCEPTION 'unknown filter key: months';
    END IF;
    IF jsonb_typeof(p_filters->'weekdays') = 'array'
       AND jsonb_array_length(p_filters->'weekdays') > 0 THEN
      v_weekdays := ARRAY(
        SELECT (jsonb_array_elements_text(p_filters->'weekdays'))::integer);
      IF EXISTS (SELECT 1 FROM unnest(v_weekdays) AS d(d) WHERE d < 0 OR d > 6) THEN
        RAISE EXCEPTION 'unknown filter key: weekdays';
      END IF;
    ELSIF jsonb_exists(p_filters, 'weekdays') AND jsonb_typeof(p_filters->'weekdays') NOT IN ('array', 'null') THEN
      RAISE EXCEPTION 'unknown filter key: weekdays';
    END IF;
    IF jsonb_typeof(p_filters->'kick_slots') = 'array'
       AND jsonb_array_length(p_filters->'kick_slots') > 0 THEN
      v_slots := ARRAY(SELECT jsonb_array_elements_text(p_filters->'kick_slots'));
      IF EXISTS (SELECT 1 FROM unnest(v_slots) AS s(s)
                  WHERE s NOT IN ('early', 'late', 'prime')) THEN
        RAISE EXCEPTION 'unknown filter key: kick_slots';
      END IF;
    ELSIF jsonb_exists(p_filters, 'kick_slots') AND jsonb_typeof(p_filters->'kick_slots') NOT IN ('array', 'null') THEN
      RAISE EXCEPTION 'unknown filter key: kick_slots';
    END IF;
    IF jsonb_typeof(p_filters->'opponents') = 'array' THEN
      v_opponents := ARRAY(
        SELECT btrim(x) FROM jsonb_array_elements_text(p_filters->'opponents') AS t(x)
         WHERE btrim(x) <> '');
      IF cardinality(v_opponents) = 0 THEN
        v_opponents := NULL;
      END IF;
    ELSIF jsonb_exists(p_filters, 'opponents') AND jsonb_typeof(p_filters->'opponents') <> 'null' THEN
      RAISE EXCEPTION 'unknown filter key: opponents';
    END IF;
    -- Trend filters (Matt, 2026-11-05). Each one is known before the bet:
    -- line movement up to the quote that is graded, the team's previous
    -- game, and the two teams' divisions.
    v_line_move := NULLIF(p_filters->>'line_move', '');
    IF v_line_move IS NOT NULL AND v_line_move NOT IN ('toward', 'against', 'none') THEN
      RAISE EXCEPTION 'unknown filter key: line_move';
    END IF;
    v_prev_result := NULLIF(p_filters->>'prev_result', '');
    IF v_prev_result IS NOT NULL AND v_prev_result NOT IN ('won', 'lost') THEN
      RAISE EXCEPTION 'unknown filter key: prev_result';
    END IF;
    v_prev_ats := NULLIF(p_filters->>'prev_ats', '');
    IF v_prev_ats IS NOT NULL AND v_prev_ats NOT IN ('covered', 'not_covered') THEN
      RAISE EXCEPTION 'unknown filter key: prev_ats';
    END IF;
    v_prev_total := NULLIF(p_filters->>'prev_total', '');
    IF v_prev_total IS NOT NULL AND v_prev_total NOT IN ('over', 'under') THEN
      RAISE EXCEPTION 'unknown filter key: prev_total';
    END IF;
    IF jsonb_exists(p_filters, 'division_game') AND p_filters->>'division_game' IS NOT NULL
       AND p_filters->>'division_game' <> '' THEN
      IF jsonb_typeof(p_filters->'division_game') <> 'boolean' THEN
        RAISE EXCEPTION 'unknown filter key: division_game';
      END IF;
      v_division := (p_filters->>'division_game')::boolean;
    END IF;
    v_needs_prev := v_prev_result IS NOT NULL OR v_prev_ats IS NOT NULL
                    OR v_prev_total IS NOT NULL;

    RETURN QUERY
    -- Each team's games this season, in order, and the game before.
    -- A team's first game of the season has no previous game.
    WITH tg AS (
      SELECT f.canonical_key, f.home_team AS team, f.commence_time,
             f.ml_home_result AS su, f.ats_home_result AS ats,
             f.ou_over_result AS ou
        FROM byom_game_facts f
       WHERE f.sport = v_sport AND f.season = v_season
      UNION ALL
      SELECT f.canonical_key, f.away_team, f.commence_time,
             f.ml_away_result, f.ats_away_result, f.ou_over_result
        FROM byom_game_facts f
       WHERE f.sport = v_sport AND f.season = v_season
    ),
    tp AS (
      SELECT tg.canonical_key, tg.team,
             lag(tg.su) OVER w AS prev_su,
             lag(tg.ats) OVER w AS prev_ats,
             lag(tg.ou) OVER w AS prev_ou,
             lag(tg.commence_time) OVER w AS prev_at
        FROM tg
      WINDOW w AS (PARTITION BY tg.team ORDER BY tg.commence_time, tg.canonical_key)
    ),
    g AS (
      SELECT f.*,
             EXTRACT(MONTH FROM (f.commence_time AT TIME ZONE 'America/New_York'))::integer AS kick_month,
             EXTRACT(DOW FROM (f.commence_time AT TIME ZONE 'America/New_York'))::integer AS kick_dow,
             EXTRACT(HOUR FROM (f.commence_time AT TIME ZONE 'America/New_York'))::integer AS kick_hour,
             hp.prev_su AS home_prev_su, hp.prev_ats AS home_prev_ats,
             ap.prev_su AS away_prev_su, ap.prev_ats AS away_prev_ats,
             -- Both teams' last games went over (or under), or neither.
             CASE WHEN hp.prev_ou = 'win' AND ap.prev_ou = 'win' THEN 'over'
                  WHEN hp.prev_ou = 'loss' AND ap.prev_ou = 'loss' THEN 'under'
             END AS prev_total,
             -- A trend on a last game is not known until that game is
             -- over (official lock). Each team's previous start, and the
             -- later of the two for prev_total.
             hp.prev_at AS home_prev_at, ap.prev_at AS away_prev_at,
             greatest(hp.prev_at, ap.prev_at) AS prev_at,
             (public.byom_team_division(f.sport, f.season, f.home_team)
                = public.byom_team_division(f.sport, f.season, f.away_team)) AS division_game
        FROM byom_game_facts f
        LEFT JOIN tp hp ON hp.canonical_key = f.canonical_key AND hp.team = f.home_team
        LEFT JOIN tp ap ON ap.canonical_key = f.canonical_key AND ap.team = f.away_team
       WHERE f.sport = v_sport AND f.season = v_season
    ),
    -- The first stored DraftKings quote of each leg: the opener a line
    -- move is measured from. Read only when the filter is set.
    opener AS (
      SELECT DISTINCT ON (o.canonical_key, o.market, o.leg_side, o.player_key)
             o.canonical_key, o.market, o.leg_side, o.player_key,
             o.point AS open_point, o.price AS open_price
        FROM byom_official_legs o
       WHERE v_line_move IS NOT NULL
         AND o.sport = v_sport AND o.season = v_season
         AND o.match_role = 'any'
         AND (v_markets IS NULL OR o.market = ANY (v_markets))
       ORDER BY o.canonical_key, o.market, o.leg_side, o.player_key, o.locked_at
    ),
    -- The closing line: the last DraftKings quote at or before kickoff.
    -- point is the HOME spread on both spread legs.
    close_game AS (
      SELECT 'spreads'::text AS mkt, 'home'::text AS side, g.home_team AS tm,
             g.ats_home_result AS res, g.dk_spread_home AS pt,
             g.dk_spread_home_price AS px, g.home_role AS role,
             g.home_rest_days AS rest, g.dk_spread_home AS team_spread,
             (g.dk_spread_home IS NULL) AS no_point, g.*
        FROM g
      UNION ALL
      SELECT 'spreads', 'away', g.away_team, g.ats_away_result, g.dk_spread_home,
             g.dk_spread_away_price, g.away_role, g.away_rest_days,
             -g.dk_spread_home, (g.dk_spread_home IS NULL), g.*
        FROM g
      UNION ALL
      SELECT 'h2h', 'home', g.home_team, g.ml_home_result, NULL::numeric,
             g.dk_ml_home_price, g.home_role, g.home_rest_days,
             g.dk_spread_home, false, g.*
        FROM g
      UNION ALL
      SELECT 'h2h', 'away', g.away_team, g.ml_away_result, NULL::numeric,
             g.dk_ml_away_price, g.away_role, g.away_rest_days,
             -g.dk_spread_home, false, g.*
        FROM g
      UNION ALL
      SELECT 'totals', 'over', NULL::text, g.ou_over_result, g.dk_total,
             g.dk_total_over_price, NULL::text, NULL::integer,
             NULL::numeric, (g.dk_total IS NULL), g.*
        FROM g
      UNION ALL
      SELECT 'totals', 'under', NULL::text, g.ou_under_result, g.dk_total,
             g.dk_total_under_price, NULL::text, NULL::integer,
             NULL::numeric, (g.dk_total IS NULL), g.*
        FROM g
    ),
    -- The official lock: the earliest stored quote where the role and
    -- the line, price, team-spread and game-total bands all fit.
    -- context_at_lock rows carry the spread and total in force at that
    -- quote. Older rows (the column false) still use the closing line,
    -- so a band does not move a lock that was stored before this search.
    official_locked AS (
      SELECT DISTINCT ON (canonical_key, market, leg_side, player_key)
             q.*
        FROM (
          SELECT o.*,
                 CASE
                   WHEN o.context_at_lock THEN o.team_spread
                   WHEN o.player_key = '' AND o.leg_side = 'home' THEN g.dk_spread_home
                   WHEN o.player_key = '' AND o.leg_side = 'away' THEN -g.dk_spread_home
                   WHEN o.team = g.home_team THEN g.dk_spread_home
                   WHEN o.team = g.away_team THEN -g.dk_spread_home
                   ELSE NULL
                 END AS spread_used,
                 CASE
                   WHEN o.context_at_lock THEN o.game_total
                   ELSE g.dk_total
                 END AS total_used,
                 -- Movement from the opener to THIS quote: what was known
                 -- when the bet became official, never the close.
                 public.byom_line_move(o.market, o.leg_side, op.open_point,
                                       op.open_price, o.point, o.price) AS move,
                 -- A candidate is the quote in force until the next one
                 -- (byom/official.py stores a row only on a change).
                 lead(o.locked_at) OVER (
                   PARTITION BY o.canonical_key, o.market, o.leg_side,
                                o.player_key, o.match_role
                   ORDER BY o.locked_at) AS next_at,
                 -- When a last-game filter becomes known: 4 hours after the
                 -- bet team's previous start (both teams' for prev_total).
                 CASE
                   WHEN NOT v_needs_prev THEN NULL
                   WHEN v_prev_total IS NOT NULL THEN g.prev_at
                   WHEN (o.player_key = '' AND o.leg_side = 'home')
                     OR (o.player_key <> '' AND o.team = g.home_team) THEN g.home_prev_at
                   WHEN (o.player_key = '' AND o.leg_side = 'away')
                     OR (o.player_key <> '' AND o.team = g.away_team) THEN g.away_prev_at
                   ELSE g.prev_at
                 END + interval '4 hours' AS wait_at,
                 g.commence_time AS g_kick
            FROM byom_official_legs o
            LEFT JOIN g ON g.canonical_key = o.canonical_key
            LEFT JOIN opener op
              ON op.canonical_key = o.canonical_key AND op.market = o.market
             AND op.leg_side = o.leg_side AND op.player_key = o.player_key
           WHERE o.sport = v_sport AND o.season = v_season
             -- Market and side before the lock search, not after it
             -- (2026-11-04). The DISTINCT ON below used to rank every
             -- market of the season. NBA props are about 108 a game.
             AND (v_markets IS NULL OR o.market = ANY (v_markets))
             AND (v_side IS NULL OR o.player_key <> '' OR o.leg_side = v_side)
             AND (v_prop_side IS NULL OR o.player_key = '' OR o.leg_side = v_prop_side)
             AND (
               -- A prop is not filtered on its team's role (Matt,
               -- 2026-11-04), so its lock is the first 'any' candidate.
               (o.player_key <> '' AND o.match_role = 'any')
               OR (o.player_key = '' AND v_role IS NULL AND o.match_role = 'any')
               OR (o.player_key = '' AND v_role IS NOT NULL AND (
                    o.match_role = v_role
                    OR (o.match_role = 'any' AND o.leg_role = v_role)))
             )
        ) q
       WHERE (v_min_price IS NULL OR q.price >= v_min_price)
         AND (v_max_price IS NULL OR q.price <= v_max_price)
         AND (v_min_line IS NULL OR (q.player_key <> '' AND q.point >= v_min_line))
         AND (v_max_line IS NULL OR (q.player_key <> '' AND q.point <= v_max_line))
         -- Team spread and game total are team-bet filters. A prop is
         -- not filtered on them, so its candidates (stored on its own
         -- line or price change) are never read for them.
         AND (v_min_spread IS NULL OR q.player_key <> '' OR q.spread_used >= v_min_spread)
         AND (v_max_spread IS NULL OR q.player_key <> '' OR q.spread_used <= v_max_spread)
         AND (v_min_total IS NULL OR q.player_key <> '' OR q.total_used >= v_min_total)
         AND (v_max_total IS NULL OR q.player_key <> '' OR q.total_used <= v_max_total)
         AND (v_line_move IS NULL OR q.move = v_line_move)
         -- A last-game filter is not known until that game is over. A
         -- candidate counts if it was still the live quote when the result
         -- was known (and before kickoff); the bet is then official at
         -- that moment, at that quote. A line that never changed after
         -- the previous game is not dropped (CE review, #1187 H1). A quote
         -- posted after the wait also passes, on purpose: with another rule
         -- (say prev + toward) the first fit can come later. ORDER BY
         -- locked_at below still takes the earliest.
         AND (q.wait_at IS NULL
              OR ((q.next_at IS NULL OR q.next_at > q.wait_at)
                  AND q.wait_at < q.g_kick))
       ORDER BY canonical_key, market, leg_side, player_key, locked_at
    ),
    raw AS (
      -- Closing game legs.
      SELECT 'close'::text AS tmg, c.mkt, c.side, c.canonical_key AS ck,
             c.commence_time AS kick, c.week AS wk, c.home_team AS ht,
             c.away_team AS at, c.tm, NULL::text AS player,
             c.pt, c.px, c.res, NULL::timestamptz AS lock_at, c.role,
             c.rest, c.is_primetime AS prime, c.side AS team_side,
             NULL::text AS ou, NULL::numeric AS prop_line,
             c.team_spread, c.dk_total AS game_total,
             CASE c.side WHEN 'home' THEN c.away_team
                         WHEN 'away' THEN c.home_team END AS opp,
             c.kick_month, c.kick_dow, c.kick_hour,
             (c.home_score IS NOT NULL AND c.away_score IS NOT NULL) AS played,
             c.no_point,
             CASE c.side WHEN 'home' THEN c.home_prev_su
                         WHEN 'away' THEN c.away_prev_su END AS prev_su,
             CASE c.side WHEN 'home' THEN c.home_prev_ats
                         WHEN 'away' THEN c.away_prev_ats END AS prev_ats,
             c.prev_total AS prev_ou,
             c.division_game AS division,
             -- The close against the opener: both known at kickoff.
             public.byom_line_move(c.mkt, c.side, op.open_point, op.open_price,
                                   c.pt, c.px) AS move
        FROM close_game c
        LEFT JOIN opener op
          ON op.canonical_key = c.canonical_key AND op.market = c.mkt
         AND op.leg_side = c.side AND op.player_key = ''
       WHERE p_timing IS DISTINCT FROM 'official'
      UNION ALL
      -- Closing props.
      SELECT 'close', p.market, s.side, p.canonical_key, g.commence_time,
             p.week, g.home_team, g.away_team, p.team, p.player_name,
             p.line,
             CASE s.side WHEN 'over' THEN p.over_price ELSE p.under_price END,
             CASE s.side WHEN 'over' THEN p.over_result ELSE p.under_result END,
             NULL::timestamptz,
             CASE WHEN p.team = g.home_team THEN g.home_role
                  WHEN p.team = g.away_team THEN g.away_role END,
             CASE WHEN p.team = g.home_team THEN g.home_rest_days
                  WHEN p.team = g.away_team THEN g.away_rest_days END,
             g.is_primetime,
             CASE WHEN p.team = g.home_team THEN 'home'
                  WHEN p.team = g.away_team THEN 'away' END,
             s.side, p.line,
             CASE WHEN p.team = g.home_team THEN g.dk_spread_home
                  WHEN p.team = g.away_team THEN -g.dk_spread_home END,
             g.dk_total,
             CASE WHEN p.team = g.home_team THEN g.away_team
                  WHEN p.team = g.away_team THEN g.home_team END,
             g.kick_month, g.kick_dow, g.kick_hour,
             -- A null prop result is ungraded, never a missing line.
             (CASE s.side WHEN 'over' THEN p.over_result
                          ELSE p.under_result END) IS NOT NULL,
             false,
             CASE WHEN p.team = g.home_team THEN g.home_prev_su
                  WHEN p.team = g.away_team THEN g.away_prev_su END,
             CASE WHEN p.team = g.home_team THEN g.home_prev_ats
                  WHEN p.team = g.away_team THEN g.away_prev_ats END,
             g.prev_total,
             g.division_game,
             public.byom_line_move(p.market, s.side, op.open_point, op.open_price,
                                   p.line, CASE s.side WHEN 'over' THEN p.over_price
                                                       ELSE p.under_price END)
        FROM byom_prop_facts p
        CROSS JOIN (VALUES ('over'), ('under')) AS s(side)
        LEFT JOIN g ON g.canonical_key = p.canonical_key
        LEFT JOIN opener op
          ON op.canonical_key = p.canonical_key AND op.market = p.market
         AND op.leg_side = s.side AND op.player_key = p.player_key
       WHERE p_timing IS DISTINCT FROM 'official'
         AND p.sport = v_sport AND p.season = v_season
         -- One market and one side before the join (2026-11-04: an NBA
         -- season holds about 128K prop facts; one market is about 16K).
         AND (v_markets IS NULL OR p.market = ANY (v_markets))
         AND (v_prop_side IS NULL OR s.side = v_prop_side)
      UNION ALL
      -- Official game legs: the first quote that fits the role and the bands.
      SELECT 'official', o.market, o.leg_side, o.canonical_key, g.commence_time,
             g.week, g.home_team, g.away_team, o.team, NULL::text,
             o.point, o.price, o.result, greatest(o.locked_at, o.wait_at), o.leg_role,
             CASE o.leg_side WHEN 'home' THEN g.home_rest_days
                             WHEN 'away' THEN g.away_rest_days END,
             g.is_primetime,
             CASE WHEN o.leg_side IN ('home', 'away') THEN o.leg_side END,
             NULL::text,
             CASE WHEN o.player_key <> '' THEN o.point END,
             o.spread_used,
             o.total_used,
             CASE o.leg_side WHEN 'home' THEN g.away_team
                             WHEN 'away' THEN g.home_team END,
             g.kick_month, g.kick_dow, g.kick_hour,
             (g.home_score IS NOT NULL AND g.away_score IS NOT NULL),
             false,
             CASE o.leg_side WHEN 'home' THEN g.home_prev_su
                             WHEN 'away' THEN g.away_prev_su END,
             CASE o.leg_side WHEN 'home' THEN g.home_prev_ats
                             WHEN 'away' THEN g.away_prev_ats END,
             g.prev_total,
             g.division_game,
             o.move
        FROM official_locked o
        JOIN g ON g.canonical_key = o.canonical_key
       WHERE p_timing IS DISTINCT FROM 'close'
         AND o.player_key = ''
         -- A total's leg_role is null, so a role filter drops it, as on close.
      UNION ALL
      -- Official props.
      SELECT 'official', o.market, o.leg_side, o.canonical_key, g.commence_time,
             p.week, g.home_team, g.away_team, o.team, p.player_name,
             o.point, o.price, o.result, greatest(o.locked_at, o.wait_at), o.leg_role,
             CASE WHEN o.team = g.home_team THEN g.home_rest_days
                  WHEN o.team = g.away_team THEN g.away_rest_days END,
             g.is_primetime,
             CASE WHEN o.team = g.home_team THEN 'home'
                  WHEN o.team = g.away_team THEN 'away' END,
             o.leg_side, o.point,
             o.spread_used,
             o.total_used,
             CASE WHEN o.team = g.home_team THEN g.away_team
                  WHEN o.team = g.away_team THEN g.home_team END,
             g.kick_month, g.kick_dow, g.kick_hour,
             o.result IS NOT NULL,
             false,
             CASE WHEN o.team = g.home_team THEN g.home_prev_su
                  WHEN o.team = g.away_team THEN g.away_prev_su END,
             CASE WHEN o.team = g.home_team THEN g.home_prev_ats
                  WHEN o.team = g.away_team THEN g.away_prev_ats END,
             g.prev_total,
             g.division_game,
             o.move
        FROM official_locked o
        JOIN byom_prop_facts p
          ON p.canonical_key = o.canonical_key
         AND p.market = o.market
         AND p.player_key = o.player_key
         AND p.sport = v_sport AND p.season = v_season
        LEFT JOIN g ON g.canonical_key = o.canonical_key
       WHERE p_timing IS DISTINCT FROM 'close'
         AND o.player_key <> ''
    ),
    kept AS (
      SELECT r.*,
             (r.px IS NOT NULL AND r.px = trunc(r.px) AND abs(r.px) >= 100) AS ok
        FROM raw r
       WHERE (v_markets IS NULL OR r.mkt = ANY (v_markets))
         AND (v_weeks IS NULL OR r.wk = ANY (v_weeks))
         -- side is home/away on a game leg or a prop's team, and
         -- over/under on a total, the same as before this file.
         AND (v_side IS NULL
              OR (r.mkt IN ('h2h', 'spreads', 'totals') AND r.side = v_side)
              OR (r.mkt NOT IN ('h2h', 'spreads', 'totals') AND r.team_side = v_side))
         -- Close reads the closing role. Official already searched for it.
         -- The same rule on the closing timing: role, team spread and
         -- game total filter game legs only.
         AND (v_role IS NULL OR r.tmg = 'official' OR r.mkt NOT IN ('h2h', 'spreads', 'totals') OR r.role = v_role)
         AND (v_min_rest IS NULL OR r.rest >= v_min_rest)
         AND (v_max_rest IS NULL OR r.rest <= v_max_rest)
         AND (v_primetime IS NULL OR r.prime = v_primetime)
         AND (v_prop_side IS NULL OR r.ou = v_prop_side)
         AND (v_min_line IS NULL OR r.prop_line >= v_min_line)
         AND (v_max_line IS NULL OR r.prop_line <= v_max_line)
         AND (v_min_price IS NULL OR r.px >= v_min_price)
         AND (v_max_price IS NULL OR r.px <= v_max_price)
         AND (v_min_spread IS NULL OR r.mkt NOT IN ('h2h', 'spreads', 'totals') OR r.team_spread >= v_min_spread)
         AND (v_max_spread IS NULL OR r.mkt NOT IN ('h2h', 'spreads', 'totals') OR r.team_spread <= v_max_spread)
         AND (v_min_total IS NULL OR r.mkt NOT IN ('h2h', 'spreads', 'totals') OR r.game_total >= v_min_total)
         AND (v_max_total IS NULL OR r.mkt NOT IN ('h2h', 'spreads', 'totals') OR r.game_total <= v_max_total)
         AND (v_months IS NULL OR r.kick_month = ANY (v_months))
         AND (v_weekdays IS NULL OR r.kick_dow = ANY (v_weekdays))
         AND (v_slots IS NULL
              OR ('early' = ANY (v_slots) AND r.kick_hour < 14)
              OR ('late' = ANY (v_slots) AND r.kick_hour >= 14 AND r.kick_hour < 19)
              OR ('prime' = ANY (v_slots) AND r.kick_hour >= 19))
         AND (v_opponents IS NULL OR r.opp = ANY (v_opponents))
         AND (v_player IS NULL OR r.player = v_player)
         AND (v_line_move IS NULL OR r.move = v_line_move)
         AND (v_prev_result IS NULL
              OR r.prev_su = CASE v_prev_result WHEN 'won' THEN 'win' ELSE 'loss' END)
         AND (v_prev_ats IS NULL
              OR r.prev_ats = CASE v_prev_ats WHEN 'covered' THEN 'win' ELSE 'loss' END)
         AND (v_prev_total IS NULL OR r.prev_ou = v_prev_total)
         AND (v_division IS NULL OR r.division = v_division)
         -- Graded, or played with no usable line or price (skipped).
         AND (r.res IS NOT NULL OR r.played)
    )
    SELECT k.tmg, k.mkt, k.side, k.ck, k.kick, k.wk, k.ht, k.at, k.tm,
           k.player, k.pt, k.px, k.res, k.lock_at, k.role,
           k.ok,
           -- Played with no line, or no American price: skipped.
           (k.played AND (k.no_point OR NOT k.ok)),
           CASE
             WHEN NOT k.ok OR k.res IS NULL THEN NULL
             WHEN k.res = 'win' THEN byom_win_units(k.px)
             WHEN k.res = 'loss' THEN -byom_risk_units(k.px)
             ELSE 0
           END,
           CASE WHEN k.ok AND k.res IS NOT NULL THEN byom_risk_units(k.px) END
      FROM kept k;
  END
  $body$;
  $fn$;

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
      -- byom_trend_filters_v1
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
      -- Every key the preview grades (byom_legs), and only those (27). An
      -- unknown key is refused, never dropped (Matt, 2026-11-05: a saved
      -- model kept 9 of the builder's 22 keys and lost the rest silently).
      IF EXISTS (
        SELECT 1 FROM jsonb_object_keys(v_filters) AS k(key)
         WHERE lower(k.key) IN (
           'side', 'role', 'weeks', 'min_rest_days', 'max_rest_days',
           'primetime', 'markets', 'prop_side', 'sport', 'min_line', 'max_line',
           'min_price', 'max_price', 'min_team_spread', 'max_team_spread',
           'min_game_total', 'max_game_total', 'months', 'weekdays',
           'kick_slots', 'opponents', 'player', 'line_move', 'prev_result',
           'prev_ats', 'prev_total', 'division_game')
           AND k.key NOT IN (
           'side', 'role', 'weeks', 'min_rest_days', 'max_rest_days',
           'primetime', 'markets', 'prop_side', 'sport', 'min_line', 'max_line',
           'min_price', 'max_price', 'min_team_spread', 'max_team_spread',
           'min_game_total', 'max_game_total', 'months', 'weekdays',
           'kick_slots', 'opponents', 'player', 'line_move', 'prev_result',
           'prev_ats', 'prev_total', 'division_game'))
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
         'kick_slots', 'opponents', 'player', 'line_move', 'prev_result',
         'prev_ats', 'prev_total', 'division_game')
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
