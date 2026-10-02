-- ESPN injury `date` on injuries.status_ts.
--
-- WHY. NFL prop veto (models/nfl_prop_injury_veto) refuses Out/Doubtful
-- only when that status predates the quote. Without a source timestamp
-- the gate cannot tell "the player was already Out when this line was
-- taken" from "we learned he was Out after we would have bet", and the
-- second case is a look-ahead leak. ESPN's core injury doc carries
-- `date` (`2026-09-12T18:14Z`, measured 2026-09-14 on KC's list). The
-- ingest writes it here. Other sports get the column too (same INSERT);
-- only NFL scoring reads it.
--
-- NULLABLE: every row written before this exists keeps NULL, and the
-- veto fails OPEN on a missing clock rather than guessing.
--
-- IDEMPOTENT. The column check returns before ALTER TABLE. ADD COLUMN
-- IF NOT EXISTS still takes AccessExclusiveLock on every execution,
-- including the one that finds the column already there.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = 'injuries'
       AND column_name = 'status_ts'
  ) THEN
    RAISE NOTICE 'injuries.status_ts already present - skipping';
    RETURN;
  END IF;

  ALTER TABLE public.injuries ADD COLUMN IF NOT EXISTS status_ts TEXT;
END $$;
