-- ncaaf_citadel_alias_2026_10_16 (2026-10-16)
--
-- ONE-OFF. Five Citadel matchups each have two games rows for one game.
-- Measured 2026-10-16 on production (Supabase Betting Model):
--
--   canonical (data_source=cfbd, away_team='The Citadel')    alias (data_source=live, away_team='Citadel Bulldogs', unscored)
--   NCAAF_2023-09-02_the-citadel_georgia-southern  34-0     NCAAF_2023-09-02_citadel-bulldogs_georgia-southern   0 odds
--   NCAAF_2024-11-23_the-citadel_clemson           51-14    NCAAF_2024-11-23_citadel-bulldogs_clemson           18 odds, 8 latest_odds (6 live books)
--   NCAAF_2025-11-08_the-citadel_ole-miss          49-0     NCAAF_2025-11-08_citadel-bulldogs_ole-miss           0 odds
--   NCAAF_2026-09-05_the-citadel_charlotte         41-43    NCAAF_2026-09-05_citadel-bulldogs_charlotte       8639 odds, 39 latest_odds, weather
--   NCAAF_2026-10-17_the-citadel_texas-a-m         unplayed NCAAF_2026-10-17_citadel-bulldogs_texas-a-m         605 odds, 12 latest_odds, weather
--
-- CFBD's school is "The Citadel"; The Odds API writes "Citadel Bulldogs".
-- The resolver's fold keeps the article, so exact, "school mascot" and prefix
-- all miss (alt_names is NULL) and odds ingest minted the alias each season.
-- mirror_scores_to_alias_rows matches on the slug pair, which differs, so the
-- aliases never received a final either.
--
-- Canonical id is the CFBD row: it holds the final (or will), and after
-- config.NCAAF_ODDS_API_MAP grows the alias, new odds land there too.
--
-- Measured children on every alias: 0 picks, 0 picks_log, 0 prop odds,
-- 0 live_* rows, 0 opening_signals, 0 public_betting, 0 lineup_slots,
-- 0 plays, 0 player_game_log. Only odds, latest_odds and game_weather.
-- Canonical odds, where any, are cfbd_* bookmakers; live-book rows beside
-- CFBD history is the normal state of every priced CFBD game, so odds move
-- unconditionally. latest_odds is keyed (game_id, market, bookmaker): a row
-- moves when canonical lacks that key (measured: no overlap), else the
-- alias copy is dropped. Every canonical already has a game_weather row.
--
-- NEVER DELETE a pick. Refuse to drop a games row while a pick or an odds
-- snapshot is still on its alias.
--
-- Guard, per pair: the canonical still reads 'The Citadel' and the alias
-- still reads 'Citadel Bulldogs' and is unscored. A second pass is a no-op.
DO $$
DECLARE
    pair  TEXT[];
    canon TEXT;
    alias TEXT;
    n     INTEGER := 0;
BEGIN
    FOREACH pair SLICE 1 IN ARRAY ARRAY[
        ['NCAAF_2023-09-02_the-citadel_georgia-southern', 'NCAAF_2023-09-02_citadel-bulldogs_georgia-southern'],
        ['NCAAF_2024-11-23_the-citadel_clemson',          'NCAAF_2024-11-23_citadel-bulldogs_clemson'],
        ['NCAAF_2025-11-08_the-citadel_ole-miss',         'NCAAF_2025-11-08_citadel-bulldogs_ole-miss'],
        ['NCAAF_2026-09-05_the-citadel_charlotte',        'NCAAF_2026-09-05_citadel-bulldogs_charlotte'],
        ['NCAAF_2026-10-17_the-citadel_texas-a-m',        'NCAAF_2026-10-17_citadel-bulldogs_texas-a-m']
    ] LOOP
        canon := pair[1];
        alias := pair[2];

        IF NOT EXISTS (
            SELECT 1 FROM games
             WHERE game_id = canon AND sport = 'NCAAF'
               AND away_team = 'The Citadel'
        ) OR NOT EXISTS (
            SELECT 1 FROM games
             WHERE game_id = alias AND sport = 'NCAAF'
               AND away_team = 'Citadel Bulldogs'
               AND home_score IS NULL
        ) THEN
            CONTINUE;
        END IF;

        UPDATE odds SET game_id = canon WHERE game_id = alias;
        UPDATE picks SET game_id = canon WHERE game_id = alias;
        UPDATE picks_log SET game_id = canon WHERE game_id = alias;
        UPDATE player_prop_odds SET game_id = canon WHERE game_id = alias;

        UPDATE latest_odds l SET game_id = canon
         WHERE l.game_id = alias
           AND NOT EXISTS (SELECT 1 FROM latest_odds c
                            WHERE c.game_id = canon
                              AND c.market = l.market
                              AND c.bookmaker = l.bookmaker);
        DELETE FROM latest_odds WHERE game_id = alias;

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
            RAISE NOTICE 'ncaaf_citadel_alias: leftover odds/picks on alias %, games row kept', alias;
            CONTINUE;
        END IF;

        -- Remaining FK children that can block the games delete. Not picks.
        -- All measured at 0 on 2026-10-16; the live loop could write to the
        -- 2026-10-17 alias between that measurement and this pass.
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
           AND away_team = 'Citadel Bulldogs'
           AND home_score IS NULL;
        GET DIAGNOSTICS n = ROW_COUNT;
        IF n > 0 THEN
            RAISE NOTICE 'ncaaf_citadel_alias: consolidated % onto %', alias, canon;
        END IF;
    END LOOP;
END $$;
