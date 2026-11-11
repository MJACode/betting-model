-- Scoreboard reads one NCAAF live row per game.
--
-- add_ncaaf_live_states.sql stored the state the live loop priced on and
-- left the table closed ("NO APP SURFACE"). Matt approved the Scoreboard
-- on 2026-10-28, which draws that state. The log stays out of .from()
-- calls. This view is the read: the latest change per game, joined to
-- games so the app can ask for a date. security_invoker, so the new
-- SELECT policy is what allows it. Measured 2026-10-28: 18,653 rows,
-- 379 games, latest seen_at 2026-10-28T03:22:38Z.
--
-- NFL has no equivalent table. The ESPN scoreboard is read in process
-- and not written here. This migration does not invent one.
DO $$
BEGIN
  IF to_regclass('public.ncaaf_live_states') IS NULL THEN
    RETURN;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'ncaaf_live_states'
       AND policyname = 'anon read ncaaf_live_states'
  ) THEN
    CREATE POLICY "anon read ncaaf_live_states"
      ON public.ncaaf_live_states
      FOR SELECT
      TO anon, authenticated
      USING (true);
  END IF;

  EXECUTE $view$
    CREATE OR REPLACE VIEW public.v_ncaaf_scoreboard_latest
    WITH (security_invoker = on) AS
    SELECT DISTINCT ON (s.game_id)
           s.game_id,
           g.game_date,
           s.seen_at AS snapshot_at,
           s.period,
           s.clock_seconds,
           s.home_score,
           s.away_score,
           s.possession,
           s.down,
           s.distance,
           s.yardline_100,
           s.raw_state
      FROM public.ncaaf_live_states s
      JOIN public.games g ON g.game_id = s.game_id
     ORDER BY s.game_id, s.seen_at DESC, s.state_id DESC
  $view$;

  EXECUTE 'GRANT SELECT ON public.v_ncaaf_scoreboard_latest TO anon, authenticated';
  EXECUTE 'GRANT SELECT ON public.ncaaf_live_states TO anon, authenticated';
END $$;
