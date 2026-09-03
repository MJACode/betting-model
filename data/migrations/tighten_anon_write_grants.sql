-- Drop the anon/authenticated WRITE grants that nothing uses.
--
-- mike, 2026-09-03: "fix the anon grant on odds."
--
-- WHAT WAS ACTUALLY THERE. Every table Supabase created carries the default
-- `anon=arwdDxtm` -- read AND write -- because default privileges grant it and
-- `REVOKE ... FROM PUBLIC` does not touch a named role. On `odds` that is 80
-- tables' worth of company, not an outlier: 57 of 80 public tables give anon
-- INSERT/UPDATE/DELETE.
--
-- ON `odds` IT IS INERT, AND SAYING OTHERWISE OVERSTATES IT. RLS is enabled and
-- both of its policies are SELECT-only, so a write is denied by RLS whatever the
-- grant says. This revoke is the second lock, not the first: it means a future
-- migration that adds a permissive policy, or disables RLS, cannot silently hand
-- anon write access to the table the whole system prices from.
--
-- SELECT IS KEPT, DELIBERATELY. The app reads `odds` directly
-- (mobile/src/lib/queries.ts fetchOddsHistory) and through v_latest_dk_odds and
-- v_latest_odds_all_books, both of which are security_invoker=on -- so they run
-- as the caller and need the caller's SELECT. Revoking it would break the line
-- movement history and every best-price display.
--
-- ────────────────────────────────────────────────────────────────────────────
-- worker_jobs AND odds_history_pulls ARE A DIFFERENT CASE: RLS IS OFF.
--
-- With no RLS there is nothing behind the grant, so anon -- the key shipped in
-- the app -- really can INSERT, UPDATE and DELETE. `worker_jobs` is the queue
-- the Railway worker CLAIMS AND EXECUTES every five minutes.
--
-- docs/followups.md records these as "not currently an open door", on the
-- strength of this query returning 0 rows:
--
--     select table_name, grantee, privilege_type
--     from information_schema.role_table_grants
--     where table_schema='public' and grantee in ('anon','authenticated');
--
-- That was a FALSE NEGATIVE. information_schema.role_table_grants only shows
-- grants the current role can see, so it returns 0 rows for `odds` too -- a
-- table whose relacl demonstrably reads `anon=arwdDxtm`. pg_class.relacl and
-- has_table_privilege() are the authoritative reads; information_schema is not.
--
-- Neither table has any app surface (no mobile/src query references either), so
-- both lose the whole grant rather than just the write half.
--
-- NOT DONE HERE: enabling RLS on those two. It needs ACCESS EXCLUSIVE and, more
-- to the point, RLS with no policy would lock out any connection that is not the
-- table owner -- and the worker's role has not been verified to be that owner.
-- The revoke closes the hole on its own; RLS would be the second lock, and it is
-- not worth risking the job queue to add it blind.

BEGIN;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON public.odds FROM anon, authenticated;

REVOKE ALL ON public.worker_jobs        FROM anon, authenticated;
REVOKE ALL ON public.odds_history_pulls FROM anon, authenticated;

-- model_artifacts is the same case again, and the worst of the three: it holds
-- the .pkl PAYLOADS the scorer loads when the file is missing from disk, so a
-- row here IS a model. RLS off + the full grant meant anon could UPDATE a
-- payload and change what every model predicts, or DELETE one and take the
-- model offline.
--
-- It is ALSO the reason a migration alone is not enough. The table is created
-- on demand by models/trainer.py::_store_artifact, so it reappeared with the
-- full default grant between one sweep of the schema and the next. The durable
-- fix is ARTIFACT_REVOKE, executed right after the CREATE in that function;
-- this line cleans up the instance that already exists.
REVOKE ALL ON public.model_artifacts FROM anon, authenticated;

COMMIT;
