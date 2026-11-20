-- Founders: Matt and Mike (Matt, 2026-11-20: "Matt and Mike have unlimited
-- searches with the MCP"; Mike's account confirmed by Matt the same day).
--
-- The MCP server reads this to skip the daily question limit. App access is
-- unaffected: both accounts already pass has_app_access() through comped
-- grants. Closed to anon and authenticated; only the worker, the dashboard and
-- the future MCP read role (granted when it is built) see it.
--
-- User ids, not emails, are stored here. One DO block in ACTIVE_MIGRATIONS:
-- DDL runs only when the table is missing; later passes only insert missing
-- rows (ON CONFLICT DO NOTHING), which is not DDL.

DO $founders$
BEGIN
  IF to_regclass('public.app_founders') IS NULL THEN
    CREATE TABLE public.app_founders (
      user_id  uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
      label    text NOT NULL,
      added_at timestamptz NOT NULL DEFAULT now(),
      added_by text NOT NULL
    );
    ALTER TABLE public.app_founders ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.app_founders FROM PUBLIC, anon, authenticated;
  END IF;

  INSERT INTO public.app_founders (user_id, label, added_by)
  SELECT v.user_id, v.label, 'matt'
    FROM (VALUES
      ('33f61a85-b7ee-4a00-9641-73600e410305'::uuid, 'Matt'),
      ('a2f697f8-02e1-4006-b7b2-6f7a0999f62c'::uuid, 'Mike')
    ) AS v(user_id, label)
   WHERE EXISTS (SELECT 1 FROM auth.users u WHERE u.id = v.user_id)
  ON CONFLICT (user_id) DO NOTHING;
END
$founders$;
