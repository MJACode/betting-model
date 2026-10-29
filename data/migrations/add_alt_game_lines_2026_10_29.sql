-- Alternate spreads and totals: the CURRENT ladder per game (Matt, 2026-10-29:
-- "yes" to fetching them once a day, for the betslip's game-line edit).
--
-- alt_game_lines: one row per (game, market, book, number), replaced per game
-- by data/ingestors/alt_game_lines.py on each fetch, in the same transaction
-- as that fetch's `odds` rows (the system of record, source
-- odds_api_alt_game_lines_live). It exists because `latest_odds` is keyed
-- (game_id, market, bookmaker) and would keep one arbitrary rung per book.
-- Same columns as v_latest_odds_all_books, plus `point` (the spread_home or
-- total_line the key is on), so the app reads it with the same column list.
-- market is 'alternate_spreads' or 'alternate_totals'; the app folds them into
-- 'spreads' / 'totals' (mobile/src/lib/queries.ts fetchGameLineRows).
--
-- Size: bounded by (games in a 3-day window) x books x rungs; the app reads
-- one game and one market at a time.
--
-- Returns on a catalog read once the table and its policy exist.
DO $$
BEGIN
  IF to_regclass('public.alt_game_lines') IS NOT NULL
     AND EXISTS (
       SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'alt_game_lines'
          AND policyname = 'anon read alt_game_lines')
  THEN
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.alt_game_lines (
    game_id      TEXT    NOT NULL REFERENCES public.games (game_id),
    game_date    TEXT    NOT NULL,
    sport        TEXT    NOT NULL,
    market       TEXT    NOT NULL CHECK (market IN ('alternate_spreads', 'alternate_totals')),
    bookmaker    TEXT    NOT NULL,
    point        DOUBLE PRECISION NOT NULL,
    spread_home  DOUBLE PRECISION,
    total_line   DOUBLE PRECISION,
    home_price   DOUBLE PRECISION,
    away_price   DOUBLE PRECISION,
    over_price   DOUBLE PRECISION,
    under_price  DOUBLE PRECISION,
    home_link    TEXT,
    away_link    TEXT,
    over_link    TEXT,
    under_link   TEXT,
    snapshot_at  TEXT,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, market, bookmaker, point)
  );

  ALTER TABLE public.alt_game_lines ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.alt_game_lines FROM anon, authenticated;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'alt_game_lines'
       AND policyname = 'anon read alt_game_lines'
  ) THEN
    CREATE POLICY "anon read alt_game_lines"
      ON public.alt_game_lines
      FOR SELECT
      TO anon, authenticated
      USING (true);
  END IF;
  GRANT SELECT ON public.alt_game_lines TO anon, authenticated;
END
$$;
