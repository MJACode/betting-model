-- Pipeline run ledger. One row per pipeline invocation (daily run or refresh
-- pass), written by tracking/run_ledger.py. Exists because until 2026-08-27
-- NOTHING recorded that a pass had run: a NameError killed every hourly pass
-- at step 9 of 24 for three days and left no trace except missing side-effects,
-- while the once-a-day health check stayed green. A pass that starts and never
-- finishes leaves finished_at NULL, so a hang or a killed worker is detectable
-- too. Read by the refresh_pass_completion / refresh_pass_steps health checks.
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id       TEXT PRIMARY KEY,
    run_kind     TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    steps_total  INTEGER,
    steps_failed INTEGER,
    failed_steps TEXT,
    ok           BOOLEAN
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_kind ON pipeline_runs(run_kind, started_at);

ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON pipeline_runs FROM anon, authenticated;
