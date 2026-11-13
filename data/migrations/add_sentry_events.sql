-- Migration: add_sentry_events. Hand-applied. NOT in ACTIVE_MIGRATIONS.
--
-- Matt, 2026-11-06: Sentry in the mobile app, and everything in Supabase
-- (CLAUDE.md §1b). data/ingestors/sentry_events.py copies every Sentry event
-- (native crashes, iOS app hangs, JS errors) here, keyed on Sentry's event id,
-- so Sentry is a second copy and this table is the system of record.
--
-- Join to app_errors on device_id (both carry the app's anonymous device id).
-- Same trust model as app_errors: RLS on, no policies, no anon or
-- authenticated grants. Only the worker (service connection) writes or reads.

CREATE TABLE IF NOT EXISTS sentry_events (
    event_id     TEXT PRIMARY KEY,           -- Sentry eventID
    issue_id     TEXT,                       -- Sentry groupID (the issue)
    received_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    occurred_at  TIMESTAMPTZ,                -- Sentry dateCreated
    event_type   TEXT,                       -- Sentry "event.type"
    level        TEXT,                       -- tag: fatal | error | warning ...
    title        TEXT,
    message      TEXT,
    culprit      TEXT,
    platform     TEXT,
    device_id    TEXT,                       -- tag set by mobile/src/lib/sentry.ts
    screen       TEXT,                       -- tag set on every navigation
    release      TEXT,
    environment  TEXT,
    update_id    TEXT,                       -- running OTA bundle
    raw          JSONB NOT NULL              -- the whole event as Sentry returned it
);

CREATE INDEX IF NOT EXISTS idx_sentry_events_occurred ON sentry_events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_sentry_events_device ON sentry_events (device_id, occurred_at DESC);

ALTER TABLE sentry_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE sentry_events FROM anon, authenticated;
