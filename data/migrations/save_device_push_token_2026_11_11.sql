-- Save one Expo push token without letting the anon key read the table.
--
-- HAND APPLIED. Not in data/view_migrations.ACTIVE_MIGRATIONS, so the worker
-- will not run this. Matt applies it himself. Do not apply it from a session.
--
-- Measured 2026-11-11 on project vvprgnrmzeekokzkrkfu, read-only except for
-- rolled-back SET ROLE anon probes:
--   device_push_tokens: 0 rows. RLS on. Policies are
--     "anon insert device token" FOR INSERT TO anon, authenticated
--       WITH CHECK (true)
--     "anon update device token" FOR UPDATE TO anon, authenticated
--       USING (true) WITH CHECK (true)
--   No SELECT policy. Grants for anon and authenticated include SELECT,
--   INSERT and UPDATE (relacl anon=arwxtm/postgres). Primary key is (token),
--   which matches the client's onConflict: 'token'.
--   app_timings, kind=request, name=device_push_tokens: 23 rows at HTTP 403
--   on app_version 1.3.0 (last 2026-11-11 14:16Z) and 8 older 401s on 1.1.0.
--   No 2xx.
--
-- As role anon, a plain INSERT succeeds. The same INSERT with
-- ON CONFLICT (token) DO UPDATE fails with
--   42501 new row violates row-level security policy for table
--   "device_push_tokens"
-- even when no row exists, so every launch takes the insert path and still
-- 403s. Adding FOR SELECT USING (true) makes that upsert succeed and also
-- lets the anon key SELECT every token. An Expo token is a bearer credential
-- for the keyless push API, so that policy is not the fix. UPDATE ... WHERE
-- token = ... as anon matches 0 rows (no error): the existing opt-out write
-- cannot see its row either.
--
-- This function runs as the table owner, who bypasses RLS, and returns nothing.
-- The same statement revokes anon/authenticated INSERT and UPDATE and drops
-- the two write policies. A plain INSERT as anon succeeded under WITH CHECK
-- (true), so those checks were skippable until the direct path was closed.
-- Re-running replaces the function and re-asserts the grants and the revoke.

DO $mig$
BEGIN
  CREATE OR REPLACE FUNCTION public.save_device_push_token(
      p_token text,
      p_device_id text,
      p_platform text,
      p_enabled boolean,
      p_last_seen text
  ) RETURNS void
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = ''
  AS $fn$
  BEGIN
    -- p_last_seen stays in the signature so a shipped client still matches.
    -- The stored clock is the server's. A device clock is not a staleness source.
    IF p_token IS NULL
       OR p_token !~ '^Expo(nent)?PushToken\[[A-Za-z0-9_-]{10,100}\]$' THEN
      RAISE EXCEPTION 'save_device_push_token: bad token' USING ERRCODE = '22023';
    END IF;
    IF p_device_id IS NOT NULL AND p_device_id !~ '^[A-Za-z0-9-]{8,64}$' THEN
      RAISE EXCEPTION 'save_device_push_token: bad device id' USING ERRCODE = '22023';
    END IF;
    IF p_platform IS NOT NULL AND p_platform NOT IN ('ios', 'android') THEN
      RAISE EXCEPTION 'save_device_push_token: bad platform' USING ERRCODE = '22023';
    END IF;
    IF p_enabled IS NULL THEN
      RAISE EXCEPTION 'save_device_push_token: enabled is required' USING ERRCODE = '22023';
    END IF;

    -- Any caller who already knows the token can disable it, re-enable it,
    -- or rebind device_id. Tokens cannot be listed. Accepted until sign-in
    -- lets auth.uid() own the row; binding the update to the stored device_id
    -- would reject a reinstall that keeps the Expo token and mints a new id.
    INSERT INTO public.device_push_tokens
        (token, device_id, platform, enabled, last_seen)
    VALUES
        (p_token, p_device_id, p_platform, p_enabled, pg_catalog.now()::text)
    ON CONFLICT (token) DO UPDATE
      SET device_id = COALESCE(EXCLUDED.device_id, public.device_push_tokens.device_id),
          platform  = COALESCE(EXCLUDED.platform, public.device_push_tokens.platform),
          enabled   = EXCLUDED.enabled,
          last_seen = pg_catalog.now()::text;
  END
  $fn$;

  ALTER FUNCTION public.save_device_push_token(text, text, text, boolean, text)
    OWNER TO postgres;

  -- PUBLIC holds EXECUTE by default. Revoking only the named roles leaves it
  -- callable. Revoke PUBLIC first, then grant the two roles the app uses.
  REVOKE ALL ON FUNCTION public.save_device_push_token(text, text, text, boolean, text)
    FROM PUBLIC, anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.save_device_push_token(text, text, text, boolean, text)
    TO anon, authenticated;

  -- A plain INSERT as anon succeeded while the write policies were
  -- WITH CHECK (true), so the checks above were optional. Close that path
  -- in this same statement.
  REVOKE INSERT, UPDATE ON public.device_push_tokens FROM anon, authenticated;
  DROP POLICY IF EXISTS "anon insert device token" ON public.device_push_tokens;
  DROP POLICY IF EXISTS "anon update device token" ON public.device_push_tokens;
END
$mig$;
