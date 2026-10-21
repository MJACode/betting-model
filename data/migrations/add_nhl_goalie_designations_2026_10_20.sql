-- Who each source says will start in goal for each NHL game, as it changed.
--
-- mike, 2026-10-20: "We should absolutely always know the goalie matchup
-- before making a bet as well." No NHL model may bet until both starting
-- goalies are confirmed (models/nhl_goalie_gate.py). nhl_goalie_stats holds
-- ONE row per team per game, written once at ~10:06Z from ESPN's probable
-- starter; ESPN's 'expected' / 'confirmed' flag was parsed and thrown away, so
-- nothing could say whether the goalie a pick was made on was ever confirmed.
-- The 6am goalie did not start in 65 of 251 team-games 2026-10-01..10-19.
--
-- APPEND-ONLY HISTORY, but for last_seen_at. data/ingestors/
-- nhl_goalie_designations.py inserts a row only when (player_name, status)
-- changed for (game_id, team, source) against the latest stored row, so the
-- table is the timeline: when ESPN first
-- listed a goalie, when it confirmed him, when DailyFaceoff agreed. Readers
-- take the latest row with DISTINCT ON over the index below.
--
--   source            'espn' (core API probableStartingGoalie) or 'dailyfaceoff'
--   status            lower case: 'confirmed', 'expected', 'likely',
--                     'unconfirmed', 'none' (the source lists the game but no
--                     starter for this team), or the source's own word
--   player_id         NHL id, resolved the way nhl_stats_ingestor resolves an
--                     ESPN name; NULL when it could not be
--   source_player_id  the source's own id for him (ESPN athlete id,
--                     DailyFaceoff goalie id); lets a poll skip re-fetching a
--                     name it already holds
--   last_seen_at      the last poll that read the source and found this row
--                     still standing (NULL = only at observed_at). The ONE
--                     column a poll updates in place: the gate refuses a
--                     confirmation ESPN has not re-read for
--                     config.NHL_GOALIE_READ_MAX_AGE_MIN, so a blind poll
--                     (ESPN blocking the worker) cannot leave an old
--                     confirmation standing all day.
--
-- Model input and audit trail, never read by the app: RLS on, anon and
-- authenticated hold nothing (the pick_placement_checks shape). The worker's
-- DATABASE_URL owns it.
--
-- IDEMPOTENT. Once the table, its index, last_seen_at and RLS exist and the
-- API roles hold no privilege, this returns on a catalog read and takes no
-- lock. One DO block: data/view_migrations.py runs each file as one statement.
--
-- The early return reads the catalog through to_regclass, never a
-- 'rel'::regclass cast: a cast is resolved while the statement is planned and
-- errors when the table is absent, so a fresh database would never reach
-- CREATE (the defect #1014 fixed in social_post_queue). The privilege checks
-- run only inside that IF, because has_table_privilege errors on a missing
-- relation too.

DO $mig$
BEGIN
  IF to_regclass('public.nhl_goalie_designations') IS NOT NULL THEN
    IF to_regclass('public.idx_nhl_goalie_designations_latest') IS NOT NULL
       AND EXISTS (
         SELECT 1 FROM pg_class
          WHERE oid = to_regclass('public.nhl_goalie_designations')
            AND relrowsecurity
       )
       AND EXISTS (
         SELECT 1 FROM pg_attribute
          WHERE attrelid = to_regclass('public.nhl_goalie_designations')
            AND attname = 'last_seen_at' AND NOT attisdropped
       )
       AND NOT has_table_privilege('anon', 'public.nhl_goalie_designations', 'SELECT')
       AND NOT has_table_privilege('anon', 'public.nhl_goalie_designations', 'INSERT')
       AND NOT has_table_privilege('anon', 'public.nhl_goalie_designations', 'UPDATE')
       AND NOT has_table_privilege('anon', 'public.nhl_goalie_designations', 'DELETE')
       AND NOT has_table_privilege('authenticated', 'public.nhl_goalie_designations', 'SELECT')
       AND NOT has_table_privilege('authenticated', 'public.nhl_goalie_designations', 'INSERT')
       AND NOT has_table_privilege('authenticated', 'public.nhl_goalie_designations', 'UPDATE')
       AND NOT has_table_privilege('authenticated', 'public.nhl_goalie_designations', 'DELETE')
    THEN
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.nhl_goalie_designations (
    designation_id    BIGSERIAL PRIMARY KEY,
    game_id           TEXT NOT NULL,
    team              TEXT NOT NULL,
    player_id         TEXT,
    player_name       TEXT,
    source            TEXT NOT NULL,
    status            TEXT NOT NULL,
    source_player_id  TEXT,
    observed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at      TIMESTAMPTZ,
    CONSTRAINT nhl_goalie_designations_source CHECK (source IN ('espn', 'dailyfaceoff'))
  );
  ALTER TABLE public.nhl_goalie_designations ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;
  CREATE INDEX IF NOT EXISTS idx_nhl_goalie_designations_latest
    ON public.nhl_goalie_designations (game_id, team, source, observed_at DESC);

  REVOKE ALL ON public.nhl_goalie_designations FROM anon, authenticated;
  REVOKE ALL ON SEQUENCE public.nhl_goalie_designations_designation_id_seq FROM anon, authenticated;
  ALTER TABLE public.nhl_goalie_designations ENABLE ROW LEVEL SECURITY;
END
$mig$;
