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
-- names (~2,400), not with the log. The partial index makes the one-time
-- fill of the empty table an index scan in ORDER BY order, not another sort
-- of the log.
--
-- THE INDEX IS MEANT TO BE BUILT BY HAND FIRST (#858 review), with
--   CREATE INDEX CONCURRENTLY idx_injuries_player_id_created
--     ON public.injuries (player_id, created_at DESC)
--     INCLUDE (player_name)
--     WHERE player_id IS NOT NULL AND player_id <> ''
--       AND player_name IS NOT NULL AND player_name <> 'Unknown';
-- CONCURRENTLY cannot run inside this runner's transaction. When a VALID
-- index with exactly that definition exists (pg_index.indisvalid and
-- indisready, full pg_get_indexdef compared), this file does not touch it.
-- A same-named index that is invalid (a cancelled CONCURRENTLY build) or
-- defined differently is left alone with a WARNING: rebuild it by hand
-- (DROP INDEX CONCURRENTLY, then the statement above). Only a MISSING index
-- is built here, as a fallback, without CONCURRENTLY: that holds ShareLock on
-- injuries (~825k rows) for the build.
--
-- NO BACKFILL HERE. The ingestor fills an empty injury_player_names on its
-- first seed (injury_ingestor._backfill_player_names, committed before the
-- seed connection closes). Doing it here too ran the 825k-row DISTINCT ON
-- inside the same transaction as the index build.
--
-- Guard on the property (table AND valid index), not on a row count. Once
-- both exist this is a catalog read and returns, so no DDL runs on later
-- passes (CREATE INDEX still takes a lock, and DDL fires a PostgREST schema
-- reload). lock_timeout 5s applies to every lock this block waits for after
-- the set_config, so a busy injuries writer does not stall
-- apply-view-migrations; the next pass retries. statement_timeout is NOT set
-- here: it is armed when a statement starts, so setting it inside this
-- already-running statement would change nothing for it.
--
-- Single statement, as data/view_migrations.py requires.

DO $mig$
DECLARE
  idx_def text;
  idx_valid boolean;
  idx_ready boolean;
  idx_ok boolean;
  want constant text :=
    'CREATE INDEX idx_injuries_player_id_created ON injuries USING btree '
    || '(player_id, created_at DESC) INCLUDE (player_name) '
    || 'WHERE ((player_id IS NOT NULL) AND (player_id <> ''''::text) '
    || 'AND (player_name IS NOT NULL) AND (player_name <> ''Unknown''::text))';
BEGIN
  SELECT pg_get_indexdef(i.indexrelid), i.indisvalid, i.indisready
    INTO idx_def, idx_valid, idx_ready
    FROM pg_index i
   WHERE i.indexrelid = to_regclass('public.idx_injuries_player_id_created');

  idx_ok := idx_def IS NOT NULL AND idx_valid AND idx_ready
    AND regexp_replace(replace(idx_def, 'public.', ''), '\s+', ' ', 'g') = want;

  IF to_regclass('public.injury_player_names') IS NOT NULL AND idx_ok THEN
    RAISE NOTICE 'injury_player_names already present - skipping';
    RETURN;
  END IF;

  PERFORM set_config('lock_timeout', '5s', true);

  IF idx_def IS NULL THEN
    -- Fallback only: the index was not built CONCURRENTLY by hand first.
    CREATE INDEX idx_injuries_player_id_created
      ON public.injuries (player_id, created_at DESC)
      INCLUDE (player_name)
      WHERE player_id IS NOT NULL
        AND player_id <> ''
        AND player_name IS NOT NULL
        AND player_name <> 'Unknown';
  ELSIF NOT idx_ok THEN
    RAISE WARNING 'idx_injuries_player_id_created exists but is not the expected valid index (valid=%, ready=%, def=%) - not touching it; DROP INDEX CONCURRENTLY and rebuild it CONCURRENTLY by hand',
      idx_valid, idx_ready, idx_def;
  END IF;

  IF to_regclass('public.injury_player_names') IS NULL THEN
    CREATE TABLE public.injury_player_names (
      player_id   TEXT PRIMARY KEY,
      player_name TEXT NOT NULL
    );
    ALTER TABLE public.injury_player_names ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.injury_player_names FROM anon, authenticated;
  END IF;
END
$mig$;
