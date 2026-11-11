-- DraftKings over and under prices on byom_prop_facts.
--
-- NOT in data/view_migrations.ACTIVE_MIGRATIONS. The worker re-runs
-- that list against production. Apply this file by hand. It is
-- idempotent: ADD COLUMN IF NOT EXISTS. A second pass adds nothing.
-- It does not replace byom_backtest. The function that stakes these
-- columns is byom_backtest_prop_dk_prices_2026_10_28.sql.
--
-- Nullable NUMERIC. A missing price stays null. This file does not
-- fill one in, and it does not write picks.
--
-- The builder stores the American price from the same DraftKings
-- quote that supplied the line. A side that quote does not price is
-- null. This file only adds the columns.
--
-- Does not create byom_prop_facts_units_2026_10_16.sql. There is no
-- unit column here.
-- One DO block. No CONCURRENTLY.

DO $mig$
BEGIN
  IF to_regclass('public.byom_prop_facts') IS NULL THEN
    RAISE EXCEPTION 'byom_prop_facts is not present; apply byom_facts_schema_2026_10_16.sql first';
  END IF;

  ALTER TABLE public.byom_prop_facts
    ADD COLUMN IF NOT EXISTS over_price NUMERIC;
  ALTER TABLE public.byom_prop_facts
    ADD COLUMN IF NOT EXISTS under_price NUMERIC;
END $mig$;
