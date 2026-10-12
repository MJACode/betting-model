-- A Discord void notice is the publish state for that lock.
--
-- v_discord_published used to return every discord_signal / discord_live
-- row, so a VOID that had been posted stayed on the app board. The notice
-- does not delete or edit the original message. It writes push_sent kind
-- discord_void, and this view drops that lock while the notice is newer
-- than the channel row (or either stamp is missing).
--
-- The pre-game key is game_id:model_id. A later pick on that game shares
-- it. When that pick posts, its signal is stamped after the notice and the
-- lock is in the view again. v_discord_void_notice still lists the key, so
-- the app can hide the VOID pick without hiding the later one.
--
-- A published VOID with no discord_void row stays in the view. That is
-- unchanged. A lock with no notice is unchanged.
--
-- security_invoker: the NOT EXISTS subquery runs as the caller. The policy
-- has to allow kind discord_void or the subquery sees none of those rows
-- and the exclusion never fires for anon. The view still returns only the
-- two channel kinds. message_id stays ungranted.
--
-- Keyword check on discord_void in the live view text and in the policy.
-- A re-run is a no-op. Must run after discord_publish_state_2026_09_23.sql,
-- which returns early once this clause is present so it cannot restore the
-- narrower view.
--
-- Does not UPDATE, DELETE or INSERT picks. One statement.

DO $mig$
DECLARE
  d text;
  pol text;
BEGIN
  d := NULL;
  IF to_regclass('public.v_discord_published') IS NOT NULL THEN
    d := pg_get_viewdef('public.v_discord_published'::regclass, true);
  END IF;

  SELECT pg_get_expr(p.polqual, p.polrelid)
    INTO pol
    FROM pg_policy p
    JOIN pg_class c ON c.oid = p.polrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public'
     AND c.relname = 'push_sent'
     AND p.polname = 'anon_read_discord_publish';

  IF d IS NOT NULL
     AND position('discord_void' in d) > 0
     AND position('sent_at' in d) > 0
     AND pol IS NOT NULL
     AND position('discord_void' in pol) > 0
     AND to_regclass('public.v_discord_void_notice') IS NOT NULL THEN
    RAISE NOTICE 'v_discord_published already drops discord_void notices - skipping';
    RETURN;
  END IF;

  EXECUTE $v$
    CREATE OR REPLACE VIEW public.v_discord_published
    WITH (security_invoker = on) AS
    SELECT s.lock_key, s.kind
    FROM public.push_sent s
    WHERE s.kind IN ('discord_signal', 'discord_live')
      AND NOT EXISTS (SELECT 1 FROM public.push_sent v
                      WHERE v.lock_key = s.lock_key AND v.kind = 'discord_void'
                        AND (s.sent_at IS NULL OR v.sent_at IS NULL
                             OR v.sent_at >= s.sent_at))
  $v$;

  EXECUTE $n$
    CREATE OR REPLACE VIEW public.v_discord_void_notice
    WITH (security_invoker = on) AS
    SELECT DISTINCT s.lock_key
    FROM public.push_sent s
    WHERE s.kind = 'discord_void'
  $n$;

  REVOKE ALL ON TABLE public.push_sent FROM anon, authenticated;
  GRANT SELECT (lock_key, kind) ON TABLE public.push_sent TO anon, authenticated;

  DROP POLICY IF EXISTS anon_read_discord_publish ON public.push_sent;
  CREATE POLICY anon_read_discord_publish ON public.push_sent
    FOR SELECT TO anon, authenticated
    USING (kind IN ('discord_signal', 'discord_live', 'discord_void'));

  GRANT SELECT ON public.v_discord_published TO anon, authenticated;
  REVOKE INSERT, UPDATE, DELETE ON public.v_discord_published
    FROM anon, authenticated;
  GRANT SELECT ON public.v_discord_void_notice TO anon, authenticated;
  REVOKE INSERT, UPDATE, DELETE ON public.v_discord_void_notice
    FROM anon, authenticated;
END $mig$;
