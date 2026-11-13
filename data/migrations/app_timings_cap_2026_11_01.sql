-- Tighten log_app_timings. Hand-applied. NOT in ACTIVE_MIGRATIONS.
--
-- Production already has app_timings and log_app_timings
-- (add_app_timings.sql, applied 2026-10-31). Apply this file by hand after
-- that one. Do not re-apply the older file after this one: it replaces the
-- function. Idempotent: ADD COLUMN IF NOT EXISTS, CREATE INDEX IF NOT EXISTS,
-- CREATE OR REPLACE. It does not DROP the table or the function. It does not
-- delete rows.
--
-- The 1,000-rows/hour cap used to key only on p_device_id, which the client
-- chooses, so an anonymous caller could rotate it and write without bound.
-- A signed-in caller is now capped on auth.uid() (stored as user_id) and
-- rotating p_device_id does not open a new budget. An anonymous caller still
-- has only the device id — there is no server-side identity on the anon key
-- — and that hole stays. The table does not grow without a bound either way:
-- the daily pipeline deletes rows older than 45 days
-- (data/app_timings_retention.py). This file does not delete.
--
-- The count and the insert take an advisory lock, and one call inserts at
-- most the room left under 1,000, so one caller cannot land ~1,099 rows.
-- ms, status, request_count and since_launch_ms are read as text and clamped.
-- A value that does not fit in INTEGER used to abort the whole call.
--
-- One script, no CONCURRENTLY. The worker must not run this on every pass:
-- CREATE INDEX and ALTER TABLE reload PostgREST's schema cache.

ALTER TABLE app_timings ADD COLUMN IF NOT EXISTS user_id UUID;

CREATE INDEX IF NOT EXISTS idx_app_timings_user_received
    ON app_timings (user_id, received_at DESC)
    WHERE user_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.log_app_timings(
    p_device_id    TEXT,
    p_rows         JSONB,
    p_app_version  TEXT DEFAULT NULL,
    p_update_id    TEXT DEFAULT NULL,
    p_platform     TEXT DEFAULT NULL
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_recent INT;
    v_uid UUID;
    v_room INT;
BEGIN
    IF p_device_id IS NULL OR length(btrim(p_device_id)) < 8 OR length(p_device_id) > 64 THEN
        RAISE EXCEPTION 'invalid device';
    END IF;
    IF p_rows IS NULL OR jsonb_typeof(p_rows) <> 'array' THEN
        RAISE EXCEPTION 'invalid rows';
    END IF;

    -- Qualified: search_path above does not include auth. NULL when the
    -- caller is the anon key with no user JWT.
    v_uid := auth.uid();

    -- Serialize this caller's cap. Two overlapping calls used to both read a
    -- count under 1,000 and both insert.
    IF v_uid IS NOT NULL THEN
        PERFORM pg_advisory_xact_lock(hashtextextended('app_timings:user:' || v_uid::text, 0));
        SELECT count(*) INTO v_recent
          FROM app_timings
         WHERE user_id = v_uid
           AND received_at > now() - interval '1 hour';
    ELSE
        PERFORM pg_advisory_xact_lock(hashtextextended('app_timings:device:' || p_device_id, 0));
        SELECT count(*) INTO v_recent
          FROM app_timings
         WHERE device_id = p_device_id
           AND received_at > now() - interval '1 hour';
    END IF;
    IF v_recent >= 1000 THEN
        RETURN;
    END IF;
    v_room := least(100, 1000 - v_recent);

    INSERT INTO app_timings (
        occurred_at, device_id, user_id, kind, name, ms, status, screen,
        request_count, since_launch_ms, app_version, update_id, platform
    )
    SELECT
        CASE
            WHEN r.occurred_at IS NULL OR btrim(r.occurred_at) = '' THEN NULL
            WHEN r.occurred_at ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})?$'
                THEN r.occurred_at::timestamptz
            ELSE NULL
        END,
        p_device_id,
        v_uid,
        r.kind,
        left(r.name, 100),
        greatest(0, least(r.ms_n, 600000))::int,
        CASE WHEN r.status_n IS NULL THEN NULL
             ELSE greatest(0, least(r.status_n, 599))::int END,
        left(r.screen, 100),
        CASE WHEN r.req_n IS NULL THEN NULL
             ELSE greatest(0, least(r.req_n, 100000))::int END,
        CASE WHEN r.since_n IS NULL THEN NULL
             ELSE greatest(0, least(r.since_n, 2147483647))::int END,
        left(p_app_version, 40),
        left(p_update_id, 64),
        left(p_platform, 40)
      FROM (
        SELECT
            elem->>'kind' AS kind,
            elem->>'name' AS name,
            elem->>'screen' AS screen,
            elem->>'occurred_at' AS occurred_at,
            CASE WHEN elem->>'ms' ~ '^-?[0-9]{1,18}$' THEN (elem->>'ms')::bigint END AS ms_n,
            CASE WHEN elem->>'status' ~ '^-?[0-9]{1,18}$' THEN (elem->>'status')::bigint END AS status_n,
            CASE WHEN elem->>'request_count' ~ '^-?[0-9]{1,18}$' THEN (elem->>'request_count')::bigint END AS req_n,
            CASE WHEN elem->>'since_launch_ms' ~ '^-?[0-9]{1,18}$' THEN (elem->>'since_launch_ms')::bigint END AS since_n
          FROM jsonb_array_elements(p_rows) AS elem
         LIMIT v_room
      ) r
     WHERE r.kind IN ('request', 'screen', 'launch')
       AND r.name IS NOT NULL
       AND r.ms_n IS NOT NULL;
END;
$$;

REVOKE ALL ON FUNCTION public.log_app_timings(TEXT, JSONB, TEXT, TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.log_app_timings(TEXT, JSONB, TEXT, TEXT, TEXT) TO anon, authenticated;
