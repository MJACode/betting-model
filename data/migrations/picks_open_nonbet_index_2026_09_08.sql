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
-- recoverable form and no-ops where the index already exists.
CREATE INDEX IF NOT EXISTS idx_picks_open_nonbet
  ON public.picks (game_id)
  WHERE result IS NULL AND signal_type <> 'BET' AND is_live IS NOT TRUE
