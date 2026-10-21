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
-- TWO RETURNS, IN THIS ORDER. Both are catalog reads. Replacing the view,
-- re-granting, and replacing the policy take locks on push_sent if this
-- block does not return first. Policy replacement takes AccessExclusiveLock.
-- Hourly run b22f8e4fb9e34d27858c341e46ce635c on 2026-10-01 waited on
-- push_sent (oid 25944) for that lock.
--
-- 1. Keyword check: if the live view already mentions discord_void, this
--    file must not put the narrower definition back.
--    discord_void_notice_2026_10_09.sql owns that clause and the policy that
--    lets the security_invoker subquery see the notice. Re-applying the body
--    below would drop the exclusion on every pass and the notice would not
--    change the publish state. This check is first on purpose: the full
--    definition below describes THIS file's body, which does not mention
--    discord_void, so a void-owned view would fail that comparison and the
--    DDL would run.
--
-- 2. Full definition, for the state before the void notice owns the view.
--    Keyword checks on this file's own body would skip a future change.
--    The guard compares the WHOLE view definition and policy expression
--    (whitespace collapsed, "public." dropped, because pg_get_viewdef leaves
--    the schema off when it is on the search_path) against what Postgres 17
--    prints for the DDL below, read from production 2026-10-02. It also
--    checks the policy's command (SELECT), that it is permissive, and that
--    its roles are exactly anon and authenticated. CHANGING THE VIEW OR
--    POLICY BELOW MEANS CHANGING want_def / want_qual TOO, or the new body
--    is never applied. Anything missing falls through and the DDL still runs.
--
-- Idempotent. One statement (a DO block) so view_migrations can re-run it.

DO $mig$
DECLARE
  d text;
  def text;
  opts text[];
  qual text;
  cmd "char";
  permissive boolean;
  roles text[];
  want_def constant text :=
    'SELECT lock_key, kind FROM push_sent s WHERE kind = ANY '
    || '(ARRAY[''discord_signal''::text, ''discord_live''::text]);';
  want_qual constant text :=
    '(kind = ANY (ARRAY[''discord_signal''::text, ''discord_live''::text]))';
BEGIN
  IF to_regclass('public.v_discord_published') IS NOT NULL THEN
    d := pg_get_viewdef('public.v_discord_published'::regclass, true);
    IF position('discord_void' in d) > 0 THEN
      RAISE NOTICE 'v_discord_published excludes discord_void; leaving that definition';
      RETURN;
    END IF;

    def := btrim(regexp_replace(replace(d, 'public.', ''), '\s+', ' ', 'g'));
    SELECT c.reloptions INTO opts
      FROM pg_class c
     WHERE c.oid = 'public.v_discord_published'::regclass;
    SELECT btrim(regexp_replace(
             replace(pg_get_expr(p.polqual, p.polrelid), 'public.', ''),
             '\s+', ' ', 'g')),
           p.polcmd,
           p.polpermissive,
           ARRAY(SELECT r::regrole::text FROM unnest(p.polroles) r ORDER BY 1)
      INTO qual, cmd, permissive, roles
      FROM pg_policy p
     WHERE p.polrelid = 'public.push_sent'::regclass
       AND p.polname = 'anon_read_discord_publish';

    IF def IS NOT DISTINCT FROM want_def
       AND opts IS NOT NULL
       AND 'security_invoker=on' = ANY (opts)
       AND qual IS NOT DISTINCT FROM want_qual
       AND cmd IS NOT DISTINCT FROM 'r'
       AND permissive IS TRUE
       AND roles IS NOT DISTINCT FROM ARRAY['anon', 'authenticated']
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
