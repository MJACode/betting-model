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
-- This function runs as the owner, who bypasses RLS, and returns nothing.
-- Re-running it replaces the function and re-asserts the grants.

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
  SET search_path = public, pg_temp
  AS $fn$
  BEGIN
    IF p_token IS NULL
       OR length(p_token) < 20
       OR length(p_token) > 200
       OR p_token <> btrim(p_token)
       OR position(' ' IN p_token) > 0 THEN
      RAISE EXCEPTION 'save_device_push_token: bad token' USING ERRCODE = '22023';
    END IF;
    IF p_device_id IS NOT NULL AND p_device_id !~ '^[A-Za-z0-9-]{8,64}$' THEN
      RAISE EXCEPTION 'save_device_push_token: bad device id' USING ERRCODE = '22023';
    END IF;
    IF p_platform IS NOT NULL AND p_platform !~ '^[a-z]{2,16}$' THEN
      RAISE EXCEPTION 'save_device_push_token: bad platform' USING ERRCODE = '22023';
    END IF;
    IF p_enabled IS NULL THEN
      RAISE EXCEPTION 'save_device_push_token: enabled is required' USING ERRCODE = '22023';
    END IF;
    IF p_last_seen IS NULL OR length(p_last_seen) > 40 THEN
      RAISE EXCEPTION 'save_device_push_token: bad last_seen' USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.device_push_tokens
        (token, device_id, platform, enabled, last_seen)
    VALUES
        (p_token, p_device_id, p_platform, p_enabled, p_last_seen)
    ON CONFLICT (token) DO UPDATE
      SET device_id = COALESCE(EXCLUDED.device_id, device_push_tokens.device_id),
          platform  = COALESCE(EXCLUDED.platform, device_push_tokens.platform),
          enabled   = EXCLUDED.enabled,
          last_seen = EXCLUDED.last_seen;
  END
  $fn$;

  -- PUBLIC holds EXECUTE by default. Revoking only the named roles leaves it
  -- callable. Revoke PUBLIC first, then grant the two roles the app uses.
  REVOKE ALL ON FUNCTION public.save_device_push_token(text, text, text, boolean, text)
    FROM PUBLIC, anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.save_device_push_token(text, text, text, boolean, text)
    TO anon, authenticated;
END
$mig$;
