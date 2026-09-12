-- Kalshi NCAAF event code -> our games row. The join `kalshi_game_markets`
-- deliberately does not carry (session 280, 2026-09-11).
--
-- Kalshi's event code (`26SEP12ARKUTAH`, shared by the winner, total and
-- spread series for one game) names a date and two team codes. The winner
-- series' two YES contracts carry the team NAMES in `yes_sub_title`
-- ("Arkansas", "Utah"), which the school resolver turns into CFBD names, and
-- the games row is then found by date (±1 day, the ET/UTC split) and the
-- unordered school pair. Kalshi does not say who is home, so the pair is
-- unordered by design and the games row supplies home/away.
--
-- One row per event code, refreshed by the recorder after each snapshot.
-- `game_id` NULL means "not resolved yet": an FCS-only game, a name the map
-- lacks, or a game the odds feed has not created. The labels are kept so an
-- unresolved row can be read and the map extended.
DO $$
BEGIN
  IF to_regclass('public.kalshi_ncaaf_events') IS NULL THEN
    CREATE TABLE public.kalshi_ncaaf_events (
      event_code    TEXT PRIMARY KEY,
      game_date     DATE NOT NULL,
      label_a       TEXT,
      label_b       TEXT,
      school_a      TEXT,
      school_b      TEXT,
      game_id       TEXT,
      resolved_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX kalshi_ncaaf_events_game ON public.kalshi_ncaaf_events (game_id);
    ALTER TABLE public.kalshi_ncaaf_events ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.kalshi_ncaaf_events FROM anon, authenticated;
  END IF;
END $$;
