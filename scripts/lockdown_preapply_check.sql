-- Abort when the live anon surface is not the 2026-11-18 baseline.
-- Run immediately after scripts/lockdown_acl_snapshot.sql and before the
-- migration. Expected: 97 relations anon can read rows from, 20 with a
-- grant but no visible rows, 82 functions anon can execute, 67 sequences
-- anon can use. Any other number means stop and re-diff.
--
-- Readable: a view or matview with SELECT, or a table whose SELECT policy
-- applies to anon or to PUBLIC. Grant-only: SELECT, RLS on, no such policy.

DO $check$
DECLARE
  readable   int;
  grant_only int;
  fns        int;
  seqs       int;
BEGIN
  SELECT count(*) INTO readable
    FROM pg_class c
   WHERE c.relnamespace = 'public'::regnamespace
     AND c.relkind IN ('r', 'v', 'm')
     AND has_table_privilege('anon', c.oid, 'SELECT')
     AND (
           c.relkind IN ('v', 'm')
        OR NOT c.relrowsecurity
        OR EXISTS (
             SELECT 1
               FROM pg_policy p
              WHERE p.polrelid = c.oid
                AND p.polcmd = 'r'
                AND (
                      cardinality(p.polroles) = 0
                   OR EXISTS (
                        SELECT 1
                          FROM pg_roles r
                         WHERE r.oid = ANY (p.polroles)
                           AND (r.rolname = 'anon'
                                OR pg_has_role('anon', r.oid, 'MEMBER'))
                      )
                )
           )
     );

  SELECT count(*) INTO grant_only
    FROM pg_class c
   WHERE c.relnamespace = 'public'::regnamespace
     AND c.relkind = 'r'
     AND c.relrowsecurity
     AND has_table_privilege('anon', c.oid, 'SELECT')
     AND NOT EXISTS (
           SELECT 1
             FROM pg_policy p
            WHERE p.polrelid = c.oid
              AND p.polcmd = 'r'
              AND (
                    cardinality(p.polroles) = 0
                 OR EXISTS (
                      SELECT 1
                        FROM pg_roles r
                       WHERE r.oid = ANY (p.polroles)
                         AND (r.rolname = 'anon'
                              OR pg_has_role('anon', r.oid, 'MEMBER'))
                    )
              )
         );

  SELECT count(*) INTO fns
    FROM pg_proc p
   WHERE p.pronamespace = 'public'::regnamespace
     AND has_function_privilege('anon', p.oid, 'EXECUTE');

  SELECT count(*) INTO seqs
    FROM pg_class c
   WHERE c.relnamespace = 'public'::regnamespace
     AND c.relkind = 'S'
     AND has_sequence_privilege('anon', c.oid, 'USAGE');

  IF readable <> 97 OR grant_only <> 20 OR fns <> 82 OR seqs <> 67 THEN
    RAISE EXCEPTION
      'anon lockdown baseline drifted: readable % grant_only % functions % sequences % (expected 97, 20, 82, 67). Stop. Do not apply.',
      readable, grant_only, fns, seqs;
  END IF;
  RAISE NOTICE 'anon baseline matches 2026-11-18 (97 readable, 20 grant-only, 82 functions, 67 sequences)';
END $check$;
