-- ncaaf_se_louisiana_ul_monroe_alias_2026_09_14 (2026-09-14)
--
-- ONE-OFF. UL Monroe 2026-09-19 has two games rows for one matchup.
-- Measured 2026-09-14 on production (Supabase Betting Model):
--
--   NCAAF_2026-09-19_se-louisiana_ul-monroe
--     away_team='SE Louisiana'  data_source=cfbd  created 2026-08-29
--   NCAAF_2026-09-19_southeastern-louisiana-lions_ul-monroe
--     away_team='Southeastern Louisiana Lions'  data_source=live  created 2026-09-14
--
-- Same commence_time 2026-09-19T20:30:00Z. CFBD's school is "SE Louisiana";
-- The Odds API writes "Southeastern Louisiana Lions". The resolver's fold,
-- school+mascot and prefix rules cannot bridge them (alt_names is NULL), so
-- odds ingest minted a second id. ncaaf_game_identity went CRIT.
--
-- Canonical id is the CFBD row: that is the school name CFBD will keep
-- writing, and after config.NCAAF_ODDS_API_MAP grows the alias, new odds
-- land there too.
--
-- Measured children on 2026-09-14: 0 odds, 0 picks, 0 prop odds on BOTH
-- ids; identical game_weather rows (Malone Stadium, 98.4 F). The live row
-- is empty of anything that is a bet of record.
--
-- Per table, move alias -> canonical when canonical has none of that kind;
-- otherwise drop the alias copy (weather / latest_* are derived or duplicated).
-- NEVER DELETE a pick. Refuse to drop the games row if a pick or odds
-- snapshot is still on the alias (a unique collision left them).
--
-- Guard: both rows still carry the measured names and are unscored. A
-- second pass is a no-op.
DO $$
DECLARE
    canon TEXT := 'NCAAF_2026-09-19_se-louisiana_ul-monroe';
    alias TEXT := 'NCAAF_2026-09-19_southeastern-louisiana-lions_ul-monroe';
    n     INTEGER := 0;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM games
         WHERE game_id = canon AND sport = 'NCAAF'
           AND home_team = 'UL Monroe' AND away_team = 'SE Louisiana'
           AND home_score IS NULL
    ) OR NOT EXISTS (
        SELECT 1 FROM games
         WHERE game_id = alias AND sport = 'NCAAF'
           AND home_team = 'UL Monroe'
           AND away_team = 'Southeastern Louisiana Lions'
           AND home_score IS NULL
    ) THEN
        RETURN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM odds WHERE game_id = canon) THEN
        UPDATE odds SET game_id = canon WHERE game_id = alias;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM picks WHERE game_id = canon) THEN
        UPDATE picks SET game_id = canon WHERE game_id = alias;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM picks_log WHERE game_id = canon) THEN
        UPDATE picks_log SET game_id = canon WHERE game_id = alias;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM player_prop_odds WHERE game_id = canon) THEN
        UPDATE player_prop_odds SET game_id = canon WHERE game_id = alias;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM latest_odds WHERE game_id = canon) THEN
        UPDATE latest_odds SET game_id = canon WHERE game_id = alias;
    ELSE
        DELETE FROM latest_odds WHERE game_id = alias;
    END IF;
    IF to_regclass('public.latest_prop_odds') IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM latest_prop_odds WHERE game_id = canon) THEN
            UPDATE latest_prop_odds SET game_id = canon WHERE game_id = alias;
        ELSE
            DELETE FROM latest_prop_odds WHERE game_id = alias;
        END IF;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM game_weather WHERE game_id = canon) THEN
        UPDATE game_weather SET game_id = canon WHERE game_id = alias;
    ELSE
        DELETE FROM game_weather WHERE game_id = alias;
    END IF;
    IF to_regclass('public.game_weather_issued') IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM game_weather_issued WHERE game_id = canon) THEN
            UPDATE game_weather_issued SET game_id = canon WHERE game_id = alias;
        ELSE
            DELETE FROM game_weather_issued WHERE game_id = alias;
        END IF;
    END IF;
    IF to_regclass('public.kalshi_ncaaf_events') IS NOT NULL THEN
        UPDATE kalshi_ncaaf_events SET game_id = canon WHERE game_id = alias;
    END IF;
    IF to_regclass('public.opening_signals') IS NOT NULL THEN
        UPDATE opening_signals SET game_id = canon WHERE game_id = alias;
    END IF;

    IF EXISTS (SELECT 1 FROM picks WHERE game_id = alias)
       OR EXISTS (SELECT 1 FROM odds WHERE game_id = alias) THEN
        RAISE NOTICE 'ncaaf_se_louisiana_alias: leftover odds/picks on alias, games row kept';
        RETURN;
    END IF;

    DELETE FROM latest_odds WHERE game_id = alias;
    DELETE FROM game_weather WHERE game_id = alias;
    IF to_regclass('public.latest_prop_odds') IS NOT NULL THEN
        DELETE FROM latest_prop_odds WHERE game_id = alias;
    END IF;
    IF to_regclass('public.game_weather_issued') IS NOT NULL THEN
        DELETE FROM game_weather_issued WHERE game_id = alias;
    END IF;
    -- Remaining FK children that can block the games delete. Not picks.
    IF to_regclass('public.latest_live_game_state') IS NOT NULL THEN
        DELETE FROM latest_live_game_state WHERE game_id = alias;
    END IF;
    IF to_regclass('public.live_game_state') IS NOT NULL THEN
        DELETE FROM live_game_state WHERE game_id = alias;
    END IF;
    IF to_regclass('public.live_credit_telemetry') IS NOT NULL THEN
        DELETE FROM live_credit_telemetry WHERE game_id = alias;
    END IF;
    IF to_regclass('public.live_pick_features') IS NOT NULL THEN
        DELETE FROM live_pick_features WHERE game_id = alias;
    END IF;
    IF to_regclass('public.live_trigger_events') IS NOT NULL THEN
        DELETE FROM live_trigger_events WHERE game_id = alias;
    END IF;
    IF to_regclass('public.public_betting') IS NOT NULL THEN
        DELETE FROM public_betting WHERE game_id = alias;
    END IF;
    IF to_regclass('public.lineup_slots') IS NOT NULL THEN
        DELETE FROM lineup_slots WHERE game_id = alias;
    END IF;

    DELETE FROM games
     WHERE game_id = alias
       AND sport = 'NCAAF'
       AND away_team = 'Southeastern Louisiana Lions'
       AND home_score IS NULL;
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n > 0 THEN
        RAISE NOTICE 'ncaaf_se_louisiana_alias: consolidated onto %', canon;
    END IF;
END $$;
