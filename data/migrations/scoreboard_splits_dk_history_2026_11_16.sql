-- DraftKings' own splits on the Scoreboard, the opening split, and a history.
--
-- Matt, 2026-11-16 (PIT @ CIN screenshot against a competitor's DK splits):
-- the Scoreboard's % Bets / % Money were Action Network's consensus
-- pseudo-book, not DraftKings, and nothing kept a history, so no movement
-- arrow could be drawn and no shown value could be traced afterwards.
--
-- 1. scoreboard_splits gains open_bet_pct / open_money_pct / open_snapshot_at:
--    the first DraftKings split seen for the side, kept on every later pass.
--    The app's arrow compares the current split against it.
-- 2. scoreboard_splits_history: every split each source returned that differs
--    from the last one stored for it. Append-only (CLAUDE.md §1b: no data is
--    ever deleted). Worker-only: RLS on, nothing granted to anon.
--
-- The guard is the property it creates. Once the three columns, the table and
-- its lock-down exist it returns on a catalog read and issues no DDL. Does not
-- touch picks, odds, public_betting or the record.
DO $$
BEGIN
  IF EXISTS (
       SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'scoreboard_splits'
          AND column_name = 'open_line_value')
     AND to_regclass('public.scoreboard_splits_history') IS NOT NULL
     AND NOT has_table_privilege('anon', 'public.scoreboard_splits_history', 'SELECT')
  THEN
    RETURN;
  END IF;

  ALTER TABLE public.scoreboard_splits
    ADD COLUMN IF NOT EXISTS open_bet_pct     numeric(5,1),
    ADD COLUMN IF NOT EXISTS open_money_pct   numeric(5,1),
    ADD COLUMN IF NOT EXISTS open_snapshot_at timestamptz,
    -- The line the opening split was measured at, so the arrow can later be
    -- limited to an unmoved line if Matt chooses (UX review 2026-11-16).
    ADD COLUMN IF NOT EXISTS open_line_value  numeric;

  CREATE TABLE IF NOT EXISTS public.scoreboard_splits_history (
    id           bigserial PRIMARY KEY,
    game_id      text NOT NULL,
    sport        text NOT NULL,
    game_date    text NOT NULL,
    market       text NOT NULL CHECK (market IN ('h2h', 'spreads', 'totals')),
    side         text NOT NULL CHECK (side IN ('home', 'away', 'over', 'under')),
    bet_pct      numeric(5,1) CHECK (bet_pct BETWEEN 0 AND 100),
    money_pct    numeric(5,1) CHECK (money_pct BETWEEN 0 AND 100),
    line_value   numeric,
    odds         integer,
    source       text NOT NULL,
    snapshot_at  timestamptz NOT NULL,
    UNIQUE (game_id, market, side, source, snapshot_at)
  );
  CREATE INDEX IF NOT EXISTS scoreboard_splits_history_key_idx
    ON public.scoreboard_splits_history (game_id, source, market, side, snapshot_at DESC);

  ALTER TABLE public.scoreboard_splits_history ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.scoreboard_splits_history FROM anon, authenticated;
  REVOKE ALL ON SEQUENCE public.scoreboard_splits_history_id_seq FROM anon, authenticated;
END $$;
