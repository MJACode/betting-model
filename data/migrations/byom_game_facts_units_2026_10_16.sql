-- Label the two unit columns on byom_game_facts.
--
-- UNAPPLIED. Runs after byom_facts_schema_2026_10_16.sql. The first pass
-- adds the labelled columns and drops the unlabelled ones. A second pass
-- returns before ALTER, so it does not take ACCESS EXCLUSIVE again.
--
-- units_uncapped is the 1u-to-win result with no risk ceiling.
-- units_capped is the result after a 3-unit risk ceiling: risk above 3
-- is cut to 3, and a win is recomputed from that risk. Both columns are
-- results. The 120h and 24h windows are UNCONFIRMED and are not in this file.
--
-- One DO block. No CONCURRENTLY.

DO $mig$
BEGIN
  IF to_regclass('public.byom_game_facts') IS NULL THEN
    RAISE EXCEPTION 'byom_game_facts is missing; apply the facts schema first';
  END IF;

  IF EXISTS (
       SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'byom_game_facts'
          AND column_name = 'ats_home_units_uncapped')
     AND NOT EXISTS (
       SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'byom_game_facts'
          AND column_name = 'ats_home_units')
  THEN
    RAISE NOTICE 'byom unit columns already labelled - skipping';
    RETURN;
  END IF;

  ALTER TABLE public.byom_game_facts
    ADD COLUMN IF NOT EXISTS ats_home_units_uncapped NUMERIC,
    ADD COLUMN IF NOT EXISTS ats_home_units_capped NUMERIC,
    ADD COLUMN IF NOT EXISTS ats_away_units_uncapped NUMERIC,
    ADD COLUMN IF NOT EXISTS ats_away_units_capped NUMERIC,
    ADD COLUMN IF NOT EXISTS ml_home_units_uncapped NUMERIC,
    ADD COLUMN IF NOT EXISTS ml_home_units_capped NUMERIC,
    ADD COLUMN IF NOT EXISTS ml_away_units_uncapped NUMERIC,
    ADD COLUMN IF NOT EXISTS ml_away_units_capped NUMERIC,
    ADD COLUMN IF NOT EXISTS ou_over_units_uncapped NUMERIC,
    ADD COLUMN IF NOT EXISTS ou_over_units_capped NUMERIC,
    ADD COLUMN IF NOT EXISTS ou_under_units_uncapped NUMERIC,
    ADD COLUMN IF NOT EXISTS ou_under_units_capped NUMERIC;

  ALTER TABLE public.byom_game_facts
    DROP COLUMN IF EXISTS ats_home_units,
    DROP COLUMN IF EXISTS ats_away_units,
    DROP COLUMN IF EXISTS ml_home_units,
    DROP COLUMN IF EXISTS ml_away_units,
    DROP COLUMN IF EXISTS ou_over_units,
    DROP COLUMN IF EXISTS ou_under_units;
END $mig$;
