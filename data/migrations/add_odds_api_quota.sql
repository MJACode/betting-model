-- Odds API credit telemetry (applied 2026-08-18 via Supabase MCP as
-- migration add_odds_api_quota — this file is the recoverable copy).
--
-- One row per UTC day holding the LATEST x-requests-used / x-requests-remaining
-- observed on any Odds API response (last write wins, so a mid-day credit
-- top-up or billing reset is reflected immediately). Written by
-- data/ingestors/odds_quota.py from both odds ingestors; read by the
-- odds_api_credits check in tracking/system_health.py and by Claude mobile
-- ("how many Odds API credits are left?").
--
-- Daily burn rate = day-over-day diff of requests_used (resets each billing
-- period).

CREATE TABLE IF NOT EXISTS public.odds_api_quota (
    quota_date         TEXT PRIMARY KEY,   -- UTC date of the observation
    requests_used      NUMERIC,
    requests_remaining NUMERIC,
    observed_at        TEXT NOT NULL
);

ALTER TABLE public.odds_api_quota ENABLE ROW LEVEL SECURITY;

-- Read-only for the app / Claude mobile; the pipeline writes via the
-- service-role DATABASE_URL, which bypasses RLS.
CREATE POLICY "anon read odds_api_quota" ON public.odds_api_quota
    FOR SELECT TO anon, authenticated USING (true);
