-- Migration: add_ncaaf_venues
-- Venue geography for NCAAF travel / altitude / surface features and weather.

-- NCAAF venues (CFBD /venues) — unlocks travel distance, timezone shift,
-- altitude, surface and crowd size, and gives the weather ingestor coordinates.
CREATE TABLE IF NOT EXISTS ncaaf_venues (
    venue_id     INTEGER PRIMARY KEY,
    name         TEXT,
    city         TEXT,
    state        TEXT,
    latitude     NUMERIC,
    longitude    NUMERIC,
    elevation_ft NUMERIC,
    capacity     INTEGER,
    grass        INTEGER,
    dome         INTEGER,
    updated_at   TEXT DEFAULT (NOW()::TEXT)
);
CREATE INDEX IF NOT EXISTS idx_ncaaf_venues_name ON ncaaf_venues(name);

ALTER TABLE games ADD COLUMN IF NOT EXISTS venue_id INTEGER;
ALTER TABLE ncaaf_venues ENABLE ROW LEVEL SECURITY;
