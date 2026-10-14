-- discord_post_one_pick (2026-10-14)
--
-- WHY. A Discord post is one lock_key in push_sent (discord_signal or
-- discord_live). Measured read-only the same day on production: 34 of those
-- posts have more than one picks row on that exact key, 35 extra rows
-- (23 discord_live posts, 23 extras; 11 discord_signal posts, 12 extras —
-- the NHL regulation post has two extras). Nine of the groups disagree with
-- the kept row, and all nine are NFL: eight live props whose extra row is a
-- different line, and T.J. Hockenson (pick 2068718 under, VOID, against the
-- kept over 2068714, WIN). A looser join on game_id + model_id alone is a
-- different, larger set and would attach picks that are not the posted bet.
-- That set is not marked here.
--
-- WHAT CHANGES. Each extra row gets condition_status = 'DUPLICATE' and a
-- note naming the kept pick. Result, profit, line, price, created_at and
-- settled_at stay as written. The kept row is the one the publisher would
-- post for that lock: a BET before anything else, then the earliest
-- created_at, then the lowest pick_id. None of the 35 extras is a graded
-- WIN, LOSS or PUSH, so the settled record does not move. The two extras
-- that were VOID (2478678 Delaware live, 2068718 Hockenson) become
-- DUPLICATE; their result stays NO_ACTION and the kept row is not touched.
-- picks_audit_trigger logs the UPDATE.
--
-- GUARD, TWO INDEXES, after the marks.
--
-- uq_picks_one_bet_per_publish_lock: one standing BET per publish lock
-- (tracking/publish_keys lock_key_sql / live_lock_key_sql). VOID, DUPLICATE
-- and result NO_ACTION are outside it. Opposite-side AVOID and NONE rows
-- stay insertable: the pregame lock omits pick_side on purpose, and a
-- unique index over every signal type would drop a BET inserted after an
-- AVOID (home then away, over then under). Pick 1968 (Braxton Ashcraft
-- under, NO_ACTION) shares a lock with the graded over 2057 and is not a
-- Discord extra; the NO_ACTION exclusion is what lets this index build.
-- A new insert's result is NULL, so a second standing BET still conflicts.
--
-- uq_picks_one_live_row: one non-DUPLICATE live BET per
-- tracking/publish_keys.unique_row_sql (game_date, model, game, player,
-- side). The pregame unique index already has this identity and does not
-- cover live rows. The first draft covered every signal type. The NFL live
-- writer inserts the AVOID first and the BET with ON CONFLICT DO NOTHING,
-- so that AVOID occupied the key and the BET was not written.
-- signal_type = 'BET' is the dedupe (a second standing BET still conflicts)
-- and the AVOID stays. live_row_index_bets_only_2026_10_14.sql replaces an
-- index already created with the wider predicate. Different sides still
-- both insert.
--
-- Both creates NOTICE and skip when a duplicate of that identity is still
-- present. They do not RAISE: this file is one transaction, and a failed
-- CREATE would roll the marks back. Scorers already INSERT ... ON CONFLICT
-- DO NOTHING, so a losing second row is not written.
--
-- GUARD ON THE UPDATE. Each extra is named with its model and game id, must
-- not already be DUPLICATE, must still be ungraded or NO_ACTION, and the
-- kept pick must still be that model and game. A second pass changes nothing.
--
-- ROLLBACK: UPDATE picks SET condition_status = NULL, condition_note = NULL
--           WHERE condition_status = 'DUPLICATE'
--             AND condition_note LIKE 'Extra copy behind the same Discord lock%';
--           Then drop the two indexes if they were created by this file and
--           no later writer depends on them.

DO $mig$
DECLARE
  n          integer;
  bet_dupes  bigint;
  live_dupes bigint;
  has_bet    boolean;
  has_live   boolean;
BEGIN
  UPDATE public.picks x
     SET condition_status = 'DUPLICATE',
         condition_note   = 'Extra copy behind the same Discord lock as pick '
                         || e.kept_id::text
                         || '. Outcome, line, price and written time unchanged. '
                         || '2026-10-14.'
    FROM (VALUES
      (2131279::bigint, 2131569::bigint, 'nfl_live_prop', 'NFL_2026_01_MIA_LV'),
      (2131460::bigint, 2131570::bigint, 'nfl_live_prop', 'NFL_2026_01_MIA_LV'),
      (2478678::bigint, 2476480::bigint, 'ncaaf_live_win_prob', 'NCAAF_2026-09-19_coastal-carolina_delaware'),
      (2558040::bigint, 2559202::bigint, 'nfl_live_prop', 'NFL_2026_02_CAR_ATL'),
      (2558709::bigint, 2559049::bigint, 'nfl_live_prop', 'NFL_2026_02_CLE_TB'),
      (2559044::bigint, 2559045::bigint, 'nfl_live_prop', 'NFL_2026_02_MIN_CHI'),
      (2559046::bigint, 2559047::bigint, 'nfl_live_prop', 'NFL_2026_02_PIT_NE'),
      (2559145::bigint, 2559211::bigint, 'nfl_live_prop', 'NFL_2026_02_CIN_HOU'),
      (2559326::bigint, 2559327::bigint, 'nfl_live_prop', 'NFL_2026_02_PHI_TEN'),
      (2559340::bigint, 2559341::bigint, 'nfl_live_prop', 'NFL_2026_02_GB_NYJ'),
      (2562773::bigint, 2562774::bigint, 'nfl_live_prop', 'NFL_2026_02_JAX_DEN'),
      (2562775::bigint, 2562776::bigint, 'nfl_live_prop', 'NFL_2026_02_LV_LAC'),
      (2562833::bigint, 2562834::bigint, 'nfl_live_prop', 'NFL_2026_02_JAX_DEN'),
      (2563081::bigint, 2563082::bigint, 'nfl_live_prop', 'NFL_2026_02_LV_LAC'),
      (2563083::bigint, 2563084::bigint, 'nfl_live_prop', 'NFL_2026_02_WAS_DAL'),
      (2563085::bigint, 2563086::bigint, 'nfl_live_prop', 'NFL_2026_02_WAS_DAL'),
      (2563894::bigint, 2563895::bigint, 'nfl_live_prop', 'NFL_2026_02_MIA_SF'),
      (2565688::bigint, 2567487::bigint, 'nfl_live_prop', 'NFL_2026_02_SEA_ARI'),
      (2567188::bigint, 2567189::bigint, 'nfl_live_prop', 'NFL_2026_02_SEA_ARI'),
      (2577062::bigint, 2577063::bigint, 'nfl_live_prop', 'NFL_2026_02_IND_KC'),
      (2626444::bigint, 2628978::bigint, 'nfl_live_prop', 'NFL_2026_02_NYG_LA'),
      (2838267::bigint, 2838310::bigint, 'nfl_live_prop', 'NFL_2026_03_ATL_GB'),
      (3208387::bigint, 3208455::bigint, 'nfl_live_prop', 'NFL_2026_04_IND_WAS'),
      (1387924::bigint, 1387923::bigint, 'mlb_f5_moneyline', 'MLB_2026-08-23_LAA_TEX'),
      (1391561::bigint, 1391560::bigint, 'mlb_f5_moneyline', 'MLB_2026-08-24_COL_WSH'),
      (1404777::bigint, 1404778::bigint, 'mlb_runline', 'MLB_2026-08-28_LAD_DET'),
      (1404793::bigint, 1404792::bigint, 'mlb_moneyline', 'MLB_2026-08-28_SD_TB'),
      (1410045::bigint, 1410044::bigint, 'mlb_f5_moneyline', 'MLB_2026-08-29_HOU_NYM'),
      (1410056::bigint, 1410057::bigint, 'mlb_f5_moneyline', 'MLB_2026-08-29_BAL_OAK'),
      (1410071::bigint, 1410070::bigint, 'mlb_f5_moneyline', 'MLB_2026-08-29_SD_TB'),
      (1631577::bigint, 1584585::bigint, 'mlb_prop_pitcher_k', 'MLB_2026-09-04_DET_CLE'),
      (1631579::bigint, 1603849::bigint, 'mlb_prop_pitcher_k', 'MLB_2026-09-04_DET_CLE'),
      (2068718::bigint, 2068714::bigint, 'nfl_prop_market', 'NFL_2026_01_GB_MIN'),
      (3585550::bigint, 3585552::bigint, 'nhl_moneyline_regulation', 'NHL_2026-10-15_PHI_DET'),
      (3585551::bigint, 3585552::bigint, 'nhl_moneyline_regulation', 'NHL_2026-10-15_PHI_DET')
    ) AS e(mark_id, kept_id, model_id, game_id)
   WHERE x.pick_id = e.mark_id
     AND x.model_id = e.model_id
     AND x.game_id = e.game_id
     AND x.condition_status IS DISTINCT FROM 'DUPLICATE'
     AND (x.result IS NULL OR x.result = 'NO_ACTION')
     AND EXISTS (
       SELECT 1 FROM public.picks k
        WHERE k.pick_id = e.kept_id
          AND k.model_id = x.model_id
          AND k.game_id = x.game_id
          AND k.pick_id <> x.pick_id);
  GET DIAGNOSTICS n = ROW_COUNT;
  RAISE NOTICE 'discord post extras marked DUPLICATE: %', n;

  SELECT EXISTS (
    SELECT 1 FROM pg_indexes
     WHERE schemaname = 'public'
       AND indexname = 'uq_picks_one_bet_per_publish_lock'
  ) INTO has_bet;

  IF NOT has_bet THEN
    SELECT count(*) INTO bet_dupes FROM (
      SELECT 1 FROM public.picks
       WHERE signal_type = 'BET'
         AND condition_status IS DISTINCT FROM 'DUPLICATE'
         AND condition_status IS DISTINCT FROM 'VOID'
         AND result IS DISTINCT FROM 'NO_ACTION'
       GROUP BY CASE WHEN COALESCE(is_live, false)
                     THEN 'live:' || game_id || ':' || model_id || ':'
                          || COALESCE(pick_side, '')
                          || COALESCE(':' || player_id, '')
                          || COALESCE(':' || player_key, '')
                          || COALESCE(':' || prop_market, '')
                     ELSE game_id || ':' || model_id
                          || COALESCE(':' || player_id, '')
                          || COALESCE(':' || player_key, '')
                          || COALESCE(':' || prop_market, '')
                END
      HAVING count(*) > 1
    ) d;
    IF bet_dupes > 0 THEN
      RAISE NOTICE 'uq_picks_one_bet_per_publish_lock skipped: % publish lock(s) still have two standing BETs', bet_dupes;
    ELSE
      CREATE UNIQUE INDEX uq_picks_one_bet_per_publish_lock
          ON public.picks ((
            CASE WHEN COALESCE(is_live, false)
                 THEN 'live:' || game_id || ':' || model_id || ':'
                      || COALESCE(pick_side, '')
                      || COALESCE(':' || player_id, '')
                      || COALESCE(':' || player_key, '')
                      || COALESCE(':' || prop_market, '')
                 ELSE game_id || ':' || model_id
                      || COALESCE(':' || player_id, '')
                      || COALESCE(':' || player_key, '')
                      || COALESCE(':' || prop_market, '')
            END
          ))
       WHERE signal_type = 'BET'
         AND condition_status IS DISTINCT FROM 'DUPLICATE'
         AND condition_status IS DISTINCT FROM 'VOID'
         AND result IS DISTINCT FROM 'NO_ACTION';
      RAISE NOTICE 'uq_picks_one_bet_per_publish_lock created';
    END IF;
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM pg_indexes
     WHERE schemaname = 'public'
       AND indexname = 'uq_picks_one_live_row'
  ) INTO has_live;

  IF NOT has_live THEN
    SELECT count(*) INTO live_dupes FROM (
      SELECT 1 FROM public.picks
       WHERE is_live IS TRUE
         AND signal_type = 'BET'
         AND condition_status IS DISTINCT FROM 'DUPLICATE'
       GROUP BY game_date, model_id, game_id,
                COALESCE(player_id, ''), COALESCE(player_key, ''),
                COALESCE(prop_market, ''), pick_side
      HAVING count(*) > 1
    ) d;
    IF live_dupes > 0 THEN
      RAISE NOTICE 'uq_picks_one_live_row skipped: % live identity group(s) still have two standing BETs', live_dupes;
    ELSE
      CREATE UNIQUE INDEX uq_picks_one_live_row
          ON public.picks (game_date, model_id, game_id,
                           COALESCE(player_id, ''),
                           COALESCE(player_key, ''),
                           COALESCE(prop_market, ''),
                           pick_side)
       WHERE is_live IS TRUE
         AND signal_type = 'BET'
         AND condition_status IS DISTINCT FROM 'DUPLICATE';
      RAISE NOTICE 'uq_picks_one_live_row created';
    END IF;
  END IF;
END
$mig$;
