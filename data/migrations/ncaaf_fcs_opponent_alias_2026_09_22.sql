-- ncaaf_fcs_opponent_alias_2026_09_22 (2026-09-22)
--
-- ONE-OFF. Three NCAAF matchups on 2026-09-26 each have two games rows.
-- Measured on production (Supabase Betting Model) the morning the
-- ncaaf_game_identity check went STALE:
--
--   NCAAF_2026-09-26_william-mary_duke
--     away William & Mary, data_source=cfbd, created 2026-08-29
--   NCAAF_2026-09-26_william-and-mary-tribe_duke
--     away William and Mary Tribe, data_source=live, created 2026-09-22 05:49Z
--
--   NCAAF_2026-09-26_long-island-university_florida-international
--     away Long Island University, data_source=cfbd, created 2026-08-29
--   NCAAF_2026-09-26_liu-sharks_florida-international
--     away LIU Sharks, data_source=live, created 2026-09-22 05:54Z
--
--   NCAAF_2026-09-26_houston-christian_north-texas
--     away Houston Christian, data_source=cfbd, created 2026-08-29
--   NCAAF_2026-09-26_houston-baptist-huskies_north-texas
--     away Houston Baptist Huskies, data_source=live, created 2026-09-22 05:59Z
--
-- Same home and the same commence_time on each pair. Live rows have week
-- NULL. Child counts on the three live ids, measured the same morning:
-- 0 odds, 0 picks, 0 picks_log, 0 player_prop_odds, 0 latest_odds,
-- 0 latest_prop_odds, 0 game_weather, 0 opening_signals, 0 tracked_bets,
-- 0 game_market_gate, 0 ncaaf team/player/qb logs, 0 kalshi, 0 public
-- betting, 0 live_game_state. Weather exists only on the CFBD ids.
--
-- Canonical id is the CFBD row. The resolver map in the same PR sends new
-- odds there; this pass removes the empty live row so the health check
-- can go green.
--
-- Per table, move alias -> canonical when canonical has none of that kind;
-- otherwise drop the alias copy. NEVER DELETE a pick. Refuse to drop the
-- games row if a pick or an odds snapshot is still on the alias.
--
-- Guard: both rows still carry the measured names and are unscored. A
-- second pass is a no-op. One pair already healed does not skip the others.
DO $$
DECLARE
    rec RECORD;
    n   INTEGER := 0;
BEGIN
    FOR rec IN
        SELECT * FROM (VALUES
            ('NCAAF_2026-09-26_william-mary_duke',
             'NCAAF_2026-09-26_william-and-mary-tribe_duke',
             'Duke', 'William & Mary', 'William and Mary Tribe'),
            ('NCAAF_2026-09-26_long-island-university_florida-international',
             'NCAAF_2026-09-26_liu-sharks_florida-international',
             'Florida International', 'Long Island University', 'LIU Sharks'),
            ('NCAAF_2026-09-26_houston-christian_north-texas',
             'NCAAF_2026-09-26_houston-baptist-huskies_north-texas',
             'North Texas', 'Houston Christian', 'Houston Baptist Huskies')
        ) AS v(canon, alias, home, away_canon, away_alias)
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM games
             WHERE game_id = rec.canon AND sport = 'NCAAF'
               AND home_team = rec.home AND away_team = rec.away_canon
               AND home_score IS NULL
        ) OR NOT EXISTS (
            SELECT 1 FROM games
             WHERE game_id = rec.alias AND sport = 'NCAAF'
               AND home_team = rec.home AND away_team = rec.away_alias
               AND home_score IS NULL
        ) THEN
            CONTINUE;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM odds WHERE game_id = rec.canon) THEN
            UPDATE odds SET game_id = rec.canon WHERE game_id = rec.alias;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM picks WHERE game_id = rec.canon) THEN
            UPDATE picks SET game_id = rec.canon WHERE game_id = rec.alias;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM picks_log WHERE game_id = rec.canon) THEN
            UPDATE picks_log SET game_id = rec.canon WHERE game_id = rec.alias;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM player_prop_odds WHERE game_id = rec.canon) THEN
            UPDATE player_prop_odds SET game_id = rec.canon WHERE game_id = rec.alias;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM latest_odds WHERE game_id = rec.canon) THEN
            UPDATE latest_odds SET game_id = rec.canon WHERE game_id = rec.alias;
        ELSE
            DELETE FROM latest_odds WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.latest_prop_odds') IS NOT NULL THEN
            IF NOT EXISTS (SELECT 1 FROM latest_prop_odds WHERE game_id = rec.canon) THEN
                UPDATE latest_prop_odds SET game_id = rec.canon WHERE game_id = rec.alias;
            ELSE
                DELETE FROM latest_prop_odds WHERE game_id = rec.alias;
            END IF;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM game_weather WHERE game_id = rec.canon) THEN
            UPDATE game_weather SET game_id = rec.canon WHERE game_id = rec.alias;
        ELSE
            DELETE FROM game_weather WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.game_weather_issued') IS NOT NULL THEN
            IF NOT EXISTS (SELECT 1 FROM game_weather_issued WHERE game_id = rec.canon) THEN
                UPDATE game_weather_issued SET game_id = rec.canon WHERE game_id = rec.alias;
            ELSE
                DELETE FROM game_weather_issued WHERE game_id = rec.alias;
            END IF;
        END IF;
        IF to_regclass('public.kalshi_ncaaf_events') IS NOT NULL THEN
            UPDATE kalshi_ncaaf_events SET game_id = rec.canon WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.opening_signals') IS NOT NULL THEN
            UPDATE opening_signals SET game_id = rec.canon WHERE game_id = rec.alias;
        END IF;

        IF EXISTS (SELECT 1 FROM picks WHERE game_id = rec.alias)
           OR EXISTS (SELECT 1 FROM odds WHERE game_id = rec.alias) THEN
            RAISE NOTICE 'ncaaf_fcs_opponent_alias: leftover odds/picks on %, games row kept', rec.alias;
            CONTINUE;
        END IF;

        DELETE FROM latest_odds WHERE game_id = rec.alias;
        DELETE FROM game_weather WHERE game_id = rec.alias;
        IF to_regclass('public.latest_prop_odds') IS NOT NULL THEN
            DELETE FROM latest_prop_odds WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.game_weather_issued') IS NOT NULL THEN
            DELETE FROM game_weather_issued WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.latest_live_game_state') IS NOT NULL THEN
            DELETE FROM latest_live_game_state WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.live_game_state') IS NOT NULL THEN
            DELETE FROM live_game_state WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.live_credit_telemetry') IS NOT NULL THEN
            DELETE FROM live_credit_telemetry WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.live_pick_features') IS NOT NULL THEN
            DELETE FROM live_pick_features WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.live_trigger_events') IS NOT NULL THEN
            DELETE FROM live_trigger_events WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.public_betting') IS NOT NULL THEN
            DELETE FROM public_betting WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.lineup_slots') IS NOT NULL THEN
            DELETE FROM lineup_slots WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.player_game_log') IS NOT NULL THEN
            DELETE FROM player_game_log WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.plays') IS NOT NULL THEN
            DELETE FROM plays WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.game_market_gate') IS NOT NULL THEN
            DELETE FROM game_market_gate WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.tracked_bets') IS NOT NULL THEN
            DELETE FROM tracked_bets WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.ncaaf_live_states') IS NOT NULL THEN
            DELETE FROM ncaaf_live_states WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.ncaaf_team_game_log') IS NOT NULL THEN
            DELETE FROM ncaaf_team_game_log WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.ncaaf_player_game_log') IS NOT NULL THEN
            DELETE FROM ncaaf_player_game_log WHERE game_id = rec.alias;
        END IF;
        IF to_regclass('public.ncaaf_qb_game') IS NOT NULL THEN
            DELETE FROM ncaaf_qb_game WHERE game_id = rec.alias;
        END IF;

        DELETE FROM games
         WHERE game_id = rec.alias
           AND sport = 'NCAAF'
           AND home_team = rec.home
           AND away_team = rec.away_alias
           AND home_score IS NULL;
        GET DIAGNOSTICS n = ROW_COUNT;
        IF n > 0 THEN
            RAISE NOTICE 'ncaaf_fcs_opponent_alias: consolidated onto %', rec.canon;
        END IF;
    END LOOP;
END $$;
