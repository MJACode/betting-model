-- live_row_index_bets_only (2026-10-14)
--
-- THE BUG. uq_picks_one_live_row, as discord_post_one_pick_2026_10_14.sql
-- first created it, is unique over every non-DUPLICATE live row:
--   WHERE is_live IS TRUE
--     AND condition_status IS DISTINCT FROM 'DUPLICATE'
-- nfl/live_model/pick_writer.py writes the AVOID for a lane, then later
-- the BET, with INSERT ... ON CONFLICT DO NOTHING. The AVOID holds the
-- key, the BET conflicts, and DO NOTHING drops the bet. A later pass of
-- this file that only asked for signal_type = 'BET' would still leave a
-- voided live BET, and a live BET whose result is NO_ACTION, holding the
-- lane. uq_picks_one_bet_per_publish_lock already excludes both.
-- Measured read-only the same day on production: the index exists with
-- the wider predicate. One live BET is condition_status VOID (pick
-- 2476480, also result NO_ACTION). Eight more live BETs are result
-- NO_ACTION with a null condition_status. Zero identity groups have two
-- standing live BETs under the predicate this file builds, so the swap
-- will not skip.
--
-- THE FIX. The same key, limited to a standing BET:
--   signal_type = 'BET'
--   AND condition_status IS DISTINCT FROM 'DUPLICATE'
--   AND condition_status IS DISTINCT FROM 'VOID'
--   AND result IS DISTINCT FROM 'NO_ACTION'
-- A second standing live BET still conflicts (the dedupe). The AVOID
-- stays (nothing is deleted). A VOID or NO_ACTION row stays, and it no
-- longer occupies the key. Different sides still both insert.
--
-- WHY A NEW FILE. discord_post_one_pick_2026_10_14.sql guards the live
-- index on "name exists" and would skip forever on a definition it may
-- already have created. This file asks about the PROPERTY. The skip
-- requires signal_type = 'BET' as one phrase, plus the VOID and
-- NO_ACTION exclusions. Two separate position() checks would treat an
-- unrelated "signal_type" and an unrelated "BET" as done. A definition
-- that is BET-only, without VOID and NO_ACTION, is not done: this file
-- re-runs, and that earlier predicate must still be replaced.
--
-- SWAP, NOT DROP-THEN-CREATE. CREATE the index under a temp name first,
-- then DROP the old one, then RENAME. The old unique index stays until
-- the new one exists, so there is no window without the BET dedupe. A
-- leftover temp index from a killed pass is dropped before the create,
-- so a temp index built from an older predicate is not renamed into place.
--
-- NOT CONCURRENTLY. A DO block is one transaction, and
-- data/view_migrations.py runs each file with conn.execute + commit.
-- CREATE INDEX CONCURRENTLY cannot run inside that transaction. The
-- unique-index migrations in this directory (picks_one_row_per_pick.sql,
-- widen_picks_one_row_per_pick_2026_09_13.sql, the file this replaces)
-- use the same form. The worker applies this on the next
-- ACTIVE_MIGRATIONS pass. Matt does not run it by hand. Writes to picks
-- block for the build. The one index that was applied by hand is
-- picks_open_nonbet_index_2026_09_08.sql, which is not a unique index
-- and says so in its header.
--
-- lock_timeout bounds how long this waits to acquire a lock. It does not
-- cap the build. If the lock is not available in 10s the statement fails,
-- the runner rolls the file back, and the next pass retries.
--
-- SELF-HEALING. If two standing live BETs already share the key, this
-- logs and does nothing, and it does not drop the old index. The dupe
-- count uses the same predicate as the new index, so a VOID or NO_ACTION
-- row beside a standing BET is not a duplicate.
--
-- Single statement, as data/view_migrations.py requires.
-- Does not UPDATE picks. Does not write push_sent.

DO $mig$
DECLARE
  def    text;
  dupes  bigint;
BEGIN
  SET LOCAL lock_timeout = '10s';

  SELECT indexdef INTO def FROM pg_indexes
   WHERE schemaname = 'public' AND indexname = 'uq_picks_one_live_row';

  IF def IS NOT NULL
     AND position('signal_type = ''BET''' in def) > 0
     AND position('IS DISTINCT FROM ''DUPLICATE''' in def) > 0
     AND position('IS DISTINCT FROM ''VOID''' in def) > 0
     AND position('IS DISTINCT FROM ''NO_ACTION''' in def) > 0 THEN
    DROP INDEX IF EXISTS public.uq_picks_one_live_row_v2;
    RAISE NOTICE 'uq_picks_one_live_row already excludes VOID and NO_ACTION - skipping';
    RETURN;
  END IF;

  SELECT count(*) INTO dupes FROM (
    SELECT 1 FROM public.picks
     WHERE is_live IS TRUE
       AND signal_type = 'BET'
       AND condition_status IS DISTINCT FROM 'DUPLICATE'
       AND condition_status IS DISTINCT FROM 'VOID'
       AND result IS DISTINCT FROM 'NO_ACTION'
     GROUP BY game_date, model_id, game_id,
              COALESCE(player_id, ''), COALESCE(player_key, ''),
              COALESCE(prop_market, ''), pick_side
    HAVING count(*) > 1
  ) d;

  IF dupes > 0 THEN
    RAISE NOTICE 'uq_picks_one_live_row not narrowed: % live identity '
                 'group(s) still have two standing BETs', dupes;
    RETURN;
  END IF;

  DROP INDEX IF EXISTS public.uq_picks_one_live_row_v2;

  CREATE UNIQUE INDEX uq_picks_one_live_row_v2
      ON public.picks (game_date, model_id, game_id,
                       COALESCE(player_id, ''),
                       COALESCE(player_key, ''),
                       COALESCE(prop_market, ''),
                       pick_side)
   WHERE is_live IS TRUE
     AND signal_type = 'BET'
     AND condition_status IS DISTINCT FROM 'DUPLICATE'
     AND condition_status IS DISTINCT FROM 'VOID'
     AND result IS DISTINCT FROM 'NO_ACTION';

  DROP INDEX IF EXISTS public.uq_picks_one_live_row;
  ALTER INDEX public.uq_picks_one_live_row_v2
    RENAME TO uq_picks_one_live_row;

  RAISE NOTICE 'uq_picks_one_live_row narrowed to standing live BETs';
END
$mig$;
