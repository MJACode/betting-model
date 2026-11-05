-- The NBA in-play loop's decision ledger (models/nba_live_loop.py).
--
-- One DECISION row per (game, model): the first decision of each in-play rule
-- on each game, bet or not (a partial unique index, below). A fetch the loop
-- could not decide on (ESPN unreadable or publishing late, starters unknown,
-- an error, the odds feed or the credit cap) writes a 'skipped' row instead,
-- as many as happen, so a decision that moved off the grade's fetch says why.
-- A fetch with no eligible quote writes a 'carried' row (no decision; the next
-- hour tries again), so every game the loop looked at has rows and a game with
-- none was never looked at (tracking/nba_live_health.py reads that). The graded rule decides ONCE per game and rule, at the
-- first fetch holding an eligible quote, and a decision that does not clear
-- its cut SPENDS the rule (docs/nba_models_2026.md 7.3, G.decision_quotes).
-- A live pick row exists only for a bet, so without this table a restart in
-- the middle of a slate would forget a no-bet decision and decide the same
-- rule again at a later fetch: a bet the grade never made. The loop refuses
-- to decide anything while this table is missing.
--
-- It is also the audit trail of what the model saw: the state, the prior, the
-- mean and spread, every priced offer (offers), and the seconds between the
-- last ESPN play and the decision (play_lag_s).
--
-- anon and authenticated get nothing; the worker's DATABASE_URL writes it.
-- One DO block: data/view_migrations.py runs each file as one statement, on
-- every pass. The early return answers "already applied" on the property this
-- migration establishes (the table exists, RLS on, no anon/authenticated
-- privilege), read through to_regclass so a fresh database never casts a
-- missing relation.

DO $mig$
BEGIN
  IF to_regclass('public.nba_live_decisions') IS NOT NULL THEN
    IF EXISTS (
         SELECT 1 FROM pg_class
          WHERE oid = to_regclass('public.nba_live_decisions')
            AND relrowsecurity
       )
       AND NOT has_table_privilege('anon', 'public.nba_live_decisions', 'SELECT')
       AND NOT has_table_privilege('anon', 'public.nba_live_decisions', 'INSERT')
       AND NOT has_table_privilege('anon', 'public.nba_live_decisions', 'UPDATE')
       AND NOT has_table_privilege('anon', 'public.nba_live_decisions', 'DELETE')
       AND NOT has_table_privilege('authenticated', 'public.nba_live_decisions', 'SELECT')
       AND NOT has_table_privilege('authenticated', 'public.nba_live_decisions', 'INSERT')
       AND NOT has_table_privilege('authenticated', 'public.nba_live_decisions', 'UPDATE')
       AND NOT has_table_privilege('authenticated', 'public.nba_live_decisions', 'DELETE')
    THEN
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.nba_live_decisions (
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
    p_home            DOUBLE PRECISION,
    mu_pre            DOUBLE PRECISION,
    period            INTEGER,
    clock_s           DOUBLE PRECISION,
    h_pts             INTEGER,
    a_pts             INTEGER,
    play_lag_s        DOUBLE PRECISION,
    artifact_version  TEXT,
    offers            JSONB,
    CONSTRAINT nba_live_decisions_outcome
      CHECK (outcome IN ('bet', 'no_bet', 'declined', 'skipped', 'carried'))
  );
  CREATE UNIQUE INDEX IF NOT EXISTS uq_nba_live_decisions_one_decision
    ON public.nba_live_decisions (game_id, model_id)
    WHERE outcome IN ('bet', 'no_bet', 'declined');
  CREATE INDEX IF NOT EXISTS nba_live_decisions_date_idx ON public.nba_live_decisions (game_date);

  ALTER TABLE public.nba_live_decisions ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.nba_live_decisions FROM anon;
  REVOKE ALL ON public.nba_live_decisions FROM authenticated;
END
$mig$;
