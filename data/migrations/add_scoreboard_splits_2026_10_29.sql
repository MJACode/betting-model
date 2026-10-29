-- % of bets and % of money per side, for the Scoreboard only.
--
-- Matt, 2026-10-29: the Scoreboard shows Odds, % Bets and % Money for a
-- chosen market. Written by data/ingestors/scoreboard_splits.py from Action
-- Network's free v2 scoreboard, one row per (game_id, market, side), the
-- latest pre-start split. Display only: public_betting stays MLB, because
-- the scorer copies that table onto every pick.
--
-- The guard is the property it creates: the table, its SELECT policy and the
-- anon grant. Once all three exist it returns on a catalog read and issues
-- no DDL. Does not touch picks, odds, public_betting or the record.
DO $$
BEGIN
  IF to_regclass('public.scoreboard_splits') IS NOT NULL
     AND EXISTS (
       SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'scoreboard_splits'
          AND policyname = 'anon read scoreboard_splits')
     AND has_table_privilege('anon', 'public.scoreboard_splits', 'SELECT')
  THEN
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.scoreboard_splits (
    game_id      text NOT NULL,
    sport        text NOT NULL,
    game_date    text NOT NULL,
    market       text NOT NULL CHECK (market IN ('h2h', 'spreads', 'totals')),
    side         text NOT NULL CHECK (side IN ('home', 'away', 'over', 'under')),
    bet_pct      numeric(5,1) CHECK (bet_pct BETWEEN 0 AND 100),
    money_pct    numeric(5,1) CHECK (money_pct BETWEEN 0 AND 100),
    line_value   numeric,
    snapshot_at  timestamptz NOT NULL,
    source       text NOT NULL DEFAULT 'action_network',
    PRIMARY KEY (game_id, market, side)
  );
  CREATE INDEX IF NOT EXISTS scoreboard_splits_date_idx
    ON public.scoreboard_splits (game_date);

  ALTER TABLE public.scoreboard_splits ENABLE ROW LEVEL SECURITY;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'scoreboard_splits'
       AND policyname = 'anon read scoreboard_splits'
  ) THEN
    CREATE POLICY "anon read scoreboard_splits"
      ON public.scoreboard_splits
      FOR SELECT
      TO anon, authenticated
      USING (true);
  END IF;

  REVOKE ALL ON public.scoreboard_splits FROM anon, authenticated;
  GRANT SELECT ON public.scoreboard_splits TO anon, authenticated;
END $$;
