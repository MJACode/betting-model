-- Best available price across config.BEST_LINE_BOOKMAKERS at score time.
-- Applied to Supabase 2026-08-28 as migration `add_best_line_columns_to_picks`.
--
-- DISPLAY + BET only. A pick's edge, its BET/AVOID call, its Kelly stake, its
-- settled P&L and its CLV all still measure against DraftKings, because every
-- threshold in docs/thresholds.md was swept on DK-implied edge and best-of-N
-- pricing runs ~2pp cheaper in implied probability (measured 2026-08-28 over 92
-- MLB games) -- adopting it as the qualifying price would loosen every cut by
-- that much without anyone deciding to.
--
-- best_edge is recorded so the true EV of the bet actually placed is visible,
-- and so the picks table accumulates real best-price history to re-sweep the
-- thresholds against later.
ALTER TABLE public.picks
  ADD COLUMN IF NOT EXISTS best_book         TEXT,
  ADD COLUMN IF NOT EXISTS best_odds         NUMERIC,
  ADD COLUMN IF NOT EXISTS best_implied_prob NUMERIC,
  ADD COLUMN IF NOT EXISTS best_edge         NUMERIC,
  ADD COLUMN IF NOT EXISTS best_bet_link     TEXT;
