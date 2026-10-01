-- Discord publish state the app can join, without opening the ledger.
--
-- Matt, 2026-09-23: Discord is the source of truth. A VOID after the post
-- does not delete the message, so the app has to see which locks were
-- posted. push_sent stays closed (RLS, no message_id grant). This view is
-- the two channel kinds and the lock_key only.
--
-- security_invoker: the caller is checked against the column grant and the
-- policy below. The worker connects as the owner and is unaffected.
--
-- Idempotent. One statement (a DO block) so view_migrations can re-run it.
--
-- ALREADY APPLIED IS A CATALOG READ. Replacing the view, re-granting, and
-- replacing the policy all take locks on push_sent if this block does not
-- return first. Policy replacement takes AccessExclusiveLock. Hourly run
-- b22f8e4fb9e34d27858c341e46ce635c on 2026-10-01 waited on push_sent
-- (oid 25944) for that lock, the third statement timeout of the pass
-- (the first was add_message_id_to_push_sent.sql). The guard is the
-- property this file establishes: the view, its security_invoker option,
-- the policy, and the column grants. Anything missing falls through and
-- the DDL below still runs.

DO $mig$
DECLARE
  def text;
  opts text[];
  qual text;
BEGIN
  IF to_regclass('public.v_discord_published') IS NOT NULL THEN
    def := pg_get_viewdef('public.v_discord_published'::regclass, true);
    SELECT c.reloptions INTO opts
      FROM pg_class c
     WHERE c.oid = 'public.v_discord_published'::regclass;
    SELECT pg_get_expr(p.polqual, p.polrelid) INTO qual
      FROM pg_policy p
     WHERE p.polrelid = 'public.push_sent'::regclass
       AND p.polname = 'anon_read_discord_publish';

    IF def IS NOT NULL
       AND position('discord_signal' in def) > 0
       AND position('discord_live' in def) > 0
       AND position('lock_key' in def) > 0
       AND position('kind' in def) > 0
       AND opts IS NOT NULL
       AND 'security_invoker=on' = ANY (opts)
       AND qual IS NOT NULL
       AND position('discord_signal' in qual) > 0
       AND position('discord_live' in qual) > 0
       AND has_column_privilege('anon', 'public.push_sent', 'lock_key', 'SELECT')
       AND has_column_privilege('anon', 'public.push_sent', 'kind', 'SELECT')
       AND NOT has_column_privilege('anon', 'public.push_sent', 'message_id', 'SELECT')
       AND has_column_privilege('authenticated', 'public.push_sent', 'lock_key', 'SELECT')
       AND has_column_privilege('authenticated', 'public.push_sent', 'kind', 'SELECT')
       AND NOT has_column_privilege('authenticated', 'public.push_sent', 'message_id', 'SELECT')
       AND has_table_privilege('anon', 'public.v_discord_published', 'SELECT')
       AND has_table_privilege('authenticated', 'public.v_discord_published', 'SELECT')
       AND NOT has_table_privilege('anon', 'public.v_discord_published', 'INSERT')
       AND NOT has_table_privilege('authenticated', 'public.v_discord_published', 'INSERT')
    THEN
      RAISE NOTICE 'v_discord_published already matches - skipping';
      RETURN;
    END IF;
  END IF;

  EXECUTE $v$
    CREATE OR REPLACE VIEW public.v_discord_published
    WITH (security_invoker = on) AS
    SELECT s.lock_key, s.kind
    FROM public.push_sent s
    WHERE s.kind IN ('discord_signal', 'discord_live')
  $v$;

  REVOKE ALL ON TABLE public.push_sent FROM anon, authenticated;
  GRANT SELECT (lock_key, kind) ON TABLE public.push_sent TO anon, authenticated;

  DROP POLICY IF EXISTS anon_read_discord_publish ON public.push_sent;
  CREATE POLICY anon_read_discord_publish ON public.push_sent
    FOR SELECT TO anon, authenticated
    USING (kind IN ('discord_signal', 'discord_live'));

  GRANT SELECT ON public.v_discord_published TO anon, authenticated;
  REVOKE INSERT, UPDATE, DELETE ON public.v_discord_published
    FROM anon, authenticated;
END $mig$;
