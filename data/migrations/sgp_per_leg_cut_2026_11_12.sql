-- Migration: sgp_per_leg_cut_2026_11_12
-- Apply via Supabase MCP apply_migration (project ref vvprgnrmzeekokzkrkfu).
-- Not in ACTIVE_MIGRATIONS, the same as add_sgp_price_observations_2026_11_06.
--
-- Matt, 2026-11-12: a 5-leg WAS@NYG slip showed FanDuel +8037; FanDuel's own
-- slip said +3085. Two causes, both fixed in the app (mobile/src/lib/sgpPricing.ts):
--   1. The same-game cut was taken once per GAME, so five legs in one game got
--      the cut two legs get.
--   2. NFL had no leg correlations, so Daniels 2+ pass TDs, Diggs 4+ catches
--      and a Diggs TD were priced as unrelated.
-- The estimate is now
--   fair = (legs multiplied) / greatest(lift, 1)
--   1 + (fair - 1) x (1 - cut) ^ extra_legs
-- where lift is the correlation's effect on the joint chance and extra_legs
-- the legs past the first in each same-game group. This migration:
--   a. stores extra_legs and corr_lift with every entered price,
--   b. refits sgp_haircuts() per extra leg, after the lift,
--   c. records the 2026-11-12 FanDuel screenshot,
--   d. stores the NFL market-level correlations the app bundles
--      (mobile/src/lib/propCorrelation.ts), measured from nfl_player_game_log
--      2022 -> 2026-11-09 by scripts/estimate_parlay_correlations.py --sport NFL.

ALTER TABLE sgp_price_observations ADD COLUMN IF NOT EXISTS extra_legs INTEGER
    CHECK (extra_legs IS NULL OR extra_legs BETWEEN 1 AND 24);
ALTER TABLE sgp_price_observations ADD COLUMN IF NOT EXISTS corr_lift NUMERIC
    CHECK (corr_lift IS NULL OR (corr_lift > 0 AND corr_lift <= 10));

-- The 2026-11-06 seed: two 2-leg NBA games, 2 extra legs. The app had no
-- correlation for those (line) legs, so its lift was 1.
UPDATE sgp_price_observations
   SET extra_legs = 2, corr_lift = 1
 WHERE id = 1 AND device_id = 'seed-matt-2026-11-06' AND extra_legs IS NULL;

-- An added argument would make an OVERLOAD, and an app build already in the
-- field (8 named arguments) would then match both: PostgREST answers that with
-- 300 Multiple Choices. Drop the old signature; the new one's defaults take
-- the old call.
DROP FUNCTION IF EXISTS public.log_sgp_price(TEXT, TEXT, INTEGER, NUMERIC, INTEGER, INTEGER, JSONB, TEXT);

CREATE OR REPLACE FUNCTION public.log_sgp_price(
    p_device_id          TEXT,
    p_book               TEXT,
    p_book_american      INTEGER,
    p_multiplied_decimal NUMERIC,
    p_sgp_groups         INTEGER,
    p_leg_count          INTEGER,
    p_legs               JSONB DEFAULT NULL,
    p_app_version        TEXT DEFAULT NULL,
    p_extra_legs         INTEGER DEFAULT NULL,
    p_corr_lift          NUMERIC DEFAULT NULL
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_recent   INT;
    v_decimal  NUMERIC;
    v_ratio    NUMERIC;
BEGIN
    IF p_device_id IS NULL OR length(btrim(p_device_id)) < 8 OR length(p_device_id) > 64 THEN
        RAISE EXCEPTION 'invalid device';
    END IF;
    IF p_book IS NULL OR p_book !~ '^[a-z0-9_]{2,32}$' THEN
        RAISE EXCEPTION 'invalid book';
    END IF;
    IF p_book_american IS NULL OR (p_book_american > -100 AND p_book_american < 100) THEN
        RAISE EXCEPTION 'invalid odds';
    END IF;
    IF p_multiplied_decimal IS NULL OR p_multiplied_decimal <= 1 THEN
        RAISE EXCEPTION 'invalid multiplied price';
    END IF;
    IF p_extra_legs IS NOT NULL AND (p_extra_legs < 1 OR p_extra_legs > 24) THEN
        RAISE EXCEPTION 'invalid extra legs';
    END IF;
    IF p_corr_lift IS NOT NULL AND (p_corr_lift <= 0 OR p_corr_lift > 10) THEN
        RAISE EXCEPTION 'invalid lift';
    END IF;

    v_decimal := CASE WHEN p_book_american > 0
                      THEN 1 + p_book_american / 100.0
                      ELSE 1 + 100.0 / abs(p_book_american) END;
    v_ratio := v_decimal / p_multiplied_decimal;
    IF v_ratio < 0.2 OR v_ratio > 1.2 THEN
        RAISE EXCEPTION 'price out of range';
    END IF;

    SELECT count(*) INTO v_recent
      FROM sgp_price_observations
     WHERE device_id = p_device_id
       AND received_at > now() - interval '1 day';
    IF v_recent >= 50 THEN
        RETURN;
    END IF;

    INSERT INTO sgp_price_observations
        (device_id, book, book_american, book_decimal, multiplied_decimal,
         sgp_groups, leg_count, legs, app_version, extra_legs, corr_lift)
    VALUES
        (p_device_id, p_book, p_book_american, v_decimal, p_multiplied_decimal,
         p_sgp_groups, p_leg_count, p_legs, p_app_version, p_extra_legs, p_corr_lift);
END;
$$;

-- Each book's cut per EXTRA same-game leg, off the profit, after the
-- correlation lift (never below 1 for price), over the
-- last 120 days. One vote per device, as before. Rows from app builds that sent
-- no extra_legs / corr_lift are left out: their cut is per game and on the raw
-- multiplied price, a different quantity.
CREATE OR REPLACE FUNCTION public.sgp_haircuts()
RETURNS TABLE (book TEXT, haircut NUMERIC, n BIGINT)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    WITH per_device AS (
        SELECT o.book,
               o.device_id,
               percentile_cont(0.5) WITHIN GROUP (
                   ORDER BY 1 - power((o.book_decimal - 1)
                                      / (o.multiplied_decimal / greatest(o.corr_lift, 1) - 1),
                                      1.0 / o.extra_legs)
               ) AS cut
          FROM sgp_price_observations o
         WHERE o.received_at > now() - interval '120 days'
           AND o.extra_legs IS NOT NULL
           AND o.corr_lift IS NOT NULL
           AND o.multiplied_decimal / greatest(o.corr_lift, 1) > 1
         GROUP BY o.book, o.device_id
    )
    SELECT d.book,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY d.cut)::NUMERIC AS haircut,
           count(*) AS n
      FROM per_device d
     GROUP BY d.book;
$$;

REVOKE ALL ON FUNCTION public.log_sgp_price(TEXT, TEXT, INTEGER, NUMERIC, INTEGER, INTEGER, JSONB, TEXT, INTEGER, NUMERIC) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.sgp_haircuts() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.log_sgp_price(TEXT, TEXT, INTEGER, NUMERIC, INTEGER, INTEGER, JSONB, TEXT, INTEGER, NUMERIC) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.sgp_haircuts() TO anon, authenticated;

-- The second observation: Matt's screenshots, 2026-11-12. FanDuel's own slip
-- priced five WAS@NYG legs +3085 as one same-game parlay. Legs at FanDuel
-- (v_latest_prop_odds_all_books, snapshot 2026-11-12 21:25 UTC): Daniels O1.5
-- pass TDs +158, Singletary anytime TD +280, Nabers O5.5 rec -120, Diggs O3.5
-- rec -172, Diggs anytime TD +240 -> 96.6416 multiplied (the app's tile read
-- +8037 = 96.64 x 0.842). Lift 1.866: the exact bivariate-normal joint at
-- those prices under the NFL correlations below (scipy), against the legs
-- multiplied. Same device id as the 11-06 seed: one person, one vote.
INSERT INTO sgp_price_observations
    (device_id, book, book_american, book_decimal, multiplied_decimal,
     sgp_groups, leg_count, legs, source, extra_legs, corr_lift)
SELECT 'seed-matt-2026-11-06', 'fanduel', 3085, 31.85, 96.6416, 1, 5,
       '[{"game":"WAS@NYG","label":"Jayden Daniels Over 1.5 Pass TDs"},
         {"game":"WAS@NYG","label":"Devin Singletary Anytime TD"},
         {"game":"WAS@NYG","label":"Malik Nabers Over 5.5 Receptions"},
         {"game":"WAS@NYG","label":"Stefon Diggs Over 3.5 Receptions"},
         {"game":"WAS@NYG","label":"Stefon Diggs Anytime TD"}]'::jsonb,
       'screenshot', 4, 1.866
 WHERE NOT EXISTS (
     SELECT 1 FROM sgp_price_observations
      WHERE source = 'screenshot' AND book = 'fanduel' AND book_american = 3085);

-- NFL market-level correlations. market_class_a / _b hold the two prop market
-- keys (ordered), relationship is same_player / same_team / opp. rho is the
-- Bonett-Price tetrachoric estimate, OVER x OVER orientation; n_pairs is the
-- player-game pairs behind it (500 minimum). Clamped to ±0.95, as the estimator does.
INSERT INTO public.parlay_correlations
    (sport, market_class_a, market_class_b, relationship, rho, source, n_pairs)
VALUES
    ('NFL','player_anytime_td','player_anytime_td','opp',0.024,'empirical',43888),
    ('NFL','player_anytime_td','player_pass_attempts','opp',0.084,'empirical',13658),
    ('NFL','player_anytime_td','player_pass_completions','opp',0.054,'empirical',13658),
    ('NFL','player_anytime_td','player_pass_tds','opp',0.049,'empirical',13658),
    ('NFL','player_anytime_td','player_pass_yds','opp',0.043,'empirical',13658),
    ('NFL','player_anytime_td','player_reception_yds','opp',0.030,'empirical',62432),
    ('NFL','player_anytime_td','player_receptions','opp',0.040,'empirical',62432),
    ('NFL','player_anytime_td','player_rush_attempts','opp',-0.057,'empirical',22995),
    ('NFL','player_anytime_td','player_rush_reception_yds','opp',0.013,'empirical',76310),
    ('NFL','player_anytime_td','player_rush_yds','opp',-0.045,'empirical',22995),
    ('NFL','player_pass_attempts','player_pass_attempts','opp',-0.067,'empirical',1070),
    ('NFL','player_pass_attempts','player_pass_completions','opp',-0.068,'empirical',2140),
    ('NFL','player_pass_attempts','player_pass_tds','opp',0.134,'empirical',2140),
    ('NFL','player_pass_attempts','player_pass_yds','opp',0.054,'empirical',2140),
    ('NFL','player_pass_attempts','player_reception_yds','opp',0.011,'empirical',9702),
    ('NFL','player_pass_attempts','player_receptions','opp',-0.054,'empirical',9702),
    ('NFL','player_pass_attempts','player_rush_attempts','opp',0.057,'empirical',3580),
    ('NFL','player_pass_attempts','player_rush_reception_yds','opp',0.010,'empirical',11863),
    ('NFL','player_pass_attempts','player_rush_yds','opp',0.057,'empirical',3580),
    ('NFL','player_pass_completions','player_pass_completions','opp',-0.100,'empirical',1070),
    ('NFL','player_pass_completions','player_pass_tds','opp',0.112,'empirical',2140),
    ('NFL','player_pass_completions','player_pass_yds','opp',0.002,'empirical',2140),
    ('NFL','player_pass_completions','player_reception_yds','opp',0.004,'empirical',9702),
    ('NFL','player_pass_completions','player_receptions','opp',-0.045,'empirical',9702),
    ('NFL','player_pass_completions','player_rush_attempts','opp',-0.014,'empirical',3580),
    ('NFL','player_pass_completions','player_rush_reception_yds','opp',-0.005,'empirical',11863),
    ('NFL','player_pass_completions','player_rush_yds','opp',-0.002,'empirical',3580),
    ('NFL','player_pass_tds','player_pass_tds','opp',0.167,'empirical',1070),
    ('NFL','player_pass_tds','player_pass_yds','opp',0.145,'empirical',2140),
    ('NFL','player_pass_tds','player_reception_yds','opp',0.065,'empirical',9702),
    ('NFL','player_pass_tds','player_receptions','opp',0.048,'empirical',9702),
    ('NFL','player_pass_tds','player_rush_attempts','opp',-0.003,'empirical',3580),
    ('NFL','player_pass_tds','player_rush_reception_yds','opp',0.051,'empirical',11863),
    ('NFL','player_pass_tds','player_rush_yds','opp',0.035,'empirical',3580),
    ('NFL','player_pass_yds','player_pass_yds','opp',0.040,'empirical',1070),
    ('NFL','player_pass_yds','player_reception_yds','opp',0.018,'empirical',9702),
    ('NFL','player_pass_yds','player_receptions','opp',-0.015,'empirical',9702),
    ('NFL','player_pass_yds','player_rush_attempts','opp',-0.004,'empirical',3580),
    ('NFL','player_pass_yds','player_rush_reception_yds','opp',0.004,'empirical',11863),
    ('NFL','player_pass_yds','player_rush_yds','opp',0.003,'empirical',3580),
    ('NFL','player_reception_yds','player_reception_yds','opp',0.007,'empirical',22198),
    ('NFL','player_reception_yds','player_receptions','opp',0.010,'empirical',44396),
    ('NFL','player_reception_yds','player_rush_attempts','opp',-0.013,'empirical',16376),
    ('NFL','player_reception_yds','player_rush_reception_yds','opp',-0.000,'empirical',54307),
    ('NFL','player_reception_yds','player_rush_yds','opp',-0.001,'empirical',16376),
    ('NFL','player_receptions','player_receptions','opp',0.006,'empirical',22198),
    ('NFL','player_receptions','player_rush_attempts','opp',-0.008,'empirical',16376),
    ('NFL','player_receptions','player_rush_reception_yds','opp',-0.000,'empirical',54307),
    ('NFL','player_receptions','player_rush_yds','opp',0.008,'empirical',16376),
    ('NFL','player_rush_attempts','player_rush_attempts','opp',-0.211,'empirical',3010),
    ('NFL','player_rush_attempts','player_rush_reception_yds','opp',-0.050,'empirical',19984),
    ('NFL','player_rush_attempts','player_rush_yds','opp',-0.147,'empirical',6020),
    ('NFL','player_rush_reception_yds','player_rush_reception_yds','opp',-0.011,'empirical',33174),
    ('NFL','player_rush_reception_yds','player_rush_yds','opp',-0.033,'empirical',19984),
    ('NFL','player_rush_yds','player_rush_yds','opp',-0.104,'empirical',3010),
    ('NFL','player_anytime_td','player_pass_attempts','same_player',-0.039,'empirical',2267),
    ('NFL','player_anytime_td','player_pass_completions','same_player',-0.006,'empirical',2267),
    ('NFL','player_anytime_td','player_pass_tds','same_player',-0.040,'empirical',2267),
    ('NFL','player_anytime_td','player_pass_yds','same_player',0.059,'empirical',2267),
    ('NFL','player_anytime_td','player_reception_yds','same_player',0.353,'empirical',10360),
    ('NFL','player_anytime_td','player_receptions','same_player',0.311,'empirical',10360),
    ('NFL','player_anytime_td','player_rush_attempts','same_player',0.387,'empirical',3812),
    ('NFL','player_anytime_td','player_rush_reception_yds','same_player',0.415,'empirical',12661),
    ('NFL','player_anytime_td','player_rush_yds','same_player',0.410,'empirical',3812),
    ('NFL','player_pass_attempts','player_pass_completions','same_player',0.889,'empirical',2267),
    ('NFL','player_pass_attempts','player_pass_tds','same_player',0.225,'empirical',2267),
    ('NFL','player_pass_attempts','player_pass_yds','same_player',0.699,'empirical',2267),
    ('NFL','player_pass_completions','player_pass_tds','same_player',0.355,'empirical',2267),
    ('NFL','player_pass_completions','player_pass_yds','same_player',0.791,'empirical',2267),
    ('NFL','player_pass_tds','player_pass_yds','same_player',0.506,'empirical',2267),
    ('NFL','player_reception_yds','player_receptions','same_player',0.796,'empirical',10360),
    ('NFL','player_reception_yds','player_rush_attempts','same_player',0.068,'empirical',1511),
    ('NFL','player_reception_yds','player_rush_reception_yds','same_player',0.950,'empirical',10360),
    ('NFL','player_reception_yds','player_rush_yds','same_player',0.054,'empirical',1511),
    ('NFL','player_receptions','player_rush_attempts','same_player',0.010,'empirical',1511),
    ('NFL','player_receptions','player_rush_reception_yds','same_player',0.743,'empirical',10360),
    ('NFL','player_receptions','player_rush_yds','same_player',-0.042,'empirical',1511),
    ('NFL','player_rush_attempts','player_rush_reception_yds','same_player',0.713,'empirical',3812),
    ('NFL','player_rush_attempts','player_rush_yds','same_player',0.772,'empirical',3812),
    ('NFL','player_rush_reception_yds','player_rush_yds','same_player',0.930,'empirical',3812),
    ('NFL','player_anytime_td','player_anytime_td','same_team',-0.055,'empirical',38678),
    ('NFL','player_anytime_td','player_pass_attempts','same_team',-0.003,'empirical',11942),
    ('NFL','player_anytime_td','player_pass_completions','same_team',0.069,'empirical',11942),
    ('NFL','player_anytime_td','player_pass_tds','same_team',0.272,'empirical',11942),
    ('NFL','player_anytime_td','player_pass_yds','same_team',0.119,'empirical',11942),
    ('NFL','player_anytime_td','player_reception_yds','same_team',0.016,'empirical',55037),
    ('NFL','player_anytime_td','player_receptions','same_team',-0.008,'empirical',55037),
    ('NFL','player_anytime_td','player_rush_attempts','same_team',0.006,'empirical',20062),
    ('NFL','player_anytime_td','player_rush_reception_yds','same_team',0.016,'empirical',67261),
    ('NFL','player_anytime_td','player_rush_yds','same_team',0.011,'empirical',20062),
    ('NFL','player_pass_attempts','player_reception_yds','same_team',0.198,'empirical',9836),
    ('NFL','player_pass_attempts','player_receptions','same_team',0.287,'empirical',9836),
    ('NFL','player_pass_attempts','player_rush_attempts','same_team',-0.110,'empirical',3287),
    ('NFL','player_pass_attempts','player_rush_reception_yds','same_team',0.117,'empirical',11685),
    ('NFL','player_pass_attempts','player_rush_yds','same_team',-0.181,'empirical',3287),
    ('NFL','player_pass_completions','player_reception_yds','same_team',0.244,'empirical',9836),
    ('NFL','player_pass_completions','player_receptions','same_team',0.336,'empirical',9836),
    ('NFL','player_pass_completions','player_rush_attempts','same_team',-0.029,'empirical',3287),
    ('NFL','player_pass_completions','player_rush_reception_yds','same_team',0.162,'empirical',11685),
    ('NFL','player_pass_completions','player_rush_yds','same_team',-0.131,'empirical',3287),
    ('NFL','player_pass_tds','player_reception_yds','same_team',0.150,'empirical',9836),
    ('NFL','player_pass_tds','player_receptions','same_team',0.097,'empirical',9836),
    ('NFL','player_pass_tds','player_rush_attempts','same_team',0.017,'empirical',3287),
    ('NFL','player_pass_tds','player_rush_reception_yds','same_team',0.121,'empirical',11685),
    ('NFL','player_pass_tds','player_rush_yds','same_team',0.002,'empirical',3287),
    ('NFL','player_pass_yds','player_reception_yds','same_team',0.332,'empirical',9836),
    ('NFL','player_pass_yds','player_receptions','same_team',0.252,'empirical',9836),
    ('NFL','player_pass_yds','player_rush_attempts','same_team',-0.034,'empirical',3287),
    ('NFL','player_pass_yds','player_rush_reception_yds','same_team',0.247,'empirical',11685),
    ('NFL','player_pass_yds','player_rush_yds','same_team',-0.109,'empirical',3287),
    ('NFL','player_reception_yds','player_reception_yds','same_team',0.007,'empirical',18748),
    ('NFL','player_reception_yds','player_receptions','same_team',0.006,'empirical',37496),
    ('NFL','player_reception_yds','player_rush_attempts','same_team',-0.001,'empirical',14902),
    ('NFL','player_reception_yds','player_rush_reception_yds','same_team',-0.006,'empirical',46663),
    ('NFL','player_reception_yds','player_rush_yds','same_team',-0.033,'empirical',14902),
    ('NFL','player_receptions','player_receptions','same_team',0.020,'empirical',18748),
    ('NFL','player_receptions','player_rush_attempts','same_team',-0.009,'empirical',14902),
    ('NFL','player_receptions','player_rush_reception_yds','same_team',-0.013,'empirical',46663),
    ('NFL','player_receptions','player_rush_yds','same_team',-0.050,'empirical',14902),
    ('NFL','player_rush_attempts','player_rush_attempts','same_team',-0.030,'empirical',1707),
    ('NFL','player_rush_attempts','player_rush_reception_yds','same_team',0.004,'empirical',17293),
    ('NFL','player_rush_attempts','player_rush_yds','same_team',0.015,'empirical',3414),
    ('NFL','player_rush_reception_yds','player_rush_reception_yds','same_team',-0.007,'empirical',28699),
    ('NFL','player_rush_reception_yds','player_rush_yds','same_team',-0.019,'empirical',17293),
    ('NFL','player_rush_yds','player_rush_yds','same_team',0.031,'empirical',1707)
ON CONFLICT (sport, market_class_a, market_class_b, relationship)
DO UPDATE SET rho = EXCLUDED.rho, source = 'empirical',
              n_pairs = EXCLUDED.n_pairs, updated_at = now()::text;
