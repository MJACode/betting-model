-- add_api_call_log — the real-time monitor's traffic table (monitoring/).
--
-- NOT REQUIRED TO APPLY BY HAND. monitoring/store.ensure_table() runs this same
-- DDL on the first flush of every process, exactly like tracking/run_ledger.py,
-- because the Supabase MCP is read-only and setup_database() only runs at
-- first-time setup. This file exists so the schema is recoverable and reviewable
-- rather than living only inside a Python string.
--
-- Applying it early just means the first dashboard load has a table to read.

CREATE TABLE IF NOT EXISTS api_call_log (
    call_id         BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL,
    api             TEXT NOT NULL,
    host            TEXT NOT NULL,
    category        TEXT NOT NULL,
    method          TEXT NOT NULL,
    path            TEXT NOT NULL,
    sport           TEXT,
    status          INTEGER,
    ok              BOOLEAN NOT NULL,
    duration_ms     INTEGER NOT NULL,
    resp_bytes      INTEGER,
    credits         NUMERIC,
    quota_remaining NUMERIC,
    error           TEXT,
    source          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_api_call_ts     ON api_call_log(ts);
CREATE INDEX IF NOT EXISTS idx_api_call_api_ts ON api_call_log(api, ts);

-- RLS on with NO policy is the intended state: the pipeline writes as the table
-- owner via DATABASE_URL and bypasses RLS, and nothing in the mobile app reads
-- this table. REVOKE names anon/authenticated rather than PUBLIC — Supabase's
-- default privileges grant them BY NAME, so a PUBLIC-only revoke is a no-op
-- (the feedback_reply lesson, session 126c).
ALTER TABLE api_call_log ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON api_call_log FROM anon, authenticated;
REVOKE ALL ON SEQUENCE api_call_log_call_id_seq FROM anon, authenticated;
