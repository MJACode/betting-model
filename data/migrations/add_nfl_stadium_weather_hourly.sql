-- The hourly Open-Meteo ISSUED-forecast series per NFL stadium, one row per
-- (stadium, hour). 2026-09-20: this is the content of nfl/data/weather_cache,
-- which held 44 JSON files (117,192 hours, 2024 and 2025 seasons) on one
-- laptop and nowhere else, and which tests/test_everything_in_supabase.py
-- has failed on since it was written. CLAUDE.md section 1b: a local file is
-- a cache of Supabase or it is a bug.
--
-- WHAT EACH ROW HOLDS. For one stadium and one UTC hour: the assembled
-- best-estimate wind (near-analysis, ~0-24h lead -- NEVER a feature, it
-- leaks), the wind forecast for that hour AS ISSUED 1..7 days earlier
-- (leakage-free; the NFL wind rule's evidence), and the assembled
-- temperature and precipitation. Units are what the module requests: mph,
-- Fahrenheit, mm. `nfl/data_ingest/weather.py` is the reader and documents
-- the three endpoints.
--
-- `game_weather_issued` is the NCAAF sibling, keyed per (game, lead) at the
-- kickoff hour. This table is the raw hourly series the NFL replays run
-- `wind_at_kickoff` over, keyed per (stadium, hour), so it stays a separate
-- table rather than a second shape in that one.
--
-- COVERAGE. Open-Meteo's issued archive starts 2024-01-18; nothing earlier
-- can be filled. Internal research data: RLS on, privileges revoked, no read
-- policy. Written by data/ingestors/nfl_weather_cache_import.py, keyed on
-- `source` so a re-run imports nothing already stored.
DO $$
BEGIN
  IF to_regclass('public.nfl_stadium_weather_hourly') IS NULL THEN
    CREATE TABLE public.nfl_stadium_weather_hourly (
      stadium_id        TEXT        NOT NULL,   -- nflverse stadium_id (BUF00, ...)
      ts                TIMESTAMPTZ NOT NULL,   -- the hour, UTC
      wind_analysis_mph NUMERIC,                -- wind_speed_10m: near-analysis, leaks
      fc_d1_mph         NUMERIC,                -- wind_speed_10m_previous_day1 .. 7:
      fc_d2_mph         NUMERIC,                -- the forecast for `ts` issued N days
      fc_d3_mph         NUMERIC,                -- before it
      fc_d4_mph         NUMERIC,
      fc_d5_mph         NUMERIC,
      fc_d6_mph         NUMERIC,
      fc_d7_mph         NUMERIC,
      temp_f            NUMERIC,                -- temperature_2m
      precip_mm         NUMERIC,                -- precipitation
      source            TEXT        NOT NULL,   -- 'nfl_weather_cache|file=<name>'
      fetched_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (stadium_id, ts)
    );
    CREATE INDEX idx_nfl_stadium_weather_hourly_source
      ON public.nfl_stadium_weather_hourly (source);
    ALTER TABLE public.nfl_stadium_weather_hourly ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nfl_stadium_weather_hourly FROM anon, authenticated;
  END IF;
END $$;
