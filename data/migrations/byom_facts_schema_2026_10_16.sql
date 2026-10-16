-- Build Your Own Model: one facts row per game, and the prop-facts table
-- the later prop builder fills. NFL first. Nothing here is a pick, a
-- stake, or a model output.
--
-- UNAPPLIED. This file has not been run against production. It is in
-- data/view_migrations.ACTIVE_MIGRATIONS, so the worker creates the empty
-- tables on the first pass after merge. A second pass returns on the
-- catalog read below and does not take ACCESS EXCLUSIVE.
--
-- The 120h and 24h lock windows are UNCONFIRMED placeholders. They are
-- not check constraints: the builder writes the window it used onto the
-- row. Changing the window does not need a new migration.
--
-- canonical_key is season_WW_away_home (2024_01_BAL_KC). games.game_id is
-- that key with an NFL_ prefix. nfl_odds_history uses the bare key through
-- 2025 and the prefixed key in 2026. games.week is NULL for every NFL
-- season; week is parsed from the key.
--
-- Results are 1u-to-win units. A push and a tie are stored, not dropped.
-- No spread-size, price-band, or line-range constraint.
--
-- One DO block. data/view_migrations runs each file as one statement.
-- No CONCURRENTLY.

DO $mig$
BEGIN
  IF to_regclass('public.byom_game_facts') IS NOT NULL
     AND to_regclass('public.byom_prop_facts') IS NOT NULL THEN
    IF (SELECT relrowsecurity FROM pg_class
         WHERE oid = 'public.byom_game_facts'::regclass)
       AND (SELECT relrowsecurity FROM pg_class
             WHERE oid = 'public.byom_prop_facts'::regclass)
       AND EXISTS (
         SELECT 1 FROM pg_policy
          WHERE polrelid = 'public.byom_game_facts'::regclass
            AND polname = 'anon read byom_game_facts')
       AND EXISTS (
         SELECT 1 FROM pg_policy
          WHERE polrelid = 'public.byom_prop_facts'::regclass
            AND polname = 'anon read byom_prop_facts')
       AND has_table_privilege('anon', 'public.byom_game_facts', 'SELECT')
       AND has_table_privilege('authenticated', 'public.byom_game_facts', 'SELECT')
       AND has_table_privilege('anon', 'public.byom_prop_facts', 'SELECT')
       AND has_table_privilege('authenticated', 'public.byom_prop_facts', 'SELECT')
       AND NOT EXISTS (
         SELECT 1
           FROM (VALUES
                  ('anon'),
                  ('authenticated')
                ) AS role(name)
           CROSS JOIN (VALUES
                  ('public.byom_game_facts'),
                  ('public.byom_prop_facts')
                ) AS rel(name)
           CROSS JOIN (VALUES
                  ('INSERT'),
                  ('UPDATE'),
                  ('DELETE'),
                  ('TRUNCATE'),
                  ('REFERENCES'),
                  ('TRIGGER')
                ) AS verb(name)
          WHERE has_table_privilege(role.name, rel.name, verb.name))
    THEN
      RAISE NOTICE 'byom facts schema already present - skipping';
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.byom_game_facts (
    canonical_key           TEXT PRIMARY KEY,
    sport                   TEXT NOT NULL,
    season                  INTEGER NOT NULL,
    week                    INTEGER NOT NULL,
    away_team               TEXT NOT NULL,
    home_team               TEXT NOT NULL,
    game_date               DATE,
    commence_time           TIMESTAMPTZ,
    home_score              NUMERIC,
    away_score              NUMERIC,
    -- UNCONFIRMED windows, recorded so a row says which placeholder built it.
    lock_window_hours       INTEGER NOT NULL,
    near_window_hours       INTEGER NOT NULL,
    lock_spread_at          TIMESTAMPTZ,
    lock_spread_lead_hours  NUMERIC,
    dk_spread_home          NUMERIC,
    dk_spread_home_price    NUMERIC,
    dk_spread_away_price    NUMERIC,
    lock_total_at           TIMESTAMPTZ,
    lock_total_lead_hours   NUMERIC,
    dk_total                NUMERIC,
    dk_over_price           NUMERIC,
    dk_under_price          NUMERIC,
    lock_ml_at              TIMESTAMPTZ,
    lock_ml_lead_hours      NUMERIC,
    dk_ml_home_price        NUMERIC,
    dk_ml_away_price        NUMERIC,
    near_spread_at          TIMESTAMPTZ,
    near_spread_home        NUMERIC,
    near_spread_home_price  NUMERIC,
    near_spread_away_price  NUMERIC,
    near_total_at           TIMESTAMPTZ,
    near_total              NUMERIC,
    near_over_price         NUMERIC,
    near_under_price        NUMERIC,
    near_ml_at              TIMESTAMPTZ,
    near_ml_home_price      NUMERIC,
    near_ml_away_price      NUMERIC,
    close_spread_at         TIMESTAMPTZ,
    close_spread_home       NUMERIC,
    close_spread_home_price NUMERIC,
    close_spread_away_price NUMERIC,
    close_total_at          TIMESTAMPTZ,
    close_total             NUMERIC,
    close_over_price        NUMERIC,
    close_under_price       NUMERIC,
    close_ml_at             TIMESTAMPTZ,
    close_ml_home_price     NUMERIC,
    close_ml_away_price     NUMERIC,
    grade_spread_home_price NUMERIC,
    grade_spread_home_book  TEXT,
    grade_spread_away_price NUMERIC,
    grade_spread_away_book  TEXT,
    grade_over_price        NUMERIC,
    grade_over_book         TEXT,
    grade_under_price       NUMERIC,
    grade_under_book        TEXT,
    grade_ml_home_price     NUMERIC,
    grade_ml_home_book      TEXT,
    grade_ml_away_price     NUMERIC,
    grade_ml_away_book      TEXT,
    ats_home_result         TEXT,
    ats_home_units          NUMERIC,
    ats_away_result         TEXT,
    ats_away_units          NUMERIC,
    ml_home_result          TEXT,
    ml_home_units           NUMERIC,
    ml_away_result          TEXT,
    ml_away_units           NUMERIC,
    ou_over_result          TEXT,
    ou_over_units           NUMERIC,
    ou_under_result         TEXT,
    ou_under_units          NUMERIC,
    home_rest_days          INTEGER,
    away_rest_days          INTEGER,
    is_primetime            BOOLEAN,
    home_role               TEXT,
    away_role               TEXT,
    line_source             TEXT NOT NULL,
    built_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT byom_game_facts_ats_home CHECK (
      ats_home_result IS NULL OR ats_home_result IN ('win', 'loss', 'push')),
    CONSTRAINT byom_game_facts_ats_away CHECK (
      ats_away_result IS NULL OR ats_away_result IN ('win', 'loss', 'push')),
    CONSTRAINT byom_game_facts_ml_home CHECK (
      ml_home_result IS NULL OR ml_home_result IN ('win', 'loss', 'tie')),
    CONSTRAINT byom_game_facts_ml_away CHECK (
      ml_away_result IS NULL OR ml_away_result IN ('win', 'loss', 'tie')),
    CONSTRAINT byom_game_facts_ou_over CHECK (
      ou_over_result IS NULL OR ou_over_result IN ('win', 'loss', 'push')),
    CONSTRAINT byom_game_facts_ou_under CHECK (
      ou_under_result IS NULL OR ou_under_result IN ('win', 'loss', 'push')),
    CONSTRAINT byom_game_facts_home_role CHECK (
      home_role IS NULL OR home_role IN ('favorite', 'underdog', 'pickem')),
    CONSTRAINT byom_game_facts_away_role CHECK (
      away_role IS NULL OR away_role IN ('favorite', 'underdog', 'pickem'))
  );

  CREATE TABLE IF NOT EXISTS public.byom_prop_facts (
    prop_key            TEXT PRIMARY KEY,
    canonical_key       TEXT NOT NULL,
    sport               TEXT NOT NULL,
    season              INTEGER NOT NULL,
    week                INTEGER NOT NULL,
    player_name         TEXT NOT NULL,
    player_key          TEXT,
    team                TEXT,
    market              TEXT NOT NULL,
    line                NUMERIC,
    lock_window_hours   INTEGER NOT NULL,
    lock_snapshot_at    TIMESTAMPTZ,
    dk_over_price       NUMERIC,
    dk_under_price      NUMERIC,
    grade_over_price    NUMERIC,
    grade_over_book     TEXT,
    grade_under_price   NUMERIC,
    grade_under_book    TEXT,
    close_snapshot_at   TIMESTAMPTZ,
    close_over_price    NUMERIC,
    close_under_price   NUMERIC,
    actual              NUMERIC,
    over_result         TEXT,
    over_units          NUMERIC,
    under_result        TEXT,
    under_units         NUMERIC,
    line_source         TEXT NOT NULL,
    built_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT byom_prop_facts_over_result CHECK (
      over_result IS NULL OR over_result IN ('win', 'loss', 'push')),
    CONSTRAINT byom_prop_facts_under_result CHECK (
      under_result IS NULL OR under_result IN ('win', 'loss', 'push'))
  );

  CREATE INDEX IF NOT EXISTS idx_byom_game_facts_season
    ON public.byom_game_facts (sport, season, week);
  CREATE INDEX IF NOT EXISTS idx_byom_game_facts_date
    ON public.byom_game_facts (game_date);
  CREATE INDEX IF NOT EXISTS idx_byom_prop_facts_game
    ON public.byom_prop_facts (canonical_key);
  CREATE INDEX IF NOT EXISTS idx_byom_prop_facts_season
    ON public.byom_prop_facts (sport, season, week);

  -- Supabase's default privileges hand anon every verb. Display data is
  -- SELECT only. RLS with a SELECT policy is the read; the revoke is what
  -- stops a write if a later grant is wider than the policy.
  REVOKE ALL ON public.byom_game_facts FROM PUBLIC, anon, authenticated;
  REVOKE ALL ON public.byom_prop_facts FROM PUBLIC, anon, authenticated;
  GRANT SELECT ON public.byom_game_facts TO anon, authenticated;
  GRANT SELECT ON public.byom_prop_facts TO anon, authenticated;
  ALTER TABLE public.byom_game_facts ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.byom_prop_facts ENABLE ROW LEVEL SECURITY;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
     WHERE polrelid = 'public.byom_game_facts'::regclass
       AND polname = 'anon read byom_game_facts') THEN
    CREATE POLICY "anon read byom_game_facts"
      ON public.byom_game_facts
      FOR SELECT TO anon, authenticated
      USING (true);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
     WHERE polrelid = 'public.byom_prop_facts'::regclass
       AND polname = 'anon read byom_prop_facts') THEN
    CREATE POLICY "anon read byom_prop_facts"
      ON public.byom_prop_facts
      FOR SELECT TO anon, authenticated
      USING (true);
  END IF;
END $mig$;
