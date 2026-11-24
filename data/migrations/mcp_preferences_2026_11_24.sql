-- AI assistant (MCP): a saved preferences profile per member, and a record of
-- what each member's assistant says it can do.
--
-- Matt, 2026-11-23/24. Two members asked their assistants (one Grok, one
-- Claude) for three prop picks on the same one-game NFL slate and got the same
-- three: the tools rank deterministically, so the same question returns the
-- same list. Matt: "Do both of these" -- (1) find out which assistants support
-- MCP elicitation (the connector asking the member a form of questions), and
-- (2) a saved preferences profile per member. On (1) he chose "measure first":
-- log what each assistant ADVERTISES when it connects rather than trust blog
-- posts. On the profile: sports and teams, price and risk, stats and books,
-- research style; reading or saving it is FREE (not one of the 10 questions).
--
-- What this adds (all in mcp_meter, none readable by anon/authenticated/
-- mcp_reader; mcp_meter_role gets EXECUTE on the two functions only):
--   mcp_meter.preference_saves   append-only: every save is a new row; the
--                                current profile is the newest row. Nothing is
--                                overwritten or deleted (CLAUDE.md §1b).
--   mcp_meter.client_capabilities one row per (member, client, protocol,
--                                client name/version, capabilities): first and
--                                last seen and how often. Answers "does this
--                                member's Claude/ChatGPT/Grok send
--                                capabilities.elicitation?" from our own data.
--   mcp_meter.record_client(...)  called on every initialize.
--   mcp_meter.profile_call(...)   get or save the profile. Applies the same
--                                refusals as begin_call (disconnected session,
--                                not entitled, suspended, terms, assistant cap)
--                                but counts no question: its log rows carry
--                                outcome 'profile', and every limit in
--                                begin_call counts outcome 'ok' only. Its own
--                                caps: limits.profile_saves_per_day (20) and
--                                limits.profile_reads_per_day (100).
--
-- Runs while the 'mcp_preferences v1' marker is missing from
-- mcp_meter.profile_call.

DO $mcp$
BEGIN
  IF position('mcp_preferences v1' IN coalesce((SELECT prosrc FROM pg_proc
       WHERE oid = to_regprocedure('mcp_meter.profile_call(uuid,text,text,text,jsonb,timestamptz)')), '')) > 0 THEN
    RETURN;
  END IF;
  IF to_regprocedure('mcp_meter.assistant_of(text)') IS NULL
     OR to_regclass('mcp_meter.connection_sessions') IS NULL THEN
    RAISE EXCEPTION 'mcp_preferences: apply mcp_multi_assistant_2026_11_22.sql first';
  END IF;

  -- Tables ------------------------------------------------------------------
  ALTER TABLE mcp_meter.limits ADD COLUMN IF NOT EXISTS profile_saves_per_day int NOT NULL DEFAULT 20;
  ALTER TABLE mcp_meter.limits ADD COLUMN IF NOT EXISTS profile_reads_per_day int NOT NULL DEFAULT 100;

  CREATE TABLE IF NOT EXISTS mcp_meter.preference_saves (
    id          bigserial PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    prefs       jsonb NOT NULL CHECK (jsonb_typeof(prefs) = 'object' AND length(prefs::text) <= 4000),
    client_id   text,
    assistant   text,
    saved_at    timestamptz NOT NULL DEFAULT now()
  );
  CREATE INDEX IF NOT EXISTS mcp_preference_saves_user
      ON mcp_meter.preference_saves (user_id, saved_at DESC, id DESC);

  CREATE TABLE IF NOT EXISTS mcp_meter.client_capabilities (
    id               bigserial PRIMARY KEY,
    user_id          uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    client_id        text NOT NULL,
    assistant        text,
    protocol_version text NOT NULL DEFAULT '',
    client_name      text NOT NULL DEFAULT '',
    client_version   text NOT NULL DEFAULT '',
    capabilities     jsonb NOT NULL DEFAULT '{}'::jsonb,
    elicitation      boolean NOT NULL DEFAULT false,
    first_seen_at    timestamptz NOT NULL DEFAULT now(),
    last_seen_at     timestamptz NOT NULL DEFAULT now(),
    seen_count       int NOT NULL DEFAULT 1
  );
  CREATE UNIQUE INDEX IF NOT EXISTS mcp_client_capabilities_key
      ON mcp_meter.client_capabilities (user_id, client_id, protocol_version, client_name,
                                        client_version, md5(capabilities::text));

  ALTER TABLE mcp_meter.preference_saves    ENABLE ROW LEVEL SECURITY;
  ALTER TABLE mcp_meter.client_capabilities ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON mcp_meter.preference_saves, mcp_meter.client_capabilities
    FROM PUBLIC, anon, authenticated, mcp_reader, mcp_meter_role;
  REVOKE ALL ON SEQUENCE mcp_meter.preference_saves_id_seq, mcp_meter.client_capabilities_id_seq
    FROM PUBLIC, anon, authenticated, mcp_reader, mcp_meter_role;

  -- What the assistant says it can do, on every initialize --------------------
  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION mcp_meter.record_client(
        p_user uuid, p_client text, p_protocol text, p_client_info jsonb, p_caps jsonb,
        p_at timestamptz DEFAULT NULL)
    RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
    AS $fn$
    -- record_client v1 (mcp_preferences_2026_11_24.sql)
    DECLARE
      t    timestamptz := coalesce(p_at, now());
      caps jsonb := CASE WHEN jsonb_typeof(p_caps) = 'object' AND length(p_caps::text) <= 4000
                         THEN p_caps ELSE '{}'::jsonb END;
      info jsonb := CASE WHEN jsonb_typeof(p_client_info) = 'object' THEN p_client_info ELSE '{}'::jsonb END;
    BEGIN
      IF p_user IS NULL THEN RETURN; END IF;
      INSERT INTO mcp_meter.client_capabilities AS cc
             (user_id, client_id, assistant, protocol_version, client_name, client_version,
              capabilities, elicitation, first_seen_at, last_seen_at, seen_count)
      VALUES (p_user, left(coalesce(p_client, 'unknown'), 200),
              mcp_meter.assistant_of(coalesce(p_client, 'unknown')),
              left(coalesce(p_protocol, ''), 40),
              left(coalesce(info->>'name', ''), 120),
              left(coalesce(info->>'version', ''), 60),
              caps, caps ? 'elicitation', t, t, 1)
      ON CONFLICT (user_id, client_id, protocol_version, client_name, client_version, md5(capabilities::text))
      DO UPDATE SET last_seen_at = greatest(cc.last_seen_at, EXCLUDED.last_seen_at),
                    seen_count = cc.seen_count + 1;
    END
    $fn$
  $ddl$;

  -- Get or save the profile (free: no question counted) -----------------------
  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION mcp_meter.profile_call(
        p_user uuid, p_client text, p_session text, p_action text, p_prefs jsonb,
        p_at timestamptz DEFAULT NULL)
    RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
    AS $fn$
    -- mcp_preferences v1 (mcp_preferences_2026_11_24.sql)
    DECLARE
      lim     mcp_meter.limits%ROWTYPE;
      t       timestamptz := coalesce(p_at, now());
      d       date := (coalesce(p_at, now()) AT TIME ZONE 'America/New_York')::date;
      cl      text := coalesce(p_client, 'unknown');
      a       text := mcp_meter.assistant_of(coalesce(p_client, 'unknown'));
      v_tool  text := CASE p_action WHEN 'save' THEN 'save_my_preferences' ELSE 'get_my_preferences' END;
      ent     text;
      verdict text := 'ok';
      n       int;
      cur     mcp_meter.preference_saves%ROWTYPE;
      merged  jsonb;
    BEGIN
      IF p_action NOT IN ('get', 'save') THEN
        RAISE EXCEPTION 'profile_call: action must be get or save' USING ERRCODE = '22023';
      END IF;
      SELECT * INTO lim FROM mcp_meter.limits WHERE id = 1;
      PERFORM pg_advisory_xact_lock(hashtextextended('mcp:' || p_user::text, 0));

      ent := mcp_meter.entitlement(p_user);
      IF p_session IS NOT NULL AND EXISTS (
           SELECT 1 FROM mcp_meter.connection_sessions s
             JOIN mcp_meter.connections c ON c.id = s.connection_id
            WHERE s.session_id = p_session AND c.user_id = p_user AND c.revoked_at IS NOT NULL) THEN
        verdict := 'disconnected';
      ELSIF ent IN ('none', 'trial', 'app_review') THEN
        verdict := 'not_entitled';
      ELSIF EXISTS (SELECT 1 FROM mcp_meter.suspensions s
                     WHERE s.user_id = p_user AND s.cleared_at IS NULL) THEN
        verdict := 'suspended';
      ELSIF NOT EXISTS (SELECT 1 FROM mcp_meter.terms_acceptances x
                         WHERE x.user_id = p_user AND x.terms_version = lim.terms_version) THEN
        verdict := 'terms_required';
      END IF;

      -- The same connection rule as begin_call: a new assistant past the cap is refused.
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

      IF verdict = 'ok' AND ent <> 'founder' THEN
        SELECT count(*) INTO n FROM mcp_meter.calls c
         WHERE c.user_id = p_user AND c.day_et = d AND c.outcome = 'profile' AND c.tool = v_tool;
        IF n >= (CASE WHEN p_action = 'save' THEN lim.profile_saves_per_day
                      ELSE lim.profile_reads_per_day END) THEN
          verdict := 'limit_reached';
        END IF;
      END IF;

      IF verdict = 'ok' AND p_action = 'save'
         AND (p_prefs IS NULL OR jsonb_typeof(p_prefs) <> 'object') THEN
        verdict := 'invalid_input';
      END IF;

      -- Logged either way. 'profile' is not 'ok', so no question is counted.
      INSERT INTO mcp_meter.calls (user_id, client_id, assistant, tool, params, called_at, day_et,
                                   question_no, rows_out, outcome, finished_at)
      VALUES (p_user, p_client, a, v_tool,
              CASE WHEN p_action = 'save' THEN jsonb_build_object('keys',
                     (SELECT coalesce(jsonb_agg(k ORDER BY k), '[]'::jsonb)
                        FROM jsonb_object_keys(CASE WHEN jsonb_typeof(p_prefs) = 'object'
                                                    THEN p_prefs ELSE '{}'::jsonb END) k))
                   ELSE '{}'::jsonb END,
              t, d, NULL, CASE WHEN verdict = 'ok' THEN 1 ELSE 0 END,
              CASE WHEN verdict = 'ok' THEN 'profile' ELSE verdict END, t);

      IF verdict <> 'ok' THEN
        RETURN jsonb_build_object('allowed', false, 'reason', verdict, 'entitlement', ent,
                                  'resets_at', mcp_meter.next_reset(t));
      END IF;

      UPDATE mcp_meter.connections SET last_used_at = t
       WHERE user_id = p_user AND client_id = cl AND revoked_at IS NULL;
      IF p_session IS NOT NULL THEN
        INSERT INTO mcp_meter.connection_sessions (connection_id, session_id, first_seen_at)
        SELECT c.id, p_session, t FROM mcp_meter.connections c
         WHERE c.user_id = p_user AND c.client_id = cl AND c.revoked_at IS NULL
        ON CONFLICT DO NOTHING;
      END IF;

      SELECT * INTO cur FROM mcp_meter.preference_saves s
       WHERE s.user_id = p_user ORDER BY s.saved_at DESC, s.id DESC LIMIT 1;

      IF p_action = 'save' THEN
        -- A save names only what changed; a key set to null clears it.
        merged := jsonb_strip_nulls(coalesce(cur.prefs, '{}'::jsonb) || p_prefs);
        IF length(merged::text) > 4000 THEN
          RETURN jsonb_build_object('allowed', false, 'reason', 'invalid_input', 'entitlement', ent,
                                    'resets_at', mcp_meter.next_reset(t));
        END IF;
        INSERT INTO mcp_meter.preference_saves (user_id, prefs, client_id, assistant, saved_at)
        VALUES (p_user, merged, p_client, a, t)
        RETURNING * INTO cur;
      END IF;

      RETURN jsonb_build_object(
        'allowed', true, 'reason', 'ok', 'entitlement', ent,
        'has_profile', cur.id IS NOT NULL,
        'preferences', coalesce(cur.prefs, '{}'::jsonb),
        'saved_at', cur.saved_at,
        'saved_from', cur.assistant);
    END
    $fn$
  $ddl$;

  -- Grants --------------------------------------------------------------------
  REVOKE ALL ON FUNCTION mcp_meter.record_client(uuid, text, text, jsonb, jsonb, timestamptz)
    FROM PUBLIC, anon, authenticated, mcp_reader;
  GRANT EXECUTE ON FUNCTION mcp_meter.record_client(uuid, text, text, jsonb, jsonb, timestamptz)
    TO mcp_meter_role;
  REVOKE ALL ON FUNCTION mcp_meter.profile_call(uuid, text, text, text, jsonb, timestamptz)
    FROM PUBLIC, anon, authenticated, mcp_reader;
  GRANT EXECUTE ON FUNCTION mcp_meter.profile_call(uuid, text, text, text, jsonb, timestamptz)
    TO mcp_meter_role;
END
$mcp$;
