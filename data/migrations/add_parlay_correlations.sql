-- Migration: add_parlay_correlations
-- Parlay leg-correlation coefficients for the mobile copula engine (Phase 2).
--
-- One canonical "+offense x +offense" rho per (sport, market-class pair, team
-- relationship). The app multiplies it by each leg's offense polarity to recover
-- the directed correlation. market_class_a <= market_class_b lexicographically so
-- lookups are order-independent. source='empirical' rows (populated by
-- scripts/estimate_parlay_correlations.py) overlay the app's bundled 'prior' map.
--
-- RLS on; anon SELECT (read-only reference data). Pipeline/estimator writes go
-- through the service-role DATABASE_URL, which bypasses RLS.

CREATE TABLE IF NOT EXISTS public.parlay_correlations (
    id              BIGSERIAL PRIMARY KEY,
    sport           TEXT NOT NULL,
    market_class_a  TEXT NOT NULL,
    market_class_b  TEXT NOT NULL,
    relationship    TEXT NOT NULL,   -- 'same' | 'opp' | 'na'
    rho             NUMERIC NOT NULL,
    source          TEXT NOT NULL DEFAULT 'empirical',
    n_pairs         BIGINT,
    updated_at      TEXT DEFAULT (now()::text),
    UNIQUE (sport, market_class_a, market_class_b, relationship)
);

ALTER TABLE public.parlay_correlations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon read parlay_correlations"
    ON public.parlay_correlations FOR SELECT TO anon, authenticated USING (true);

-- Seed empirical MLB coefficients (2019-2025 player_game_log x games; phi
-- coefficients of +offense-oriented binary outcomes, hits>=2 / starter Ks<=5 /
-- game total>8). Regenerate with scripts/estimate_parlay_correlations.py.
INSERT INTO public.parlay_correlations
    (sport, market_class_a, market_class_b, relationship, rho, source, n_pairs)
VALUES
    ('MLB','off_prop','off_prop','same',        0.0446,'empirical',1792720),
    ('MLB','off_prop','off_prop','opp',         0.0106,'empirical',1935124),
    ('MLB','game_total','off_prop','na',        0.1237,'empirical', 327372),
    ('MLB','game_total','pitching_prop','na',   0.1354,'empirical',  29235),
    ('MLB','off_prop','pitching_prop','opp',    0.0654,'empirical', 333974),
    ('MLB','off_prop','pitching_prop','same',  -0.0105,'empirical', 333945)
ON CONFLICT (sport, market_class_a, market_class_b, relationship)
DO UPDATE SET rho = EXCLUDED.rho, source = EXCLUDED.source,
              n_pairs = EXCLUDED.n_pairs, updated_at = now()::text;
