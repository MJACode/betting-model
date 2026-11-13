-- ncaaf_fcs_opponent_alias_2026_10_21 (rewritten 2026-11-13)
--
-- ONE-OFF. Eleven NCAAF games each have two games rows for one game: the
-- CFBD row (the final) and a row the odds ingest minted from the Odds API's
-- nickname for the FCS visitor (the odds). The Odds API writes "William and
-- Mary Tribe", "LIU Sharks" and "Houston Baptist Huskies"; CFBD's schools are
-- "William & Mary", "Long Island University" and "Houston Christian" (a
-- rename). No fold, "school mascot" or prefix rule bridges them, alt_names is
-- NULL on all three, so every game the feed priced got a second id.
-- config.NCAAF_ODDS_API_MAP gains all three in the same change, so new odds
-- land on the CFBD id. This file moves the odds already stored.
--
-- Measured 2026-11-13 on production (Supabase Betting Model), read-only.
-- canon = data_source cfbd, scored. alias = data_source live, unscored.
-- Counts are odds / latest_odds / game_weather rows on each id.
--
--   canon                                                      alias                                                  alias           canon
--   NCAAF_2023-09-09_houston-christian_western-kentucky  52-22  NCAAF_2023-09-09_houston-baptist-huskies_western-kentucky   0/0/0     0/0/1
--   NCAAF_2023-09-16_long-island-university_baylor       30-7   NCAAF_2023-09-16_liu-sharks_baylor                         16/10/0    0/0/1
--   NCAAF_2023-10-07_william-mary_virginia               27-13  NCAAF_2023-10-07_william-and-mary-tribe_virginia           15/11/0    0/0/1
--   NCAAF_2024-09-07_william-mary_coastal-carolina       40-21  NCAAF_2024-09-07_william-and-mary-tribe_coastal-carolina   48/30/0    0/0/1
--   NCAAF_2025-08-30_long-island-university_florida      55-0   NCAAF_2025-08-30_liu-sharks_florida                       134/22/0    2/2/1
--   NCAAF_2025-09-06_long-island-university_eastern-michigan 23-28 NCAAF_2025-09-06_liu-sharks_eastern-michigan            177/31/0    3/3/1
--   NCAAF_2025-09-13_houston-christian_nebraska          59-7   NCAAF_2025-09-13_houston-baptist-huskies_nebraska          35/27/0    4/4/1
--   NCAAF_2025-09-13_william-mary_virginia               55-16  NCAAF_2025-09-13_william-and-mary-tribe_virginia           52/34/0    6/6/1
--   NCAAF_2026-09-26_william-mary_duke                   62-7   NCAAF_2026-09-26_william-and-mary-tribe_duke              519/16/1    0/0/1
--   NCAAF_2026-09-26_long-island-university_florida-international 20-3 NCAAF_2026-09-26_liu-sharks_florida-international 486/20/1  0/0/1
--   NCAAF_2026-09-26_houston-christian_north-texas       63-14  NCAAF_2026-09-26_houston-baptist-huskies_north-texas      323/17/1    0/0/1
--
-- Odds on the aliases are live-book rows, including bought history
-- (source odds_api_historical, historical_inplay|..., and
-- odds_api_ncaaf_derivative_am). Odds on the five canons that have any are
-- cfbd_bovada / cfbd_draftkings rows. Both kinds side by side is the normal
-- state of a priced CFBD game, so odds move as a whole. The odds update
-- trigger recomputes latest_odds for the old and the new key of each moved
-- row; the latest_odds lines below are the backstop for a server without it.
--
-- Seven aliases also carry ncaaf_derivative_fetches rows (the first-half and
-- team-total purchase ledger, keyed game_id + read_slot), 10 rows in all; no
-- canon has one. They move with the odds they describe, so a re-run of that
-- purchase under the new map finds them and buys nothing twice.
--
-- Two kickoffs differ inside a pair: 2026-09-26 Duke 19:30Z (canon) vs 19:32Z
-- (alias), 2025-09-06 Eastern Michigan 23:00Z vs 23:05Z. The game id is built
-- from the ET date and the two schools, not the kickoff, so neither matters.
--
-- Measured 0 on every alias: picks, player_prop_odds, latest_prop_odds,
-- game_weather_issued, opening_signals, tracked_bets, kalshi_ncaaf_events,
-- live_game_state, latest_live_game_state, live_pick_features,
-- live_scoreboard, live_trigger_events, live_credit_telemetry, dk_live_reads,
-- ncaaf_live_states, ncaaf_moneyline_decisions, ncaaf player/qb/team logs,
-- player_game_log, plays, public_betting, scoreboard_splits,
-- team_period_results, lineup_slots, game_market_gate, alt_game_lines,
-- alt_game_line_fetches, capper_picks. picks_log was counted on the three
-- 2026-09-26 aliases (0); it has no index on game_id and no foreign key to
-- games, and no pick exists on any alias, so it is not touched here (each
-- UPDATE would be a scan of a 2.4 GB table for rows that cannot exist).
--
-- NOT HANDLED HERE, seen in the same query:
--   NCAAF_2024-09-07_liu-sharks_tcu and NCAAF_2026-09-04_liu-sharks_kansas.
--   Their CFBD rows carry the UTC date (NCAAF_2024-09-08_long-island-
--   university_tcu, NCAAF_2026-09-05_long-island-university_kansas), the
--   night-game ET/UTC split, which is a different shape from the eleven.
--   NCAAF_2023-09-09_houston_western-kentucky, the old prefix-rule phantom
--   ("Houston Christian Huskies" read as "Houston"), a different name.
--
-- NEVER DELETE a pick, and never move one onto an id that already has that
-- model's pick. Refuse to drop a games row while a pick or an odds row is
-- still on its alias.
--
-- Guard, per pair, on the property this establishes: the alias row is gone.
-- A pair runs only while its alias still exists with the measured nickname
-- and no score, and its canon exists with the CFBD school. Once an alias is
-- deleted the pair is a primary-key lookup and a CONTINUE, so a second pass
-- is a no-op. One pair already healed does not skip the others.
DO $$
DECLARE
    pair  TEXT[];
    canon TEXT;
    alias TEXT;
    home  TEXT;
    away_canon TEXT;
    away_alias TEXT;
    n     INTEGER := 0;
BEGIN
    FOREACH pair SLICE 1 IN ARRAY ARRAY[
        ['NCAAF_2023-09-09_houston-christian_western-kentucky',
         'NCAAF_2023-09-09_houston-baptist-huskies_western-kentucky',
         'Western Kentucky', 'Houston Christian', 'Houston Baptist Huskies'],
        ['NCAAF_2023-09-16_long-island-university_baylor',
         'NCAAF_2023-09-16_liu-sharks_baylor',
         'Baylor', 'Long Island University', 'LIU Sharks'],
        ['NCAAF_2023-10-07_william-mary_virginia',
         'NCAAF_2023-10-07_william-and-mary-tribe_virginia',
         'Virginia', 'William & Mary', 'William and Mary Tribe'],
        ['NCAAF_2024-09-07_william-mary_coastal-carolina',
         'NCAAF_2024-09-07_william-and-mary-tribe_coastal-carolina',
         'Coastal Carolina', 'William & Mary', 'William and Mary Tribe'],
        ['NCAAF_2025-08-30_long-island-university_florida',
         'NCAAF_2025-08-30_liu-sharks_florida',
         'Florida', 'Long Island University', 'LIU Sharks'],
        ['NCAAF_2025-09-06_long-island-university_eastern-michigan',
         'NCAAF_2025-09-06_liu-sharks_eastern-michigan',
         'Eastern Michigan', 'Long Island University', 'LIU Sharks'],
        ['NCAAF_2025-09-13_houston-christian_nebraska',
         'NCAAF_2025-09-13_houston-baptist-huskies_nebraska',
         'Nebraska', 'Houston Christian', 'Houston Baptist Huskies'],
        ['NCAAF_2025-09-13_william-mary_virginia',
         'NCAAF_2025-09-13_william-and-mary-tribe_virginia',
         'Virginia', 'William & Mary', 'William and Mary Tribe'],
        ['NCAAF_2026-09-26_william-mary_duke',
         'NCAAF_2026-09-26_william-and-mary-tribe_duke',
         'Duke', 'William & Mary', 'William and Mary Tribe'],
        ['NCAAF_2026-09-26_long-island-university_florida-international',
         'NCAAF_2026-09-26_liu-sharks_florida-international',
         'Florida International', 'Long Island University', 'LIU Sharks'],
        ['NCAAF_2026-09-26_houston-christian_north-texas',
         'NCAAF_2026-09-26_houston-baptist-huskies_north-texas',
         'North Texas', 'Houston Christian', 'Houston Baptist Huskies']
    ] LOOP
        canon      := pair[1];
        alias      := pair[2];
        home       := pair[3];
        away_canon := pair[4];
        away_alias := pair[5];

        -- Already consolidated (or never ours): nothing to do.
        IF NOT EXISTS (
            SELECT 1 FROM games
             WHERE game_id = alias AND sport = 'NCAAF'
               AND home_team = home AND away_team = away_alias
               AND home_score IS NULL
        ) THEN
            CONTINUE;
        END IF;
        -- The CFBD row must be there to receive the odds. Its score is not a
        -- condition: every canon here is already final.
        IF NOT EXISTS (
            SELECT 1 FROM games
             WHERE game_id = canon AND sport = 'NCAAF'
               AND home_team = home AND away_team = away_canon
        ) THEN
            RAISE NOTICE 'ncaaf_fcs_opponent_alias: canon % missing, alias % kept', canon, alias;
            CONTINUE;
        END IF;

        UPDATE odds SET game_id = canon WHERE game_id = alias;
        UPDATE player_prop_odds SET game_id = canon WHERE game_id = alias;
        UPDATE picks p SET game_id = canon
         WHERE p.game_id = alias
           AND NOT EXISTS (SELECT 1 FROM picks c
                            WHERE c.game_id = canon AND c.model_id = p.model_id);

        UPDATE latest_odds l SET game_id = canon
         WHERE l.game_id = alias
           AND NOT EXISTS (SELECT 1 FROM latest_odds c
                            WHERE c.game_id = canon
                              AND c.market = l.market
                              AND c.bookmaker = l.bookmaker
                              AND c.line_key = l.line_key);
        DELETE FROM latest_odds WHERE game_id = alias;

        IF to_regclass('public.latest_prop_odds') IS NOT NULL THEN
            UPDATE latest_prop_odds l SET game_id = canon
             WHERE l.game_id = alias
               AND NOT EXISTS (SELECT 1 FROM latest_prop_odds c
                                WHERE c.game_id = canon
                                  AND c.market = l.market
                                  AND c.player_name = l.player_name
                                  AND c.bookmaker = l.bookmaker
                                  AND c.line IS NOT DISTINCT FROM l.line);
            DELETE FROM latest_prop_odds WHERE game_id = alias;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM game_weather WHERE game_id = canon) THEN
            UPDATE game_weather SET game_id = canon WHERE game_id = alias;
        ELSE
            DELETE FROM game_weather WHERE game_id = alias;
        END IF;
        IF to_regclass('public.game_weather_issued') IS NOT NULL THEN
            UPDATE game_weather_issued w SET game_id = canon
             WHERE w.game_id = alias
               AND NOT EXISTS (SELECT 1 FROM game_weather_issued c
                                WHERE c.game_id = canon AND c.lead_days = w.lead_days);
            DELETE FROM game_weather_issued WHERE game_id = alias;
        END IF;
        IF to_regclass('public.ncaaf_derivative_fetches') IS NOT NULL THEN
            -- A ledger row whose slot the canon already holds stays where it
            -- is: it has no foreign key, and the canon's own row is the newer
            -- record of that purchase.
            UPDATE ncaaf_derivative_fetches f SET game_id = canon
             WHERE f.game_id = alias
               AND NOT EXISTS (SELECT 1 FROM ncaaf_derivative_fetches c
                                WHERE c.game_id = canon AND c.read_slot = f.read_slot);
        END IF;
        IF to_regclass('public.kalshi_ncaaf_events') IS NOT NULL THEN
            UPDATE kalshi_ncaaf_events SET game_id = canon WHERE game_id = alias;
        END IF;
        IF to_regclass('public.opening_signals') IS NOT NULL THEN
            UPDATE opening_signals SET game_id = canon WHERE game_id = alias;
        END IF;

        IF EXISTS (SELECT 1 FROM picks WHERE game_id = alias)
           OR EXISTS (SELECT 1 FROM odds WHERE game_id = alias) THEN
            RAISE NOTICE 'ncaaf_fcs_opponent_alias: leftover odds/picks on alias %, games row kept', alias;
            CONTINUE;
        END IF;

        -- Remaining children that can block the games delete. Not picks.
        -- All measured at 0 on 2026-11-13; every alias here is a past game.
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
           AND home_team = home
           AND away_team = away_alias
           AND home_score IS NULL;
        GET DIAGNOSTICS n = ROW_COUNT;
        IF n > 0 THEN
            RAISE NOTICE 'ncaaf_fcs_opponent_alias: consolidated % onto %', alias, canon;
        END IF;
    END LOOP;
END $$;
