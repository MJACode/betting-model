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
-- IDEMPOTENT. ADD COLUMN IF NOT EXISTS still takes AccessExclusiveLock on
-- picks before it notices the column. Hourly run
-- b22f8e4fb9e34d27858c341e46ce635c on 2026-10-01 waited on picks (oid 17680)
-- for that lock until statement_timeout (2min). Columns are a catalog check.
-- The legacy stamp is an UPDATE (RowExclusiveLock) and runs only while a
-- captured row still has a NULL method. COMMENT takes
-- ShareUpdateExclusiveLock and runs only when the text differs.

DO $$
DECLARE
  c_pct text := col_description(
    'public.picks'::regclass,
    (SELECT attnum FROM pg_attribute
      WHERE attrelid = 'public.picks'::regclass
        AND attname = 'clv_pct' AND NOT attisdropped));
  c_method text := col_description(
    'public.picks'::regclass,
    (SELECT attnum FROM pg_attribute
      WHERE attrelid = 'public.picks'::regclass
        AND attname = 'clv_method' AND NOT attisdropped));
  c_book text := col_description(
    'public.picks'::regclass,
    (SELECT attnum FROM pg_attribute
      WHERE attrelid = 'public.picks'::regclass
        AND attname = 'clv_close_book' AND NOT attisdropped));
  want_pct CONSTANT text :=
    'Probability-point CLV: (fair_close_p - fair_bet_p)*100, same-line only. '
    'fair_close_p is the multiplicative no-vig close except zero-vig books '
    '(kalshi) and one-way markets. fair_bet_p is no-vig at lock when the '
    'two-way matches dk_odds, else raw bet implied. NULL when the number moved. '
    'docs/clv.md.';
  want_method CONSTANT text :=
    'How clv_pct was computed: no_vig | zero_vig | raw_one_way | raw_one_sided '
    '(legacy, pre-2026-09-14). Pedigree averages no_vig and zero_vig only.';
  want_book CONSTANT text :=
    'Book whose last pre-game snapshot is the close (Pinnacle when present). '
    'closing_dk_odds holds that book''s American on our side.';
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'picks'
       AND column_name = 'clv_method'
  ) THEN
    ALTER TABLE public.picks ADD COLUMN IF NOT EXISTS clv_method TEXT;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'picks'
       AND column_name = 'clv_close_book'
  ) THEN
    ALTER TABLE public.picks ADD COLUMN IF NOT EXISTS clv_close_book TEXT;
  END IF;

  -- Backfill only. A captured row with no method is still the legacy
  -- definition; once none remain this does not take RowExclusiveLock.
  IF EXISTS (
    SELECT 1 FROM public.picks
     WHERE clv_captured_at IS NOT NULL
       AND clv_method IS NULL
     LIMIT 1
  ) THEN
    UPDATE public.picks
       SET clv_method = 'raw_one_sided'
     WHERE clv_captured_at IS NOT NULL
       AND clv_method IS NULL;
  END IF;

  -- One copy of each comment. A second literal that drifted would rewrite
  -- the column on every pass (ShareUpdateExclusiveLock) after the first.
  IF c_pct IS DISTINCT FROM want_pct THEN
    EXECUTE 'COMMENT ON COLUMN public.picks.clv_pct IS ' || quote_literal(want_pct);
  END IF;
  IF c_method IS DISTINCT FROM want_method THEN
    EXECUTE 'COMMENT ON COLUMN public.picks.clv_method IS ' || quote_literal(want_method);
  END IF;
  IF c_book IS DISTINCT FROM want_book THEN
    EXECUTE 'COMMENT ON COLUMN public.picks.clv_close_book IS ' || quote_literal(want_book);
  END IF;
END $$;
