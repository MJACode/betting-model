-- 2026-10-01: injuries-refresh statement_timeout.
--
-- Hourly runs 40ab88f5 (20:17 UTC) and a4a04838 (20:58 UTC) logged
-- pipeline_log step=injury status=error (log_id 115154, 115196):
-- "current transaction is aborted, commands ignored until end of transaction
-- block". Postgres in the same windows cancelled the statement for
-- statement_timeout first. The follow-on is what the ingestor recorded,
-- because nothing rolled the transaction back before the next command.
--
-- The statement auto-explain caught was:
--   SELECT DISTINCT ON (player_id) player_id, player_name FROM injuries
--   WHERE player_id IS NOT NULL AND player_id <> ''
--     AND player_name IS NOT NULL AND player_name <> 'Unknown'
--   ORDER BY player_id, created_at DESC
-- Plan: Seq Scan + Sort of 822,508 rows, cost 145558, ~63s. Under the
-- concurrent api_call_daily rollup that crossed the 120s statement_timeout.
-- SELECT MAX(created_at) FROM injuries was a parallel seq scan (~22s, cost
-- 22406). The freshness probe no longer issues it (newest injury_id). This
-- file removes the sort from the name seed.
--
-- THE SHAPE. One row per athlete, written by the ingestor when it inserts
-- an injury. The refresh reads that table. Cost scales with the number of
-- names (~2,400), not with the log. The partial index exists so this
-- backfill — and any rebuild of the same DISTINCT ON — is an index scan in
-- ORDER BY order, not another sort of the log.
--
-- Guard on the property (table AND index present), not on a row count.
-- Once both exist this is a catalog read and returns. No DDL on later
-- passes: CREATE INDEX still takes a lock and fires a PostgREST schema
-- reload when it is executed. lock_timeout so a busy injuries writer does
-- not stall apply-view-migrations; the next pass retries.
--
-- Single statement, as data/view_migrations.py requires. Not CONCURRENTLY:
-- that cannot run inside this runner's transaction. ShareLock blocks
-- injury inserts for the build only; the refresh that inserts runs after
-- this step.

DO $mig$
BEGIN
  IF to_regclass('public.injury_player_names') IS NOT NULL
     AND EXISTS (
       SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname = 'idx_injuries_player_id_created'
     ) THEN
    RAISE NOTICE 'injury_player_names already present - skipping';
    RETURN;
  END IF;

  PERFORM set_config('lock_timeout', '5s', true);
  PERFORM set_config('statement_timeout', '100s', true);

  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
     WHERE schemaname = 'public'
       AND indexname = 'idx_injuries_player_id_created'
  ) THEN
    CREATE INDEX idx_injuries_player_id_created
      ON public.injuries (player_id, created_at DESC)
      INCLUDE (player_name)
      WHERE player_id IS NOT NULL
        AND player_id <> ''
        AND player_name IS NOT NULL
        AND player_name <> 'Unknown';
  END IF;

  IF to_regclass('public.injury_player_names') IS NULL THEN
    CREATE TABLE public.injury_player_names (
      player_id   TEXT PRIMARY KEY,
      player_name TEXT NOT NULL
    );
    ALTER TABLE public.injury_player_names ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.injury_player_names FROM anon, authenticated;
  END IF;

  INSERT INTO public.injury_player_names (player_id, player_name)
  SELECT DISTINCT ON (player_id) player_id, player_name
    FROM public.injuries
   WHERE player_id IS NOT NULL AND player_id <> ''
     AND player_name IS NOT NULL AND player_name <> 'Unknown'
   ORDER BY player_id, created_at DESC
  ON CONFLICT (player_id) DO NOTHING;
END
$mig$;
