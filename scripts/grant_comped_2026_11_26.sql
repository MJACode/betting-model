-- Premium access changes requested by Matt 2026-11-26.
-- Do NOT run from the worker and do NOT add this file to ACTIVE_MIGRATIONS.
--
-- Run once in the Supabase SQL editor for project vvprgnrmzeekokzkrkfu
-- (Betting Model), as postgres. Claude's database access is read-only
-- (CLAUDE.md section 1b), so this file is run by hand.
--
--   1. ryan.pad.murphy@gmail.com (user e6170cc2-7a3e-4a10-ab82-90534185982f,
--      created 2026-11-14, never signed in, one comped grant, no
--      subscription; measured 2026-11-26): the comped grant is EXPIRED
--      (expires_at = now()), not deleted. "No data is ever deleted" (CLAUDE.md
--      section 1b) and deleting the auth user would cascade-delete the grant
--      row. Expiring it removes app access and the Discord invite at once.
--   2. rmurphisms@gmail.com     -> new email login + indefinite comped grant.
--   3. larrypizzi3@gmail.com    -> new email login + indefinite comped grant.
--      Neither address had an auth.users row on 2026-11-26.
--
-- Body for 2 and 3 is scripts/grant_tester_comped_2026_11_16.sql with the
-- email and note changed. Each person signs in with "Email me a code" on that
-- address. Sign in with Apple "Hide My Email" would create a SEPARATE account
-- with no grant.
--
-- Re-running is safe: it expires nothing already expired and inserts nothing
-- already present.

-- 1. Expire Ryan's grant.
UPDATE public.access_grants
SET expires_at = now(),
    notes = coalesce(notes, '') || ' | expired by Matt 2026-11-26 (replaced by rmurphisms@gmail.com)'
WHERE user_id = 'e6170cc2-7a3e-4a10-ab82-90534185982f'
  AND access_source = 'comped'
  AND (expires_at IS NULL OR expires_at > now());

-- 2 and 3. Create logins and comped grants.
DO $$
DECLARE
    v_email text;
    v_uid uuid;
BEGIN
    FOREACH v_email IN ARRAY ARRAY['rmurphisms@gmail.com', 'larrypizzi3@gmail.com']
    LOOP
        v_uid := NULL;
        SELECT id INTO v_uid
        FROM auth.users
        WHERE lower(email) = v_email
          AND is_sso_user = false
        LIMIT 1;

        IF v_uid IS NULL THEN
            v_uid := gen_random_uuid();
            INSERT INTO auth.users (
                instance_id, id, aud, role, email, encrypted_password,
                email_confirmed_at, confirmation_token, recovery_token,
                email_change_token_new, email_change_token_current,
                reauthentication_token, email_change,
                raw_app_meta_data, raw_user_meta_data,
                created_at, updated_at, is_sso_user, is_anonymous
            ) VALUES (
                '00000000-0000-0000-0000-000000000000', v_uid,
                'authenticated', 'authenticated', v_email, '',
                now(), '', '', '', '', '',
                '',  -- email_change: GoTrue cannot scan NULL here (2026-11-16 OTP 500s)
                jsonb_build_object('provider', 'email', 'providers', jsonb_build_array('email')),
                jsonb_build_object('sub', v_uid::text, 'email', v_email,
                                   'email_verified', true, 'phone_verified', false),
                now(), now(), false, false
            );
            INSERT INTO auth.identities (
                provider_id, user_id, identity_data, provider,
                last_sign_in_at, created_at, updated_at
            ) VALUES (
                v_uid::text, v_uid,
                jsonb_build_object('sub', v_uid::text, 'email', v_email,
                                   'email_verified', true, 'phone_verified', false),
                'email', now(), now(), now()
            );
        END IF;

        INSERT INTO public.access_grants (user_id, access_source, notes)
        SELECT v_uid, 'comped', 'comped by Matt 2026-11-26 (full access)'
        WHERE NOT EXISTS (
            SELECT 1 FROM public.access_grants g
            WHERE g.user_id = v_uid
              AND g.access_source = 'comped'
              AND (g.expires_at IS NULL OR g.expires_at > now())
        );
    END LOOP;
END $$;

-- Read-back: Ryan shows an expires_at in the past; the two new rows show
-- expires_at null.
SELECT u.id, u.email, g.access_source, g.granted_at, g.expires_at, g.notes
FROM auth.users u
LEFT JOIN public.access_grants g ON g.user_id = u.id
WHERE lower(u.email) IN ('ryan.pad.murphy@gmail.com',
                         'rmurphisms@gmail.com',
                         'larrypizzi3@gmail.com')
ORDER BY u.email;
