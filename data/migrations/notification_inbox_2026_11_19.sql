-- Notification inbox and per-sport mutes.
--
-- HAND APPLIED. Not in data/view_migrations.ACTIVE_MIGRATIONS, so the worker
-- will not run this. Matt applies it himself. Do not apply it from a session.
--
-- push_sent cannot back an inbox: it is a global dedupe ledger, stores no
-- title or body, is not per user, and has no read state. This adds one row
-- per alert per signed-in user, plus a per-user per-sport on/off.
--
-- The app reads the last 7 days (sent_at >= now() - 7 days). Rows older than
-- that stay out of the inbox, the bell and the badge. Physical removal is
-- tracking.notification_inbox.prune_notification_inbox, which asks
-- config.data_deletion_approved('notification_inbox') first and deletes
-- nothing until mike opens that gate (CLAUDE.md section 1b). No new
-- scheduler and no pg_cron: the daily push step calls the prune.
--
-- Re-running replaces the function, the policies and the grants.

DO $mig$
BEGIN
  ALTER TABLE public.device_push_tokens
    ADD COLUMN IF NOT EXISTS user_id uuid;

  CREATE INDEX IF NOT EXISTS idx_device_push_tokens_user
    ON public.device_push_tokens (user_id);

  -- A 6-arg overload beside the 5-arg function makes PostgREST answer 300
  -- when a shipped client sends the original five names. Drop the old
  -- signature. The new one defaults p_user_id so that client still matches.
  DROP FUNCTION IF EXISTS public.save_device_push_token(text, text, text, boolean, text);

  CREATE OR REPLACE FUNCTION public.save_device_push_token(
      p_token text,
      p_device_id text,
      p_platform text,
      p_enabled boolean,
      p_last_seen text,
      p_user_id uuid DEFAULT NULL
  ) RETURNS void
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = ''
  AS $fn$
  DECLARE
    v_uid uuid;
    v_gone boolean;
  BEGIN
    -- p_last_seen stays in the signature so a shipped client still matches.
    -- The stored clock is the server's. The owner is auth.uid(), never the
    -- id the caller typed. p_user_id is only a compatibility argument: a
    -- value that is not this session is rejected. Anon has no uid, so a
    -- caller who passes any user id is rejected, and a signed-out save
    -- stores NULL (that is the unlink).
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

    v_uid := auth.uid();
    IF p_user_id IS NOT NULL AND p_user_id IS DISTINCT FROM v_uid THEN
      RAISE EXCEPTION 'save_device_push_token: user does not match the session'
        USING ERRCODE = '42501';
    END IF;
    -- The phone can still hold a JWT after delete_my_login(). Writing that
    -- id back would violate the user foreign key and leave the token
    -- enabled. A uid with no auth.users row is stored as NULL.
    -- Dynamic SQL: a scratch database has no auth.users, and a static
    -- reference would fail to plan even when the table check is false.
    IF v_uid IS NOT NULL AND pg_catalog.to_regclass('auth.users') IS NOT NULL THEN
      EXECUTE 'SELECT NOT EXISTS (SELECT 1 FROM auth.users AS u WHERE u.id = $1)'
        INTO v_gone
        USING v_uid;
      IF v_gone THEN
        v_uid := NULL;
      END IF;
    END IF;

    INSERT INTO public.device_push_tokens
        (token, device_id, platform, enabled, last_seen, user_id)
    VALUES
        (p_token, p_device_id, p_platform, p_enabled, pg_catalog.now()::text, v_uid)
    ON CONFLICT (token) DO UPDATE
      SET device_id = COALESCE(EXCLUDED.device_id, public.device_push_tokens.device_id),
          platform  = COALESCE(EXCLUDED.platform, public.device_push_tokens.platform),
          enabled   = EXCLUDED.enabled,
          last_seen = pg_catalog.now()::text,
          user_id   = v_uid;
  END
  $fn$;

  ALTER FUNCTION public.save_device_push_token(text, text, text, boolean, text, uuid)
    OWNER TO postgres;

  REVOKE ALL ON FUNCTION public.save_device_push_token(text, text, text, boolean, text, uuid)
    FROM PUBLIC, anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.save_device_push_token(text, text, text, boolean, text, uuid)
    TO anon, authenticated;

  CREATE TABLE IF NOT EXISTS public.notification_inbox (
      id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id         uuid NOT NULL,
      kind            text NOT NULL,
      title           text NOT NULL,
      body            text NOT NULL,
      sport           text,
      route           jsonb NOT NULL,
      notification_id text NOT NULL,
      sent_at         timestamptz NOT NULL DEFAULT pg_catalog.now(),
      read_at         timestamptz,
      UNIQUE (user_id, notification_id)
  );

  CREATE INDEX IF NOT EXISTS idx_notification_inbox_user_sent
    ON public.notification_inbox (user_id, sent_at DESC);

  CREATE INDEX IF NOT EXISTS idx_notification_inbox_unread
    ON public.notification_inbox (user_id)
    WHERE read_at IS NULL;

  -- Only read_at moves after insert. A client update cannot rewrite the
  -- alert or reassign it to someone else.
  CREATE OR REPLACE FUNCTION public.notification_inbox_freeze()
  RETURNS trigger
  LANGUAGE plpgsql
  SET search_path = ''
  AS $fn$
  BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.user_id IS DISTINCT FROM OLD.user_id
       OR NEW.kind IS DISTINCT FROM OLD.kind
       OR NEW.title IS DISTINCT FROM OLD.title
       OR NEW.body IS DISTINCT FROM OLD.body
       OR NEW.sport IS DISTINCT FROM OLD.sport
       OR NEW.route IS DISTINCT FROM OLD.route
       OR NEW.notification_id IS DISTINCT FROM OLD.notification_id
       OR NEW.sent_at IS DISTINCT FROM OLD.sent_at
    THEN
      RAISE EXCEPTION 'notification_inbox: only read_at may change'
        USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
  END
  $fn$;

  ALTER FUNCTION public.notification_inbox_freeze() OWNER TO postgres;
  REVOKE ALL ON FUNCTION public.notification_inbox_freeze() FROM PUBLIC, anon, authenticated;

  DROP TRIGGER IF EXISTS notification_inbox_freeze ON public.notification_inbox;
  CREATE TRIGGER notification_inbox_freeze
    BEFORE UPDATE ON public.notification_inbox
    FOR EACH ROW
    EXECUTE FUNCTION public.notification_inbox_freeze();

  ALTER TABLE public.notification_inbox ENABLE ROW LEVEL SECURITY;

  DROP POLICY IF EXISTS notification_inbox_select ON public.notification_inbox;
  DROP POLICY IF EXISTS notification_inbox_insert ON public.notification_inbox;
  DROP POLICY IF EXISTS notification_inbox_update ON public.notification_inbox;

  CREATE POLICY notification_inbox_select ON public.notification_inbox
    FOR SELECT TO authenticated
    USING (user_id = (SELECT auth.uid()));

  CREATE POLICY notification_inbox_insert ON public.notification_inbox
    FOR INSERT TO authenticated
    WITH CHECK (user_id = (SELECT auth.uid()));

  CREATE POLICY notification_inbox_update ON public.notification_inbox
    FOR UPDATE TO authenticated
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));

  REVOKE ALL ON public.notification_inbox FROM PUBLIC, anon, authenticated;
  GRANT SELECT, INSERT, UPDATE ON public.notification_inbox TO authenticated;

  -- Absence of a row means the sport is on. enabled = false is a mute.
  -- The worker skips the push and writes no inbox row for a muted sport.
  -- A row already stored is hidden by the app (inbox and badge) while muted.
  CREATE TABLE IF NOT EXISTS public.notification_sport_prefs (
      user_id    uuid NOT NULL,
      sport      text NOT NULL,
      enabled    boolean NOT NULL DEFAULT true,
      updated_at timestamptz NOT NULL DEFAULT pg_catalog.now(),
      PRIMARY KEY (user_id, sport),
      CONSTRAINT notification_sport_prefs_sport CHECK (sport IN (
          'MLB', 'WNBA', 'NBA', 'NFL', 'NCAAF', 'NCAAB', 'NCAABW',
          'UFC', 'NHL', 'ATP', 'WTA', 'EUROLEAGUE'
      ))
  );

  ALTER TABLE public.notification_sport_prefs ENABLE ROW LEVEL SECURITY;

  DROP POLICY IF EXISTS notification_sport_prefs_select ON public.notification_sport_prefs;
  DROP POLICY IF EXISTS notification_sport_prefs_insert ON public.notification_sport_prefs;
  DROP POLICY IF EXISTS notification_sport_prefs_update ON public.notification_sport_prefs;

  CREATE POLICY notification_sport_prefs_select ON public.notification_sport_prefs
    FOR SELECT TO authenticated
    USING (user_id = (SELECT auth.uid()));

  CREATE POLICY notification_sport_prefs_insert ON public.notification_sport_prefs
    FOR INSERT TO authenticated
    WITH CHECK (user_id = (SELECT auth.uid()));

  CREATE POLICY notification_sport_prefs_update ON public.notification_sport_prefs
    FOR UPDATE TO authenticated
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));

  REVOKE ALL ON public.notification_sport_prefs FROM PUBLIC, anon, authenticated;
  GRANT SELECT, INSERT, UPDATE ON public.notification_sport_prefs TO authenticated;

  -- The caller's own alerts. Account deletion already removes the caller's
  -- other rows (delete_my_account). This is that same delete, for the two
  -- tables that did not exist then, plus unlinking this user's tokens.
  -- It is not the 7-day retention prune.
  CREATE OR REPLACE FUNCTION public.forget_my_notifications()
  RETURNS void
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = ''
  AS $fn$
  DECLARE
    v_uid uuid;
  BEGIN
    v_uid := auth.uid();
    IF v_uid IS NULL THEN
      RAISE EXCEPTION 'forget_my_notifications: not signed in' USING ERRCODE = '42501';
    END IF;
    DELETE FROM public.notification_inbox WHERE user_id = v_uid;
    DELETE FROM public.notification_sport_prefs WHERE user_id = v_uid;
    UPDATE public.device_push_tokens
       SET user_id = NULL
     WHERE user_id = v_uid;
  END
  $fn$;

  ALTER FUNCTION public.forget_my_notifications() OWNER TO postgres;
  REVOKE ALL ON FUNCTION public.forget_my_notifications() FROM PUBLIC, anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.forget_my_notifications() TO authenticated;

  -- When the login row itself is deleted, the history goes with it.
  -- device_push_tokens stays (the install) and its user_id is cleared.
  IF pg_catalog.to_regclass('auth.users') IS NOT NULL THEN
    ALTER TABLE public.notification_inbox
      DROP CONSTRAINT IF EXISTS notification_inbox_user_fk;
    ALTER TABLE public.notification_inbox
      ADD CONSTRAINT notification_inbox_user_fk
      FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE;

    ALTER TABLE public.notification_sport_prefs
      DROP CONSTRAINT IF EXISTS notification_sport_prefs_user_fk;
    ALTER TABLE public.notification_sport_prefs
      ADD CONSTRAINT notification_sport_prefs_user_fk
      FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE;

    ALTER TABLE public.device_push_tokens
      DROP CONSTRAINT IF EXISTS device_push_tokens_user_fk;
    ALTER TABLE public.device_push_tokens
      ADD CONSTRAINT device_push_tokens_user_fk
      FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE SET NULL;
  END IF;
END
$mig$;
