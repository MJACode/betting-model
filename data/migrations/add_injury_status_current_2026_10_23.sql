-- Each player's CURRENT injury designation, one row per (sport, player).
--
-- WHY. Matt, 2026-10-23, off the Stats board: Romeo Doubs ranked #3 on NFL
-- Anytime TD while on Injured Reserve. The app had no injury feed at all, so
-- nothing on the row said he was not playing. `injuries` already held the
-- answer (Out / Injured Reserve, refreshed every pass), but it is an
-- append-only log -- 1.4M rows, a fresh snapshot per sport every ~50 min --
-- and "the newest row per player" over a log is a state table the WRITER
-- maintains, never a view the app computes (.claude/rules/data-integrity.md).
--
-- WRITTEN BY data/ingestors/injury_ingestor.py after each successful ESPN
-- pull: per (sport, team) present in the pull, the team's rows are replaced.
-- A team the pull did not return keeps its last rows, and the app ignores
-- anything whose `as_of` is older than its freshness window, so a feed outage
-- ages out instead of freezing a player as Out forever.
--
-- Only absences are stored (scenario A, never 'Active' or 'Returning').
-- `player_key` is data/name_match.normalize_player_name(player_name), the
-- same fold the app's normalizePlayerName applies -- the join it reads by.
--
-- IDEMPOTENT: guarded on the table's existence, so every pipeline pass after
-- the first is a no-op that takes no lock and fires no DDL event.
DO $$
BEGIN
  IF to_regclass('public.injury_status_current') IS NULL THEN
    CREATE TABLE public.injury_status_current (
      sport        TEXT NOT NULL,
      team         TEXT NOT NULL,
      player_key   TEXT NOT NULL,
      player_name  TEXT NOT NULL,
      player_id    TEXT,
      -- Canonical status from the ingestor: Out, Doubtful, Questionable,
      -- Day-To-Day, IL10, IL15, IL60.
      status       TEXT NOT NULL,
      -- ESPN's own designation where it is more specific than `status`
      -- ('Injured Reserve', 'Suspension').
      injury_type  TEXT,
      -- ESPN's injury `date`, as the log stores it (TEXT, may be NULL).
      status_ts    TEXT,
      -- When the ingestor last confirmed this row.
      as_of        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (sport, team, player_key)
    );

    -- Written by the pipeline as the table owner; read by the app's anon key.
    -- REVOKE names anon/authenticated rather than PUBLIC: Supabase's default
    -- privileges grant them BY NAME, so a PUBLIC-only revoke is a no-op.
    ALTER TABLE public.injury_status_current ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.injury_status_current FROM anon, authenticated;
    GRANT SELECT ON public.injury_status_current TO anon, authenticated;
    CREATE POLICY "anon read injury_status_current"
      ON public.injury_status_current FOR SELECT TO anon, authenticated USING (true);
  END IF;
END $$;
