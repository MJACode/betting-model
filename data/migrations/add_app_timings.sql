-- Migration: add_app_timings
-- Apply via Supabase MCP apply_migration (project ref vvprgnrmzeekokzkrkfu) or
-- the SQL editor. Not in ACTIVE_MIGRATIONS, the same as add_app_errors.sql.
-- Applied to production 2026-10-31. A fresh database needs this file by hand,
-- then data/migrations/app_timings_cap_2026_11_01.sql (also hand-applied).
-- The worker deletes rows older than 45 days; that does not need either file
-- re-applied. See docs/app_timings.md.
--
-- Load times measured on the phone (2026-10-31, Matt: "improve the performance
-- of the app" — measure first). pg_stat_statements says how long a query ran on
-- the server; only the phone sees network time and how long a screen waited.
-- Each row is one of:
--
--   request  one Supabase call: name = view/table, or rpc:<fn>; ms = network +
--            server; status = HTTP status, 0 = no response
--   screen   navigation to a screen -> every request it started has finished
--            (request_count of them)
--   launch   JS start -> the first screen loaded
--
-- Same trust model as app_errors: RLS on, no policies, no anon grants on the
-- table. The only way in is log_app_timings(), insert-only, returns nothing.

CREATE TABLE IF NOT EXISTS app_timings (
    id               BIGSERIAL PRIMARY KEY,
    received_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    occurred_at      TIMESTAMPTZ,          -- device clock; may be skewed
    device_id        TEXT NOT NULL,
    kind             TEXT NOT NULL CHECK (kind IN ('request', 'screen', 'launch')),
    name             TEXT NOT NULL,
    ms               INTEGER NOT NULL,
    status           INTEGER,
    screen           TEXT,
    request_count    INTEGER,
    since_launch_ms  INTEGER,
    app_version      TEXT,
    update_id        TEXT,
    platform         TEXT
);

CREATE INDEX IF NOT EXISTS idx_app_timings_received ON app_timings (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_timings_kind_name ON app_timings (kind, name, received_at DESC);
-- The per-device hourly cap in log_app_timings filters these two columns.
CREATE INDEX IF NOT EXISTS idx_app_timings_device_received
    ON app_timings (device_id, received_at DESC);

ALTER TABLE app_timings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE app_timings FROM anon, authenticated;
REVOKE ALL ON SEQUENCE app_timings_id_seq FROM anon, authenticated;

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
BEGIN
    IF p_device_id IS NULL OR length(btrim(p_device_id)) < 8 OR length(p_device_id) > 64 THEN
        RAISE EXCEPTION 'invalid device';
    END IF;
    IF p_rows IS NULL OR jsonb_typeof(p_rows) <> 'array' THEN
        RAISE EXCEPTION 'invalid rows';
    END IF;

    -- Nothing here is authenticated, so bound what one install can write. The
    -- app sends at most 100 rows a call; a live board polling every 30 s makes
    -- a few hundred an hour. Past the cap, rows are dropped silently.
    SELECT count(*) INTO v_recent
      FROM app_timings
     WHERE device_id = p_device_id
       AND received_at > now() - interval '1 hour';
    IF v_recent >= 1000 THEN
        RETURN;
    END IF;

    INSERT INTO app_timings (
        occurred_at, device_id, kind, name, ms, status, screen, request_count,
        since_launch_ms, app_version, update_id, platform
    )
    SELECT r.occurred_at, p_device_id, r.kind, left(r.name, 100),
           greatest(0, least(r.ms, 600000)), r.status, left(r.screen, 100),
           r.request_count, r.since_launch_ms,
           left(p_app_version, 40), left(p_update_id, 64), left(p_platform, 40)
      FROM (
        SELECT * FROM jsonb_to_recordset(p_rows) AS x(
            kind TEXT, name TEXT, ms INTEGER, status INTEGER, screen TEXT,
            request_count INTEGER, since_launch_ms INTEGER, occurred_at TIMESTAMPTZ)
        LIMIT 100
      ) r
     WHERE r.kind IN ('request', 'screen', 'launch')
       AND r.name IS NOT NULL
       AND r.ms IS NOT NULL;
END;
$$;

REVOKE ALL ON FUNCTION public.log_app_timings(TEXT, JSONB, TEXT, TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.log_app_timings(TEXT, JSONB, TEXT, TEXT, TEXT) TO anon, authenticated;
