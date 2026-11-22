-- AI assistant (MCP): a member may connect several assistants; the daily
-- limit is one pool across all of them.
--
-- Matt, 2026-11-22. The foundation allowed ONE connection per member, keyed on
-- the OAuth client id. An assistant registers a NEW client id every time it is
-- reconnected, so a member who reconnected Claude was refused as "connected to
-- a different assistant" (measured 2026-11-22: Matt's Claude 0d34b350..., then
-- Grok 04ca31a8..., then a reconnected Claude 6fa640ef..., both refused).
--
-- What changes:
--   * An ASSISTANT is the family its sign-in returns to (mcp_meter.assistant_of):
--     claude.ai / claude.com -> 'claude', chatgpt.com / openai.com ->
--     'chatgpt', grok.com / x.ai -> 'grok', any other host -> that host, and a
--     client unknown to auth.oauth_clients -> its own id. The redirect host is
--     used, not the registered name: anyone can register under any name, but
--     the tokens only ever go to the redirect host.
--   * Up to limits.max_assistants (3) different assistants connected at once.
--     Every client of an assistant already connected is let in (a reconnect is
--     the same assistant); a 4th different assistant is refused 'app_limit'.
--   * One question pool per member, as before (counted by user, not client).
--     A burst of lookups is grouped per ASSISTANT, so two assistants asking at
--     the same moment are two questions, not one.
--   * Disconnect is per assistant: public.mcp_disconnect_assistant(text). The
--     old public.mcp_disconnect() still disconnects everything (older builds).
--   * public.mcp_my_status() adds 'assistants' (one entry per connected
--     assistant, with its questions today) and 'max_assistants'. Every field an
--     older build reads is kept.
--   * begin_call_session records a sign-in session on the connection of ITS
--     client only, so disconnecting Grok never cuts off Claude.
--
-- Nothing is deleted. The one-per-member unique index is dropped (an index,
-- not data) and replaced by one active row per (member, client).
--
-- Markers: begin_call keeps the text 'mcp_meter v2' and mcp_my_status keeps
-- 'mcp_my_status v2', so the foundation and mcp_status_client migrations stay
-- no-ops and never put the one-app versions back. This file runs while
-- 'mcp_meter v3' is missing from begin_call.

DO $mcp$
DECLARE
  lookup text;
  body   text;
BEGIN
  IF position('mcp_meter v3' IN coalesce((SELECT prosrc FROM pg_proc
       WHERE oid = to_regprocedure('mcp_meter.begin_call(uuid,text,text,jsonb,timestamptz)')), '')) > 0 THEN
    RETURN;
  END IF;
  IF to_regprocedure('mcp_meter.begin_call_session(uuid,text,text,text,jsonb,timestamptz)') IS NULL THEN
    RAISE EXCEPTION 'mcp_multi_assistant: apply mcp_session_revoke_2026_11_21.sql first';
  END IF;

  -- Tables ------------------------------------------------------------------
  ALTER TABLE mcp_meter.limits ADD COLUMN IF NOT EXISTS max_assistants int NOT NULL DEFAULT 3;
  ALTER TABLE mcp_meter.connections ADD COLUMN IF NOT EXISTS assistant text;
  ALTER TABLE mcp_meter.calls ADD COLUMN IF NOT EXISTS assistant text;
  DROP INDEX IF EXISTS mcp_meter.mcp_connections_one_active;
  CREATE UNIQUE INDEX IF NOT EXISTS mcp_connections_one_active_client
      ON mcp_meter.connections (user_id, client_id) WHERE revoked_at IS NULL;
  CREATE INDEX IF NOT EXISTS mcp_connections_user_assistant
      ON mcp_meter.connections (user_id, assistant) WHERE revoked_at IS NULL;

  -- Which assistant a client belongs to ---------------------------------------
  IF to_regclass('auth.oauth_clients') IS NOT NULL THEN
    lookup := '(SELECT lower(substring(split_part(o.redirect_uris, '','', 1)
                                       FROM ''^[a-zA-Z]+://([^/:]+)''))
                  FROM auth.oauth_clients o WHERE o.id::text = p_client)';
  ELSE
    lookup := 'NULL::text';
  END IF;
  body := $fn$
    DECLARE h text;
    BEGIN
      IF p_client IS NULL OR p_client = '' THEN
        RETURN 'unknown';
      END IF;
      h := @LOOKUP@;
      IF h IS NULL OR h = '' THEN
        RETURN left(p_client, 200);
      END IF;
      RETURN CASE
        WHEN h IN ('claude.ai', 'claude.com') OR h LIKE '%.claude.ai' OR h LIKE '%.claude.com' THEN 'claude'
        WHEN h IN ('chatgpt.com', 'openai.com') OR h LIKE '%.chatgpt.com' OR h LIKE '%.openai.com' THEN 'chatgpt'
        WHEN h IN ('grok.com', 'x.ai') OR h LIKE '%.grok.com' OR h LIKE '%.x.ai' THEN 'grok'
        ELSE left(h, 200)
      END;
    END
  $fn$;
  EXECUTE format($ddl$
    CREATE OR REPLACE FUNCTION mcp_meter.assistant_of(p_client text)
    RETURNS text
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
    AS %L
  $ddl$, replace(body, '@LOOKUP@', lookup));

  -- Existing rows get their assistant (an added column, nothing overwritten).
  UPDATE mcp_meter.connections SET assistant = mcp_meter.assistant_of(client_id)
   WHERE assistant IS NULL;

  -- The gate ------------------------------------------------------------------
  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION mcp_meter.begin_call(
        p_user uuid, p_client text, p_tool text, p_params jsonb,
        p_at timestamptz DEFAULT NULL)
    RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
    AS $fn$
    -- mcp_meter v3 (mcp_multi_assistant_2026_11_22.sql); replaces mcp_meter v2
    DECLARE
      lim        mcp_meter.limits%ROWTYPE;
      t          timestamptz := coalesce(p_at, now());
      d          date := (coalesce(p_at, now()) AT TIME ZONE 'America/New_York')::date;
      cl         text := coalesce(p_client, 'unknown');
      a          text := mcp_meter.assistant_of(coalesce(p_client, 'unknown'));
      ent        text;
      last_call  mcp_meter.calls%ROWTYPE;
      calls_day  int;
      rows_day   int;
      calls_min  int;
      burst_n    int;
      burst_t0   timestamptz;
      q_max      int;
      q          int;
      new_q      boolean;
      used       int;
      cid        bigint;
      verdict    text := 'ok';
    BEGIN
      SELECT * INTO lim FROM mcp_meter.limits WHERE id = 1;
      -- One call at a time per member.
      PERFORM pg_advisory_xact_lock(hashtextextended('mcp:' || p_user::text, 0));

      ent := mcp_meter.entitlement(p_user);
      IF ent IN ('none', 'trial', 'app_review') THEN
        verdict := 'not_entitled';
      ELSIF EXISTS (SELECT 1 FROM mcp_meter.suspensions s
                     WHERE s.user_id = p_user AND s.cleared_at IS NULL) THEN
        verdict := 'suspended';
      ELSIF NOT EXISTS (SELECT 1 FROM mcp_meter.terms_acceptances a2
                         WHERE a2.user_id = p_user AND a2.terms_version = lim.terms_version) THEN
        verdict := 'terms_required';
      END IF;

      -- Connections: one row per client; at most max_assistants assistants.
      IF verdict = 'ok' AND NOT EXISTS (
           SELECT 1 FROM mcp_meter.connections c
            WHERE c.user_id = p_user AND c.client_id = cl AND c.revoked_at IS NULL) THEN
        IF NOT EXISTS (SELECT 1 FROM mcp_meter.connections c
                        WHERE c.user_id = p_user AND c.assistant = a AND c.revoked_at IS NULL)
           AND (SELECT count(DISTINCT c.assistant) FROM mcp_meter.connections c
                 WHERE c.user_id = p_user AND c.revoked_at IS NULL) >= lim.max_assistants THEN
          verdict := 'app_limit';
        ELSE
          INSERT INTO mcp_meter.connections (user_id, client_id, assistant, connected_at)
          VALUES (p_user, cl, a, t);
        END IF;
      END IF;

      IF verdict = 'ok' THEN
        -- The day's question number is the member's (one pool); a burst is
        -- grouped per assistant.
        SELECT coalesce(max(c.question_no), 0) INTO q_max FROM mcp_meter.calls c
         WHERE c.user_id = p_user AND c.day_et = d AND c.outcome = 'ok';
        SELECT * INTO last_call FROM mcp_meter.calls c
         WHERE c.user_id = p_user AND c.day_et = d AND c.outcome = 'ok'
           AND coalesce(c.assistant, mcp_meter.assistant_of(c.client_id)) = a
         ORDER BY c.called_at DESC, c.id DESC LIMIT 1;
        IF last_call.id IS NULL THEN
          new_q := true;
        ELSE
          SELECT count(*), min(c.called_at) INTO burst_n, burst_t0
            FROM mcp_meter.calls c
           WHERE c.user_id = p_user AND c.day_et = d AND c.outcome = 'ok'
             AND c.question_no = last_call.question_no;
          new_q := t - last_call.called_at > make_interval(secs => lim.burst_gap_s)
                OR burst_n >= lim.burst_max_calls
                OR t - burst_t0 > make_interval(secs => lim.burst_max_s);
        END IF;
        q := CASE WHEN new_q THEN q_max + 1 ELSE last_call.question_no END;

        IF ent <> 'founder' THEN
          SELECT count(*), coalesce(sum(c.rows_out), 0) INTO calls_day, rows_day
            FROM mcp_meter.calls c
           WHERE c.user_id = p_user AND c.day_et = d AND c.outcome = 'ok';
          SELECT count(*) INTO calls_min FROM mcp_meter.calls c
           WHERE c.user_id = p_user AND c.outcome = 'ok'
             AND c.called_at > t - interval '1 minute';
          IF calls_min >= lim.calls_per_minute THEN
            verdict := 'rate_limited';
          ELSIF calls_day >= lim.calls_per_day OR rows_day >= lim.rows_per_day
                OR q > lim.questions_per_day THEN
            verdict := 'limit_reached';
          END IF;
        END IF;
      END IF;

      -- The pool used so far today: a continued burst does not lower it.
      used := CASE WHEN verdict = 'ok' THEN greatest(q, coalesce(q_max, 0)) ELSE coalesce(q_max, 0) END;

      INSERT INTO mcp_meter.calls (user_id, client_id, assistant, tool, params, called_at, day_et,
                                   question_no, outcome)
      VALUES (p_user, p_client, a, left(coalesce(p_tool, ''), 64), coalesce(p_params, '{}'::jsonb),
              t, d, CASE WHEN verdict = 'ok' THEN q END, verdict)
      RETURNING id INTO cid;

      IF verdict = 'ok' THEN
        UPDATE mcp_meter.connections SET last_used_at = t
         WHERE user_id = p_user AND client_id = cl AND revoked_at IS NULL;
      END IF;

      RETURN jsonb_build_object(
        'allowed', verdict = 'ok',
        'reason', verdict,
        'call_id', cid,
        'assistant', a,
        'entitlement', ent,
        'unlimited', ent = 'founder',
        'max_assistants', lim.max_assistants,
        'questions_used', used,
        'questions_left', CASE WHEN ent = 'founder' THEN NULL
                               ELSE greatest(lim.questions_per_day - used, 0) END,
        'resets_at', mcp_meter.next_reset(t));
    END
    $fn$
  $ddl$;

  -- A sign-in session belongs to the connection of its own client.
  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION mcp_meter.begin_call_session(
        p_user uuid, p_client text, p_session text, p_tool text, p_params jsonb,
        p_at timestamptz DEFAULT NULL)
    RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
    AS $fn$
    -- begin_call_session v2 (mcp_multi_assistant_2026_11_22.sql)
    DECLARE
      t   timestamptz := coalesce(p_at, now());
      g   jsonb;
      cid bigint;
    BEGIN
      IF p_session IS NOT NULL AND EXISTS (
           SELECT 1 FROM mcp_meter.connection_sessions s
             JOIN mcp_meter.connections c ON c.id = s.connection_id
            WHERE s.session_id = p_session AND c.user_id = p_user
              AND c.revoked_at IS NOT NULL) THEN
        INSERT INTO mcp_meter.calls (user_id, client_id, assistant, tool, params, called_at, day_et, outcome)
        VALUES (p_user, p_client, mcp_meter.assistant_of(coalesce(p_client, 'unknown')),
                left(coalesce(p_tool, ''), 64), coalesce(p_params, '{}'::jsonb),
                t, (t AT TIME ZONE 'America/New_York')::date, 'disconnected')
        RETURNING id INTO cid;
        RETURN jsonb_build_object('allowed', false, 'reason', 'disconnected', 'call_id', cid,
                                  'entitlement', mcp_meter.entitlement(p_user),
                                  'resets_at', mcp_meter.next_reset(t));
      END IF;

      g := mcp_meter.begin_call(p_user, p_client, p_tool, p_params, p_at);

      IF p_session IS NOT NULL AND (g->>'allowed')::boolean THEN
        INSERT INTO mcp_meter.connection_sessions (connection_id, session_id, first_seen_at)
        SELECT c.id, p_session, t FROM mcp_meter.connections c
         WHERE c.user_id = p_user AND c.client_id = coalesce(p_client, 'unknown')
           AND c.revoked_at IS NULL
        ON CONFLICT DO NOTHING;
      END IF;
      RETURN g;
    END
    $fn$
  $ddl$;

  -- For members ---------------------------------------------------------------
  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.mcp_disconnect_assistant(p_assistant text)
    RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
    AS $fn$
    DECLARE uid uuid := auth.uid();
    BEGIN
      IF uid IS NULL THEN
        RAISE EXCEPTION 'mcp_disconnect_assistant: sign in required' USING ERRCODE = '42501';
      END IF;
      UPDATE mcp_meter.connections SET revoked_at = now(), revoked_by = 'member'
       WHERE user_id = uid AND revoked_at IS NULL AND assistant = p_assistant;
      RETURN FOUND;
    END
    $fn$
  $ddl$;

  IF to_regclass('auth.oauth_clients') IS NOT NULL THEN
    lookup := '(SELECT jsonb_build_object(
                   ''name'', left(o.client_name, 80),
                   ''host'', lower(substring(split_part(o.redirect_uris, '','', 1)
                                            FROM ''^[a-zA-Z]+://([^/:]+)'')))
                  FROM auth.oauth_clients o WHERE o.id::text = x.client_id)';
  ELSE
    lookup := 'NULL::jsonb';
  END IF;
  body := $fn$
    -- mcp_my_status v3 (mcp_multi_assistant_2026_11_22.sql); keeps every mcp_my_status v2 field
    DECLARE
      uid uuid := auth.uid();
      lim mcp_meter.limits%ROWTYPE;
      d   date := (now() AT TIME ZONE 'America/New_York')::date;
      ent text;
      used int;
      conn mcp_meter.connections%ROWTYPE;
      meta jsonb;
      list jsonb;
    BEGIN
      IF uid IS NULL THEN
        RAISE EXCEPTION 'mcp_my_status: sign in required' USING ERRCODE = '42501';
      END IF;
      SELECT * INTO lim FROM mcp_meter.limits WHERE id = 1;
      ent := mcp_meter.entitlement(uid);
      SELECT coalesce(max(c.question_no), 0) INTO used FROM mcp_meter.calls c
       WHERE c.user_id = uid AND c.day_et = d AND c.outcome = 'ok';

      -- One entry per connected assistant, named from its newest client.
      SELECT coalesce(jsonb_agg(e ORDER BY e->>'connected_at'), '[]'::jsonb) INTO list FROM (
        SELECT jsonb_build_object(
                 'assistant', g.assistant,
                 'client_name', (SELECT m->>'name' FROM (SELECT @META@ AS m) z),
                 'client_host', (SELECT m->>'host' FROM (SELECT @META@ AS m) z),
                 'connected_at', g.connected_at,
                 'last_used_at', g.last_used_at,
                 'questions_today', (SELECT count(DISTINCT k.question_no) FROM mcp_meter.calls k
                                      WHERE k.user_id = uid AND k.day_et = d AND k.outcome = 'ok'
                                        AND coalesce(k.assistant, mcp_meter.assistant_of(k.client_id))
                                            = g.assistant)) AS e
          FROM (SELECT c.assistant,
                       min(c.connected_at) AS connected_at,
                       max(c.last_used_at) AS last_used_at,
                       (array_agg(c.client_id ORDER BY c.connected_at DESC))[1] AS client_id
                  FROM mcp_meter.connections c
                 WHERE c.user_id = uid AND c.revoked_at IS NULL
                 GROUP BY c.assistant) g,
               LATERAL (SELECT g.client_id) x
      ) s;

      -- The newest connection, for builds that read one connected app.
      SELECT * INTO conn FROM mcp_meter.connections c
       WHERE c.user_id = uid AND c.revoked_at IS NULL
       ORDER BY coalesce(c.last_used_at, c.connected_at) DESC LIMIT 1;
      SELECT (SELECT @META@ FROM (SELECT conn.client_id) x(client_id)) INTO meta;

      RETURN jsonb_build_object(
        'entitlement', ent,
        'eligible', ent IN ('founder', 'paid', 'comped'),
        'can_view', ent IN ('founder', 'paid', 'comped', 'app_review'),
        'preview_only', ent = 'app_review',
        'unlimited', ent = 'founder',
        'trial_converts_at', (SELECT max(s2.trial_end) FROM public.subscriptions s2
                               WHERE s2.user_id = uid AND s2.status = 'trialing'),
        'terms_version', lim.terms_version,
        'terms_accepted', EXISTS (SELECT 1 FROM mcp_meter.terms_acceptances a
                                   WHERE a.user_id = uid AND a.terms_version = lim.terms_version),
        'suspended', EXISTS (SELECT 1 FROM mcp_meter.suspensions s3
                              WHERE s3.user_id = uid AND s3.cleared_at IS NULL),
        'connected_client', conn.client_id,
        'connected_client_name', meta->>'name',
        'connected_client_host', meta->>'host',
        'connected_at', conn.connected_at,
        'last_used_at', conn.last_used_at,
        'assistants', list,
        'max_assistants', lim.max_assistants,
        'questions_per_day', lim.questions_per_day,
        'questions_used', used,
        'questions_left', CASE WHEN ent = 'founder' THEN NULL
                               ELSE greatest(lim.questions_per_day - used, 0) END,
        'resets_at', mcp_meter.next_reset(now()));
    END
  $fn$;
  EXECUTE format($ddl$
    CREATE OR REPLACE FUNCTION public.mcp_my_status()
    RETURNS jsonb
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
    AS %L
  $ddl$, replace(body, '@META@', lookup));

  -- Grants --------------------------------------------------------------------
  REVOKE ALL ON FUNCTION mcp_meter.assistant_of(text) FROM PUBLIC, anon, authenticated, mcp_reader;
  GRANT EXECUTE ON FUNCTION mcp_meter.assistant_of(text) TO mcp_meter_role;
  REVOKE ALL ON FUNCTION mcp_meter.begin_call(uuid, text, text, jsonb, timestamptz)
    FROM PUBLIC, anon, authenticated, mcp_reader;
  GRANT EXECUTE ON FUNCTION mcp_meter.begin_call(uuid, text, text, jsonb, timestamptz) TO mcp_meter_role;
  REVOKE ALL ON FUNCTION mcp_meter.begin_call_session(uuid, text, text, text, jsonb, timestamptz)
    FROM PUBLIC, anon, authenticated, mcp_reader;
  GRANT EXECUTE ON FUNCTION mcp_meter.begin_call_session(uuid, text, text, text, jsonb, timestamptz)
    TO mcp_meter_role;
  REVOKE ALL ON FUNCTION public.mcp_disconnect_assistant(text) FROM PUBLIC, anon;
  GRANT EXECUTE ON FUNCTION public.mcp_disconnect_assistant(text) TO authenticated, service_role;
  REVOKE ALL ON FUNCTION public.mcp_my_status() FROM PUBLIC, anon;
  GRANT EXECUTE ON FUNCTION public.mcp_my_status() TO authenticated, service_role;
END
$mcp$;
