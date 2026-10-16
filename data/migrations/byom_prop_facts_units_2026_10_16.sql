-- Label prop unit columns and record why a prop did or did not grade.
--
-- UNAPPLIED. Runs after byom_facts_schema_2026_10_16.sql. The facts
-- schema created over_units and under_units with no cap label. This file
-- adds the labelled pair and log_status, then drops the unlabelled
-- columns. A second pass returns before ALTER.
--
-- log_status is the thin-data rule that fired: logged,
-- non_participant, missing_log, unplayed, ambiguous. See byom/prop_facts.py.
-- Anytime TD limits are not a column. They are the stat the builder sums.
--
-- The unit columns are results, not a stake. The 24h prop lock is
-- UNCONFIRMED and is not in this file.
-- One DO block. No CONCURRENTLY.

DO $mig$
BEGIN
  IF to_regclass('public.byom_prop_facts') IS NULL THEN
    RAISE EXCEPTION 'byom_prop_facts is missing; apply the facts schema first';
  END IF;

  IF EXISTS (
       SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'byom_prop_facts'
          AND column_name = 'over_units_uncapped')
     AND EXISTS (
       SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'byom_prop_facts'
          AND column_name = 'log_status')
     AND NOT EXISTS (
       SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'byom_prop_facts'
          AND column_name = 'over_units')
  THEN
    RAISE NOTICE 'byom prop unit columns already labelled - skipping';
    RETURN;
  END IF;

  ALTER TABLE public.byom_prop_facts
    ADD COLUMN IF NOT EXISTS over_units_uncapped NUMERIC,
    ADD COLUMN IF NOT EXISTS over_units_capped NUMERIC,
    ADD COLUMN IF NOT EXISTS under_units_uncapped NUMERIC,
    ADD COLUMN IF NOT EXISTS under_units_capped NUMERIC,
    ADD COLUMN IF NOT EXISTS log_status TEXT;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
     WHERE conname = 'byom_prop_facts_log_status') THEN
    ALTER TABLE public.byom_prop_facts
      ADD CONSTRAINT byom_prop_facts_log_status CHECK (
        log_status IS NULL OR log_status IN (
          'logged', 'non_participant', 'missing_log', 'unplayed', 'ambiguous'));
  END IF;

  ALTER TABLE public.byom_prop_facts
    DROP COLUMN IF EXISTS over_units,
    DROP COLUMN IF EXISTS under_units;
END $mig$;
