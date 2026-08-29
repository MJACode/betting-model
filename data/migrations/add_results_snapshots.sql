-- Every number the results recap publishes, stored so it can be audited later.
--
-- The recap is computed at post time from live tables, so "why did Monday say
-- +2.1u?" was answerable only by re-running the query against data that has
-- since changed -- late settlements, a threshold sweep, a model pause all move
-- the historical figure. This records what was ACTUALLY published, per date,
-- per scope, per sport, alongside the CLV it was published with.
--
-- One row per (game_date, scope, sport): scope 'daily' | 'all_time', sport NULL
-- for the overall line. Idempotent: re-posting the same date overwrites its own
-- rows rather than duplicating them.
DO $$
BEGIN
  IF to_regclass('public.results_snapshots') IS NULL THEN
    CREATE TABLE public.results_snapshots (
      snapshot_id   BIGSERIAL PRIMARY KEY,
      game_date     TEXT NOT NULL,
      scope         TEXT NOT NULL CHECK (scope IN ('daily', 'all_time')),
      sport         TEXT,
      wins          INTEGER NOT NULL DEFAULT 0,
      losses        INTEGER NOT NULL DEFAULT 0,
      pushes        INTEGER NOT NULL DEFAULT 0,
      settled       INTEGER NOT NULL DEFAULT 0,
      record_only   INTEGER NOT NULL DEFAULT 0,
      units         NUMERIC,
      risked        NUMERIC,
      roi_pct       NUMERIC,
      -- CLV is captured only for game-level picks with a closing DK price, so
      -- the denominator travels with the percentage. Live picks are excluded by
      -- construction -- an in-play price has no meaningful close.
      clv_graded    INTEGER NOT NULL DEFAULT 0,
      clv_beat      INTEGER NOT NULL DEFAULT 0,
      clv_pct       NUMERIC,
      published_at  TEXT NOT NULL
    );
    CREATE UNIQUE INDEX results_snapshots_key
      ON public.results_snapshots (game_date, scope, COALESCE(sport, ''));
    CREATE INDEX results_snapshots_date ON public.results_snapshots (game_date);

    -- Written by the pipeline as the table owner; readable by the app.
    ALTER TABLE public.results_snapshots ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.results_snapshots FROM anon, authenticated;
    GRANT SELECT ON public.results_snapshots TO anon, authenticated;
    CREATE POLICY "anon read results_snapshots"
      ON public.results_snapshots FOR SELECT TO anon, authenticated USING (true);
  END IF;
END $$;
