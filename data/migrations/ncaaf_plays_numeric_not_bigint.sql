-- ncaaf_plays: numeric columns become NUMERIC, which has no range at all.
--
-- WHY (2026-09-12, attempts 1 and 2 of the ncaaf_pbp_pull job). The first run
-- failed `integer out of range`; the columns were widened to BIGINT; the second
-- run failed `bigint out of range`. So some value CFBD serves genuinely exceeds
-- 2^63, and widening one more step would be the third guess in a row.
--
-- NUMERIC is not a bigger guess, it is the end of guessing: arbitrary
-- precision, no ceiling. These are numbers a third party chooses and we do not
-- validate; the schema's job is to store them faithfully so they can be looked
-- at, not to have an opinion about their magnitude. Every semantic column here
-- is tiny in practice (a period is 1-4, a down is 1-4), so the cost is a few
-- bytes on ~235k rows a season against a class of failure that has now cost
-- two deploy cycles.
--
-- AND THE GUARD THAT SHOULD HAVE CAUGHT IT HAD A HOLE. `_check_ranges` tested
-- with `pd.to_numeric(..., errors="coerce")`, and coerce turns a value too
-- large to represent into NaN -- which the check then skipped as missing. It
-- discarded precisely the values it existed to find, then let them through to
-- Postgres, which reports a range error naming nothing. Fixed in
-- ncaaf_live/backtest/pull_pbp.py to inspect the raw objects, and it now
-- REPORTS rather than raises, because a faithful store plus a visible range is
-- more useful than a refusal that stops the corpus landing.
DO $$
DECLARE
  col TEXT;
BEGIN
  IF to_regclass('public.ncaaf_plays') IS NULL THEN
    RETURN;
  END IF;
  FOREACH col IN ARRAY ARRAY[
    'play_number', 'period', 'clock_minutes', 'clock_seconds',
    'offense_score', 'defense_score', 'offense_timeouts', 'defense_timeouts',
    'down', 'distance', 'yards_to_goal', 'yards_gained', 'season', 'week'
  ] LOOP
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'ncaaf_plays'
        AND column_name = col AND data_type IN ('integer', 'bigint')
    ) THEN
      EXECUTE format('ALTER TABLE public.ncaaf_plays ALTER COLUMN %I TYPE NUMERIC', col);
    END IF;
  END LOOP;
END $$;
