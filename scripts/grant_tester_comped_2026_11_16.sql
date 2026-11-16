-- One-shot tester grant: brent.lincoln@yahoo.com, full app access.
-- Do NOT run from the worker and do NOT add this file to ACTIVE_MIGRATIONS.
--
-- Run in the Supabase SQL editor for project vvprgnrmzeekokzkrkfu
-- (Betting Model), as postgres. Same body as
-- scripts/grant_founder_comped_2026_11_05.sql with the email and note changed.
--
-- Why 'comped' and not a subscriptions row: "full paid user" means the app
-- unlocks exactly as a payer's does. my_access() / has_app_access() unlock on
-- an active RevenueCat subscription OR an active comped access_grants row
-- (CLAUDE.md section 6). A hand-written subscriptions row would invent a
-- RevenueCat purchase that never happened. comped also opens the subscriber
-- Discord invite.
--
-- APPLIED 2026-11-16 through the Supabase MCP (user id
-- 79e2efd9-3880-42dc-8873-4c9a36a797f8). Verified: email identity present,
-- one comped grant with expires_at null, and has_app_access() = true when run
-- as that user. Kept as the record and as the template for the next tester.
-- Also applied the same day, same body with v_email changed, for
-- bcook2929@gmail.com (user id b79e36c9-f0c5-4690-bf35-c7c56a653c2e),
-- has_app_access() = true as that user.
--
-- Before the apply there was no auth.users row for this email, so
-- the block below creates the email login in the shape GoTrue stores, then
-- adds one indefinite comped grant (expires_at null). He signs in with
-- "Email me a code" on that address and lands on the existing account.
-- Sign in with Apple using "Hide My Email" would create a SEPARATE account
-- with no grant -- he should use the email code path.
--
-- It does not delete, update or expire any row. Re-running inserts nothing.

DO $$
DECLARE
    v_email text := 'brent.lincoln@yahoo.com';
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
            email_change,
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
            '',  -- email_change: GoTrue cannot scan NULL here (2026-11-16 OTP 500s)
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
            updated_at
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
            now()
        );
    END IF;

    INSERT INTO public.access_grants (user_id, access_source, notes)
    SELECT v_uid, 'comped', 'comped by Matt 2026-11-16 (full access, TestFlight tester)'
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
WHERE lower(u.email) = 'brent.lincoln@yahoo.com';
