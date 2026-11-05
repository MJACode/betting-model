-- Build Your Own Model: NBA prop records inside the app's 3s read limit.
--
-- Measured 2026-11-04 after #1169's NBA backfill, as anon:
-- byom_record(2026, NBA player_points over) took 3,687 ms, over the 3s
-- anon timeout. The closing half took 1,682 ms. It read every NBA prop
-- fact of the season and filtered to the market after the join. The
-- same read filtered to one market took 41 ms. The official half took
-- 1,978 ms. Its join to byom_prop_facts on (canonical_key, market,
-- player_key) had no index, so it merge-joined the whole table and
-- removed 895,998 rows (1,949 ms on its own).
--
-- This file adds the two indexes and replaces byom_legs with
-- byom_official_market_pushdown_2026_11_04.sql's body. The closing prop
-- branch gains the market and over/under filters, and the official prop
-- join gains sport and season. Same rows and same answers: both filters
-- were already applied in `kept`. Keeps the three earlier markers so
-- those files' guards still skip. Guarded with to_regprocedure, and a
-- body the adapter damaged is treated as absent. CREATE INDEX (not
-- CONCURRENTLY) briefly blocks writes to byom_prop_facts. Does not write
-- picks.
--
-- 2026-11-05 (#1172 Medium, Matt via CE): the function sets
-- plan_cache_mode to force_custom_plan, beside search_path. PostgREST
-- reuses a pooled connection. After a few calls, plpgsql can switch a
-- RETURN QUERY to a generic plan, and a generic plan of
-- (v_markets IS NULL OR p.market = ANY(v_markets)) does not use
-- idx_byom_prop_facts_market. The skip requires that setting, so a body
-- applied before this line is replaced once and then left alone.

DO $mig$
BEGIN
  IF to_regclass('public.byom_prop_facts') IS NULL THEN
    RAISE EXCEPTION 'apply byom_facts_schema_2026_10_16.sql first';
  END IF;

  IF to_regclass('public.idx_byom_prop_facts_leg') IS NULL THEN
    CREATE INDEX IF NOT EXISTS idx_byom_prop_facts_leg
      ON public.byom_prop_facts (canonical_key, market, player_key);
  END IF;
  IF to_regclass('public.idx_byom_prop_facts_market') IS NULL THEN
    CREATE INDEX IF NOT EXISTS idx_byom_prop_facts_market
      ON public.byom_prop_facts (sport, season, market);
  END IF;

  IF EXISTS (
    SELECT 1 FROM pg_proc p
     WHERE p.oid = to_regprocedure('public.byom_legs(integer, jsonb, text)')
       AND position('byom_prop_lookup_v1' in p.prosrc) > 0
       AND position('p_filters %s' in p.prosrc) = 0
       AND 'plan_cache_mode=force_custom_plan' = ANY (p.proconfig)
  ) THEN
    RAISE NOTICE 'byom prop lookup already present - skipping';
    RETURN;
  END IF;

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
       'kick_slots', 'opponents', 'player')
     LIMIT 1;
    IF v_bad IS NOT NULL THEN
      RAISE EXCEPTION 'unknown filter key: %', v_bad;
    END IF;

    v_sport := COALESCE(NULLIF(p_filters->>'sport', ''), 'NFL');
    IF v_sport NOT IN ('NFL', 'NBA') THEN
      RAISE EXCEPTION 'unknown sport';
    END IF;

    IF p_season IS NULL THEN
      v_month := EXTRACT(MONTH FROM (now() AT TIME ZONE 'America/New_York'))::integer;
      v_year := EXTRACT(YEAR FROM (now() AT TIME ZONE 'America/New_York'))::integer;
      IF v_sport = 'NBA' THEN
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

    RETURN QUERY
    WITH g AS (
      SELECT f.*,
             EXTRACT(MONTH FROM (f.commence_time AT TIME ZONE 'America/New_York'))::integer AS kick_month,
             EXTRACT(DOW FROM (f.commence_time AT TIME ZONE 'America/New_York'))::integer AS kick_dow,
             EXTRACT(HOUR FROM (f.commence_time AT TIME ZONE 'America/New_York'))::integer AS kick_hour
        FROM byom_game_facts f
       WHERE f.sport = v_sport AND f.season = v_season
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
                 END AS total_used
            FROM byom_official_legs o
            LEFT JOIN g ON g.canonical_key = o.canonical_key
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
             c.no_point
        FROM close_game c
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
             false
        FROM byom_prop_facts p
        CROSS JOIN (VALUES ('over'), ('under')) AS s(side)
        LEFT JOIN g ON g.canonical_key = p.canonical_key
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
             o.point, o.price, o.result, o.locked_at, o.leg_role,
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
             false
        FROM official_locked o
        JOIN g ON g.canonical_key = o.canonical_key
       WHERE p_timing IS DISTINCT FROM 'close'
         AND o.player_key = ''
         -- A total's leg_role is null, so a role filter drops it, as on close.
      UNION ALL
      -- Official props.
      SELECT 'official', o.market, o.leg_side, o.canonical_key, g.commence_time,
             p.week, g.home_team, g.away_team, o.team, p.player_name,
             o.point, o.price, o.result, o.locked_at, o.leg_role,
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
             false
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

END $mig$;
