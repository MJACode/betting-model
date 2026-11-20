-- Step B, part 2: tracked_bets owner column and owner-only policies.
-- HAND APPLIED in the Supabase SQL editor (project vvprgnrmzeekokzkrkfu).
-- Part 1 (every anon revoke) was applied 2026-11-20 through the MCP; this
-- part needs a confirmation the MCP prompt could not get. One transaction:
-- it either applies whole or not at all. The guard at the end refuses to
-- commit unless the 3 policies are owner-scoped and all 145 rows are still
-- there. Backup: ops.tracked_bets_pre_step_b_20261120 (145 rows, hash-matched).
-- The two legacy anon policies are renamed and retargeted rather than
-- dropped, which ends in the same three policies as step B.

BEGIN;

ALTER TABLE public.tracked_bets
    ADD COLUMN IF NOT EXISTS user_id uuid NULL DEFAULT auth.uid()
    REFERENCES auth.users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS tracked_bets_user_id_idx
    ON public.tracked_bets (user_id);

DO $backfill$
DECLARE src text := '';
BEGIN
  IF to_regclass('public.app_timings') IS NOT NULL THEN
    src := 'SELECT device_id, user_id FROM public.app_timings'
        || ' WHERE user_id IS NOT NULL AND device_id IS NOT NULL';
  END IF;
  IF to_regclass('public.feedback_threads') IS NOT NULL THEN
    IF src <> '' THEN src := src || ' UNION '; END IF;
    src := src || 'SELECT device_id, user_id FROM public.feedback_threads'
        || ' WHERE user_id IS NOT NULL AND device_id IS NOT NULL';
  END IF;
  IF src = '' THEN RETURN; END IF;
  EXECUTE
    'UPDATE public.tracked_bets tb SET user_id = mapped.user_id FROM ('
    || 'SELECT device_id, min(user_id::text)::uuid AS user_id FROM ('
    || src || ') seen GROUP BY device_id '
    || 'HAVING count(DISTINCT user_id) = 1) mapped '
    || 'WHERE tb.user_id IS NULL AND tb.device_id = mapped.device_id';
END $backfill$;
ALTER POLICY "anon insert tracked_bets" ON public.tracked_bets RENAME TO tracked_bets_owner_insert;
ALTER POLICY tracked_bets_owner_insert ON public.tracked_bets
    TO authenticated WITH CHECK (user_id = (SELECT auth.uid()));
ALTER POLICY "anon delete tracked_bets" ON public.tracked_bets RENAME TO tracked_bets_owner_delete;
ALTER POLICY tracked_bets_owner_delete ON public.tracked_bets
    TO authenticated USING (user_id = (SELECT auth.uid()));
CREATE POLICY tracked_bets_owner_select ON public.tracked_bets
    FOR SELECT TO authenticated
    USING (user_id = (SELECT auth.uid()));
REVOKE ALL ON public.tracked_bets FROM anon;
REVOKE ALL ON public.tracked_bets FROM authenticated;
GRANT SELECT, INSERT, DELETE ON public.tracked_bets TO authenticated;

-- Direct DELETE cannot see a legacy NULL user_id row. This function can,
-- and only when no other account is stored for that device.
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
END $fn$;
REVOKE ALL ON FUNCTION public.untrack_tracked_bet(text, bigint) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.untrack_tracked_bet(text, bigint)
    TO postgres, authenticated, service_role;

-- Account deletion. Same rule as untrack, for every row on this device.
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
END $fn$;
REVOKE ALL ON FUNCTION public.clear_my_tracked_bets(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.clear_my_tracked_bets(text)
    TO postgres, authenticated, service_role;

DO $guard$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM pg_policy WHERE polrelid = 'public.tracked_bets'::regclass;
  IF n <> 3 THEN RAISE EXCEPTION 'tracked_bets has % policies, expected 3', n; END IF;
  IF EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = 'public.tracked_bets'::regclass
               AND (cardinality(p.polroles) = 0
                    OR 'anon'::regrole = ANY (p.polroles)
                    OR pg_get_expr(coalesce(p.polqual, p.polwithcheck), p.polrelid) NOT LIKE '%auth.uid()%')) THEN
    RAISE EXCEPTION 'a tracked_bets policy is not owner-scoped';
  END IF;
  IF has_table_privilege('anon', 'public.tracked_bets', 'INSERT')
     OR has_table_privilege('anon', 'public.tracked_bets', 'DELETE') THEN
    RAISE EXCEPTION 'anon can still write tracked_bets';
  END IF;
  IF has_function_privilege('anon', 'public.untrack_tracked_bet(text,bigint)', 'EXECUTE')
     OR has_function_privilege('anon', 'public.clear_my_tracked_bets(text)', 'EXECUTE') THEN
    RAISE EXCEPTION 'anon can execute a tracked_bets function';
  END IF;
  SELECT count(*) INTO n FROM public.tracked_bets;
  IF n <> 145 THEN RAISE EXCEPTION 'tracked_bets row count changed to %', n; END IF;
END $guard$;

NOTIFY pgrst, 'reload schema';
COMMIT;
