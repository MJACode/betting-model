-- AI assistant (MCP): Disconnect really disconnects.
--
-- The foundation's mcp_disconnect() sets revoked_at on the member's active
-- connection, which frees the one-app slot. But the app's OAuth tokens stay
-- valid, so its next question would simply open a NEW connection: the member
-- taps Disconnect and the assistant keeps working.
--
-- Fix, in the meter (the one place every call passes):
--   mcp_meter.connection_sessions  each Supabase Auth session (one per
--                                  approval; a refresh keeps it) seen on a
--                                  connection. Kept forever, like the rest.
--   mcp_meter.begin_call_session   what the connector calls now. A session
--                                  that belonged to a disconnected connection
--                                  is refused as 'disconnected' (and logged);
--                                  otherwise it runs begin_call and records
--                                  the session on the active connection.
-- Reconnecting means approving again in the assistant, which makes a new
-- session. A token with no session_id claim (NULL) is metered as before.
--
-- Runs only while mcp_meter.begin_call_session does not exist.

DO $mcp$
BEGIN
  IF to_regprocedure('mcp_meter.begin_call_session(uuid,text,text,text,jsonb,timestamptz)') IS NOT NULL THEN
    RETURN;
  END IF;
  IF to_regprocedure('mcp_meter.begin_call(uuid,text,text,jsonb,timestamptz)') IS NULL THEN
    RAISE EXCEPTION 'mcp_session_revoke: apply mcp_foundation_2026_11_21.sql first';
  END IF;

  CREATE TABLE IF NOT EXISTS mcp_meter.connection_sessions (
    connection_id bigint NOT NULL REFERENCES mcp_meter.connections(id) ON DELETE CASCADE,
    session_id    text NOT NULL,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (connection_id, session_id)
  );
  CREATE INDEX IF NOT EXISTS mcp_connection_sessions_session
      ON mcp_meter.connection_sessions (session_id);
  ALTER TABLE mcp_meter.connection_sessions ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON mcp_meter.connection_sessions FROM PUBLIC, anon, authenticated, mcp_reader, mcp_meter_role;

  EXECUTE $ddl$
    CREATE OR REPLACE FUNCTION mcp_meter.begin_call_session(
        p_user uuid, p_client text, p_session text, p_tool text, p_params jsonb,
        p_at timestamptz DEFAULT NULL)
    RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
    AS $fn$
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
        INSERT INTO mcp_meter.calls (user_id, client_id, tool, params, called_at, day_et, outcome)
        VALUES (p_user, p_client, left(coalesce(p_tool, ''), 64), coalesce(p_params, '{}'::jsonb),
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
         WHERE c.user_id = p_user AND c.revoked_at IS NULL
        ON CONFLICT DO NOTHING;
      END IF;
      RETURN g;
    END
    $fn$
  $ddl$;

  REVOKE ALL ON FUNCTION mcp_meter.begin_call_session(uuid, text, text, text, jsonb, timestamptz)
    FROM PUBLIC, anon, authenticated, mcp_reader;
  GRANT EXECUTE ON FUNCTION mcp_meter.begin_call_session(uuid, text, text, text, jsonb, timestamptz)
    TO mcp_meter_role;
END
$mcp$;
