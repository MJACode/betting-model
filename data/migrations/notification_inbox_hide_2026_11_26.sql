-- Notification inbox: a member can delete an alert from their list.
--
-- HAND APPLIED. Not in data/view_migrations.ACTIVE_MIGRATIONS, so the worker
-- will not run this. Matt applies it himself. Do not apply it from a session.
-- Requires notification_inbox_2026_11_19.sql first.
--
-- "Delete" in the app is a HIDE, not a DELETE (CLAUDE.md section 1b: no data
-- is ever deleted). The row stays; deleted_at is stamped and the app, the
-- bell, the icon badge and the worker's unread count all skip it.
--
-- A retry of the same alert hits ON CONFLICT (user_id, notification_id)
-- DO NOTHING, so a hidden alert does not come back.
--
-- Until this is applied the app reads without the column and hides the
-- delete controls, and the worker counts unread as before.
--
-- Re-running is safe.

DO $mig$
BEGIN
  ALTER TABLE public.notification_inbox
    ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

  -- The unread index now also skips hidden rows, which is what the worker
  -- and the badge count.
  DROP INDEX IF EXISTS public.idx_notification_inbox_unread;
  CREATE INDEX IF NOT EXISTS idx_notification_inbox_unread
    ON public.notification_inbox (user_id)
    WHERE read_at IS NULL AND deleted_at IS NULL;

  -- Only read_at and deleted_at move after insert. A hidden row stays hidden:
  -- a client update cannot clear deleted_at once it is set.
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
      RAISE EXCEPTION 'notification_inbox: only read_at and deleted_at may change'
        USING ERRCODE = '42501';
    END IF;
    IF OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS DISTINCT FROM OLD.deleted_at THEN
      RAISE EXCEPTION 'notification_inbox: a deleted alert stays deleted'
        USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
  END
  $fn$;

  ALTER FUNCTION public.notification_inbox_freeze() OWNER TO postgres;
  REVOKE ALL ON FUNCTION public.notification_inbox_freeze() FROM PUBLIC, anon, authenticated;
END
$mig$;
