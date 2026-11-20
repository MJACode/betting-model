-- tracked_bets: each signed-in account owns its own rows (anon-key lockdown,
-- step B part 2). Applied by the worker through ACTIVE_MIGRATIONS, so it is one
-- DO block and safe to run on every pass: once the owner column and the three
-- owner policies exist, it returns without touching anything.
--
-- Before: anon and authenticated could INSERT any row (check true) and DELETE
-- with USING true, so one client could wipe every tracked bet. Step B part 1
-- (2026-11-20) already took every anon grant away; this closes the signed-in
-- half. Backup: ops.tracked_bets_pre_step_b_20261120 (145 rows, hash-matched).
--
-- Same end state as anon_lockdown_step_b_2026_11.sql's tracked_bets section.
-- The two legacy anon policies are renamed and retargeted rather than dropped.
-- No row is deleted here. Legacy rows keep user_id NULL unless their device
-- maps to exactly one account; the worker still reads them (it bypasses RLS).

DO $mig$
DECLARE
  src text := '';
  n int;
BEGIN
  IF to_regclass('public.tracked_bets') IS NULL THEN
    RETURN;
  END IF;

  -- Already applied: owner column present, the three owner policies present,
  -- and no policy still open to anon or to every role.
  IF EXISTS (SELECT 1 FROM information_schema.columns
              WHERE table_schema = 'public' AND table_name = 'tracked_bets'
                AND column_name = 'user_id')
     AND (SELECT count(*) FROM pg_policy
           WHERE polrelid = 'public.tracked_bets'::regclass
             AND polname IN ('tracked_bets_owner_insert',
                             'tracked_bets_owner_select',
                             'tracked_bets_owner_delete')) = 3
     AND NOT EXISTS (SELECT 1 FROM pg_policy p
                      WHERE p.polrelid = 'public.tracked_bets'::regclass
                        AND (cardinality(p.polroles) = 0
                             OR 'anon'::regrole = ANY (p.polroles)))
  THEN
    RETURN;
  END IF;

  ALTER TABLE public.tracked_bets
      ADD COLUMN IF NOT EXISTS user_id uuid NULL DEFAULT auth.uid()
      REFERENCES auth.users(id) ON DELETE CASCADE;
  CREATE INDEX IF NOT EXISTS tracked_bets_user_id_idx
      ON public.tracked_bets (user_id);

  -- Fill a legacy row only when its device maps to exactly one account.
  IF to_regclass('public.app_timings') IS NOT NULL THEN
    src := 'SELECT device_id, user_id FROM public.app_timings'
        || ' WHERE user_id IS NOT NULL AND device_id IS NOT NULL';
  END IF;
  IF to_regclass('public.feedback_threads') IS NOT NULL THEN
    IF src <> '' THEN src := src || ' UNION '; END IF;
    src := src || 'SELECT device_id, user_id FROM public.feedback_threads'
        || ' WHERE user_id IS NOT NULL AND device_id IS NOT NULL';
  END IF;
  IF src <> '' THEN
    EXECUTE
      'UPDATE public.tracked_bets tb SET user_id = mapped.user_id FROM ('
      || 'SELECT device_id, min(user_id::text)::uuid AS user_id FROM ('
      || src || ') seen GROUP BY device_id '
      || 'HAVING count(DISTINCT user_id) = 1) mapped '
      || 'WHERE tb.user_id IS NULL AND tb.device_id = mapped.device_id';
  END IF;

  -- Owner policies. Rename the legacy ones where they exist; create the rest.
  IF EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = 'public.tracked_bets'::regclass
               AND polname = 'anon insert tracked_bets')
     AND NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = 'public.tracked_bets'::regclass
               AND polname = 'tracked_bets_owner_insert') THEN
    ALTER POLICY "anon insert tracked_bets" ON public.tracked_bets
        RENAME TO tracked_bets_owner_insert;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = 'public.tracked_bets'::regclass
               AND polname = 'anon delete tracked_bets')
     AND NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = 'public.tracked_bets'::regclass
               AND polname = 'tracked_bets_owner_delete') THEN
    ALTER POLICY "anon delete tracked_bets" ON public.tracked_bets
        RENAME TO tracked_bets_owner_delete;
  END IF;

  IF EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = 'public.tracked_bets'::regclass
               AND polname = 'tracked_bets_owner_insert') THEN
    ALTER POLICY tracked_bets_owner_insert ON public.tracked_bets
        TO authenticated WITH CHECK (user_id = (SELECT auth.uid()));
  ELSE
    CREATE POLICY tracked_bets_owner_insert ON public.tracked_bets
        FOR INSERT TO authenticated
        WITH CHECK (user_id = (SELECT auth.uid()));
  END IF;
  IF EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = 'public.tracked_bets'::regclass
               AND polname = 'tracked_bets_owner_delete') THEN
    ALTER POLICY tracked_bets_owner_delete ON public.tracked_bets
        TO authenticated USING (user_id = (SELECT auth.uid()));
  ELSE
    CREATE POLICY tracked_bets_owner_delete ON public.tracked_bets
        FOR DELETE TO authenticated
        USING (user_id = (SELECT auth.uid()));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policy WHERE polrelid = 'public.tracked_bets'::regclass
               AND polname = 'tracked_bets_owner_select') THEN
    CREATE POLICY tracked_bets_owner_select ON public.tracked_bets
        FOR SELECT TO authenticated
        USING (user_id = (SELECT auth.uid()));
  END IF;

  REVOKE ALL ON public.tracked_bets FROM anon;
  REVOKE ALL ON public.tracked_bets FROM authenticated;
  GRANT SELECT, INSERT, DELETE ON public.tracked_bets TO authenticated;
  IF to_regclass('public.tracked_bets_id_seq') IS NOT NULL THEN
    GRANT USAGE ON SEQUENCE public.tracked_bets_id_seq TO authenticated;
  END IF;

  -- A direct DELETE cannot see a legacy NULL row. These can, and only when no
  -- other account is stored for that device.
  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.untrack_tracked_bet(
        p_device_id text, p_pick_id bigint)
    RETURNS void
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = ''
    AS $fn$
    DECLARE
      uid uuid := auth.uid();
      other_owner boolean := false;
    BEGIN
      IF uid IS NULL THEN
        RAISE EXCEPTION 'untrack_tracked_bet: sign in required' USING ERRCODE = '42501';
      END IF;
      IF p_device_id IS NULL OR p_device_id !~ '^[A-Za-z0-9-]{8,64}$' THEN
        RAISE EXCEPTION 'untrack_tracked_bet: bad device id' USING ERRCODE = '22023';
      END IF;
      IF to_regclass('public.app_timings') IS NOT NULL THEN
        EXECUTE
          'SELECT EXISTS (SELECT 1 FROM public.app_timings'
          || ' WHERE device_id = $1 AND user_id IS NOT NULL AND user_id <> $2)'
          INTO other_owner USING p_device_id, uid;
      END IF;
      IF NOT other_owner AND to_regclass('public.feedback_threads') IS NOT NULL THEN
        EXECUTE
          'SELECT EXISTS (SELECT 1 FROM public.feedback_threads'
          || ' WHERE device_id = $1 AND user_id IS NOT NULL AND user_id <> $2)'
          INTO other_owner USING p_device_id, uid;
      END IF;
      IF other_owner THEN
        DELETE FROM public.tracked_bets
         WHERE pick_id = p_pick_id AND device_id = p_device_id AND user_id = uid;
        RETURN;
      END IF;
      DELETE FROM public.tracked_bets
       WHERE pick_id = p_pick_id AND device_id = p_device_id
         AND (user_id = uid OR user_id IS NULL);
    END $fn$
  $ddl$;
  REVOKE ALL ON FUNCTION public.untrack_tracked_bet(text, bigint) FROM PUBLIC, anon;
  GRANT EXECUTE ON FUNCTION public.untrack_tracked_bet(text, bigint)
      TO postgres, authenticated, service_role;

  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.clear_my_tracked_bets(p_device_id text)
    RETURNS void
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = ''
    AS $fn$
    DECLARE
      uid uuid := auth.uid();
      other_owner boolean := false;
    BEGIN
      IF uid IS NULL THEN
        RAISE EXCEPTION 'clear_my_tracked_bets: sign in required' USING ERRCODE = '42501';
      END IF;
      IF p_device_id IS NULL OR p_device_id !~ '^[A-Za-z0-9-]{8,64}$' THEN
        RAISE EXCEPTION 'clear_my_tracked_bets: bad device id' USING ERRCODE = '22023';
      END IF;
      IF to_regclass('public.app_timings') IS NOT NULL THEN
        EXECUTE
          'SELECT EXISTS (SELECT 1 FROM public.app_timings'
          || ' WHERE device_id = $1 AND user_id IS NOT NULL AND user_id <> $2)'
          INTO other_owner USING p_device_id, uid;
      END IF;
      IF NOT other_owner AND to_regclass('public.feedback_threads') IS NOT NULL THEN
        EXECUTE
          'SELECT EXISTS (SELECT 1 FROM public.feedback_threads'
          || ' WHERE device_id = $1 AND user_id IS NOT NULL AND user_id <> $2)'
          INTO other_owner USING p_device_id, uid;
      END IF;
      IF other_owner THEN
        DELETE FROM public.tracked_bets
         WHERE device_id = p_device_id AND user_id = uid;
        RETURN;
      END IF;
      DELETE FROM public.tracked_bets
       WHERE device_id = p_device_id
         AND (user_id = uid OR user_id IS NULL);
    END $fn$
  $ddl$;
  REVOKE ALL ON FUNCTION public.clear_my_tracked_bets(text) FROM PUBLIC, anon;
  GRANT EXECUTE ON FUNCTION public.clear_my_tracked_bets(text)
      TO postgres, authenticated, service_role;

  -- Read-back. Any failure raises and the whole block rolls back.
  SELECT count(*) INTO n FROM pg_policy WHERE polrelid = 'public.tracked_bets'::regclass;
  IF n <> 3 THEN
    RAISE EXCEPTION 'tracked_bets has % policies, expected 3', n;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = 'public.tracked_bets'::regclass
               AND (cardinality(p.polroles) = 0
                    OR 'anon'::regrole = ANY (p.polroles)
                    OR pg_get_expr(coalesce(p.polqual, p.polwithcheck), p.polrelid)
                       NOT LIKE '%auth.uid()%')) THEN
    RAISE EXCEPTION 'a tracked_bets policy is not owner-scoped';
  END IF;
  IF has_table_privilege('anon', 'public.tracked_bets', 'INSERT')
     OR has_table_privilege('anon', 'public.tracked_bets', 'DELETE') THEN
    RAISE EXCEPTION 'anon can still write tracked_bets';
  END IF;
END
$mig$;
