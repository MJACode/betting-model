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
-- Keyword check: if the live view already mentions discord_void, this file
-- must not put the narrower definition back.
-- discord_void_notice_2026_10_09.sql owns that clause and the policy that
-- lets the security_invoker subquery see the notice. Re-applying the body
-- below would drop the exclusion on every pass and the notice would not
-- change the publish state.
--
-- Idempotent. One statement (a DO block) so view_migrations can re-run it.

DO $mig$
DECLARE
  d text;
BEGIN
  IF to_regclass('public.v_discord_published') IS NOT NULL THEN
    d := pg_get_viewdef('public.v_discord_published'::regclass, true);
    IF position('discord_void' in d) > 0 THEN
      RAISE NOTICE 'v_discord_published excludes discord_void; leaving that definition';
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
