-- NCAAB period scores and the ESPN box-score miss ledger (2026-10-30).
--
-- ncaab_period_scores: one row per (game, period) for every final NCAAB game.
-- Period 1 and 2 are the halves, 3 and later the overtimes, in the stored
-- games row's home/away orientation. `source` names the ESPN endpoint the
-- line scores came from: 'espn_summary' (the refresh-pass box feed, one call
-- per game) or 'espn_scoreboard' (the backfill, one call per date). Written by
-- data/ingestors/ncaab_espn_box.py, which refuses any game whose periods do
-- not sum to the stored final. Grading input for first-half and second-half
-- markets; the halves the research round fetched for 2020-21 to 2025-26 lived
-- only on one laptop until the backfill stores them here.
--
-- ncaab_box_misses: one row per game ESPN could not answer usefully (not
-- final, a box score that is missing a number or does not add up, a final
-- that differs from the stored one), with the attempt count, so a bad game is
-- not fetched on every refresh pass.
--
-- Worker-only: RLS on, anon and authenticated hold nothing, no policy. The
-- writer creates the same two tables at write time behind
-- data/ddl_guard.schema_is_current (the NCAAB tables' convention), and
-- tests/test_ncaab_espn_box.py holds the two definitions equal.
--
-- IDEMPOTENT. ENABLE ROW LEVEL SECURITY and REVOKE take AccessExclusiveLock on
-- every execution, so once both tables exist with RLS on and nothing granted
-- to anon or authenticated this returns on a catalog read. Single DO block,
-- because data/view_migrations.py runs each file as ONE statement.
DO $mig$
BEGIN
  IF to_regclass('public.ncaab_period_scores') IS NOT NULL
     AND to_regclass('public.ncaab_box_misses') IS NOT NULL
     AND to_regclass('public.idx_ncaab_period_scores_season') IS NOT NULL THEN
    IF NOT EXISTS (
         SELECT 1 FROM pg_class
          WHERE oid IN (to_regclass('public.ncaab_period_scores'),
                        to_regclass('public.ncaab_box_misses'))
            AND NOT relrowsecurity
       )
       AND NOT EXISTS (
         SELECT 1
           FROM pg_roles r
           CROSS JOIN (VALUES ('public.ncaab_period_scores'),
                              ('public.ncaab_box_misses')) AS t(rel)
          WHERE r.rolname IN ('anon', 'authenticated')
            AND has_table_privilege(r.oid, t.rel, 'SELECT,INSERT,UPDATE,DELETE')
       )
    THEN
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.ncaab_period_scores (
    game_id        TEXT NOT NULL,
    period         INTEGER NOT NULL,
    home_points    INTEGER NOT NULL,
    away_points    INTEGER NOT NULL,
    espn_event_id  BIGINT NOT NULL,
    season         INTEGER NOT NULL,
    game_date      TEXT NOT NULL,
    source         TEXT NOT NULL,
    loaded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, period)
  );
  CREATE INDEX IF NOT EXISTS idx_ncaab_period_scores_season
    ON public.ncaab_period_scores (season);

  CREATE TABLE IF NOT EXISTS public.ncaab_box_misses (
    espn_event_id  BIGINT PRIMARY KEY,
    game_id        TEXT NOT NULL,
    attempts       INTEGER NOT NULL,
    first_at       TIMESTAMPTZ NOT NULL,
    last_at        TIMESTAMPTZ NOT NULL,
    reason         TEXT
  );

  REVOKE ALL ON public.ncaab_period_scores FROM anon, authenticated;
  REVOKE ALL ON public.ncaab_box_misses FROM anon, authenticated;
  ALTER TABLE public.ncaab_period_scores ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.ncaab_box_misses ENABLE ROW LEVEL SECURITY;
END $mig$;
