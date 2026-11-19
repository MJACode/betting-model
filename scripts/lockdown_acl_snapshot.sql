-- Read-only except for the snapshot table itself. Run in the SQL editor as
-- postgres, in the same session, immediately before step A and again before
-- step B. Then run scripts/lockdown_preapply_check.sql. If that raises,
-- do not apply the migration.
--
-- Replace :label with pre_step_a_YYYYMMDD or pre_step_b_YYYYMMDD.
-- Copy the inserted rows out (see the COPY at the bottom) and keep the file
-- next to ops/acl_snapshots/.

CREATE SCHEMA IF NOT EXISTS ops;
REVOKE ALL ON SCHEMA ops FROM PUBLIC, anon, authenticated;

CREATE TABLE IF NOT EXISTS ops.acl_snapshot (
    taken_at timestamptz NOT NULL DEFAULT now(),
    label    text NOT NULL,
    kind     text NOT NULL,
    object   text NOT NULL,
    detail   jsonb NOT NULL
);
REVOKE ALL ON ops.acl_snapshot FROM PUBLIC, anon, authenticated;

-- Edit the label before running. One label per apply.
INSERT INTO ops.acl_snapshot (label, kind, object, detail)
SELECT 'pre_step_a_20261118', 'relacl', c.oid::regclass::text,
       jsonb_build_object(
           'relkind', c.relkind,
           'acl', c.relacl::text[],
           'rls', c.relrowsecurity,
           'force_rls', c.relforcerowsecurity,
           'opts', c.reloptions)
  FROM pg_class c
 WHERE c.relnamespace = 'public'::regnamespace
   AND c.relkind IN ('r', 'v', 'm', 'p', 'f', 'S')
UNION ALL
SELECT 'pre_step_a_20261118', 'attacl',
       a.attrelid::regclass::text || '.' || a.attname,
       jsonb_build_object('acl', a.attacl::text[])
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
 WHERE c.relnamespace = 'public'::regnamespace
   AND a.attacl IS NOT NULL
UNION ALL
SELECT 'pre_step_a_20261118', 'proacl', p.oid::regprocedure::text,
       jsonb_build_object(
           'acl', p.proacl::text[],
           'secdef', p.prosecdef,
           'owner', pg_get_userbyid(p.proowner))
  FROM pg_proc p
 WHERE p.pronamespace = 'public'::regnamespace
UNION ALL
SELECT 'pre_step_a_20261118', 'policy',
       schemaname || '.' || tablename || ':' || policyname,
       jsonb_build_object(
           'cmd', cmd, 'roles', roles, 'permissive', permissive,
           'qual', qual, 'with_check', with_check)
  FROM pg_policies
 WHERE schemaname = 'public'
UNION ALL
SELECT 'pre_step_a_20261118', 'defacl',
       pg_get_userbyid(d.defaclrole) || ':' || d.defaclobjtype
         || CASE WHEN d.defaclnamespace = 0 THEN ':global' ELSE '' END,
       jsonb_build_object(
           'acl', d.defaclacl::text[],
           'global', d.defaclnamespace = 0)
  FROM pg_default_acl d
 WHERE d.defaclnamespace = 'public'::regnamespace
    OR d.defaclnamespace = 0;
