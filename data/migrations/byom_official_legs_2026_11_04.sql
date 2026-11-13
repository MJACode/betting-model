-- Build Your Own Model: the official pick, beside the closing line.
--
-- Matt, 2026-11-04. A builder model's bet becomes official at the first
-- DraftKings quote, at or before kickoff, where the leg fits the model's
-- rules and the side has an American price ("it's all about when a line
-- becomes an official pick"). That line and price are the bet of record;
-- a later move does not change it. The closing line (byom_game_facts,
-- byom_prop_facts) is still graded beside it.
--
-- Staking is the main models' rule (Matt, same day: "do what we do in
-- the app on the main models"): stake_for in tracking/discord_notifier.py.
-- Each bet is 1u to win, risk capped at 3u (MAX_RISK_UNITS). At -400 the
-- risk is 3u and the win is 0.75u. A push and a tie are 0. Before this
-- file a -400 loss cost 4u.
--
-- What this file creates:
--   byom_official_legs   one row per leg and role, written by byom/official.py
--   byom_leg_label       the label a screen shows. The only place a pick's
--                        number is built from the stored fields (CLAUDE.md §00)
--   byom_win_units / byom_risk_units   the staking above
--   byom_legs            every kept leg, both timings. The one filter parser
--   byom_record          per timing and market: the record and the units
--   byom_bets            the bets one timing counts, newest first
--   byom_backtest        the same signature and columns as before, now the
--                        closing rows of byom_legs, so the saved-model
--                        snapshot reads the capped staking too
--
-- Filters: the production byom_backtest before this file accepted only
-- side, role, weeks, rest, primetime, markets, prop_side and sport. The
-- Phase A keys (byom_prop_phase_a_filters_2026_10_29.sql) were recorded
-- as applied but were not in the live body (measured 2026-11-04,
-- pg_get_functiondef). This file accepts them, with that file's meaning.
-- On the official timing, min/max_line and min/max_price read the
-- official quote's own line and price. Team spread and game total read
-- the closing game line. None of them moves the lock: a lock is searched
-- on role only.
--
-- In data/view_migrations.ACTIVE_MIGRATIONS. The guard returns before
-- any DDL once the table, its grants, its policy, and the five functions
-- carrying byom_official_legs_v1 are present. Does not write picks.

DO $mig$
BEGIN
  -- to_regclass, never ::regclass, in the guard: plpgsql does not
  -- short-circuit AND, and a cast of a missing table raises.
  IF COALESCE((SELECT c.relrowsecurity FROM pg_class c
                WHERE c.oid = to_regclass('public.byom_official_legs')), false)
     AND EXISTS (
       SELECT 1 FROM pg_policy
        WHERE polrelid = to_regclass('public.byom_official_legs')
          AND polname = 'anon read byom_official_legs')
     AND EXISTS (
       SELECT 1 FROM information_schema.role_table_grants
        WHERE table_schema = 'public' AND table_name = 'byom_official_legs'
          AND grantee = 'anon' AND privilege_type = 'SELECT')
     AND NOT EXISTS (
       SELECT 1 FROM information_schema.role_table_grants
        WHERE table_schema = 'public' AND table_name = 'byom_official_legs'
          AND grantee IN ('anon', 'authenticated')
          AND privilege_type <> 'SELECT')
     AND (SELECT count(*) FROM pg_proc p
           WHERE p.pronamespace = 'public'::regnamespace
             AND p.proname IN ('byom_legs', 'byom_record', 'byom_bets',
                               'byom_backtest', 'byom_leg_label')
             AND position('byom_official_legs_v1' in p.prosrc) > 0) = 5
  THEN
    RAISE NOTICE 'byom official legs already present - skipping';
    RETURN;
  END IF;

  IF to_regclass('public.byom_game_facts') IS NULL
     OR to_regclass('public.byom_prop_facts') IS NULL THEN
    RAISE EXCEPTION 'apply byom_facts_schema_2026_10_16.sql first';
  END IF;

  CREATE TABLE IF NOT EXISTS public.byom_official_legs (
    canonical_key   TEXT NOT NULL,
    sport           TEXT NOT NULL,
    season          INTEGER NOT NULL,
    market          TEXT NOT NULL,
    -- home/away on h2h and spreads, over/under on totals and props.
    leg_side        TEXT NOT NULL,
    -- '' on a game leg, the normalised player name on a prop.
    player_key      TEXT NOT NULL DEFAULT '',
    -- The role a model asks for. 'any' is the first priced quote.
    match_role      TEXT NOT NULL,
    -- The leg's role at the lock. Null when no spread was in force yet.
    leg_role        TEXT,
    team            TEXT,
    locked_at       TIMESTAMPTZ NOT NULL,
    -- The HOME spread on a spread leg (CLAUDE.md §4), the total on a
    -- total, the player line on a prop, null on a moneyline.
    point           NUMERIC,
    price           NUMERIC NOT NULL,
    result          TEXT,
    built_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (canonical_key, market, leg_side, player_key, match_role),
    CONSTRAINT byom_official_legs_role CHECK (
      match_role IN ('any', 'favorite', 'underdog', 'pickem')),
    CONSTRAINT byom_official_legs_leg_role CHECK (
      leg_role IS NULL OR leg_role IN ('favorite', 'underdog', 'pickem')),
    CONSTRAINT byom_official_legs_result CHECK (
      result IS NULL OR result IN ('win', 'loss', 'push', 'tie'))
  );
  CREATE INDEX IF NOT EXISTS idx_byom_official_legs_season
    ON public.byom_official_legs (sport, season, match_role, market);

  REVOKE ALL ON public.byom_official_legs FROM PUBLIC, anon, authenticated;
  GRANT SELECT ON public.byom_official_legs TO anon, authenticated;
  ALTER TABLE public.byom_official_legs ENABLE ROW LEVEL SECURITY;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
     WHERE polrelid = 'public.byom_official_legs'::regclass
       AND polname = 'anon read byom_official_legs') THEN
    CREATE POLICY "anon read byom_official_legs"
      ON public.byom_official_legs
      FOR SELECT TO anon, authenticated
      USING (true);
  END IF;

  -- ── staking: stake_for, 1u to win, risk capped at 3u ──────────────────
  EXECUTE $fn$
  CREATE OR REPLACE FUNCTION public.byom_risk_units(p_price numeric)
  RETURNS numeric LANGUAGE sql IMMUTABLE
  SET search_path = public, pg_temp
  AS $body$
    -- byom_official_legs_v1
    SELECT CASE
      WHEN p_price IS NULL OR p_price <> trunc(p_price) OR abs(p_price) < 100
        THEN NULL
      WHEN p_price > 0 THEN least(100 / p_price, 3)
      ELSE least(abs(p_price) / 100, 3)
    END
  $body$;
  $fn$;

  EXECUTE $fn$
  CREATE OR REPLACE FUNCTION public.byom_win_units(p_price numeric)
  RETURNS numeric LANGUAGE sql IMMUTABLE
  SET search_path = public, pg_temp
  AS $body$
    -- byom_official_legs_v1. The win on a capped risk, so the two agree.
    SELECT CASE
      WHEN byom_risk_units(p_price) IS NULL THEN NULL
      WHEN p_price > 0 THEN byom_risk_units(p_price) * p_price / 100
      ELSE byom_risk_units(p_price) * 100 / abs(p_price)
    END
  $body$;
  $fn$;

  -- ── the label: built here, once ───────────────────────────────────────
  EXECUTE $fn$
  CREATE OR REPLACE FUNCTION public.byom_leg_label(
    p_market text, p_side text, p_team text, p_point numeric,
    p_player text)
  RETURNS text LANGUAGE sql IMMUTABLE
  SET search_path = public, pg_temp
  AS $body$
    -- byom_official_legs_v1
    -- A spread's stored point is the HOME number. The away side is its
    -- negative. 0 is PK. A prop Yes/No market's over is Yes.
    SELECT CASE
      WHEN p_market = 'h2h' THEN p_team || ' ML'
      WHEN p_market = 'spreads' THEN p_team || ' ' || (
        SELECT CASE WHEN v = 0 THEN 'PK'
                    WHEN v > 0 THEN '+' || trim_scale(v)::text
                    ELSE trim_scale(v)::text END
          FROM (SELECT CASE WHEN p_side = 'away' THEN -p_point
                            ELSE p_point END AS v) s)
      WHEN p_market = 'totals' THEN initcap(p_side) || ' ' || trim_scale(p_point)::text
      WHEN p_market IN ('player_anytime_td', 'player_double_double',
                        'player_triple_double')
        THEN p_player || CASE WHEN p_side = 'over' THEN ' Yes' ELSE ' No' END
      ELSE p_player || ' ' || initcap(p_side) || ' ' || trim_scale(p_point)::text
    END
  $body$;
  $fn$;

  -- ── every kept leg ────────────────────────────────────────────────────
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
  AS $body$
  DECLARE
    -- byom_official_legs_v1
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
    IF p_filters ? 'primetime' AND p_filters->>'primetime' IS NOT NULL
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
    ELSIF p_filters ? 'months' AND jsonb_typeof(p_filters->'months') NOT IN ('array', 'null') THEN
      RAISE EXCEPTION 'unknown filter key: months';
    END IF;
    IF jsonb_typeof(p_filters->'weekdays') = 'array'
       AND jsonb_array_length(p_filters->'weekdays') > 0 THEN
      v_weekdays := ARRAY(
        SELECT (jsonb_array_elements_text(p_filters->'weekdays'))::integer);
      IF EXISTS (SELECT 1 FROM unnest(v_weekdays) AS d(d) WHERE d < 0 OR d > 6) THEN
        RAISE EXCEPTION 'unknown filter key: weekdays';
      END IF;
    ELSIF p_filters ? 'weekdays' AND jsonb_typeof(p_filters->'weekdays') NOT IN ('array', 'null') THEN
      RAISE EXCEPTION 'unknown filter key: weekdays';
    END IF;
    IF jsonb_typeof(p_filters->'kick_slots') = 'array'
       AND jsonb_array_length(p_filters->'kick_slots') > 0 THEN
      v_slots := ARRAY(SELECT jsonb_array_elements_text(p_filters->'kick_slots'));
      IF EXISTS (SELECT 1 FROM unnest(v_slots) AS s(s)
                  WHERE s NOT IN ('early', 'late', 'prime')) THEN
        RAISE EXCEPTION 'unknown filter key: kick_slots';
      END IF;
    ELSIF p_filters ? 'kick_slots' AND jsonb_typeof(p_filters->'kick_slots') NOT IN ('array', 'null') THEN
      RAISE EXCEPTION 'unknown filter key: kick_slots';
    END IF;
    IF jsonb_typeof(p_filters->'opponents') = 'array' THEN
      v_opponents := ARRAY(
        SELECT btrim(x) FROM jsonb_array_elements_text(p_filters->'opponents') AS t(x)
         WHERE btrim(x) <> '');
      IF cardinality(v_opponents) = 0 THEN
        v_opponents := NULL;
      END IF;
    ELSIF p_filters ? 'opponents' AND jsonb_typeof(p_filters->'opponents') <> 'null' THEN
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
      UNION ALL
      -- Official game legs: the first quote that fits the role asked for.
      SELECT 'official', o.market, o.leg_side, o.canonical_key, g.commence_time,
             g.week, g.home_team, g.away_team, o.team, NULL::text,
             o.point, o.price, o.result, o.locked_at, o.leg_role,
             CASE o.leg_side WHEN 'home' THEN g.home_rest_days
                             WHEN 'away' THEN g.away_rest_days END,
             g.is_primetime,
             CASE WHEN o.leg_side IN ('home', 'away') THEN o.leg_side END,
             NULL::text, NULL::numeric,
             CASE o.leg_side WHEN 'home' THEN g.dk_spread_home
                             WHEN 'away' THEN -g.dk_spread_home END,
             g.dk_total,
             CASE o.leg_side WHEN 'home' THEN g.away_team
                             WHEN 'away' THEN g.home_team END,
             g.kick_month, g.kick_dow, g.kick_hour,
             (g.home_score IS NOT NULL AND g.away_score IS NOT NULL),
             false
        FROM byom_official_legs o
        JOIN g ON g.canonical_key = o.canonical_key
       WHERE p_timing IS DISTINCT FROM 'close'
         AND o.sport = v_sport AND o.season = v_season
         AND o.player_key = ''
         -- A total has only 'any', so a role filter drops it, as on close.
         AND o.match_role = COALESCE(v_role, 'any')
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
             CASE WHEN o.team = g.home_team THEN g.dk_spread_home
                  WHEN o.team = g.away_team THEN -g.dk_spread_home END,
             g.dk_total,
             CASE WHEN o.team = g.home_team THEN g.away_team
                  WHEN o.team = g.away_team THEN g.home_team END,
             g.kick_month, g.kick_dow, g.kick_hour,
             o.result IS NOT NULL,
             false
        FROM byom_official_legs o
        JOIN byom_prop_facts p
          ON p.canonical_key = o.canonical_key
         AND p.market = o.market
         AND p.player_key = o.player_key
        LEFT JOIN g ON g.canonical_key = o.canonical_key
       WHERE p_timing IS DISTINCT FROM 'close'
         AND o.sport = v_sport AND o.season = v_season
         AND o.player_key <> ''
         AND o.match_role = COALESCE(v_role, 'any')
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
         AND (v_role IS NULL OR r.tmg = 'official' OR r.role = v_role)
         AND (v_min_rest IS NULL OR r.rest >= v_min_rest)
         AND (v_max_rest IS NULL OR r.rest <= v_max_rest)
         AND (v_primetime IS NULL OR r.prime = v_primetime)
         AND (v_prop_side IS NULL OR r.ou = v_prop_side)
         AND (v_min_line IS NULL OR r.prop_line >= v_min_line)
         AND (v_max_line IS NULL OR r.prop_line <= v_max_line)
         AND (v_min_price IS NULL OR r.px >= v_min_price)
         AND (v_max_price IS NULL OR r.px <= v_max_price)
         AND (v_min_spread IS NULL OR r.team_spread >= v_min_spread)
         AND (v_max_spread IS NULL OR r.team_spread <= v_max_spread)
         AND (v_min_total IS NULL OR r.game_total >= v_min_total)
         AND (v_max_total IS NULL OR r.game_total <= v_max_total)
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

  -- ── per timing and market ─────────────────────────────────────────────
  EXECUTE $fn$
  CREATE OR REPLACE FUNCTION public.byom_record(
    p_season integer,
    p_filters jsonb DEFAULT '{}'::jsonb
  )
  RETURNS TABLE (
    timing text, market text, bets bigint, wins bigint, losses bigint,
    pushes bigint, ties bigint, units numeric, risked numeric, skipped bigint
  )
  LANGUAGE sql
  STABLE
  SECURITY INVOKER
  SET search_path = public, pg_temp
  AS $body$
    -- byom_official_legs_v1
    SELECT l.timing, l.market,
           count(*) FILTER (WHERE l.units IS NOT NULL),
           count(*) FILTER (WHERE l.units IS NOT NULL AND l.result = 'win'),
           count(*) FILTER (WHERE l.units IS NOT NULL AND l.result = 'loss'),
           count(*) FILTER (WHERE l.units IS NOT NULL AND l.result = 'push'),
           count(*) FILTER (WHERE l.units IS NOT NULL AND l.result = 'tie'),
           COALESCE(sum(l.units), 0),
           COALESCE(sum(l.risk), 0),
           count(*) FILTER (WHERE l.no_line AND l.units IS NULL)
      FROM byom_legs(p_season, p_filters, NULL) l
     GROUP BY l.timing, l.market
     ORDER BY l.timing, l.market
  $body$;
  $fn$;

  -- ── the bets one timing counts ────────────────────────────────────────
  EXECUTE $fn$
  CREATE OR REPLACE FUNCTION public.byom_bets(
    p_season integer,
    p_filters jsonb DEFAULT '{}'::jsonb,
    p_timing text DEFAULT 'official'
  )
  RETURNS TABLE (
    canonical_key text, commence_time timestamptz, market text,
    leg_side text, label text, home_team text, away_team text,
    player_name text, point numeric, price numeric, result text,
    units numeric, locked_at timestamptz, total_bets bigint
  )
  LANGUAGE sql
  STABLE
  SECURITY INVOKER
  SET search_path = public, pg_temp
  AS $body$
    -- byom_official_legs_v1
    -- Only the counted bets: graded and priced. Newest first. At most
    -- 500 rows; total_bets is the full count, so a screen can say so.
    SELECT l.canonical_key, l.commence_time, l.market, l.leg_side,
           byom_leg_label(l.market, l.leg_side, l.team, l.point, l.player_name),
           l.home_team, l.away_team, l.player_name, l.point, l.price,
           l.result, l.units, l.locked_at, count(*) OVER ()
      FROM byom_legs(p_season, p_filters, COALESCE(p_timing, 'official')) l
     WHERE l.units IS NOT NULL
     ORDER BY l.commence_time DESC NULLS LAST, l.canonical_key, l.market,
              l.player_name NULLS FIRST, l.leg_side
     LIMIT 500
  $body$;
  $fn$;

  -- ── byom_backtest: same signature and columns, closing rows ───────────
  EXECUTE $fn$
  CREATE OR REPLACE FUNCTION public.byom_backtest(
    p_season integer,
    p_filters jsonb DEFAULT '{}'::jsonb
  )
  RETURNS TABLE (
    market text, bets bigint, wins bigint, losses bigint, pushes bigint,
    ties bigint, units numeric, skipped bigint
  )
  LANGUAGE sql
  STABLE
  SECURITY INVOKER
  SET search_path = public, pg_temp
  AS $body$
    -- byom_backtest_v1
    -- byom_dk_start_price
    -- byom_dk_price_fallback
    -- byom_total_side
    -- byom_prop_dk_prices
    -- byom_prop_side
    -- byom_nba_props
    -- byom_prop_phase_a
    -- byom_official_legs_v1
    SELECT r.market, r.bets, r.wins, r.losses, r.pushes, r.ties, r.units, r.skipped
      FROM byom_record(p_season, p_filters) r
     WHERE r.timing = 'close'
     ORDER BY r.market
  $body$;
  $fn$;

  REVOKE ALL ON FUNCTION public.byom_risk_units(numeric) FROM PUBLIC;
  REVOKE ALL ON FUNCTION public.byom_win_units(numeric) FROM PUBLIC;
  REVOKE ALL ON FUNCTION public.byom_leg_label(text, text, text, numeric, text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION public.byom_legs(integer, jsonb, text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION public.byom_record(integer, jsonb) FROM PUBLIC;
  REVOKE ALL ON FUNCTION public.byom_bets(integer, jsonb, text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION public.byom_backtest(integer, jsonb) FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION public.byom_risk_units(numeric) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.byom_win_units(numeric) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.byom_leg_label(text, text, text, numeric, text) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.byom_legs(integer, jsonb, text) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.byom_record(integer, jsonb) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.byom_bets(integer, jsonb, text) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.byom_backtest(integer, jsonb) TO anon, authenticated;
END $mig$;
