-- Daily system health check results (tracking/system_health.py).
-- One row per (run_date, check_name); the daily pipeline's final step upserts.
-- Anon SELECT so Claude mobile / the app can surface today's system status.
-- Applied to Supabase 2026-07-04 via migration add_system_health_checks.

CREATE TABLE IF NOT EXISTS system_health_checks (
    id          BIGSERIAL PRIMARY KEY,
    run_date    TEXT NOT NULL,
    check_name  TEXT NOT NULL,
    status      TEXT NOT NULL,          -- OK | STALE | EMPTY | SKIPPED | ERROR
    severity    TEXT NOT NULL,          -- CRIT | WARN
    detail      TEXT,
    latest_seen TEXT,
    checked_at  TEXT NOT NULL,
    UNIQUE(run_date, check_name)
);
CREATE INDEX IF NOT EXISTS idx_health_run_date ON system_health_checks(run_date);
ALTER TABLE system_health_checks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon read system_health_checks" ON system_health_checks
    FOR SELECT TO anon, authenticated USING (true);
