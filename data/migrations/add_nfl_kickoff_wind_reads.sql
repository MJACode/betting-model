-- Kickoff-hour wind readings from the live NFL wind card, one row per game
-- per poll. 2026-10-11: nfl_wind_totals locked the under on the first hourly
-- Open-Meteo read at or above 11 mph. The threshold check now uses the
-- minimum over a covered 12-hour window (nfl/models/wind_totals.ruling_wind),
-- and this table is the window.
--
-- This is the forecast. It is not a pick. A game that never covers the window
-- has rows here and no row in `picks`.
--
-- Internal research data: RLS on, privileges revoked, no read policy. Written
-- by nfl/data_ingest/kickoff_wind_reads.py on each live poll. Idempotent: the
-- card also creates the table if this migration has not run yet, and a second
-- pass of either path is a no-op.
DO $$
BEGIN
  IF to_regclass('public.nfl_kickoff_wind_reads') IS NULL THEN
    CREATE TABLE public.nfl_kickoff_wind_reads (
      game_id     TEXT        NOT NULL,   -- nflverse id, the card's game_id
      observed_at TIMESTAMPTZ NOT NULL,   -- when this poll read the forecast
      wind_mph    NUMERIC     NOT NULL,   -- kickoff-hour wind_speed_10m, mph
      PRIMARY KEY (game_id, observed_at)
    );
    ALTER TABLE public.nfl_kickoff_wind_reads ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nfl_kickoff_wind_reads FROM anon, authenticated;
  END IF;
END $$;
