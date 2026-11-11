-- One-shot founder grant. Do NOT run from the worker and do NOT add this
-- file to ACTIVE_MIGRATIONS.
--
-- Run in the Supabase SQL editor for project vvprgnrmzeekokzkrkfu
-- (Betting Model), as postgres, AFTER
-- data/migrations/add_access_grants_2026_11_05.sql has been applied.
-- If access_grants does not exist yet, stop and apply that migration first.
--
-- What this does
--   1. Ensures one auth login for matt.alksninis@gmail.com.
--      There is no public.profiles table. The login row is auth.users plus
--      an email row in auth.identities. Measured 2026-11-05: that user
--      already exists (email provider, no subscriptions row), so the insert
--      below does not run. It is here so a missing row is created in the
--      same shape GoTrue already stored, and no other email is created.
--   2. Inserts one indefinite comped grant (expires_at left null) with note
--      'founder TF unblock' when no active comped grant exists.
--      comped unlocks the app and the subscriber Discord invite.
--
-- What this does not do
--   It does not delete, update, or expire any row. It does not touch Whop,
--   subscriptions, or any other email. Re-running it inserts nothing if an
--   active comped grant is already there.
--
-- After it commits, the installed TestFlight build reads my_access().entitled
-- and unlocks the app on the next launch. No new EAS build is required for
-- that. The Discord invite button on that build still follows the
-- subscriptions row until the JS update that treats source 'comped' as paid
-- is on the phone.

DO $$
DECLARE
    v_email text := 'matt.alksninis@gmail.com';
    v_uid uuid;
BEGIN
    SELECT id INTO v_uid
    FROM auth.users
    WHERE lower(email) = v_email
      AND is_sso_user = false
    LIMIT 1;

    IF v_uid IS NULL THEN
        v_uid := gen_random_uuid();
        INSERT INTO auth.users (
            instance_id,
            id,
            aud,
            role,
            email,
            encrypted_password,
            email_confirmed_at,
            confirmation_token,
            recovery_token,
            email_change_token_new,
            email_change_token_current,
            reauthentication_token,
            raw_app_meta_data,
            raw_user_meta_data,
            created_at,
            updated_at,
            is_sso_user,
            is_anonymous
        ) VALUES (
            '00000000-0000-0000-0000-000000000000',
            v_uid,
            'authenticated',
            'authenticated',
            v_email,
            '',
            now(),
            '',
            '',
            '',
            '',
            '',
            jsonb_build_object('provider', 'email', 'providers', jsonb_build_array('email')),
            jsonb_build_object(
                'sub', v_uid::text,
                'email', v_email,
                'email_verified', true,
                'phone_verified', false
            ),
            now(),
            now(),
            false,
            false
        );
        INSERT INTO auth.identities (
            provider_id,
            user_id,
            identity_data,
            provider,
            last_sign_in_at,
            created_at,
            updated_at,
            email
        ) VALUES (
            v_uid::text,
            v_uid,
            jsonb_build_object(
                'sub', v_uid::text,
                'email', v_email,
                'email_verified', true,
                'phone_verified', false
            ),
            'email',
            now(),
            now(),
            now(),
            v_email
        );
    END IF;

    INSERT INTO public.access_grants (user_id, access_source, notes)
    SELECT v_uid, 'comped', 'founder TF unblock'
    WHERE NOT EXISTS (
        SELECT 1
        FROM public.access_grants g
        WHERE g.user_id = v_uid
          AND g.access_source = 'comped'
          AND (g.expires_at IS NULL OR g.expires_at > now())
    );
END $$;

SELECT u.id,
       u.email,
       g.access_source,
       g.granted_at,
       g.expires_at,
       g.notes
FROM auth.users u
LEFT JOIN public.access_grants g
    ON g.user_id = u.id
   AND g.access_source = 'comped'
   AND (g.expires_at IS NULL OR g.expires_at > now())
WHERE lower(u.email) = 'matt.alksninis@gmail.com';
