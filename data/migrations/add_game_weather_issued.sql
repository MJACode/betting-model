-- Point-in-time ISSUED weather forecasts for NCAAF games, one row per
-- (game, lead in days). The train/serve repair for the totals model's wx_*
-- features (session 280, 2026-09-10).
--
-- WHY. `game_weather` holds Open-Meteo REANALYSIS for every historical NCAAF
-- game -- the weather that happened -- and the totals regression trained on
-- it. Production scores on the FORECAST `ingest_upcoming` writes a few days
-- out. A model fitted on truth and served a forecast overstates what weather
-- can tell it (docs/sports/ncaaf.md calls every historical weather edge "an
-- upper bound"; the NFL wind rule measured the same gap as 59.3% on observed
-- wind against 47.5% on the deployed lead-3 forecast). The NFL module already
-- pulls `*_previous_dayN` from historical-forecast-api.open-meteo.com; this
-- table is that series for college venues, so a refit can train on what the
-- scorer will actually see.
--
-- COVERAGE. Open-Meteo's issued-forecast archive starts 2024-01-18, so only
-- the 2024 and 2025 seasons can be filled; earlier training rows keep
-- reanalysis, and any experiment says so.
--
-- `game_weather` is untouched: it is the truth series and stays the record
-- of what happened. Internal research data: RLS on, privileges revoked, no
-- read policy.
DO $$
BEGIN
  IF to_regclass('public.game_weather_issued') IS NULL THEN
    CREATE TABLE public.game_weather_issued (
      game_id       TEXT        NOT NULL,
      lead_days     SMALLINT    NOT NULL,
      -- The forecast issued `lead_days` before the kickoff HOUR (UTC), read at
      -- that hour. Domes carry the same fixed 72 / 0 / 0 the backfill writes.
      temp_f        NUMERIC,
      wind_mph      NUMERIC,
      precip_mm     NUMERIC,
      kick_hour_utc SMALLINT,
      is_dome_game  SMALLINT    NOT NULL DEFAULT 0,
      fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (game_id, lead_days)
    );
    ALTER TABLE public.game_weather_issued ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.game_weather_issued FROM anon, authenticated;
  END IF;
END $$;
