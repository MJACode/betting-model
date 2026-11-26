-- Every table of every DK Network prop-split article version, as printed: header cells and body rows.
--
-- mike, 2026-11-26. The first import (worker_jobs 1724494) parsed 4 of 35 article versions: 31 versions from
-- 2026-09-17 to 2026-11-16 use a table layout no parser reads, and their tables were counted as skipped and not
-- kept. CLAUDE.md §1b: a dataset that cost a fetch is stored first. This keeps every table, parsed or not, so a
-- layout is parsed later from the database without fetching the page again; data/ingestors/dk_prop_splits.py
-- re-reads a version once if its tables are not here.
--
-- Worker-only: RLS on, nothing granted to anon or authenticated. The guard is the property it creates: once the
-- table exists and anon cannot read it, it returns on a catalog read and issues no DDL.
DO $$
BEGIN
  IF to_regclass('public.dk_prop_split_tables') IS NOT NULL
     AND NOT has_table_privilege('anon', 'public.dk_prop_split_tables', 'SELECT')
  THEN
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.dk_prop_split_tables (
    post_id        bigint NOT NULL,
    post_modified  timestamptz NOT NULL,
    table_no       integer NOT NULL,
    section        text,
    header         jsonb NOT NULL,
    body           jsonb NOT NULL,
    layout         text,
    source         text NOT NULL DEFAULT 'dk_network_article',
    fetched_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (post_id, post_modified, table_no)
  );

  ALTER TABLE public.dk_prop_split_tables ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.dk_prop_split_tables FROM anon, authenticated;
END $$;
