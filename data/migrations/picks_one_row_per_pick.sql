-- picks_one_row_per_pick (2026-09-05)
--
-- ONE ROW PER PICK, enforced by the database.
--
-- Matt, 2026-09-05: "The same bet showed multiple times for a signal. It
-- should just be the first one?" -- eleven identical "Logan Allen Over 4.5
-- Hits" rows on the model detail screen, all WIN, all +$117.
--
-- The cause is fixed in models/scorer.py (both locks used to release when a
-- pick was SETTLED, so a doubleheader's finished game 1 unlocked a key its
-- game 2 commence_time still left scoreable). This is the backstop for every
-- other path -- two overlapping passes racing, a future scorer, a hand-run
-- backfill -- because a rule enforced only in Python is a rule that holds
-- until the next writer.
--
-- THE KEY IS THE PICK LOCK'S KEY: (game_date, model_id, game_id, player_id,
-- pick_side) on pre-game rows. Measured before shipping, over all 144,669
-- pre-game pick rows ever written: 63 violations, every one of them from this
-- bug and all MLB. Alternate lines do NOT violate it -- they are odds rows,
-- and the scorer still writes exactly one line per player and side (only 1
-- key in the last month carried two lines, itself a re-score after a released
-- lock). Live rows are excluded: the live lock and first_signal_repair own
-- that lane (564 live BETs, 0 duplicates).
--
-- SELF-HEALING, AND IT NEVER FIGHTS THE DATA. The index is created only once
-- the table is clean, so this file can sit in the active list from the moment
-- it merges: while duplicates remain it logs how many and does nothing, and
-- the first pass after scripts/dedupe_picks.py --apply creates it. That is the
-- guard-on-the-property rule from live_record_start_views_2026_09_01.sql -- it
-- asks about the invariant, not about its own past output.
--
-- Single statement, as data/view_migrations.py requires.

DO $mig$
DECLARE
  dupes bigint;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_indexes
              WHERE schemaname = 'public'
                AND indexname = 'uq_picks_one_row_per_pick') THEN
    RAISE NOTICE 'uq_picks_one_row_per_pick already present - skipping';
    RETURN;
  END IF;

  SELECT count(*) INTO dupes FROM (
    SELECT 1 FROM picks
     WHERE is_live IS NOT TRUE
     GROUP BY game_date, model_id, game_id, COALESCE(player_id, ''), pick_side
    HAVING count(*) > 1
  ) d;

  IF dupes > 0 THEN
    RAISE NOTICE 'picks still carries % duplicated key(s) - run '
                 'python -m scripts.dedupe_picks --apply, then this creates '
                 'the index on the next pass', dupes;
    RETURN;
  END IF;

  CREATE UNIQUE INDEX uq_picks_one_row_per_pick
      ON public.picks (game_date, model_id, game_id,
                       COALESCE(player_id, ''), pick_side)
   WHERE is_live IS NOT TRUE;
  RAISE NOTICE 'uq_picks_one_row_per_pick created - one row per pick is now '
               'enforced by the database';
END
$mig$;
