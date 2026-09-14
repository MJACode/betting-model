-- Honest CLV: stamp the formula, name the close book.
--
-- Through 2026-09-14, picks.clv_pct was raw one-sided implied on a single
-- DraftKings (or pick-book) close: american_to_implied_prob(close) -
-- american_to_implied_prob(bet). That number still has hold in it and
-- flatters vig-widening at close. The capture path now writes the
-- multiplicative no-vig close (docs/clv.md). Mixing the two definitions in
-- v_public_track_record.avg_clv_pct would silently change what Sharp Score
-- reads as pedigree.
--
-- clv_method:
--   raw_one_sided  legacy rows, until _capture_clv / _backfill_clv rewrite them
--   no_vig         two-way (or 3-way) multiplicative de-vig
--   zero_vig       Kalshi / Polymarket — already no-vig, not de-vigged again
--   raw_one_way    one-sided sportsbook quote; recorded, excluded from pedigree
--
-- clv_close_book is the book whose pre-game snapshot was the close (Pinnacle
-- when that snapshot exists). closing_dk_odds keeps the American on our side
-- (legacy name).
--
-- IDEMPOTENT: ADD COLUMN IF NOT EXISTS; the stamp only fills NULL method on
-- already-captured rows.

DO $$
BEGIN
  ALTER TABLE public.picks ADD COLUMN IF NOT EXISTS clv_method TEXT;
  ALTER TABLE public.picks ADD COLUMN IF NOT EXISTS clv_close_book TEXT;

  UPDATE public.picks
     SET clv_method = 'raw_one_sided'
   WHERE clv_captured_at IS NOT NULL
     AND clv_method IS NULL;

  COMMENT ON COLUMN public.picks.clv_pct IS
    'Probability-point CLV: (fair_close_p - fair_bet_p)*100, same-line only. '
    'fair_close_p is the multiplicative no-vig close except zero-vig books '
    '(kalshi) and one-way markets. fair_bet_p is no-vig at lock when the '
    'two-way matches dk_odds, else raw bet implied. NULL when the number moved. '
    'docs/clv.md.';
  COMMENT ON COLUMN public.picks.clv_method IS
    'How clv_pct was computed: no_vig | zero_vig | raw_one_way | raw_one_sided '
    '(legacy, pre-2026-09-14). Pedigree averages no_vig and zero_vig only.';
  COMMENT ON COLUMN public.picks.clv_close_book IS
    'Book whose last pre-game snapshot is the close (Pinnacle when present). '
    'closing_dk_odds holds that book''s American on our side.';
END $$;
