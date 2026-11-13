-- DraftKings' own in-play board for every sport with an in-play model
-- (mike, 2026-11-13: "Move everything over to the fast way"): the columns
-- dk_live_reads needs beyond NCAAB's spread and total.
--
--   home_ml / away_ml   the main moneyline, on OUR games row's sides (the NFL
--                       late-game leader and the NCAAF win-probability models
--                       bet it)
--   possession          football: 'home' / 'away', on our sides
--   down / distance     football: the down and the yards to go
--   yardline            football: DraftKings' own number, stored as given; its
--                       scale is not yet measured against ESPN, so no model
--                       reads it yet
--
-- Written by data/ingestors/dk_live_board.py on mike's machine; the feed
-- refuses to start until these exist. One DO block: data/view_migrations.py
-- runs each file as one statement, on every pass, and the early return answers
-- "already applied" on the property this migration establishes (all six
-- columns exist), read through to_regclass so a fresh database never casts a
-- missing relation.

DO $mig$
BEGIN
  IF to_regclass('public.dk_live_reads') IS NULL THEN
    RETURN;                       -- dk_live_reads_2026_11_12.sql runs first on a fresh database
  END IF;
  IF (SELECT COUNT(*) FROM information_schema.columns
       WHERE table_schema = 'public' AND table_name = 'dk_live_reads'
         AND column_name IN ('home_ml', 'away_ml', 'possession', 'down', 'distance', 'yardline')) = 6 THEN
    RETURN;
  END IF;

  ALTER TABLE public.dk_live_reads ADD COLUMN IF NOT EXISTS home_ml    DOUBLE PRECISION;
  ALTER TABLE public.dk_live_reads ADD COLUMN IF NOT EXISTS away_ml    DOUBLE PRECISION;
  ALTER TABLE public.dk_live_reads ADD COLUMN IF NOT EXISTS possession TEXT;
  ALTER TABLE public.dk_live_reads ADD COLUMN IF NOT EXISTS down       INTEGER;
  ALTER TABLE public.dk_live_reads ADD COLUMN IF NOT EXISTS distance   INTEGER;
  ALTER TABLE public.dk_live_reads ADD COLUMN IF NOT EXISTS yardline   INTEGER;
END
$mig$;
