-- The copy on mike's PC over time: what the ops dashboard's PC copy section
-- reads. mike, 2026-11-16 (in a question dialog, relayed): "locals" is the
-- copy on his PC (Documents\betting_local_copies), and he wants the last
-- nightly copy's time and duration, the tables that do not match Supabase,
-- each copy's size over time and the free disk, from one row the nightly
-- copy writes when it ends.
--
-- WHAT IT BUILDS. One table, written only by scripts/local_mirror_report.py:
-- last in each pass of the PC's LocalMirror task (source 'nightly'), or by
-- hand (source 'manual'). One row per report. Rows are only ever added:
-- nothing updates or deletes one (CLAUDE.md section 1b, NO DATA IS EVER
-- DELETED), and a pass reported twice keeps its first row (the unique key on
-- source and pass_id, with ON CONFLICT DO NOTHING in the writer).
--
-- Every number is read on the PC, from the copy's own files: the Supabase
-- copy's last finished run (supabase_mirror\STATE.json), each table's latest
-- exact-count check (its manifest.json), the GitHub copy's summary, the bytes
-- under the copy's folder, and the disk's free space. Nothing here is
-- computed from Supabase.
--
-- Neither the mobile app nor its users read this: anon and authenticated get
-- nothing, and row level security is on with no policy. The dashboard reads
-- it as the database owner through its own Retool connection.
--
-- One DO block: data/view_migrations.py runs each file as one statement on
-- every pass. It returns on a catalog read only while everything this file
-- establishes still holds: the table and its id sequence exist, the table
-- carries this file's marker (the hash of this file with the marker blanked),
-- row level security is on, and neither the table, any of its columns nor
-- the sequence holds a grant to anon, authenticated or PUBLIC. So an edit
-- here is applied on the next pass, and so is a repair: row level security
-- switched off, or any such grant, is undone on the next pass.
--
-- The grant check reads the access lists themselves, not has_table_privilege:
-- a privilege a role only INHERITS (a membership such as pg_read_all_data)
-- is not on these lists, and no REVOKE below could remove it, so checking for
-- it would fail every pass and re-run the whole file each time (the gap the
-- review of #1391 found in the database health file). PUBLIC is on the lists
-- as grantee 0, and the REVOKEs below name it.

DO $mig$
BEGIN
  IF to_regclass('public.pc_copy_snapshots') IS NOT NULL
     AND to_regclass('public.pc_copy_snapshots_snapshot_id_seq') IS NOT NULL
  THEN
    IF COALESCE(obj_description('public.pc_copy_snapshots'::regclass, 'pg_class'), '')
         = 'pc_copy_snapshots 3484e844935a'
       AND (SELECT relrowsecurity FROM pg_class WHERE oid = 'public.pc_copy_snapshots'::regclass)
       AND NOT EXISTS (
         SELECT 1 FROM pg_class c, aclexplode(c.relacl) a
          WHERE c.oid IN ('public.pc_copy_snapshots'::regclass,
                          'public.pc_copy_snapshots_snapshot_id_seq'::regclass)
            AND a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole))
       AND NOT EXISTS (
         SELECT 1 FROM pg_attribute att, aclexplode(att.attacl) a
          WHERE att.attrelid = 'public.pc_copy_snapshots'::regclass
            AND a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole))
    THEN
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.pc_copy_snapshots (
    snapshot_id          BIGSERIAL PRIMARY KEY,
    taken_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source               TEXT NOT NULL,
    -- the LocalMirror pass's own stamp (yyyymmddThhmmssZ); the report's own
    -- time for a manual row
    pass_id              TEXT NOT NULL,
    host                 TEXT,
    pass_started_at      TIMESTAMPTZ,
    -- the Supabase copy's last FINISHED run (STATE.json). A run by hand with
    -- --only covers one table; copy_tables says how many it covered.
    copy_run_id          TEXT,
    copy_started_at      TIMESTAMPTZ,
    copy_finished_at     TIMESTAMPTZ,
    copy_tables          INTEGER,
    copy_rows_pulled     BIGINT,
    copy_db_seconds      INTEGER,
    copy_paused_seconds  INTEGER,
    -- nightly: did that run start in this pass? false means the pass's copy
    -- did not finish and the run above is an older one. NULL on a manual row.
    copy_this_pass       BOOLEAN,
    -- ["schema.table", ...], the tables that run could not copy
    failed_tables        JSONB,
    -- [{table, local_rows, supabase_rows, ranges_differ, ranges_not_counted,
    --   checked_at}]: tables whose latest exact-count check differed
    differing_tables     JSONB,
    -- each step's exit code in this pass (NULL on a manual row)
    github_exit          INTEGER,
    supabase_exit        INTEGER,
    duckdb_exit          INTEGER,
    -- the GitHub copy's last finished run (github\_mirror_summary.json)
    github_finished_at   TIMESTAMPTZ,
    github_repos         INTEGER,
    github_repos_failed  INTEGER,
    -- on disk: the Supabase copy's tables, from their manifests
    local_tables         INTEGER,
    local_rows           BIGINT,
    -- bytes under the copy's folder, by copy; other is logs, bin and the
    -- folders other jobs keep there
    tables_bytes         BIGINT,
    schema_bytes         BIGINT,
    storage_bytes        BIGINT,
    github_bytes         BIGINT,
    duckdb_bytes         BIGINT,
    other_bytes          BIGINT,
    total_bytes          BIGINT,
    total_files          BIGINT,
    -- the disk the copy is on
    disk_total_bytes     BIGINT,
    disk_free_bytes      BIGINT,
    report_ms            INTEGER,
    CONSTRAINT pc_copy_snapshots_source CHECK (source IN ('nightly', 'manual')),
    CONSTRAINT pc_copy_snapshots_pass UNIQUE (source, pass_id)
  );

  ALTER TABLE public.pc_copy_snapshots ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.pc_copy_snapshots FROM PUBLIC, anon, authenticated;
  REVOKE ALL ON SEQUENCE public.pc_copy_snapshots_snapshot_id_seq FROM PUBLIC, anon, authenticated;

  COMMENT ON TABLE public.pc_copy_snapshots IS 'pc_copy_snapshots 3484e844935a';
END $mig$;
