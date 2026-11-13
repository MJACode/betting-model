-- Latest-row index for the Scoreboard NCAAF read.
--
-- NOT in data/view_migrations.ACTIVE_MIGRATIONS. The worker re-runs
-- that list against production. Apply this file by hand after Matt
-- says so. v_ncaaf_scoreboard_latest is already on prod
-- (schema_migrations 20261028230300). This file does not replace it.
--
-- Measured 2026-10-28, EXPLAIN on prod:
--   WHERE game_date = '2026-10-25' filters after Unique and sorts the
--   log (18,661 rows, cost 3659).
--   WHERE game_id = ANY of three ids pushes into
--   ncaaf_live_states_game (149 rows, cost 411) and still
--   incremental-sorts seen_at DESC, state_id DESC.
-- The app filters by game_id. This index matches that ORDER BY
-- (game_id, seen_at DESC, state_id DESC) so the leftover sort is the
-- index order. The existing indexes are (game_id, seen_at) and do not
-- include state_id.
--
-- Idempotent. Does not rewrite the view, picks, or odds.
-- One DO block. No CONCURRENTLY.

DO $mig$
BEGIN
  IF to_regclass('public.ncaaf_live_states') IS NULL THEN
    RAISE EXCEPTION 'ncaaf_live_states is not present';
  END IF;

  EXECUTE
    'CREATE INDEX IF NOT EXISTS ncaaf_live_states_scoreboard_idx '
    'ON public.ncaaf_live_states (game_id, seen_at DESC, state_id DESC)';
END $mig$;
