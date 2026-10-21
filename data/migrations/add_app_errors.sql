-- Migration: add_app_errors
-- Apply via Supabase MCP apply_migration (project ref vvprgnrmzeekokzkrkfu) or
-- the SQL editor. Mirrored in supabase_schema.sql.
--
-- Crash and error reports from the mobile app (2026-10-19, Matt: "Set up crash
-- logging"). The app had no crash reporting at all, so "it crashes now and then
-- on first open" could not be traced to anything. Each row is one report:
--
--   js_fatal       an uncaught JS error that is about to close the app
--   js_error       an uncaught JS error the runtime survived
--   render         a screen threw while rendering; the error boundary caught it
--   early_exit     the PREVIOUS launch never reached "up for 15s". Covers a
--                  native crash JS cannot see, AND a user closing the app inside
--                  15s, AND the restart an OTA reload does. `stage` and
--                  `extra.gap_ms` (marker to next launch) separate them: an OTA
--                  reload that worked comes back in about a second; a crash the
--                  user reopened takes as long as it took them to tap the icon.
--   emergency_launch  expo-updates rolled back to the built-in bundle because
--                  the downloaded one crashed (Updates.isEmergencyLaunch).
--
-- Same trust model as feedback_threads: RLS on, no policies, no anon grants on
-- the table. The only way in is log_app_error(), insert-only, so the anon key
-- can write a report and cannot read anyone's.

CREATE TABLE IF NOT EXISTS app_errors (
    id                BIGSERIAL PRIMARY KEY,
    received_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    occurred_at       TIMESTAMPTZ,          -- device clock; may be skewed
    device_id         TEXT NOT NULL,
    kind              TEXT NOT NULL CHECK (kind IN
                        ('js_fatal', 'js_error', 'render', 'early_exit', 'emergency_launch')),
    message           TEXT,
    stack             TEXT,
    component_stack   TEXT,
    screen            TEXT,                 -- focused route when it happened
    stage             TEXT,                 -- startup stage: launching | ota_reload | running
    app_version       TEXT,                 -- native binary (app.json version)
    update_id         TEXT,                 -- running OTA bundle, NULL = built-in bundle
    update_created_at TEXT,                 -- when that bundle was published
    platform          TEXT,
    extra             JSONB
);

CREATE INDEX IF NOT EXISTS idx_app_errors_received ON app_errors(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_errors_kind ON app_errors(kind, received_at DESC);
-- The 60/hour cap in log_app_error filters (device_id, received_at). This
-- file is not in ACTIVE_MIGRATIONS and is not re-applied by this change.
CREATE INDEX IF NOT EXISTS idx_app_errors_device_received
    ON app_errors (device_id, received_at DESC);

ALTER TABLE app_errors ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE app_errors FROM anon, authenticated;
REVOKE ALL ON SEQUENCE app_errors_id_seq FROM anon, authenticated;

CREATE OR REPLACE FUNCTION public.log_app_error(
    p_device_id         TEXT,
    p_kind              TEXT,
    p_message           TEXT        DEFAULT NULL,
    p_stack             TEXT        DEFAULT NULL,
    p_component_stack   TEXT        DEFAULT NULL,
    p_screen            TEXT        DEFAULT NULL,
    p_stage             TEXT        DEFAULT NULL,
    p_app_version       TEXT        DEFAULT NULL,
    p_update_id         TEXT        DEFAULT NULL,
    p_update_created_at TEXT        DEFAULT NULL,
    p_platform          TEXT        DEFAULT NULL,
    p_occurred_at       TIMESTAMPTZ DEFAULT NULL,
    p_extra             JSONB       DEFAULT NULL
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_recent INT;
BEGIN
    IF p_device_id IS NULL OR length(btrim(p_device_id)) < 8 OR length(p_device_id) > 64 THEN
        RAISE EXCEPTION 'invalid device';
    END IF;
    IF p_kind NOT IN ('js_fatal', 'js_error', 'render', 'early_exit', 'emergency_launch') THEN
        RAISE EXCEPTION 'invalid kind';
    END IF;
    IF p_extra IS NOT NULL AND length(p_extra::text) > 4000 THEN
        p_extra := NULL;
    END IF;

    -- Nothing here is authenticated, so bound what one install can write. A
    -- crash loop past this cap drops reports silently rather than erroring:
    -- the first 60 in an hour already say what the loop is.
    SELECT count(*) INTO v_recent
      FROM app_errors
     WHERE device_id = p_device_id
       AND received_at > now() - interval '1 hour';
    IF v_recent >= 60 THEN
        RETURN;
    END IF;

    INSERT INTO app_errors (
        occurred_at, device_id, kind, message, stack, component_stack, screen,
        stage, app_version, update_id, update_created_at, platform, extra
    ) VALUES (
        p_occurred_at, p_device_id, p_kind,
        left(p_message, 2000), left(p_stack, 8000), left(p_component_stack, 4000),
        left(p_screen, 100), left(p_stage, 40), left(p_app_version, 40),
        left(p_update_id, 64), left(p_update_created_at, 40), left(p_platform, 40),
        p_extra
    );
END;
$$;

REVOKE ALL ON FUNCTION public.log_app_error(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, JSONB
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.log_app_error(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, JSONB
) TO anon, authenticated;
