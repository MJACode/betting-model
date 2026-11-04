-- App Review fixed-code attempt log.
--
-- NOT in data/view_migrations.ACTIVE_MIGRATIONS. The worker must not apply
-- this. Matt runs it once in the Supabase SQL editor before the review
-- binary is submitted. The app-review-sign-in edge function refuses every
-- code, including the right one, until this table exists.
--
-- One row per wrong code from one caller. No email and no code. `bucket`
-- is a SHA-256 of the caller address, not the address. RLS on, no policies.
-- anon and authenticated have no privileges. service_role inserts from the
-- edge function (it bypasses RLS and still needs the grant below).

DO $mig$
BEGIN
  -- Nested so has_table_privilege is not called when the table is absent.
  -- A table from the first draft of this file has no bucket column, so it
  -- does not take the early return.
  IF to_regclass('public.app_review_sign_in_attempts') IS NOT NULL
     AND EXISTS (
       SELECT 1
         FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'app_review_sign_in_attempts'
          AND column_name = 'bucket'
          AND is_nullable = 'NO'
     )
  THEN
    IF NOT has_table_privilege('anon', 'public.app_review_sign_in_attempts', 'SELECT')
       AND NOT has_table_privilege('authenticated', 'public.app_review_sign_in_attempts', 'SELECT')
       AND NOT has_table_privilege('anon', 'public.app_review_sign_in_attempts', 'INSERT')
       AND has_table_privilege('service_role', 'public.app_review_sign_in_attempts', 'INSERT')
    THEN
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.app_review_sign_in_attempts (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    bucket       text NOT NULL,
    attempted_at timestamptz NOT NULL DEFAULT now()
  );

  ALTER TABLE public.app_review_sign_in_attempts
    ADD COLUMN IF NOT EXISTS bucket text;
  UPDATE public.app_review_sign_in_attempts
     SET bucket = 'unkeyed'
   WHERE bucket IS NULL;
  ALTER TABLE public.app_review_sign_in_attempts
    ALTER COLUMN bucket SET NOT NULL;

  CREATE INDEX IF NOT EXISTS app_review_sign_in_attempts_attempted_at_idx
    ON public.app_review_sign_in_attempts (attempted_at);

  CREATE INDEX IF NOT EXISTS app_review_sign_in_attempts_bucket_attempted_at_idx
    ON public.app_review_sign_in_attempts (bucket, attempted_at);

  ALTER TABLE public.app_review_sign_in_attempts ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON TABLE public.app_review_sign_in_attempts FROM PUBLIC;
  REVOKE ALL ON TABLE public.app_review_sign_in_attempts FROM anon, authenticated;
  GRANT SELECT, INSERT, DELETE ON TABLE public.app_review_sign_in_attempts TO service_role;

  COMMENT ON TABLE public.app_review_sign_in_attempts IS
    'Wrong-code counts for app-review-sign-in, one SHA-256 bucket per caller. No client policy.';
END
$mig$;
