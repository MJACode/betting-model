-- Drop the anon/authenticated WRITE grants from every public table that never
-- deliberately opened one. SELECT is untouched everywhere.
--
-- mike, 2026-09-03: "do the remaining 53 tables." Measured at run time it is 51
-- -- the earlier 53 was arithmetic over a snapshot that had already moved
-- (model_artifacts appeared and was revoked in between, and the team-stats
-- rebuild added tables). The count is not hard-coded for that reason.
--
-- ────────────────────────────────────────────────────────────────────────────
-- THE RULE, AND WHY IT CANNOT BREAK A CLIENT
--
-- Revoke INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER from anon and
-- authenticated on every table in `public` EXCEPT those carrying a PERMISSIVE
-- write policy for those roles. A write policy is the only evidence that
-- somebody meant to allow a write from the app; everything else is Supabase's
-- default `anon=arwdDxtm`, handed out by default privileges and never asked for.
--
-- Every client was checked before this was written, not after:
--
--   mobile app (anon / authenticated)
--       Direct writes: tracked_bets and device_push_tokens. That is ALL --
--       two call sites in mobile/src. Both keep their grant (both carry a
--       write policy).
--       Everything else it writes goes through an RPC. Of the RPCs it calls,
--       every SECURITY INVOKER one is STABLE -- Postgres forbids a write in a
--       STABLE function -- and every VOLATILE one (the five feedback_*
--       functions) is SECURITY DEFINER, so it runs as the owner and needs no
--       grant from the caller. There is therefore no app path that a revoke
--       here can reach.
--
--   supabase/functions/* (8 edge functions, incl. all billing: stripe-*,
--   whop-webhook, revenuecat-webhook, sharpsports*)
--       All use SUPABASE_SERVICE_ROLE_KEY. service_role keeps arwdDxtm and is
--       never named below. discord-link also holds the anon key, but only to
--       call auth.getUser() for identity -- no table access.
--
--   worker, scheduler, dashboard, Retool
--       Connect as `postgres` over DATABASE_URL. Owner, unaffected.
--
-- SELECT IS NEVER REVOKED. The app reads most of these tables, several through
-- security_invoker views that run as the caller. Taking SELECT would fail
-- silently -- PostgREST returns a permission error the client folds into
-- `error` and the screen renders empty.
--
-- ────────────────────────────────────────────────────────────────────────────
-- WHY A DO BLOCK RATHER THAN 51 WRITTEN-OUT STATEMENTS
--
-- Because the list goes stale and the RULE does not. models/trainer.py creates
-- model_artifacts on demand, and it reappeared with the full default grant
-- between two sweeps of the schema hours apart -- a hard-coded list would have
-- missed it and every table added since. This is re-runnable and idempotent,
-- and it NOTICEs each table it touches so the run log is the audit record.
--
-- NOT done here: ALTER DEFAULT PRIVILEGES, which is the only thing that stops
-- the next new table arriving with the grant again. It changes what happens to
-- every future table in the schema -- a new app-facing table would need an
-- explicit GRANT SELECT -- so it is mike's call, not a side effect of this.

BEGIN;

DO $$
DECLARE
    r          record;
    n_revoked  int := 0;
BEGIN
    FOR r IN
        SELECT c.oid, c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          -- something to revoke
          AND (has_table_privilege('anon',          c.oid, 'INSERT')
            OR has_table_privilege('anon',          c.oid, 'UPDATE')
            OR has_table_privilege('anon',          c.oid, 'DELETE')
            OR has_table_privilege('authenticated', c.oid, 'INSERT')
            OR has_table_privilege('authenticated', c.oid, 'UPDATE')
            OR has_table_privilege('authenticated', c.oid, 'DELETE'))
          -- and nobody deliberately opened a write on it
          AND NOT EXISTS (
                SELECT 1 FROM pg_policy p
                WHERE p.polrelid = c.oid
                  AND p.polpermissive
                  AND p.polcmd IN ('*', 'w', 'a', 'd'))
        ORDER BY c.relname
    LOOP
        EXECUTE format(
            'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
            'ON public.%I FROM anon, authenticated', r.relname);
        RAISE NOTICE 'revoked writes on %', r.relname;
        n_revoked := n_revoked + 1;
    END LOOP;

    RAISE NOTICE 'revoked anon/authenticated writes on % table(s)', n_revoked;

    -- The tables that MUST still be writable by the app. Asserted rather than
    -- assumed: if a policy is ever dropped, the loop above would silently
    -- start catching one of these, and the betslip or push registration would
    -- break with no error anywhere near the cause.
    IF NOT (has_table_privilege('anon', 'public.tracked_bets', 'INSERT')
        AND has_table_privilege('anon', 'public.tracked_bets', 'DELETE')
        AND has_table_privilege('anon', 'public.device_push_tokens', 'INSERT')
        AND has_table_privilege('anon', 'public.device_push_tokens', 'UPDATE')
        AND has_table_privilege('anon', 'public.feedback', 'INSERT')) THEN
        RAISE EXCEPTION 'a table the app writes lost its grant -- rolling back';
    END IF;
END $$;

COMMIT;
