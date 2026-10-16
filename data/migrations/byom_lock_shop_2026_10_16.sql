-- Build Your Own Model: the book shop at the DraftKings lock.
--
-- UNAPPLIED. This file has not been run against production. It is in
-- data/view_migrations.ACTIVE_MIGRATIONS, so the worker creates the empty
-- table on the first pass after merge. A second pass returns on the
-- catalog read below and does not take ACCESS EXCLUSIVE.
--
-- Worker-only. The rows are every book's price at DraftKings' line,
-- including Pinnacle. The app does not read them. anon and authenticated
-- hold no privilege. RLS is on with no policy. The worker owns the table
-- and bypasses RLS. FORCE ROW LEVEL SECURITY is not used.
--
-- One row per book at DraftKings' line, at the grade lock and at the near
-- lock. The windows are UNCONFIRMED placeholders and are not check
-- constraints: the builder writes the window it used onto the row.
--
-- The first capture is kept. A later rebuild grades from these rows after
-- the live quotes have been pruned. Nothing here is a pick or a stake.
--
-- One DO block. data/view_migrations runs each file as one statement.
-- No CONCURRENTLY.

DO $mig$
BEGIN
  IF to_regclass('public.byom_lock_shop') IS NOT NULL THEN
    IF (SELECT relrowsecurity FROM pg_class
         WHERE oid = 'public.byom_lock_shop'::regclass)
       AND NOT EXISTS (
         SELECT 1 FROM pg_policy
          WHERE polrelid = 'public.byom_lock_shop'::regclass)
       AND NOT EXISTS (
         SELECT 1
           FROM (VALUES ('anon'), ('authenticated')) AS role(name)
           CROSS JOIN (VALUES
             ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE'),
             ('TRUNCATE'), ('REFERENCES'), ('TRIGGER')) AS verb(name)
          WHERE has_table_privilege(
            role.name, 'public.byom_lock_shop', verb.name))
    THEN
      RAISE NOTICE 'byom lock shop already present - skipping';
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.byom_lock_shop (
    canonical_key      TEXT NOT NULL,
    sport              TEXT NOT NULL,
    season             INTEGER NOT NULL,
    week               INTEGER NOT NULL,
    -- UNCONFIRMED window, recorded so a row says which placeholder built it.
    lock_window_hours  INTEGER NOT NULL,
    market             TEXT NOT NULL,
    bookmaker          TEXT NOT NULL,
    line_source        TEXT NOT NULL,
    snapshot_at        TIMESTAMPTZ,
    point              NUMERIC,
    dk_point           NUMERIC,
    price_home         NUMERIC,
    price_away         NUMERIC,
    captured_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (canonical_key, lock_window_hours, market, bookmaker),
    CONSTRAINT byom_lock_shop_market CHECK (
      market IN ('spreads', 'totals', 'h2h'))
  );

  CREATE INDEX IF NOT EXISTS idx_byom_lock_shop_season
    ON public.byom_lock_shop (sport, season, week);

  -- A copy applied while this table was readable still has the policy.
  DROP POLICY IF EXISTS "anon read byom_lock_shop" ON public.byom_lock_shop;

  REVOKE ALL ON public.byom_lock_shop FROM PUBLIC, anon, authenticated;
  ALTER TABLE public.byom_lock_shop ENABLE ROW LEVEL SECURITY;
END $mig$;
