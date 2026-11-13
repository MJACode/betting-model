-- The women's college basketball halftime loop's decision ledger
-- (models/ncaabw_live_loop.py, model ncaabw_live_total_ht).
--
-- One FINAL row per (game, model), kept by a partial unique index: the
-- decision of the first price read of the halftime break that held an
-- eligible quote ('bet', 'no_bet' when its EV was under the cut, 'declined'
-- when a platform gate refused it), or 'missed' when the third quarter began
-- with no eligible quote seen. The graded rule decides ONCE per game and a
-- decision under the cut SPENDS it (docs/sports/ncaabw.md, "In play"). A pick
-- row exists only for a bet, so without this table a restart would forget a
-- no-bet decision and decide the game again at the next read: a bet the grade
-- never made. A read the loop could not decide on (ESPN unreadable, publishing
-- late or disagreeing with itself, the odds feed, an error) writes a
-- 'skipped' row; a read inside the break with no eligible quote a 'carried'
-- row. The loop refuses to decide anything while this table is missing.
--
-- It is also the audit trail of what the model saw: the halftime score, the
-- pre-game numbers, the mean and spread of the points to come, every priced
-- quote of the read, and the seconds between ESPN's newest play and the read.
--
-- anon and authenticated get nothing; the pollers' DATABASE_URL writes it.
-- One DO block: data/view_migrations.py runs each file as one statement, on
-- every pass. The early return answers "already applied" on the property this
-- migration establishes (the table exists, RLS on, no anon/authenticated
-- privilege), read through to_regclass so a fresh database never casts a
-- missing relation.

DO $mig$
BEGIN
  IF to_regclass('public.ncaabw_live_decisions') IS NOT NULL THEN
    IF EXISTS (
         SELECT 1 FROM pg_class
          WHERE oid = to_regclass('public.ncaabw_live_decisions')
            AND relrowsecurity
       )
       AND NOT has_table_privilege('anon', 'public.ncaabw_live_decisions', 'SELECT')
       AND NOT has_table_privilege('anon', 'public.ncaabw_live_decisions', 'INSERT')
       AND NOT has_table_privilege('anon', 'public.ncaabw_live_decisions', 'UPDATE')
       AND NOT has_table_privilege('anon', 'public.ncaabw_live_decisions', 'DELETE')
       AND NOT has_table_privilege('authenticated', 'public.ncaabw_live_decisions', 'SELECT')
       AND NOT has_table_privilege('authenticated', 'public.ncaabw_live_decisions', 'INSERT')
       AND NOT has_table_privilege('authenticated', 'public.ncaabw_live_decisions', 'UPDATE')
       AND NOT has_table_privilege('authenticated', 'public.ncaabw_live_decisions', 'DELETE')
    THEN
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.ncaabw_live_decisions (
    id                BIGSERIAL PRIMARY KEY,
    game_id           TEXT NOT NULL,
    model_id          TEXT NOT NULL,
    game_date         TEXT,
    decided_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetch_at          TIMESTAMPTZ,
    outcome           TEXT NOT NULL,
    reason            TEXT,
    market            TEXT,
    book              TEXT,
    side              TEXT,
    line              DOUBLE PRECISION,
    price             DOUBLE PRECISION,
    ev                DOUBLE PRECISION,
    p_win             DOUBLE PRECISION,
    p_push            DOUBLE PRECISION,
    model_mean        DOUBLE PRECISION,
    model_sd          DOUBLE PRECISION,
    mu_pre            DOUBLE PRECISION,
    t_pre             DOUBLE PRECISION,
    quote_at          TIMESTAMPTZ,
    h_pts             INTEGER,
    a_pts             INTEGER,
    play_lag_s        DOUBLE PRECISION,
    artifact_version  TEXT,
    offers            JSONB,
    CONSTRAINT ncaabw_live_decisions_outcome
      CHECK (outcome IN ('bet', 'no_bet', 'declined', 'missed', 'skipped', 'carried'))
  );
  CREATE UNIQUE INDEX IF NOT EXISTS uq_ncaabw_live_decisions_one_decision
    ON public.ncaabw_live_decisions (game_id, model_id)
    WHERE outcome IN ('bet', 'no_bet', 'declined', 'missed');
  CREATE INDEX IF NOT EXISTS ncaabw_live_decisions_date_idx ON public.ncaabw_live_decisions (game_date);

  ALTER TABLE public.ncaabw_live_decisions ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.ncaabw_live_decisions FROM anon;
  REVOKE ALL ON public.ncaabw_live_decisions FROM authenticated;
END
$mig$;
