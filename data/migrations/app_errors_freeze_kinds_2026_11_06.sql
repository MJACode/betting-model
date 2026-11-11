-- Freeze tracking report kinds for app_errors. Hand-applied. NOT in
-- ACTIVE_MIGRATIONS. Apply after add_app_errors.sql; do not re-apply that
-- older file after this one (it would put back the five-kind list).
--
-- 2026-11-06, Matt: a screen stopped responding and needed a restart, "in
-- other spots" too, and app_errors held nothing: a freeze throws no error.
-- mobile/src/lib/freezeLog.ts adds three kinds:
--
--   restart      the previous session ended on screen or in the app switcher
--                without going to background, or the app was relaunched
--                within 2 minutes of going to background. What a member does
--                when the screen will not respond.
--   js_stall     the JS thread stopped for 5s or more while on screen.
--   modal_stuck  a pop-up was opened or closed and iOS never confirmed it
--                (onShow / onDismiss) within 4s.
--
-- Every report now carries extra.trail (the last 40 screens, taps, pop-ups
-- and app-state changes), so the extra cap goes from 4,000 to 16,000 chars.
-- Idempotent. Drops and re-adds only the kind CHECK; deletes no rows.

DO $$
DECLARE c TEXT;
BEGIN
    FOR c IN
        SELECT conname FROM pg_constraint
         WHERE conrelid = 'public.app_errors'::regclass AND contype = 'c'
           AND pg_get_constraintdef(oid) LIKE '%kind%'
    LOOP
        EXECUTE format('ALTER TABLE public.app_errors DROP CONSTRAINT %I', c);
    END LOOP;
END $$;

ALTER TABLE public.app_errors ADD CONSTRAINT app_errors_kind_check CHECK (kind IN
    ('js_fatal', 'js_error', 'render', 'early_exit', 'emergency_launch',
     'restart', 'js_stall', 'modal_stuck'));

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
    IF p_kind NOT IN ('js_fatal', 'js_error', 'render', 'early_exit', 'emergency_launch',
                      'restart', 'js_stall', 'modal_stuck') THEN
        RAISE EXCEPTION 'invalid kind';
    END IF;
    IF p_extra IS NOT NULL AND length(p_extra::text) > 16000 THEN
        p_extra := NULL;
    END IF;

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
REVOKE ALL ON FUNCTION public.log_app_error(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, JSONB
) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.log_app_error(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, JSONB
) TO anon, authenticated;
