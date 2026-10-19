-- 2026-10-12 (mike: "5) yes" -- move the free data the NFL edge search
-- fetched into Supabase). One row per FILE, gzipped, checksummed on the raw
-- bytes: the shape nfl_live_prop_snapshots and nfl_odds_cache_backup already
-- use, so a restore proves it reproduced the original file. Written and read
-- by scripts/nfl_research_backup.py. Not app-readable.
--
-- What it holds: Kalshi NFL winner-market history (1-minute candles, raw
-- responses, 2025 and 2026), Open-Meteo ERA5 / issued-forecast responses for
-- NFL venues, and the nflverse play-by-play files the search graded on.
--
-- NO DDL ON A REPEAT PASS: everything is inside the create-once block, so the
-- every-pass run takes no lock and fires no PostgREST reload (data/ddl_guard.py).
--
-- ONE statement (a DO block): data/view_migrations runs each file through a
-- single conn.execute.
DO $$
BEGIN
  IF to_regclass('public.nfl_research_data_backup') IS NULL THEN
    CREATE TABLE public.nfl_research_data_backup (
      id           BIGSERIAL PRIMARY KEY,
      rel_path     TEXT NOT NULL UNIQUE,   -- path under the cache root
      source       TEXT NOT NULL,          -- 'nfl_edge_search|<kind>'
      sha256       TEXT NOT NULL,          -- of the RAW bytes
      raw_bytes    BIGINT NOT NULL,
      gz_bytes     BIGINT NOT NULL,
      content_gz   BYTEA NOT NULL,
      backed_up_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX idx_nfl_research_data_backup_source
      ON public.nfl_research_data_backup (source);
    ALTER TABLE public.nfl_research_data_backup ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nfl_research_data_backup FROM anon, authenticated;
    REVOKE ALL ON SEQUENCE public.nfl_research_data_backup_id_seq FROM anon, authenticated;
  END IF;
END $$;
