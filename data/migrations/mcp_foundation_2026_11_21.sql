-- AI assistant (MCP) connector: the database foundation.
-- Matt, 2026-11-20/21: paid and comped members only (not a free trial),
-- 10 questions a day, 30 lookups a day, 5 a minute, midnight ET reset, one
-- connected app; Matt and Mike (public.app_founders) unlimited; members accept
-- the AI assistant terms (web/content/terms.md section 19) before connecting.
--
-- Two schemas, neither readable by anon or authenticated:
--   mcp_stats  the Stats views the connector may read (filled in with the
--              connector's tools; empty here). Role mcp_reader: USAGE + SELECT
--              on those views only, read-only, 3 s timeout.
--   mcp_meter  limits, connections, terms acceptances, the request log and
--              suspensions. Role mcp_meter_role: EXECUTE on the gate functions
--              only, no table access.
-- Both roles are NOLOGIN. The connector's server connects as postgres and runs
-- each request as  SET LOCAL ROLE mcp_meter_role  (to meter) then
--   SET LOCAL ROLE mcp_reader; SET LOCAL transaction_read_only = on;
--   SET LOCAL statement_timeout = '3s'  (to read).
-- Role-level settings below apply at login only, not after SET ROLE, which is
-- why the server sets them per transaction as well.
--
-- What members call from the app or the consent page (authenticated only):
--   public.mcp_accept_terms(version, client)  record acceptance
--   public.mcp_my_status()                    Settings screen state
--   public.mcp_disconnect()                   Disconnect button
--
-- Nothing here deletes a row: a disconnect or a cleared suspension is a
-- timestamp (CLAUDE.md "no data is ever deleted").
--
-- One DO block in ACTIVE_MIGRATIONS. It runs only while the marker
-- 'mcp_meter v2' is missing from mcp_meter.begin_call, so a pass after the
-- first issues no DDL. A change bumps the marker.
--
-- v2 (Matt, 2026-11-21): App Review accounts are 'app_review': they can see
-- the AI Assistant screens (mcp_my_status.can_view) but cannot connect
-- (begin_call refuses them as not_entitled).

DO $mcp$
BEGIN
  IF to_regprocedure('mcp_meter.begin_call(uuid,text,text,jsonb,timestamptz)') IS NOT NULL
     AND position('mcp_meter v2' IN (SELECT prosrc FROM pg_proc
          WHERE oid = to_regprocedure('mcp_meter.begin_call(uuid,text,text,jsonb,timestamptz)'))) > 0
  THEN
    RETURN;
  END IF;

  -- Roles ------------------------------------------------------------------
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_reader') THEN
    CREATE ROLE mcp_reader NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_meter_role') THEN
    CREATE ROLE mcp_meter_role NOLOGIN NOINHERIT;
  END IF;
  GRANT mcp_reader TO postgres;
  GRANT mcp_meter_role TO postgres;
  ALTER ROLE mcp_reader SET default_transaction_read_only = on;
  ALTER ROLE mcp_reader SET statement_timeout = '3s';

  -- Schemas ----------------------------------------------------------------
  CREATE SCHEMA IF NOT EXISTS mcp_stats;
  CREATE SCHEMA IF NOT EXISTS mcp_meter;
  REVOKE ALL ON SCHEMA mcp_stats FROM PUBLIC, anon, authenticated;
  REVOKE ALL ON SCHEMA mcp_meter FROM PUBLIC, anon, authenticated, mcp_reader;
  GRANT USAGE ON SCHEMA mcp_stats TO mcp_reader;
  GRANT USAGE ON SCHEMA mcp_meter TO mcp_meter_role;
  -- Views added to mcp_stats later are readable by mcp_reader and nobody else.
  ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA mcp_stats
      REVOKE ALL ON TABLES FROM PUBLIC;
  ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA mcp_stats
      GRANT SELECT ON TABLES TO mcp_reader;
  ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA mcp_meter
      REVOKE ALL ON TABLES FROM PUBLIC;
  ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA mcp_meter
      REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

  -- Tables -----------------------------------------------------------------
  CREATE TABLE IF NOT EXISTS mcp_meter.limits (
    id                 int PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    questions_per_day  int NOT NULL DEFAULT 10,
    calls_per_day      int NOT NULL DEFAULT 30,
    calls_per_minute   int NOT NULL DEFAULT 5,
    rows_per_day       int NOT NULL DEFAULT 200,
    burst_gap_s        int NOT NULL DEFAULT 120,
    burst_max_calls    int NOT NULL DEFAULT 5,
    burst_max_s        int NOT NULL DEFAULT 300,
    terms_version      text NOT NULL DEFAULT '2026-11-21',
    updated_at         timestamptz NOT NULL DEFAULT now(),
    updated_by         text NOT NULL DEFAULT 'matt'
  );
  INSERT INTO mcp_meter.limits (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

  CREATE TABLE IF NOT EXISTS mcp_meter.terms_acceptances (
    id            bigserial PRIMARY KEY,
    user_id       uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    terms_version text NOT NULL,
    client_id     text,
    accepted_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, terms_version)
  );

  CREATE TABLE IF NOT EXISTS mcp_meter.connections (
    id           bigserial PRIMARY KEY,
    user_id      uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    client_id    text NOT NULL,
    connected_at timestamptz NOT NULL DEFAULT now(),
    last_used_at timestamptz,
    revoked_at   timestamptz,
    revoked_by   text
  );
  CREATE UNIQUE INDEX IF NOT EXISTS mcp_connections_one_active
      ON mcp_meter.connections (user_id) WHERE revoked_at IS NULL;

  CREATE TABLE IF NOT EXISTS mcp_meter.calls (
    id          bigserial PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    client_id   text,
    tool        text NOT NULL,
    params      jsonb NOT NULL DEFAULT '{}'::jsonb,
    called_at   timestamptz NOT NULL,
    day_et      date NOT NULL,
    question_no int,
    rows_out    int,
    outcome     text NOT NULL,
    finished_at timestamptz
  );
  CREATE INDEX IF NOT EXISTS mcp_calls_user_day
      ON mcp_meter.calls (user_id, day_et, called_at);

  CREATE TABLE IF NOT EXISTS mcp_meter.suspensions (
    id           bigserial PRIMARY KEY,
    user_id      uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    reason       text NOT NULL,
    suspended_at timestamptz NOT NULL DEFAULT now(),
    cleared_at   timestamptz,
    cleared_by   text
  );

  ALTER TABLE mcp_meter.limits            ENABLE ROW LEVEL SECURITY;
  ALTER TABLE mcp_meter.terms_acceptances ENABLE ROW LEVEL SECURITY;
  ALTER TABLE mcp_meter.connections       ENABLE ROW LEVEL SECURITY;
  ALTER TABLE mcp_meter.calls             ENABLE ROW LEVEL SECURITY;
  ALTER TABLE mcp_meter.suspensions       ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON ALL TABLES IN SCHEMA mcp_meter FROM PUBLIC, anon, authenticated, mcp_reader, mcp_meter_role;
  REVOKE ALL ON ALL SEQUENCES IN SCHEMA mcp_meter FROM PUBLIC, anon, authenticated, mcp_reader, mcp_meter_role;

  -- Who may use it ---------------------------------------------------------
  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION mcp_meter.entitlement(p_user uuid)
    RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
    AS $fn$
      SELECT CASE
        WHEN p_user IS NULL THEN 'none'
        WHEN EXISTS (SELECT 1 FROM public.app_founders f WHERE f.user_id = p_user) THEN 'founder'
        WHEN EXISTS (SELECT 1 FROM public.subscriptions s
                      WHERE s.user_id = p_user AND s.status = 'active'
                        AND (s.current_period_end IS NULL OR s.current_period_end > now())) THEN 'paid'
        WHEN EXISTS (SELECT 1 FROM public.access_grants g
                      WHERE g.user_id = p_user AND g.access_source = 'comped'
                        AND (g.expires_at IS NULL OR g.expires_at > now())) THEN 'comped'
        WHEN EXISTS (SELECT 1 FROM public.access_grants g
                      WHERE g.user_id = p_user AND g.access_source = 'app_review'
                        AND (g.expires_at IS NULL OR g.expires_at > now())) THEN 'app_review'
        WHEN EXISTS (SELECT 1 FROM public.subscriptions s
                      WHERE s.user_id = p_user AND s.status = 'trialing'
                        AND (s.current_period_end IS NULL OR s.current_period_end > now())) THEN 'trial'
        ELSE 'none'
      END
    $fn$
  $ddl$;

  -- Midnight ET after a moment.
  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION mcp_meter.next_reset(p_at timestamptz)
    RETURNS timestamptz
    LANGUAGE sql STABLE SET search_path = ''
    AS $fn$
      SELECT ((((p_at AT TIME ZONE 'America/New_York')::date + 1)::timestamp)
              AT TIME ZONE 'America/New_York')
    $fn$
  $ddl$;

  -- The gate the server calls before every tool. Records the call either way.
  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION mcp_meter.begin_call(
        p_user uuid, p_client text, p_tool text, p_params jsonb,
        p_at timestamptz DEFAULT NULL)
    RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
    AS $fn$
    -- mcp_meter v2 (mcp_foundation_2026_11_21.sql)
    DECLARE
      lim        mcp_meter.limits%ROWTYPE;
      t          timestamptz := coalesce(p_at, now());
      d          date := (coalesce(p_at, now()) AT TIME ZONE 'America/New_York')::date;
      ent        text;
      conn       mcp_meter.connections%ROWTYPE;
      last_call  mcp_meter.calls%ROWTYPE;
      calls_day  int;
      rows_day   int;
      calls_min  int;
      burst_n    int;
      burst_t0   timestamptz;
      q          int;
      new_q      boolean;
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
      ELSIF NOT EXISTS (SELECT 1 FROM mcp_meter.terms_acceptances a
                         WHERE a.user_id = p_user AND a.terms_version = lim.terms_version) THEN
        verdict := 'terms_required';
      END IF;

      IF verdict = 'ok' THEN
        SELECT * INTO conn FROM mcp_meter.connections c
         WHERE c.user_id = p_user AND c.revoked_at IS NULL;
        IF NOT FOUND THEN
          INSERT INTO mcp_meter.connections (user_id, client_id, connected_at)
          VALUES (p_user, coalesce(p_client, 'unknown'), t);
        ELSIF conn.client_id IS DISTINCT FROM coalesce(p_client, 'unknown') THEN
          verdict := 'one_app';
        END IF;
      END IF;

      IF verdict = 'ok' THEN
        SELECT * INTO last_call FROM mcp_meter.calls c
         WHERE c.user_id = p_user AND c.day_et = d AND c.outcome = 'ok'
         ORDER BY c.called_at DESC, c.id DESC LIMIT 1;
        q := coalesce(last_call.question_no, 0);
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
        IF new_q THEN q := q + 1; END IF;

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

      INSERT INTO mcp_meter.calls (user_id, client_id, tool, params, called_at, day_et,
                                   question_no, outcome)
      VALUES (p_user, p_client, left(coalesce(p_tool, ''), 64), coalesce(p_params, '{}'::jsonb),
              t, d, CASE WHEN verdict = 'ok' THEN q END, verdict)
      RETURNING id INTO cid;

      IF verdict = 'ok' THEN
        UPDATE mcp_meter.connections SET last_used_at = t
         WHERE user_id = p_user AND revoked_at IS NULL;
      END IF;

      RETURN jsonb_build_object(
        'allowed', verdict = 'ok',
        'reason', verdict,
        'call_id', cid,
        'entitlement', ent,
        'unlimited', ent = 'founder',
        'questions_used', CASE WHEN verdict = 'ok' THEN q ELSE coalesce(q - CASE WHEN new_q THEN 1 ELSE 0 END, 0) END,
        'questions_left', CASE WHEN ent = 'founder' THEN NULL
                               ELSE greatest(lim.questions_per_day
                                    - CASE WHEN verdict = 'ok' THEN q
                                           ELSE coalesce(q - CASE WHEN new_q THEN 1 ELSE 0 END, 0) END, 0) END,
        'resets_at', mcp_meter.next_reset(t));
    END
    $fn$
  $ddl$;

  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION mcp_meter.finish_call(p_call bigint, p_rows int, p_outcome text DEFAULT NULL)
    RETURNS void
    LANGUAGE sql SECURITY DEFINER SET search_path = ''
    AS $fn$
      UPDATE mcp_meter.calls
         SET rows_out = greatest(coalesce(p_rows, 0), 0),
             finished_at = now(),
             outcome = CASE WHEN p_outcome IS NULL OR outcome <> 'ok' THEN outcome ELSE p_outcome END
       WHERE id = p_call
    $fn$
  $ddl$;

  -- For members, from the app and the consent page --------------------------
  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.mcp_accept_terms(p_version text, p_client text DEFAULT NULL)
    RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
    AS $fn$
    DECLARE uid uuid := auth.uid();
    BEGIN
      IF uid IS NULL THEN
        RAISE EXCEPTION 'mcp_accept_terms: sign in required' USING ERRCODE = '42501';
      END IF;
      IF p_version IS DISTINCT FROM (SELECT terms_version FROM mcp_meter.limits WHERE id = 1) THEN
        RAISE EXCEPTION 'mcp_accept_terms: not the current terms' USING ERRCODE = '22023';
      END IF;
      INSERT INTO mcp_meter.terms_acceptances (user_id, terms_version, client_id)
      VALUES (uid, p_version, left(p_client, 200))
      ON CONFLICT (user_id, terms_version) DO NOTHING;
      RETURN true;
    END
    $fn$
  $ddl$;

  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.mcp_my_status()
    RETURNS jsonb
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
    AS $fn$
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
        'connected_at', conn.connected_at,
        'last_used_at', conn.last_used_at,
        'questions_per_day', lim.questions_per_day,
        'questions_used', used,
        'questions_left', CASE WHEN ent = 'founder' THEN NULL
                               ELSE greatest(lim.questions_per_day - used, 0) END,
        'resets_at', mcp_meter.next_reset(now()));
    END
    $fn$
  $ddl$;

  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION public.mcp_disconnect()
    RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
    AS $fn$
    DECLARE uid uuid := auth.uid();
    BEGIN
      IF uid IS NULL THEN
        RAISE EXCEPTION 'mcp_disconnect: sign in required' USING ERRCODE = '42501';
      END IF;
      UPDATE mcp_meter.connections SET revoked_at = now(), revoked_by = 'member'
       WHERE user_id = uid AND revoked_at IS NULL;
      RETURN FOUND;
    END
    $fn$
  $ddl$;

  -- Grants ------------------------------------------------------------------
  REVOKE ALL ON ALL FUNCTIONS IN SCHEMA mcp_meter FROM PUBLIC, anon, authenticated, mcp_reader;
  GRANT EXECUTE ON FUNCTION mcp_meter.begin_call(uuid, text, text, jsonb, timestamptz) TO mcp_meter_role;
  GRANT EXECUTE ON FUNCTION mcp_meter.finish_call(bigint, int, text) TO mcp_meter_role;
  GRANT EXECUTE ON FUNCTION mcp_meter.entitlement(uuid) TO mcp_meter_role;
  GRANT EXECUTE ON FUNCTION mcp_meter.next_reset(timestamptz) TO mcp_meter_role;
  REVOKE ALL ON FUNCTION public.mcp_accept_terms(text, text) FROM PUBLIC, anon;
  REVOKE ALL ON FUNCTION public.mcp_my_status() FROM PUBLIC, anon;
  REVOKE ALL ON FUNCTION public.mcp_disconnect() FROM PUBLIC, anon;
  GRANT EXECUTE ON FUNCTION public.mcp_accept_terms(text, text) TO authenticated, service_role;
  GRANT EXECUTE ON FUNCTION public.mcp_my_status() TO authenticated, service_role;
  GRANT EXECUTE ON FUNCTION public.mcp_disconnect() TO authenticated, service_role;
END
$mcp$;
