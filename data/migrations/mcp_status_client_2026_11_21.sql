-- AI assistant (MCP): name the connected app in public.mcp_my_status().
--
-- The foundation returned connected_client as the OAuth client id (a uuid),
-- which the app cannot show. This adds two fields from Supabase Auth's
-- auth.oauth_clients:
--   connected_client_name   the name the app registered with ("Claude")
--   connected_client_host   the host of its first redirect address ("claude.ai")
-- The app names the assistant from the HOST when it is one it knows, because
-- with dynamic client registration anyone can register under any name.
--
-- Every other field is unchanged. Runs only while "mcp_my_status v2" is not in
-- the function's source. Where auth.oauth_clients does not exist (a scratch
-- cluster), both fields are NULL.

DO $mcp$
DECLARE
  lookup_name text;
  lookup_host text;
  body text;
BEGIN
  IF position('mcp_my_status v2' IN coalesce((SELECT prosrc FROM pg_proc
       WHERE oid = to_regprocedure('public.mcp_my_status()')), '')) > 0 THEN
    RETURN;
  END IF;
  IF to_regprocedure('public.mcp_my_status()') IS NULL THEN
    RAISE EXCEPTION 'mcp_status_client: apply mcp_foundation_2026_11_21.sql first';
  END IF;

  IF to_regclass('auth.oauth_clients') IS NOT NULL THEN
    lookup_name := '(SELECT left(o.client_name, 80) FROM auth.oauth_clients o
                      WHERE o.id::text = conn.client_id)';
    lookup_host := '(SELECT substring(split_part(o.redirect_uris, '','', 1)
                             FROM ''^[a-z]+://([^/:]+)'')
                       FROM auth.oauth_clients o WHERE o.id::text = conn.client_id)';
  ELSE
    lookup_name := 'NULL::text';
    lookup_host := 'NULL::text';
  END IF;

  body := $fn$
    -- mcp_my_status v2
    DECLARE
      uid uuid := auth.uid();
      lim mcp_meter.limits%ROWTYPE;
      d   date := (now() AT TIME ZONE 'America/New_York')::date;
      ent text;
      used int;
      conn mcp_meter.connections%ROWTYPE;
    BEGIN
      IF uid IS NULL THEN
        RAISE EXCEPTION 'mcp_my_status: sign in required' USING ERRCODE = '42501';
      END IF;
      SELECT * INTO lim FROM mcp_meter.limits WHERE id = 1;
      ent := mcp_meter.entitlement(uid);
      SELECT coalesce(max(c.question_no), 0) INTO used FROM mcp_meter.calls c
       WHERE c.user_id = uid AND c.day_et = d AND c.outcome = 'ok';
      SELECT * INTO conn FROM mcp_meter.connections c
       WHERE c.user_id = uid AND c.revoked_at IS NULL;
      RETURN jsonb_build_object(
        'entitlement', ent,
        'eligible', ent IN ('founder', 'paid', 'comped'),
        'can_view', ent IN ('founder', 'paid', 'comped', 'app_review'),
        'preview_only', ent = 'app_review',
        'unlimited', ent = 'founder',
        'trial_converts_at', (SELECT max(s.trial_end) FROM public.subscriptions s
                               WHERE s.user_id = uid AND s.status = 'trialing'),
        'terms_version', lim.terms_version,
        'terms_accepted', EXISTS (SELECT 1 FROM mcp_meter.terms_acceptances a
                                   WHERE a.user_id = uid AND a.terms_version = lim.terms_version),
        'suspended', EXISTS (SELECT 1 FROM mcp_meter.suspensions s
                              WHERE s.user_id = uid AND s.cleared_at IS NULL),
        'connected_client', conn.client_id,
        'connected_client_name', CASE WHEN conn.client_id IS NULL THEN NULL ELSE @NAME@ END,
        'connected_client_host', CASE WHEN conn.client_id IS NULL THEN NULL ELSE @HOST@ END,
        'connected_at', conn.connected_at,
        'last_used_at', conn.last_used_at,
        'questions_per_day', lim.questions_per_day,
        'questions_used', used,
        'questions_left', CASE WHEN ent = 'founder' THEN NULL
                               ELSE greatest(lim.questions_per_day - used, 0) END,
        'resets_at', mcp_meter.next_reset(now()));
    END
  $fn$;
  body := replace(replace(body, '@NAME@', lookup_name), '@HOST@', lookup_host);

  EXECUTE format($ddl$
    CREATE OR REPLACE FUNCTION public.mcp_my_status()
    RETURNS jsonb
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
    AS %L
  $ddl$, body);

  REVOKE ALL ON FUNCTION public.mcp_my_status() FROM PUBLIC, anon;
  GRANT EXECUTE ON FUNCTION public.mcp_my_status() TO authenticated, service_role;
END
$mcp$;
