-- ncaaf_plays: every numeric column becomes BIGINT.
--
-- WHY (2026-09-12, the first run of the ncaaf_pbp_pull job). The insert died
-- with `NumericValueOutOfRange: integer out of range` and Postgres does not
-- name the column, so the traceback said only that SOMETHING did not fit in
-- int32. Rather than guess which, two changes: the writer now range-checks
-- every numeric column before the INSERT and raises naming the column and the
-- value (`store_season` in ncaaf_live/backtest/pull_pbp.py), and the columns
-- themselves widen here.
--
-- INT32 WAS AN ARBITRARY CEILING ON DATA WE DO NOT CONTROL. These are values a
-- third-party feed chooses; CFBD already serves 18-digit play ids and 9-digit
-- game ids (both TEXT here for exactly that reason), and picking 2,147,483,647
-- as the limit for its other numbers was a guess dressed as a schema. The
-- semantic columns are all small -- a period is 1-4, a down is 1-4 -- so BIGINT
-- costs 4 bytes a column on ~235k rows a season and removes a whole class of
-- failure. The range check is what catches a value that is actually WRONG; the
-- width is what stops a merely large one from being fatal.
--
-- Safe on an empty or populated table: ALTER ... TYPE BIGINT is a widening
-- conversion Postgres does without rewriting the values' meaning.
DO $$
DECLARE
  col TEXT;
BEGIN
  IF to_regclass('public.ncaaf_plays') IS NULL THEN
    RETURN;                       -- add_ncaaf_plays.sql has not run yet
  END IF;
  FOREACH col IN ARRAY ARRAY[
    'play_number', 'period', 'clock_minutes', 'clock_seconds',
    'offense_score', 'defense_score', 'offense_timeouts', 'defense_timeouts',
    'down', 'distance', 'yards_to_goal', 'yards_gained', 'season', 'week'
  ] LOOP
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'ncaaf_plays'
        AND column_name = col AND data_type = 'integer'
    ) THEN
      EXECUTE format('ALTER TABLE public.ncaaf_plays ALTER COLUMN %I TYPE BIGINT', col);
    END IF;
  END LOOP;
END $$;
