-- injuries_read_indexes (2026-11-14)
--
-- WHY. Three reads of `injuries` (1.8M rows, 383 MB) had no index to use and
-- crossed the 2-minute statement timeout once the database slowed
-- (2026-11-12 on; issue #1328). Plans read on production 2026-11-14:
--
--   SELECT MAX(report_date) FROM injuries WHERE sport = $1 AND report_date <= $2
--     the NFL prop injury veto and the injury reads (428,125 calls, max 119.7s):
--     an index-only scan over 378,507 entries of idx_injuries_team_date.
--   SELECT MAX(created_at) FROM injuries
--     the refresh pass's freshness gate (3,689 calls, max 115.0s): a parallel
--     sequential scan of the whole table.
--   SELECT DISTINCT player_name, player_id, team, activation_date FROM injuries
--     WHERE sport = $1 AND scenario = $2 AND activation_date ... (the return
--     ramp; 9,172 calls, max 118.7s): an index scan over the sport's rows.
--     Its timeouts aborted the injuries run (fixed in injury_ingestor.py).
--
-- Each becomes a short index lookup with the matching index.
--
-- Built on production first with CREATE INDEX CONCURRENTLY (it cannot run
-- inside the migration runner's transaction). This file is the recoverable
-- copy, in the shape of picks_open_nonbet_index_2026_09_08.sql: the catalog
-- check returns before any lock, because CREATE INDEX IF NOT EXISTS takes
-- ShareLock on the table before it checks the name, and would wait behind
-- every writer on every pass. A same-named index that is invalid or defined
-- differently is left alone with a WARNING; rebuild it CONCURRENTLY by hand.
-- Only a missing index is created here (a fresh database).
DO $mig$
DECLARE
  names text[] := ARRAY['idx_injuries_sport_report_date', 'idx_injuries_created_at',
                        'idx_injuries_return_ramp'];
  wants text[] := ARRAY[
    'CREATE INDEX idx_injuries_sport_report_date ON injuries USING btree (sport, report_date)',
    'CREATE INDEX idx_injuries_created_at ON injuries USING btree (created_at)',
    'CREATE INDEX idx_injuries_return_ramp ON injuries USING btree (sport, scenario, activation_date) '
      || 'WHERE (activation_date IS NOT NULL)'];
  i int;
  def text;
  valid boolean;
  ready boolean;
BEGIN
  FOR i IN 1 .. array_length(names, 1) LOOP
    SELECT pg_get_indexdef(x.indexrelid), x.indisvalid, x.indisready
      INTO def, valid, ready
      FROM pg_index x
     WHERE x.indexrelid = to_regclass('public.' || names[i]);

    IF def IS NOT NULL THEN
      IF NOT (valid AND ready
              AND regexp_replace(replace(def, 'public.', ''), '\s+', ' ', 'g') = wants[i]) THEN
        RAISE WARNING '% exists but is not the expected valid index (valid=%, ready=%, def=%) - not touching it; rebuild it CONCURRENTLY by hand',
          names[i], valid, ready, def;
      END IF;
      CONTINUE;
    END IF;

    EXECUTE replace(wants[i], ' ON injuries ', ' ON public.injuries ');
    RAISE NOTICE '% created', names[i];
  END LOOP;
END $mig$;
