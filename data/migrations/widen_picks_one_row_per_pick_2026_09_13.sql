-- widen_picks_one_row_per_pick (2026-09-13, Matt / Reviewer #699 A2)
--
-- THE BUG. uq_picks_one_row_per_pick was
--   (game_date, model_id, game_id, COALESCE(player_id, ''), pick_side)
-- WHERE is_live IS NOT TRUE.
-- nfl_prop_market writes player_key + prop_market and leaves player_id NULL
-- (the same identity tracking/publish_keys.py already special-cases). A
-- whole game's unders therefore share one key, and the third INSERT is an
-- IntegrityError that aborts the card. Live at 2026-09-13 17:27 UTC:
--
--   Key (..., COALESCE(player_id, ''), pick_side)=
--     (2026-09-13, nfl_prop_market, NFL_2026_01_DAL_NYG, , under)
--   already exists.
--
-- THE FIX. Widen the index by KEY_PARTS: player_id, player_key, prop_market
-- (tracking/publish_keys.KEY_PARTS), keeping game_date and pick_side. A
-- player_id-only row (every distributional prop, every game-level model)
-- still coalesces the two new columns to '', so its uniqueness is unchanged.
--
-- WHY A NEW FILE. picks_one_row_per_pick.sql already ran in production; its
-- guard is "index exists" and would skip forever on the narrow definition.
-- This file asks about the PROPERTY (indexdef contains player_key AND
-- prop_market), never about its own past output.
--
-- SWAP, NOT DROP-THEN-CREATE. CREATE the wide index under a temp name
-- first, then DROP the narrow one, then RENAME. The old unique index stays
-- until the new one exists, so there is no window without uniqueness.
-- CREATE UNIQUE INDEX is not CONCURRENT (a DO $$ block is one transaction;
-- CONCURRENTLY cannot run inside one) — the same lock the 2026-09-05
-- migration took. Call this out: writes to picks block for the build.
--
-- SELF-HEALING. If the table has true duplicates on the NEW key, this
-- logs and does nothing (and does not drop the old index). scripts/
-- dedupe_picks.py partitions on unique_row_sql() now; --apply then a
-- later pass creates the wide index.
--
-- Single statement, as data/view_migrations.py requires.

DO $mig$
DECLARE
  def text;
  dupes bigint;
  has_v2 boolean;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'picks'
       AND column_name = 'player_key'
  ) OR NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'picks'
       AND column_name = 'prop_market'
  ) THEN
    RAISE NOTICE 'picks.player_key / prop_market missing - skipping';
    RETURN;
  END IF;

  SELECT indexdef INTO def FROM pg_indexes
   WHERE schemaname = 'public' AND indexname = 'uq_picks_one_row_per_pick';

  IF def IS NOT NULL
     AND position('player_key' in def) > 0
     AND position('prop_market' in def) > 0 THEN
    RAISE NOTICE 'uq_picks_one_row_per_pick already includes player_key and '
                 'prop_market - skipping';
    RETURN;
  END IF;

  SELECT count(*) INTO dupes FROM (
    SELECT 1 FROM picks
     WHERE is_live IS NOT TRUE
     GROUP BY game_date, model_id, game_id,
              COALESCE(player_id, ''), COALESCE(player_key, ''),
              COALESCE(prop_market, ''), pick_side
    HAVING count(*) > 1
  ) d;

  IF dupes > 0 THEN
    RAISE NOTICE 'picks still carries % duplicated key(s) on the widened '
                 'identity - run python -m scripts.dedupe_picks --apply, '
                 'then this replaces the index on the next pass', dupes;
    RETURN;
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM pg_indexes
     WHERE schemaname = 'public'
       AND indexname = 'uq_picks_one_row_per_pick_v2'
  ) INTO has_v2;

  IF NOT has_v2 THEN
    CREATE UNIQUE INDEX uq_picks_one_row_per_pick_v2
        ON public.picks (game_date, model_id, game_id,
                         COALESCE(player_id, ''),
                         COALESCE(player_key, ''),
                         COALESCE(prop_market, ''),
                         pick_side)
     WHERE is_live IS NOT TRUE;
  END IF;

  DROP INDEX IF EXISTS public.uq_picks_one_row_per_pick;
  ALTER INDEX public.uq_picks_one_row_per_pick_v2
    RENAME TO uq_picks_one_row_per_pick;

  RAISE NOTICE 'uq_picks_one_row_per_pick widened with player_key and '
               'prop_market - nfl_prop_market null player_id rows no longer '
               'collide per side';
END
$mig$;
