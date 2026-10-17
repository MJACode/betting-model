-- 2026-10-12 (mike: "3) yes" -- buy the halftime second-half lines and the
-- 2025 in-game lines). data/ingestors/nfl_inplay_history.py writes them into
-- nfl_odds_history, the append-only, never-pruned NFL game-line archive.
--
-- source: which purchase a row came from, so a re-run resumes off what is
-- stored instead of buying it twice (CLAUDE.md §1b, tests/test_everything_in_supabase).
-- Rows written before this column existed carry NULL.
--
-- nfl_odds_history_pulls: one row per paid call, INCLUDING a call that
-- returned nothing. Without it, an event the feed had no second-half market
-- for writes no odds row, and every re-run would pay for it again. Not
-- app-readable: an ingestion ledger.
--
-- NO DDL ON A REPEAT PASS. This file runs on every worker pass
-- (data/view_migrations.ACTIVE_MIGRATIONS). ALTER TABLE takes ACCESS
-- EXCLUSIVE even when IF NOT EXISTS makes it a no-op, and nfl_odds_history is
-- written every minute by the NFL poll; ENABLE ROW LEVEL SECURITY also fires
-- PostgREST's schema reload (data/ddl_guard.py). So every statement is gated
-- on the catalog and a second run does nothing. Applied to production
-- 2026-10-12, before the purchase.
--
-- ONE statement (a DO block): data/view_migrations runs each file through a
-- single conn.execute.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema = 'public' AND table_name = 'nfl_odds_history'
                   AND column_name = 'source') THEN
    ALTER TABLE public.nfl_odds_history ADD COLUMN source TEXT;
  END IF;

  IF to_regclass('public.nfl_odds_history_pulls') IS NULL THEN
    CREATE TABLE public.nfl_odds_history_pulls (
      request_key   TEXT PRIMARY KEY,   -- '<kind>|<event or season>|<requested ts>'
      kind          TEXT NOT NULL,      -- 'inplay' | 'halftime' | 'events'
      season        INTEGER,
      requested_at  TEXT NOT NULL,
      served_at     TEXT,
      http_status   INTEGER,
      credits_last  INTEGER,            -- x-requests-last on the response
      rows_written  INTEGER NOT NULL DEFAULT 0,
      pulled_at     TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX idx_nfl_odds_history_pulls_kind
      ON public.nfl_odds_history_pulls (kind, season);
    ALTER TABLE public.nfl_odds_history_pulls ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nfl_odds_history_pulls FROM anon, authenticated;
  END IF;
END $$;
