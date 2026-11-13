-- Live scores for the Scoreboard: NFL, NBA and NHL.
--
-- Matt, 2026-10-29: the Scoreboard shows every game for a sport, live games
-- and scores included. MLB and NCAAF already store in-progress state. These
-- three stored nothing until `games` got the final score.
--
-- One row per game, the latest state, written by
-- data/ingestors/live_scoreboard.py (the `live_scoreboard` poller job) from
-- ESPN's site scoreboard. Only 'in' and 'post' games are written. The app
-- reads it directly (declared in data/anon_readable.py).
--
-- Runs on every migration pass, so the guard is the property it creates:
-- the table, its SELECT policy and the anon grant. Once all three exist it
-- returns on a catalog read and issues no DDL (operations.md: DDL on every
-- pass forces a PostgREST schema reload). Does not touch picks, odds or the
-- record.
DO $$
BEGIN
  IF to_regclass('public.live_scoreboard') IS NOT NULL
     AND EXISTS (
       SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'live_scoreboard'
          AND policyname = 'anon read live_scoreboard')
     AND has_table_privilege('anon', 'public.live_scoreboard', 'SELECT')
  THEN
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.live_scoreboard (
    game_id      text PRIMARY KEY,
    sport        text NOT NULL,
    game_date    text NOT NULL,
    event_id     text,
    state        text NOT NULL CHECK (state IN ('in', 'post')),
    home_score   integer,
    away_score   integer,
    period       integer,
    clock_label  text,
    situation    text,
    possession   text CHECK (possession IN ('home', 'away')),
    snapshot_at  timestamptz NOT NULL,
    source       text NOT NULL DEFAULT 'espn_site'
  );
  CREATE INDEX IF NOT EXISTS live_scoreboard_date_idx
    ON public.live_scoreboard (game_date);

  ALTER TABLE public.live_scoreboard ENABLE ROW LEVEL SECURITY;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'live_scoreboard'
       AND policyname = 'anon read live_scoreboard'
  ) THEN
    CREATE POLICY "anon read live_scoreboard"
      ON public.live_scoreboard
      FOR SELECT
      TO anon, authenticated
      USING (true);
  END IF;

  -- Supabase's default grant is ALL; REVOKE FROM PUBLIC does nothing.
  -- Revoke by name, then give the app SELECT only.
  REVOKE ALL ON public.live_scoreboard FROM anon, authenticated;
  GRANT SELECT ON public.live_scoreboard TO anon, authenticated;
END $$;
