-- Period splits in scoreboard_splits_history (Matt, 2026-11-26: "Yes on splits").
--
-- Action Network's consensus splits each period (worker_jobs 1698627): NBA
-- halves and quarters, NFL / NCAAF first half and quarters, NCAAB halves, NHL
-- first period. data/ingestors/scoreboard_splits.py stores them under the odds
-- table's period names (h2h_q1, spreads_h1, totals_p1, ...), which the table's
-- market CHECK refused: it allowed only h2h / spreads / totals.
--
-- The check now allows those three and each with one period suffix. Every row
-- already stored satisfies it (a subset), and nothing else changes: same table,
-- same grants, append-only, worker-only.
--
-- Guarded on the property it creates: the named constraint
-- scoreboard_splits_history_market_period_check exists and the old one does
-- not. The ingestor reads the same catalog fact before fetching any period.
DO $$
BEGIN
  IF to_regclass('public.scoreboard_splits_history') IS NULL THEN
    RETURN;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_constraint
              WHERE conrelid = 'public.scoreboard_splits_history'::regclass
                AND conname = 'scoreboard_splits_history_market_period_check')
     AND NOT EXISTS (SELECT 1 FROM pg_constraint
                      WHERE conrelid = 'public.scoreboard_splits_history'::regclass
                        AND conname = 'scoreboard_splits_history_market_check')
  THEN
    RETURN;
  END IF;

  ALTER TABLE public.scoreboard_splits_history
    DROP CONSTRAINT IF EXISTS scoreboard_splits_history_market_check;
  ALTER TABLE public.scoreboard_splits_history
    DROP CONSTRAINT IF EXISTS scoreboard_splits_history_market_period_check;
  ALTER TABLE public.scoreboard_splits_history
    ADD CONSTRAINT scoreboard_splits_history_market_period_check
    CHECK (market ~ '^(h2h|spreads|totals)(_(h1|h2|q[1-4]|p1))?$');
END $$;
