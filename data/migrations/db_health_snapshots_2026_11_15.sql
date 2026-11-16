-- Database health over time: what the ops dashboard's Database tab reads.
-- mike, 2026-11-15: "I want to add a section on database health, size and
-- any other metrics you think are cool and change over time. both locals
-- and supabase".
--
-- WHAT IT BUILDS. Four tables, written only by tracking/db_health.py (the
-- worker job db_health_snapshot, hourly). Rows are only ever added: nothing
-- updates or deletes one (CLAUDE.md section 1b, NO DATA IS EVER DELETED).
--
--   db_health_snapshots  one row per run: the database's size, row
--       estimates, client connections, and Postgres's own running counters
--       (cache reads, commits, rollbacks, temp files, statement time)
--       exactly as Postgres reports them, i.e. totals since their last
--       reset. The rate is the change between two rows. A counter that went
--       DOWN was reset in between, and the dashboard shows nothing for that
--       gap rather than a negative rate.
--   db_table_snapshots   every table's size and row estimate. Taken on the
--       first run of each six-hour block (table_rows_taken marks the run).
--   db_query_snapshots   the statements that have used the most database
--       time (pg_stat_statements), with their running totals, on the same
--       six-hour runs.
--   db_query_texts       each statement's normalised text, once per queryid,
--       so a 2 KB statement is not stored again on every run.
--
-- Row counts are pg_stat_user_tables.n_live_tup: Postgres's own estimate,
-- refreshed by autovacuum and ANALYZE. Nothing here runs count(*).
--
-- Neither the mobile app nor its users read these: anon and authenticated
-- get nothing, and row level security is on with no policy. The dashboard
-- reads them as the database owner through its own Retool connection.
--
-- One DO block: data/view_migrations.py runs each file as one statement on
-- every pass. It returns on a catalog read once db_health_snapshots carries
-- this file's marker (the hash of this file with the marker blanked) and
-- the two app roles still have nothing, so an edit here is applied on the
-- next pass and a re-grant is undone.

DO $mig$
BEGIN
  IF COALESCE(obj_description(to_regclass('public.db_health_snapshots'), 'pg_class'), '')
       = 'db_health_snapshots 0e8c3b995b8d'
     AND to_regclass('public.db_table_snapshots') IS NOT NULL
     AND to_regclass('public.db_query_snapshots') IS NOT NULL
     AND to_regclass('public.db_query_texts') IS NOT NULL
     AND NOT has_table_privilege('anon', 'public.db_health_snapshots', 'SELECT')
     AND NOT has_table_privilege('authenticated', 'public.db_health_snapshots', 'SELECT')
     AND NOT has_table_privilege('anon', 'public.db_table_snapshots', 'SELECT')
     AND NOT has_table_privilege('authenticated', 'public.db_table_snapshots', 'SELECT')
     AND NOT has_table_privilege('anon', 'public.db_query_snapshots', 'SELECT')
     AND NOT has_table_privilege('authenticated', 'public.db_query_snapshots', 'SELECT')
     AND NOT has_table_privilege('anon', 'public.db_query_texts', 'SELECT')
     AND NOT has_table_privilege('authenticated', 'public.db_query_texts', 'SELECT')
  THEN
    RETURN;
  END IF;

  -- 1. one row per run
  CREATE TABLE IF NOT EXISTS public.db_health_snapshots (
    snapshot_id            BIGSERIAL PRIMARY KEY,
    taken_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source                 TEXT NOT NULL,
    duration_ms            INTEGER,
    -- size, bytes
    db_bytes               BIGINT NOT NULL,
    table_bytes            BIGINT,
    index_bytes            BIGINT,
    toast_bytes            BIGINT,
    relations              INTEGER,
    -- rows, Postgres's estimates
    live_rows_est          BIGINT,
    dead_rows_est          BIGINT,
    -- client connections at the moment of the run
    connections            INTEGER,
    connections_active     INTEGER,
    connections_idle       INTEGER,
    connections_idle_in_tx INTEGER,
    max_connections        INTEGER,
    longest_xact_s         DOUBLE PRECISION,
    waiting_locks          INTEGER,
    xid_age                BIGINT,
    freeze_max_age         BIGINT,
    -- pg_stat_database running totals, since stats_reset
    blks_hit               BIGINT,
    blks_read              BIGINT,
    xact_commit            BIGINT,
    xact_rollback          BIGINT,
    tup_inserted           BIGINT,
    tup_updated            BIGINT,
    tup_deleted            BIGINT,
    temp_files             BIGINT,
    temp_bytes             BIGINT,
    deadlocks              BIGINT,
    stats_reset            TIMESTAMPTZ,
    -- pg_stat_database session time, ms, since stats_reset: the change in
    -- active_time over the wall time between two rows is the average number
    -- of statements running at once
    active_time_ms         DOUBLE PRECISION,
    idle_in_tx_time_ms     DOUBLE PRECISION,
    session_time_ms        DOUBLE PRECISION,
    sessions               BIGINT,
    sessions_abandoned     BIGINT,
    sessions_fatal         BIGINT,
    sessions_killed        BIGINT,
    -- pg_stat_statements totals, since stmt_reset. NOT a running counter:
    -- Postgres drops the least-used statements when its list is full
    -- (stmt_dealloc counts those passes), and their time leaves the sum.
    stmt_count             INTEGER,
    stmt_calls             BIGINT,
    stmt_exec_ms           DOUBLE PRECISION,
    stmt_reset             TIMESTAMPTZ,
    stmt_dealloc           BIGINT,
    -- indexes never scanned since stats_reset (unique and primary keys left out)
    unused_indexes         INTEGER,
    unused_index_bytes     BIGINT,
    -- Supabase Storage
    storage_objects        BIGINT,
    storage_bytes          BIGINT,
    storage_buckets        JSONB,
    table_rows_taken       BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT db_health_snapshots_source CHECK (source IN ('worker', 'manual'))
  );

  -- 2. every table, every six hours
  CREATE TABLE IF NOT EXISTS public.db_table_snapshots (
    snapshot_id    BIGINT NOT NULL REFERENCES public.db_health_snapshots (snapshot_id),
    taken_at       TIMESTAMPTZ NOT NULL,
    schema_name    TEXT NOT NULL,
    table_name     TEXT NOT NULL,
    kind           TEXT NOT NULL,
    total_bytes    BIGINT NOT NULL,
    heap_bytes     BIGINT,
    index_bytes    BIGINT,
    toast_bytes    BIGINT,
    live_rows_est  BIGINT,
    dead_rows_est  BIGINT,
    n_tup_ins      BIGINT,
    n_tup_upd      BIGINT,
    n_tup_del      BIGINT,
    seq_scan       BIGINT,
    idx_scan       BIGINT,
    last_vacuum    TIMESTAMPTZ,
    last_analyze   TIMESTAMPTZ,
    PRIMARY KEY (snapshot_id, schema_name, table_name),
    CONSTRAINT db_table_snapshots_kind CHECK (kind IN ('table', 'matview'))
  );

  -- 3. the heaviest statements, every six hours
  CREATE TABLE IF NOT EXISTS public.db_query_snapshots (
    snapshot_id        BIGINT NOT NULL REFERENCES public.db_health_snapshots (snapshot_id),
    taken_at           TIMESTAMPTZ NOT NULL,
    queryid            BIGINT NOT NULL,
    role_name          TEXT NOT NULL,
    toplevel           BOOLEAN NOT NULL,
    calls              BIGINT,
    total_exec_ms      DOUBLE PRECISION,
    mean_exec_ms       DOUBLE PRECISION,
    max_exec_ms        DOUBLE PRECISION,
    rows               BIGINT,
    shared_blks_hit    BIGINT,
    shared_blks_read   BIGINT,
    temp_blks_written  BIGINT,
    PRIMARY KEY (snapshot_id, queryid, role_name, toplevel)
  );

  -- 4. each statement's text, once
  CREATE TABLE IF NOT EXISTS public.db_query_texts (
    queryid     BIGINT PRIMARY KEY,
    query       TEXT NOT NULL,
    first_seen  TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );

  -- The first version of this file (applied 2026-11-16 03:40 UTC) created the
  -- table without these; a database that already has them skips each one.
  ALTER TABLE public.db_health_snapshots
    ADD COLUMN IF NOT EXISTS active_time_ms DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS idle_in_tx_time_ms DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS session_time_ms DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS sessions BIGINT,
    ADD COLUMN IF NOT EXISTS sessions_abandoned BIGINT,
    ADD COLUMN IF NOT EXISTS sessions_fatal BIGINT,
    ADD COLUMN IF NOT EXISTS sessions_killed BIGINT,
    ADD COLUMN IF NOT EXISTS stmt_dealloc BIGINT;

  ALTER TABLE public.db_health_snapshots ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.db_table_snapshots ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.db_query_snapshots ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.db_query_texts ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.db_health_snapshots FROM anon, authenticated;
  REVOKE ALL ON public.db_table_snapshots FROM anon, authenticated;
  REVOKE ALL ON public.db_query_snapshots FROM anon, authenticated;
  REVOKE ALL ON public.db_query_texts FROM anon, authenticated;
  REVOKE ALL ON SEQUENCE public.db_health_snapshots_snapshot_id_seq FROM anon, authenticated;

  COMMENT ON TABLE public.db_health_snapshots IS 'db_health_snapshots 0e8c3b995b8d';
END $mig$;
