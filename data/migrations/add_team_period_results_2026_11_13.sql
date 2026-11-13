-- Team betting results by period, for the Stats tab's Betting filters
-- (Matt, 2026-11-13: "add halves and quarters", "filter last 5 / last 10 ATS
-- or O/U", "pick quarter/half/full game, then full season / last 10/5/3, also
-- home-away").
--
-- team_period_results: one row per team, per game, per period (FG, H1, Q1,
-- Q2, Q3, Q4). It holds the period's score, the line it is graded against,
-- the ATS and over/under result, and each side's rest days, so the app can
-- count any window (season, last N), any venue and the favourite / underdog
-- and rest splits from the same rows. Written by
-- data/ingestors/team_period_results.py (the pipeline's nba_quarters step).
-- A stored table, never a view over `odds`: the newest-row-per-key read is a
-- state the writer maintains (.claude/rules/data-integrity.md).
--
-- The line: DraftKings' last pre-tip number for that period's market; with no
-- DraftKings row, the median of every other book's last pre-tip number,
-- rounded to the nearest half point. `line_source` says which.
--
-- Once the table, its index and the policy exist, this returns on a catalog
-- read. A no-op still reloads PostgREST's schema cache (data/ddl_guard.py),
-- which is why it checks first.
DO $$
BEGIN
  IF to_regclass('public.team_period_results') IS NOT NULL
     AND to_regclass('public.team_period_results_sport_season') IS NOT NULL
     AND EXISTS (
       SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'team_period_results'
          AND policyname = 'anon read team_period_results')
  THEN
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.team_period_results (
    sport          TEXT    NOT NULL,
    season         INTEGER NOT NULL,
    game_id        TEXT    NOT NULL,
    team           TEXT    NOT NULL,
    period         TEXT    NOT NULL,
    game_date      TEXT    NOT NULL,
    opponent       TEXT    NOT NULL,
    is_home        BOOLEAN NOT NULL,
    pts_for        INTEGER NOT NULL,
    pts_against    INTEGER NOT NULL,
    -- The team's own number, standard form: negative = favoured.
    spread         NUMERIC,
    total_line     NUMERIC,
    -- 'draftkings' or 'consensus'; NULL when no line.
    spread_source  TEXT,
    total_source   TEXT,
    -- 'W' / 'L' / 'P' and 'O' / 'U' / 'P'; NULL when no line.
    ats            TEXT,
    ou             TEXT,
    rest_days      INTEGER,
    opp_rest_days  INTEGER,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, team, period),
    CONSTRAINT team_period_results_period CHECK (period IN ('FG', 'H1', 'Q1', 'Q2', 'Q3', 'Q4')),
    CONSTRAINT team_period_results_ats CHECK (ats IS NULL OR ats IN ('W', 'L', 'P')),
    CONSTRAINT team_period_results_ou CHECK (ou IS NULL OR ou IN ('O', 'U', 'P'))
  );
  CREATE INDEX IF NOT EXISTS team_period_results_sport_season
    ON public.team_period_results (sport, season, period, team, game_date DESC);

  ALTER TABLE public.team_period_results ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.team_period_results FROM anon, authenticated;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'team_period_results'
       AND policyname = 'anon read team_period_results'
  ) THEN
    CREATE POLICY "anon read team_period_results"
      ON public.team_period_results
      FOR SELECT
      TO anon, authenticated
      USING (true);
  END IF;
  GRANT SELECT ON public.team_period_results TO anon, authenticated;
END $$;
