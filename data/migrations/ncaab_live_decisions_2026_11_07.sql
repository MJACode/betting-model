-- The NCAAB in-play loop's decision ledger (models/ncaab_live_loop.py).
--
-- One DECISION row per (game, model): the first decision of each in-play rule
-- on each game, bet or not (a partial unique index, below). The graded rule
-- decides ONCE per game and rule, at the first fetch holding an eligible
-- quote, and a decision that does not clear the night's cut SPENDS the rule
-- (docs/sports/ncaab.md, "In play"). A pick row exists only for a bet, so
-- without this table a restart would forget a no-bet decision and decide the
-- same rule again at a later fetch: a bet the grade never made. A fetch the
-- loop could not decide on (ESPN unreadable or publishing late, the odds feed,
-- an error) writes a 'skipped' row; a fetch with no eligible quote a
-- 'carried' row. The loop refuses to decide anything while this table is
-- missing.
--
-- It is also the audit trail of what the model saw: the state, the priors,
-- the mean and spread, every priced offer, the night's cut and how many bets
-- the night already held (night_cut, slate_games, night_bets_before), and the
-- seconds between the newest ESPN play and the decision (play_lag_s).
--
-- anon and authenticated get nothing; the worker's DATABASE_URL writes it.
-- One DO block: data/view_migrations.py runs each file as one statement, on
-- every pass. The early return answers "already applied" on the property this
-- migration establishes (the table exists, RLS on, no anon/authenticated
-- privilege), read through to_regclass so a fresh database never casts a
-- missing relation.

DO $mig$
BEGIN
  IF to_regclass('public.ncaab_live_decisions') IS NOT NULL THEN
    IF EXISTS (
         SELECT 1 FROM pg_class
          WHERE oid = to_regclass('public.ncaab_live_decisions')
            AND relrowsecurity
       )
       AND NOT has_table_privilege('anon', 'public.ncaab_live_decisions', 'SELECT')
       AND NOT has_table_privilege('anon', 'public.ncaab_live_decisions', 'INSERT')
       AND NOT has_table_privilege('anon', 'public.ncaab_live_decisions', 'UPDATE')
       AND NOT has_table_privilege('anon', 'public.ncaab_live_decisions', 'DELETE')
       AND NOT has_table_privilege('authenticated', 'public.ncaab_live_decisions', 'SELECT')
       AND NOT has_table_privilege('authenticated', 'public.ncaab_live_decisions', 'INSERT')
       AND NOT has_table_privilege('authenticated', 'public.ncaab_live_decisions', 'UPDATE')
       AND NOT has_table_privilege('authenticated', 'public.ncaab_live_decisions', 'DELETE')
    THEN
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.ncaab_live_decisions (
    id                BIGSERIAL PRIMARY KEY,
    game_id           TEXT NOT NULL,
    model_id          TEXT NOT NULL,
    game_date         TEXT,
    decided_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetch_at          TIMESTAMPTZ,
    outcome           TEXT NOT NULL,
    reason            TEXT,
    phase             TEXT,
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
    night_cut         DOUBLE PRECISION,
    slate_games       INTEGER,
    night_bets_before INTEGER,
    period            INTEGER,
    clock_s           DOUBLE PRECISION,
    h_pts             INTEGER,
    a_pts             INTEGER,
    play_lag_s        DOUBLE PRECISION,
    artifact_version  TEXT,
    offers            JSONB,
    CONSTRAINT ncaab_live_decisions_outcome
      CHECK (outcome IN ('bet', 'no_bet', 'declined', 'skipped', 'carried'))
  );
  CREATE UNIQUE INDEX IF NOT EXISTS uq_ncaab_live_decisions_one_decision
    ON public.ncaab_live_decisions (game_id, model_id)
    WHERE outcome IN ('bet', 'no_bet', 'declined');
  CREATE INDEX IF NOT EXISTS ncaab_live_decisions_date_idx ON public.ncaab_live_decisions (game_date);

  ALTER TABLE public.ncaab_live_decisions ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.ncaab_live_decisions FROM anon;
  REVOKE ALL ON public.ncaab_live_decisions FROM authenticated;
END
$mig$;
