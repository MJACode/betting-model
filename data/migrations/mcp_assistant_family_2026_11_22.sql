-- AI assistant (MCP): an assistant is named from EVERY redirect host its
-- sign-in registered, and the AI assistant terms move to 2026-11-22.
--
-- 1. Review L2 on #1583 (Matt: "Fix L2", 2026-11-22). mcp_meter.assistant_of
--    read only the FIRST redirect URI, so a client registered with
--    "https://claude.ai/cb,https://other.host/cb" counted as Claude and could
--    take Claude's place past the three-assistant cap. Now every host is
--    mapped to its family (claude / chatgpt / grok, else the host itself):
--      all hosts in one family  -> that family
--      they disagree            -> 'client:<client id>', an assistant of its own
--      no oauth_clients row     -> the client id, as before
--    Active connections are re-labelled with the new name (a derived label,
--    nothing deleted). mcp_my_status already resolves names through the same
--    column and coalesce, so it needs no change.
-- 2. Matt, 2026-11-22 ("Update the terms"): section 19 now says up to three
--    assistants sharing the daily limit, so limits.terms_version becomes
--    '2026-11-22'. Every member accepts once more on their next connect; the
--    consent page reads the current version from mcp_my_status, so the site
--    and the database cannot disagree while this file waits for a worker pass.
--
-- Runs while 'assistant_of v2' is missing from mcp_meter.assistant_of.

DO $mcp$
DECLARE
  hosts text;
  body  text;
BEGIN
  IF position('assistant_of v2' IN coalesce((SELECT prosrc FROM pg_proc
       WHERE oid = to_regprocedure('mcp_meter.assistant_of(text)')), '')) > 0 THEN
    RETURN;
  END IF;
  IF to_regprocedure('mcp_meter.assistant_of(text)') IS NULL THEN
    RAISE EXCEPTION 'mcp_assistant_family: apply mcp_multi_assistant_2026_11_22.sql first';
  END IF;

  IF to_regclass('auth.oauth_clients') IS NOT NULL THEN
    hosts := '(SELECT array_agg(DISTINCT lower(substring(btrim(u) FROM ''^[a-zA-Z]+://([^/:]+)'')))
                 FROM auth.oauth_clients o, unnest(string_to_array(o.redirect_uris, '','')) u
                WHERE o.id::text = p_client
                  AND substring(btrim(u) FROM ''^[a-zA-Z]+://([^/:]+)'') IS NOT NULL)';
  ELSE
    hosts := 'NULL::text[]';
  END IF;

  body := $fn$
    -- assistant_of v2 (mcp_assistant_family_2026_11_22.sql): every redirect host
    DECLARE
      hs  text[];
      fam text[];
    BEGIN
      IF p_client IS NULL OR p_client = '' THEN
        RETURN 'unknown';
      END IF;
      hs := @HOSTS@;
      IF hs IS NULL OR cardinality(hs) = 0 THEN
        RETURN left(p_client, 200);
      END IF;
      SELECT array_agg(DISTINCT CASE
               WHEN h IN ('claude.ai', 'claude.com') OR h LIKE '%.claude.ai' OR h LIKE '%.claude.com' THEN 'claude'
               WHEN h IN ('chatgpt.com', 'openai.com') OR h LIKE '%.chatgpt.com' OR h LIKE '%.openai.com' THEN 'chatgpt'
               WHEN h IN ('grok.com', 'x.ai') OR h LIKE '%.grok.com' OR h LIKE '%.x.ai' THEN 'grok'
               ELSE h END)
        INTO fam FROM unnest(hs) h;
      IF cardinality(fam) = 1 THEN
        RETURN left(fam[1], 200);
      END IF;
      RETURN left('client:' || p_client, 200);
    END
  $fn$;
  EXECUTE format($ddl$
    CREATE OR REPLACE FUNCTION mcp_meter.assistant_of(p_client text)
    RETURNS text
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
    AS %L
  $ddl$, replace(body, '@HOSTS@', hosts));
  REVOKE ALL ON FUNCTION mcp_meter.assistant_of(text) FROM PUBLIC, anon, authenticated, mcp_reader;
  GRANT EXECUTE ON FUNCTION mcp_meter.assistant_of(text) TO mcp_meter_role;

  -- Re-label active connections whose name changed under the new rule.
  UPDATE mcp_meter.connections c
     SET assistant = mcp_meter.assistant_of(c.client_id)
   WHERE c.revoked_at IS NULL
     AND c.assistant IS DISTINCT FROM mcp_meter.assistant_of(c.client_id);

  -- The terms members accept (web/content/terms.md section 19).
  UPDATE mcp_meter.limits
     SET terms_version = '2026-11-22', updated_at = now(), updated_by = 'matt'
   WHERE id = 1 AND terms_version = '2026-11-21';
END
$mcp$;
