-- DraftKings' own player-prop handle and bet shares, from DK Network's prop-split articles.
--
-- mike, 2026-11-26 ("Do all the outstanding tasks now"). DK Network's splits table covers
-- moneyline / spread / total only; prop splits are published as articles for featured NFL
-- games (34 found through the WordPress posts API, 2026-09-14 to 2026-11-23, worker_jobs
-- 1723195). data/ingestors/dk_prop_splits.py reads them.
--
-- 1. dk_prop_split_articles: one row per article version (post id, WordPress modified time)
--    the importer has read, with how many rows it stored, so a version is fetched once.
-- 2. dk_prop_splits: one row per table row of that version. An edited article is a new
--    version and new rows; nothing is updated or deleted (CLAUDE.md §1b).
--
-- Worker-only: RLS on, nothing granted to anon or authenticated. The guard is the property
-- it creates: once both tables exist and anon cannot read either, it returns on a catalog
-- read and issues no DDL. Touches no pick, odds, split or record table.
DO $$
BEGIN
  IF to_regclass('public.dk_prop_split_articles') IS NOT NULL
     AND to_regclass('public.dk_prop_splits') IS NOT NULL
     AND NOT has_table_privilege('anon', 'public.dk_prop_split_articles', 'SELECT')
     AND NOT has_table_privilege('anon', 'public.dk_prop_splits', 'SELECT')
  THEN
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.dk_prop_split_articles (
    post_id        bigint NOT NULL,
    post_modified  timestamptz NOT NULL,
    post_date      timestamptz,
    title          text NOT NULL,
    link           text,
    updated_text   text,
    game_id        text,
    rows_stored    integer NOT NULL,
    tables_skipped integer NOT NULL,
    source         text NOT NULL DEFAULT 'dk_network_article',
    fetched_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (post_id, post_modified)
  );

  CREATE TABLE IF NOT EXISTS public.dk_prop_splits (
    id             bigserial PRIMARY KEY,
    post_id        bigint NOT NULL,
    post_modified  timestamptz NOT NULL,
    game_id        text,
    table_no       integer NOT NULL,
    row_no         integer NOT NULL,
    section        text,
    layout         text NOT NULL CHECK (layout IN ('side_line', 'leaders')),
    prop_text      text NOT NULL,
    player         text,
    market         text,
    line_value     numeric,
    handle_side    text,
    handle_pct     numeric(5,1) CHECK (handle_pct BETWEEN 0 AND 100),
    bets_side      text,
    bets_pct       numeric(5,1) CHECK (bets_pct BETWEEN 0 AND 100),
    source         text NOT NULL DEFAULT 'dk_network_article',
    fetched_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (post_id, post_modified, table_no, row_no)
  );
  CREATE INDEX IF NOT EXISTS dk_prop_splits_game_idx ON public.dk_prop_splits (game_id, post_modified DESC);

  ALTER TABLE public.dk_prop_split_articles ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.dk_prop_splits ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.dk_prop_split_articles FROM anon, authenticated;
  REVOKE ALL ON public.dk_prop_splits FROM anon, authenticated;
  REVOKE ALL ON SEQUENCE public.dk_prop_splits_id_seq FROM anon, authenticated;
END $$;
