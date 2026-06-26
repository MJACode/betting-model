-- Migration: add_push_notifications
-- Apply via Supabase MCP apply_migration (project ref vvprgnrmzeekokzkrkfu) or
-- the SQL editor. Mirrors the blocks in supabase_schema.sql + db_setup.py.
--
-- Signal-flip push notifications:
--   device_push_tokens — one row per device that opted in to notifications. The
--     mobile app upserts its Expo push token (anon INSERT/UPDATE; no SELECT so
--     tokens can't be enumerated). The pipeline reads via service-role.
--   push_sent — ledger of which (lock_key, kind) we've already pushed, so a
--     signal is never notified twice across hourly runs.

CREATE TABLE IF NOT EXISTS device_push_tokens (
    token       TEXT PRIMARY KEY,           -- ExponentPushToken[...]
    platform    TEXT,                        -- 'ios' | 'android'
    enabled     BOOLEAN DEFAULT TRUE,
    created_at  TEXT DEFAULT (NOW()::TEXT),
    last_seen   TEXT DEFAULT (NOW()::TEXT)
);

CREATE TABLE IF NOT EXISTS push_sent (
    id        BIGSERIAL PRIMARY KEY,
    lock_key  TEXT NOT NULL,
    kind      TEXT NOT NULL,                 -- 'new_bet' | 'dropped'
    sent_at   TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(lock_key, kind)
);

CREATE INDEX IF NOT EXISTS idx_push_sent_kind ON push_sent(kind);

ALTER TABLE device_push_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_sent ENABLE ROW LEVEL SECURITY;

-- The app registers/updates its own token with the anon key. No SELECT policy:
-- anon can write a token but never read the token table (privacy). The pipeline
-- writes push_sent + reads tokens via service-role DATABASE_URL (bypasses RLS).
CREATE POLICY "anon insert device token" ON device_push_tokens
    FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY "anon update device token" ON device_push_tokens
    FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);
