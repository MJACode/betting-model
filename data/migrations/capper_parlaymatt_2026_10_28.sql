-- ParlayMatt shares Eggz's capper tables. capper_key says whose row it is.
-- Existing rows are Eggz. parlay_id points a leg at the one parlay row that
-- carries the stated price and stake. A leg is not a second unit.
--
-- Does not rewrite picks, snapshots, push_sent, or the published views.
-- Single DO block. Returns before ALTER once the property holds: both
-- capper_key columns are NOT NULL with the eggz default, and parlay_id exists.

DO $mig$
BEGIN
  IF to_regclass('public.capper_picks') IS NULL
     OR to_regclass('public.capper_messages') IS NULL
  THEN
    RAISE NOTICE 'capper tables are not here yet - skipping';
    RETURN;
  END IF;

  IF EXISTS (
       SELECT 1 FROM information_schema.columns
       WHERE table_schema = 'public' AND table_name = 'capper_picks'
         AND column_name = 'parlay_id'
     )
     AND EXISTS (
       SELECT 1 FROM information_schema.columns
       WHERE table_schema = 'public' AND table_name = 'capper_picks'
         AND column_name = 'capper_key' AND is_nullable = 'NO'
         AND column_default LIKE '%eggz%'
     )
     AND EXISTS (
       SELECT 1 FROM information_schema.columns
       WHERE table_schema = 'public' AND table_name = 'capper_messages'
         AND column_name = 'capper_key' AND is_nullable = 'NO'
         AND column_default LIKE '%eggz%'
     )
  THEN
    RAISE NOTICE 'capper key columns already present - skipping';
    RETURN;
  END IF;

  ALTER TABLE public.capper_picks ADD COLUMN IF NOT EXISTS capper_key TEXT;
  ALTER TABLE public.capper_picks ADD COLUMN IF NOT EXISTS parlay_id BIGINT;
  ALTER TABLE public.capper_messages ADD COLUMN IF NOT EXISTS capper_key TEXT;

  UPDATE public.capper_picks SET capper_key = 'eggz' WHERE capper_key IS NULL;
  UPDATE public.capper_messages SET capper_key = 'eggz' WHERE capper_key IS NULL;

  ALTER TABLE public.capper_picks ALTER COLUMN capper_key SET DEFAULT 'eggz';
  ALTER TABLE public.capper_messages ALTER COLUMN capper_key SET DEFAULT 'eggz';
  ALTER TABLE public.capper_picks ALTER COLUMN capper_key SET NOT NULL;
  ALTER TABLE public.capper_messages ALTER COLUMN capper_key SET NOT NULL;
END $mig$;
