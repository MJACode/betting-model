-- The Betting PC monitor on mike's phone (mike, 2026-11-21: "can u create an
-- app for my phone too").
--
-- The monitor runs on mike's PC (pc_monitor/) and reads things only the PC can
-- see: Task Scheduler, its processes, its log files. A phone cannot reach the
-- PC, so the PC writes what its window shows into this one row, and the cloud
-- monitor on the worker (monitoring/server.py, /pc/) serves the same page from
-- it.
--
-- pc_monitor_state  one row per PC.
--   view          the page's JSON, as the PC's window last built it.
--   published_at  when the PC last wrote it (the database clock). The phone
--                 page greys everything once this is old: the PC is off,
--                 asleep or its monitor is not running.
--   demand_at     when a phone last asked for the page. The PC rewrites the row
--                 every 2 s while this is recent and once a minute otherwise,
--                 so a 13 KB row is not rewritten all day for nobody.
--   phone_token   the secret in the phone link. It opens /pc/ only, never the
--                 rest of the cloud monitor. The PC makes it once and shows the
--                 link as a QR code in its own window.
--
-- Nobody but the database owner and the service role reads it: anon,
-- authenticated and backroom_reader are revoked by name, because the token is
-- in it. One DO block: data/view_migrations.py runs each file as one statement
-- on every pass, and the early return answers "already applied" on the
-- property this migration establishes.

DO $mig$
DECLARE
  t regclass := to_regclass('public.pc_monitor_state');
  r text;
  done boolean := true;
BEGIN
  IF t IS NULL OR NOT EXISTS (SELECT 1 FROM pg_class WHERE oid = t AND relrowsecurity) THEN
    done := false;
  ELSE
    FOREACH r IN ARRAY ARRAY['anon', 'authenticated', 'backroom_reader'] LOOP
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r)
         AND (has_table_privilege(r, t, 'SELECT') OR has_table_privilege(r, t, 'INSERT')
              OR has_table_privilege(r, t, 'UPDATE') OR has_table_privilege(r, t, 'DELETE')) THEN
        done := false;
      END IF;
    END LOOP;
  END IF;
  IF done THEN
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.pc_monitor_state (
    host          TEXT PRIMARY KEY,
    view          JSONB NOT NULL DEFAULT '{}'::jsonb,
    published_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    demand_at     TIMESTAMPTZ,
    phone_token   TEXT NOT NULL
  );
  ALTER TABLE public.pc_monitor_state ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.pc_monitor_state FROM anon;
  REVOKE ALL ON public.pc_monitor_state FROM authenticated;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'backroom_reader') THEN
    REVOKE ALL ON public.pc_monitor_state FROM backroom_reader;
  END IF;
END
$mig$;
