-- After step B, and after anything later creates a public object.
-- Read-only except that it raises. It does not revoke.
--
-- anon may keep site_public_record, log_app_error, log_app_timings,
-- and save_device_push_token. Anything else in public is a miss.
-- storage, graphql and graphql_public are not looked at.
--
-- A table created by supabase_admin still arrives with anon, because
-- postgres is not a member of that role and cannot change its defaults.
-- This check is what flags that object. --lockdown-b revokes it when
-- the runner owns it, and fails when it does not.

DO $check$
DECLARE bad text;
BEGIN
  SELECT string_agg(format('%s.%s', n.nspname, c.relname), ', ' ORDER BY c.relname)
    INTO bad
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public'
     AND c.relkind IN ('r', 'v', 'm', 'p', 'f')
     AND c.relname <> 'site_public_record'
     AND CASE WHEN c.relkind IN ('r', 'v', 'm', 'p', 'f') THEN
           has_table_privilege('anon', c.oid, 'SELECT')
           OR has_table_privilege('anon', c.oid, 'INSERT')
           OR has_table_privilege('anon', c.oid, 'UPDATE')
           OR has_table_privilege('anon', c.oid, 'DELETE')
         ELSE false END;
  IF bad IS NOT NULL THEN
    RAISE EXCEPTION 'anon still has table privs on: %', bad;
  END IF;

  SELECT string_agg(c.relname, ', ' ORDER BY c.relname) INTO bad
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public'
     AND c.relkind = 'S'
     AND c.relacl IS NOT NULL
     AND EXISTS (
       SELECT 1 FROM aclexplode(c.relacl) a
        WHERE a.grantee = (SELECT oid FROM pg_roles WHERE rolname = 'anon')
          AND a.privilege_type = 'USAGE'
     );
  IF bad IS NOT NULL THEN
    RAISE EXCEPTION 'anon still has sequence usage on: %', bad;
  END IF;

  SELECT string_agg(p.oid::regprocedure::text, ', ' ORDER BY p.proname) INTO bad
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'public'
     AND p.proname NOT IN ('log_app_error', 'log_app_timings', 'save_device_push_token', 'site_public_record_rows', 'premium_pre_request')
     AND has_function_privilege('anon', p.oid, 'EXECUTE');
  IF bad IS NOT NULL THEN
    RAISE EXCEPTION 'anon still executes: %', bad;
  END IF;
END
$check$;
