-- The EuroLeague halftime loop's decision ledger (models/euroleague_live_loop.py,
-- model euroleague_live_spread_ht).
--
-- One FINAL row per (game, model), kept by a partial unique index: the
-- decision of the first price read of the halftime break that held an
-- eligible quote ('bet', 'no_bet' when its EV was under the cut, 'declined'
-- when a platform gate refused it), or 'missed' when the third quarter began
-- with no eligible quote seen. The graded rule decides ONCE per game and a
-- decision under the cut SPENDS it (docs/sports/euroleague.md, "Halftime
-- spread"). A pick row exists only for a bet, so this table is also where
-- every scored game's no-bet decision lives: the whole universe the model
-- priced can be graded from it. Without it a restart would forget a no-bet
-- decision and decide the game again at the next read: a bet the grade never
-- made. A read the loop could not decide on (EuroLeague's API unreadable or
-- disagreeing with itself, no pre-game number, the odds feed, an error)
-- writes a 'skipped' row; a read inside the break with no eligible quote a
-- 'carried' row. The loop refuses to decide anything while this table is
-- missing.
--
-- It is also the audit trail of what the model saw: the half-time score,
-- Pinnacle's pre-game numbers, the half's last shot and the game's first on
-- EuroLeague's shot chart, the mean and spread of the margin to come, and
-- every priced quote of the read.
--
-- anon and authenticated get nothing; the pollers' DATABASE_URL writes it.
-- One DO block: data/view_migrations.py runs each file as one statement, on
-- every pass. The early return answers "already applied" on the property this
-- migration establishes (the table exists, RLS on, no anon/authenticated
-- privilege), read through to_regclass so a fresh database never casts a
-- missing relation.

DO $mig$
BEGIN
  IF to_regclass('public.euroleague_live_decisions') IS NOT NULL THEN
    IF EXISTS (
         SELECT 1 FROM pg_class
          WHERE oid = to_regclass('public.euroleague_live_decisions')
            AND relrowsecurity
       )
       AND NOT has_table_privilege('anon', 'public.euroleague_live_decisions', 'SELECT')
       AND NOT has_table_privilege('anon', 'public.euroleague_live_decisions', 'INSERT')
       AND NOT has_table_privilege('anon', 'public.euroleague_live_decisions', 'UPDATE')
       AND NOT has_table_privilege('anon', 'public.euroleague_live_decisions', 'DELETE')
       AND NOT has_table_privilege('authenticated', 'public.euroleague_live_decisions', 'SELECT')
       AND NOT has_table_privilege('authenticated', 'public.euroleague_live_decisions', 'INSERT')
       AND NOT has_table_privilege('authenticated', 'public.euroleague_live_decisions', 'UPDATE')
       AND NOT has_table_privilege('authenticated', 'public.euroleague_live_decisions', 'DELETE')
    THEN
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.euroleague_live_decisions (
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
    prior_m           DOUBLE PRECISION,
    prior_t           DOUBLE PRECISION,
    quote_at          TIMESTAMPTZ,
    h_pts             INTEGER,
    a_pts             INTEGER,
    first_shot        TIMESTAMPTZ,
    last_q2_shot      TIMESTAMPTZ,
    api_read_at       TIMESTAMPTZ,
    artifact_version  TEXT,
    offers            JSONB,
    CONSTRAINT euroleague_live_decisions_outcome
      CHECK (outcome IN ('bet', 'no_bet', 'declined', 'missed', 'skipped', 'carried'))
  );
  CREATE UNIQUE INDEX IF NOT EXISTS uq_euroleague_live_decisions_one_decision
    ON public.euroleague_live_decisions (game_id, model_id)
    WHERE outcome IN ('bet', 'no_bet', 'declined', 'missed');
  CREATE INDEX IF NOT EXISTS euroleague_live_decisions_date_idx ON public.euroleague_live_decisions (game_date);

  ALTER TABLE public.euroleague_live_decisions ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.euroleague_live_decisions FROM anon;
  REVOKE ALL ON public.euroleague_live_decisions FROM authenticated;
END
$mig$;
