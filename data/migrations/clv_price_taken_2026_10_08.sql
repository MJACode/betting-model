-- CLV at the price taken (mike, 2026-10-08: "grade CLV at the price taken").
--
-- Through 2026-10-08, _capture_clv graded the bet at DraftKings whenever the row
-- carried a DraftKings price: dk_odds against a DraftKings lock snapshot, even
-- when the pick was decided and settled at another book. From this change the
-- bet is COALESCE(decision_odds, dk_odds) at the book it was taken
-- (paper_tracker._bet_price_and_book): decision_book, else the book the label
-- names (market-relative prop cards, NFL wind/opener cards), else DraftKings.
--
-- WHAT THIS DOES, in one idempotent statement (data/view_migrations.py runs it
-- on every pass; every DDL is behind a guard on the property it establishes,
-- so the no-op path fires no DDL event):
--
--   1. picks.clv_bet_book: the book the bet side was graded at. Every capture
--      writes it from this change on. picks_log is untouched: log_picks_changes()
--      copies named columns and no clv_* column is among them.
--
--   2. Stamps clv_method = 'graded_at_dk_legacy' on captured rows whose bet was
--      taken somewhere other than DraftKings and that were graded at DraftKings:
--        - dk_odds present and decision_book not DraftKings
--          (153 at a different price + 51 at the same price, 2026-10-08), and
--        - the NFL cards whose label names a book other than DK.
--      Rows with no DraftKings price (30, 2026-10-08) and the market-relative
--      prop cards were already graded at the price taken and are not stamped.
--      v_public_track_record, model_quality and the pedigree average only
--      no_vig / zero_vig, so a stamped row leaves the published average until
--      _backfill_clv re-measures it, and returns with the new number.
--
-- THE GUARD IS clv_bet_book IS NULL, never clv_captured_at. A recomputed row
-- carries clv_bet_book, so this UPDATE stops matching it; a row the recompute
-- cannot re-measure is marked the same way and keeps the legacy stamp. Nulling
-- clv_captured_at here would re-null on every pass, forever.

DO $mig$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'picks'
                    AND column_name = 'clv_bet_book') THEN
    ALTER TABLE public.picks ADD COLUMN clv_bet_book TEXT;
    COMMENT ON COLUMN public.picks.clv_bet_book IS
      'Book the CLV bet side was graded at: the book the pick was taken at '
      '(decision_book, else the label book, else draftkings). Its lock two-way '
      'at created_at de-vigs the bet when it shows the price taken. NULL on rows '
      'captured before 2026-10-08. docs/clv.md.';
    RAISE NOTICE 'picks.clv_bet_book added';
  END IF;

  UPDATE public.picks p
     SET clv_method = 'graded_at_dk_legacy'
   WHERE p.clv_captured_at IS NOT NULL
     AND p.clv_bet_book IS NULL
     AND p.clv_method IN ('no_vig', 'zero_vig', 'raw_one_way')
     AND p.signal_type = 'BET'
     AND p.is_live IS NOT TRUE
     AND p.game_date >= '2026-09-09'
     AND (   (p.dk_odds IS NOT NULL
              AND p.decision_book IS NOT NULL
              AND lower(p.decision_book) <> 'draftkings')
          OR (p.model_id IN ('nfl_wind_totals', 'nfl_opener_spread')
              AND p.decision_book IS NULL
              AND upper(substring(p.pick_label from ',\s*([A-Za-z_]+)\)')) <> 'DK'));
END $mig$;
