-- 2026-09-08: the scorer's housekeeping sweep (and, before it, the pre-loop
-- bulk DELETE) filtered picks on result IS NULL AND signal_type <> 'BET' AND
-- is_live IS NOT TRUE, joined to the look-ahead window of games. EXPLAIN on
-- production: Seq Scan on picks, 137,630 open non-BET rows examined per pass,
-- every ten minutes in the evening. Thirty-five "canceling statement due to
-- statement timeout ... while deleting tuple in relation picks" failures in
-- the week to 09-08 sat on that statement.
--
-- Partial index on exactly that predicate. With it the planner runs a nested
-- loop over the ~700 window games with an index scan per game (measured on
-- production after creation: cost 11,267 either way but 0 rows scanned
-- outside the window; build 0.8s, 1 MB). Matt, 2026-09-08: "add the index."
--
-- Applied to production first with CREATE INDEX CONCURRENTLY (cannot run
-- inside the migration runner's transaction); this repo copy is the
-- recoverable form. CREATE INDEX IF NOT EXISTS still opens picks with
-- ShareLock before the name check (indexcmds.c), which waits behind every
-- writer. Hourly run b22f8e4fb9e34d27858c341e46ce635c logged this statement
-- at 2026-10-01 17:19:03Z, between the two push_sent timeouts. The catalog
-- check returns before that lock. The index predicate is part of the
-- property: a same-named index with a different definition is not "done".
--
-- 2026-10-02 (#857 review): the check is pg_index, not pg_indexes, so an
-- INVALID index (a CONCURRENTLY build that was cancelled) is not "done".
-- The definition is compared in full against what Postgres 17 prints for
-- the index above (read from production 2026-10-02: valid, ready). A
-- same-named index that is invalid or defined differently is LEFT ALONE
-- with a WARNING: CREATE INDEX IF NOT EXISTS would only take ShareLock on
-- picks and then no-op on the name, so falling through fixes nothing.
-- Repair it by hand (DROP INDEX CONCURRENTLY, CREATE INDEX CONCURRENTLY).
-- Only a missing index is created here.
DO $mig$
DECLARE
  def text;
  valid boolean;
  ready boolean;
  want constant text :=
    'CREATE INDEX idx_picks_open_nonbet ON picks USING btree (game_id) '
    || 'WHERE ((result IS NULL) AND (signal_type <> ''BET''::text) '
    || 'AND (is_live IS NOT TRUE))';
BEGIN
  SELECT pg_get_indexdef(i.indexrelid), i.indisvalid, i.indisready
    INTO def, valid, ready
    FROM pg_index i
   WHERE i.indexrelid = to_regclass('public.idx_picks_open_nonbet');

  IF def IS NOT NULL THEN
    IF valid AND ready
       AND regexp_replace(replace(def, 'public.', ''), '\s+', ' ', 'g') = want THEN
      RAISE NOTICE 'idx_picks_open_nonbet already present - skipping';
    ELSE
      RAISE WARNING 'idx_picks_open_nonbet exists but is not the expected valid index (valid=%, ready=%, def=%) - not touching it; rebuild it CONCURRENTLY by hand',
        valid, ready, def;
    END IF;
    RETURN;
  END IF;

  CREATE INDEX IF NOT EXISTS idx_picks_open_nonbet
    ON public.picks (game_id)
    WHERE result IS NULL AND signal_type <> 'BET' AND is_live IS NOT TRUE;
END $mig$;
