-- The in-app notifications inbox (Matt, 2026-11-14): "I'd like to see
-- notifications and you can go and look at past ones, but also see if you
-- missed any ... do a read-all ... or you click on it and then that clears
-- one". Decisions Matt approved the same day: a bell in the header, start
-- fresh (no rebuilt history), log alerts even while push is off, 30 days.
--
-- WHY A NEW TABLE. push_sent records THAT a pick was considered for a push,
-- keyed on lock_key. It never stored the words a phone showed, so nothing can
-- be rebuilt from it without guessing the text (CLAUDE.md §00). From this
-- migration on, every push the worker builds is saved here word for word,
-- the same title and body that went to Expo.
--
--   notification_inbox       one row per notification. device_id NULL means
--                            every device: the signal summaries go to every
--                            opted-in phone with the same words. A line-change
--                            alert or a feedback reply names its one device.
--                            Rows are written whether or not any phone has
--                            push on, which is what lets a muted install see
--                            what it missed.
--   notification_reads       which notifications one device has opened.
--   notification_read_marks  one row per device: everything at or before
--                            read_all_at counts as read. "Read all" moves it.
--                            The first inbox fetch creates it at that moment,
--                            so a new install starts with no unread backlog
--                            and can still scroll back 30 days.
--
-- Rows are never deleted (Supabase is the system of record). The 30-day
-- window is applied by the read functions, not by a pruner.
--
-- ACCESS. RLS on, no policies, anon/authenticated table grants revoked. The
-- app's only way in is the four SECURITY DEFINER functions below, keyed on the
-- per-install device id, the trust model feedback_threads and
-- member_sportsbooks already use. The worker writes with DATABASE_URL.
--
-- In data/view_migrations.ACTIVE_MIGRATIONS. The first pass after merge
-- creates it; later passes return on the catalog read below and take no lock.

DO $mig$
BEGIN
  IF to_regclass('public.notification_inbox') IS NOT NULL
     AND to_regclass('public.notification_reads') IS NOT NULL
     AND to_regclass('public.notification_read_marks') IS NOT NULL
     AND to_regprocedure('public.notification_inbox_for_device(text)') IS NOT NULL
     AND to_regprocedure('public.notification_unread_count(text)') IS NOT NULL
     AND to_regprocedure('public.notification_mark_read(text,bigint)') IS NOT NULL
     AND to_regprocedure('public.notification_mark_all_read(text)') IS NOT NULL
     AND has_function_privilege('anon', 'public.notification_inbox_for_device(text)', 'EXECUTE')
     AND has_function_privilege('anon', 'public.notification_mark_all_read(text)', 'EXECUTE')
     AND NOT has_table_privilege('anon', 'public.notification_inbox', 'SELECT')
     AND NOT has_table_privilege('authenticated', 'public.notification_inbox', 'SELECT')
  THEN
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.notification_inbox (
    id          BIGSERIAL PRIMARY KEY,
    device_id   TEXT,
    kind        TEXT NOT NULL,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    data        JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  CREATE INDEX IF NOT EXISTS notification_inbox_created_idx
    ON public.notification_inbox (created_at DESC);
  CREATE INDEX IF NOT EXISTS notification_inbox_device_idx
    ON public.notification_inbox (device_id, created_at DESC)
    WHERE device_id IS NOT NULL;

  CREATE TABLE IF NOT EXISTS public.notification_reads (
    device_id        TEXT NOT NULL,
    notification_id  BIGINT NOT NULL REFERENCES public.notification_inbox(id),
    read_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (device_id, notification_id)
  );

  CREATE TABLE IF NOT EXISTS public.notification_read_marks (
    device_id    TEXT PRIMARY KEY,
    read_all_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );

  ALTER TABLE public.notification_inbox      ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.notification_reads      ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.notification_read_marks ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.notification_inbox      FROM anon, authenticated;
  REVOKE ALL ON public.notification_reads      FROM anon, authenticated;
  REVOKE ALL ON public.notification_read_marks FROM anon, authenticated;
  REVOKE ALL ON SEQUENCE public.notification_inbox_id_seq FROM anon, authenticated;

  -- This device's notifications from the last 30 days, newest first, each with
  -- whether it is read. The first call for a device creates its read mark at
  -- now(), so an install starts at zero unread.
  CREATE OR REPLACE FUNCTION public.notification_inbox_for_device(p_device_id TEXT)
  RETURNS TABLE (
    id          BIGINT,
    kind        TEXT,
    title       TEXT,
    body        TEXT,
    data        JSONB,
    created_at  TIMESTAMPTZ,
    is_read     BOOLEAN
  )
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = ''
  AS $fn$
  BEGIN
    IF p_device_id IS NULL OR p_device_id !~ '^[A-Za-z0-9-]{8,64}$' THEN
      RAISE EXCEPTION 'invalid device' USING ERRCODE = '22023';
    END IF;
    INSERT INTO public.notification_read_marks (device_id, read_all_at)
    VALUES (p_device_id, pg_catalog.now())
    ON CONFLICT (device_id) DO NOTHING;

    RETURN QUERY
      SELECT n.id, n.kind, n.title, n.body, n.data, n.created_at,
             (n.created_at <= m.read_all_at
              OR EXISTS (SELECT 1 FROM public.notification_reads r
                          WHERE r.device_id = p_device_id
                            AND r.notification_id = n.id)) AS is_read
        FROM public.notification_inbox n
        JOIN public.notification_read_marks m ON m.device_id = p_device_id
       WHERE (n.device_id IS NULL OR n.device_id = p_device_id)
         AND n.created_at > pg_catalog.now() - interval '30 days'
       ORDER BY n.created_at DESC, n.id DESC
       LIMIT 300;
  END;
  $fn$;

  -- The bell's badge. Zero for a device that has never opened the inbox, the
  -- same answer the first fetch would give.
  CREATE OR REPLACE FUNCTION public.notification_unread_count(p_device_id TEXT)
  RETURNS INT
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path = ''
  AS $fn$
    SELECT COALESCE(count(*), 0)::INT
      FROM public.notification_inbox n
      JOIN public.notification_read_marks m ON m.device_id = p_device_id
     WHERE p_device_id ~ '^[A-Za-z0-9-]{8,64}$'
       AND (n.device_id IS NULL OR n.device_id = p_device_id)
       AND n.created_at > pg_catalog.now() - interval '30 days'
       AND n.created_at > m.read_all_at
       AND NOT EXISTS (SELECT 1 FROM public.notification_reads r
                        WHERE r.device_id = p_device_id
                          AND r.notification_id = n.id);
  $fn$;

  -- Clear one. Only a notification this device can see is accepted, so an id
  -- belonging to another device's alert writes nothing.
  CREATE OR REPLACE FUNCTION public.notification_mark_read(
      p_device_id TEXT, p_notification_id BIGINT)
  RETURNS VOID
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = ''
  AS $fn$
  BEGIN
    IF p_device_id IS NULL OR p_device_id !~ '^[A-Za-z0-9-]{8,64}$' THEN
      RAISE EXCEPTION 'invalid device' USING ERRCODE = '22023';
    END IF;
    INSERT INTO public.notification_reads (device_id, notification_id)
    SELECT p_device_id, n.id
      FROM public.notification_inbox n
     WHERE n.id = p_notification_id
       AND (n.device_id IS NULL OR n.device_id = p_device_id)
    ON CONFLICT (device_id, notification_id) DO NOTHING;
  END;
  $fn$;

  -- Read all: move the mark to now and drop the per-item rows it now covers.
  CREATE OR REPLACE FUNCTION public.notification_mark_all_read(p_device_id TEXT)
  RETURNS VOID
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = ''
  AS $fn$
  BEGIN
    IF p_device_id IS NULL OR p_device_id !~ '^[A-Za-z0-9-]{8,64}$' THEN
      RAISE EXCEPTION 'invalid device' USING ERRCODE = '22023';
    END IF;
    INSERT INTO public.notification_read_marks (device_id, read_all_at)
    VALUES (p_device_id, pg_catalog.now())
    ON CONFLICT (device_id) DO UPDATE SET read_all_at = EXCLUDED.read_all_at;
    DELETE FROM public.notification_reads WHERE device_id = p_device_id;
  END;
  $fn$;

  REVOKE ALL ON FUNCTION public.notification_inbox_for_device(text) FROM PUBLIC, anon, authenticated;
  REVOKE ALL ON FUNCTION public.notification_unread_count(text) FROM PUBLIC, anon, authenticated;
  REVOKE ALL ON FUNCTION public.notification_mark_read(text, bigint) FROM PUBLIC, anon, authenticated;
  REVOKE ALL ON FUNCTION public.notification_mark_all_read(text) FROM PUBLIC, anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.notification_inbox_for_device(text) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.notification_unread_count(text) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.notification_mark_read(text, bigint) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.notification_mark_all_read(text) TO anon, authenticated;
END $mig$;
