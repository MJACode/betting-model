-- scored_outcomes_doubleheader_guard_2026_09_25 -- NOT APPLIED. NOT IN
-- data/view_migrations.ACTIVE_MIGRATIONS. Needs Matt's go-ahead before either.
--
-- WHY. On 2026-09-25 both games of the BAL@NYY doubleheader shared one games
-- row (MLB_2026-09-25_BAL_NYY), and mv_scored_pick_outcomes -- which joins
-- picks to games on game_id -- graded game-2 rows on game 1's final, as the
-- settler did. The id fix (data/mlb_game_id.py) gives game 2 its own `_G2` row
-- going forward, so NEW rows need nothing here. This file is for the rows
-- already stored under a collapsed id: it ungrades ('U', so the row leaves the
-- view) a pick whose scored row went live more than 60 minutes before the
-- pick's own start, or that was created after the row's game had ended.
--
-- MEASURED 2026-09-25 (read-only, Supabase): 652 of 151,448 matview rows would
-- leave it, on 7 games, 5 of them BETs. Six games are 2026 doubleheaders
-- (07-22 BAL_BOS, 07-22 PIT_NYY, 07-28 CLE_CIN, 07-29 ATL_NYM, 08-29 ARI_SF,
-- 08-29 BOS_NYY). The seventh was MLB_2026-08-13_CIN_CWS (91 rows).
--
-- CIN_CWS WAS A REGRESSION, FIXED HERE (2026-09-28). It is a single game
-- (Stats API gamePk 824561, doubleHeader N, 12:10 PM CT = 17:10Z, firstPitch
-- 17:10Z, 186 min, no delay). The book listed it at 18:11Z until ~15:00Z,
-- then 17:11Z; the games row's commence_time was later re-stamped back to
-- 18:11Z. The 91 rows are exactly its 7 AVOID + 84 NONE picks written
-- 10:09-14:18Z with game_time 18:11Z -- all BEFORE first pitch, all for this
-- game. The live feed went live at 17:00:01Z, 71 minutes before 18:11, so the
-- 60-minute first-pitch rule ungraded them. A doubleheader game 2 cannot start
-- within two hours of game 1's first pitch (it follows a whole game; the six
-- collapsed rows above measure 340-386 minutes), so the rule now needs 120
-- minutes -- the same gap as paper_tracker._DH_FIRST_PITCH_GAP. Re-measured
-- 2026-09-28 against the current matview (152,966 rows): 518 rows on the six
-- doubleheaders leave it (5 BETs: 656351, 656369, 883305, 883532, 914594),
-- CIN_CWS keeps all 91, and no other game moves.
--
-- A postponement is also 'Final' in the live feed, with no score
-- (MLB_2026-07-27_CLE_CIN); `finals` counts played finals only, as the
-- settler's guard does. The settler's check 5 (final within 30 minutes of the
-- pick's start) is deliberately NOT mirrored here: on the current matview it
-- would move exactly one row, BET 2899429, whose disposition Matt is deciding.
--
-- REVIEW FIXES (2026-09-28).
-- M1: checks 3 and 4 applied to EVERY game here while the settler limits them
--   to doubleheader days -- that, not only the 60-minute threshold, is why
--   CIN_CWS (a single game) lost 91 rows. They now apply only to a
--   doubleheader row: the 25 collapsed 2026 base ids (Stats API gameNumber=2,
--   read 2026-09-28; listed in `dh_rows`) or any base id that has a `_G2`
--   row. The 120-minute gap stays as a second line.
-- M2: every recreated object (the matview and both dependents) gets REVOKE
--   ALL FROM PUBLIC, anon, authenticated before its captured grants are
--   re-applied -- Supabase's default privileges grant anon/authenticated on a
--   new object by name -- and grants keep WITH GRANT OPTION; COMMENTs on the
--   objects and their columns are captured and restored.
-- Idempotency marker: pg_get_viewdef strips comments, so the old in-body
--   marker never matched. The matview's COMMENT carries dh_guard_2026_09_25.
-- Index: a partial index on live_game_state for the `finals` CTE.
--
-- WHAT IT DOES. The matview body is decide_on_best_price_2026_09_09.sql's,
-- unchanged but for the `finals` CTE, one join and two WHEN lines. Its two
-- dependents (v_model_full_outcome_picks, v_model_full_outcome_record -- read
-- from pg_depend on 2026-09-25) are captured with pg_get_viewdef and their
-- grants with aclexplode, dropped, and recreated verbatim. Plain DROP, never
-- CASCADE: an unexpected further dependent makes this RAISE rather than
-- silently lose a view. Idempotent on the dh_guard_2026_09_25 COMMENT marker.
--
-- It does not UPDATE, DELETE or re-settle any stored pick; picks.result is
-- untouched. CREATE MATERIALIZED VIEW populates the view, so no REFRESH.

-- The `finals` CTE reads only played 'Final' states; without this it scans
-- every live_game_state row per refresh.
CREATE INDEX IF NOT EXISTS live_game_state_final_idx
  ON public.live_game_state (game_id, snapshot_at)
  WHERE abstract_game_state = 'Final';

DO $mig$
DECLARE
  v record;
  saved jsonb := '[]'::jsonb;
  mv jsonb;
  obj jsonb;
  g record;
  c record;
BEGIN
  IF COALESCE(obj_description('public.mv_scored_pick_outcomes'::regclass, 'pg_class'), '')
       LIKE '%dh_guard_2026_09_25%' THEN
    RETURN;
  END IF;

  -- Definition, options, grants (with grant option), object comment and
  -- column comments of each object, so it comes back exactly as it was.
  FOR v IN
    SELECT c.oid, c.relname, c.relowner, c.relacl,
           pg_get_viewdef(c.oid, true) AS def, c.reloptions
      FROM pg_class c
     WHERE c.relname IN ('v_model_full_outcome_picks', 'v_model_full_outcome_record',
                         'mv_scored_pick_outcomes')
       AND c.relnamespace = 'public'::regnamespace
     ORDER BY c.relname
  LOOP
    obj := jsonb_build_object(
      'name', v.relname, 'def', v.def,
      'opts', COALESCE(array_to_string(v.reloptions, ', '), ''),
      'comment', obj_description(v.oid, 'pg_class'),
      'colcomments', (SELECT COALESCE(jsonb_agg(jsonb_build_object(
                         'col', a.attname, 'comment', col_description(v.oid, a.attnum))), '[]'::jsonb)
                        FROM pg_attribute a
                       WHERE a.attrelid = v.oid AND a.attnum > 0 AND NOT a.attisdropped
                         AND col_description(v.oid, a.attnum) IS NOT NULL),
      'grants', (SELECT COALESCE(jsonb_agg(jsonb_build_object(
                   'grantee', CASE WHEN a.grantee = 0 THEN 'PUBLIC'
                                   ELSE quote_ident(a.grantee::regrole::text) END,
                   'priv', a.privilege_type, 'opt', a.is_grantable)), '[]'::jsonb)
                   FROM aclexplode(COALESCE(v.relacl, '{}'::aclitem[])) a
                  WHERE a.grantee <> v.relowner));
    IF v.relname = 'mv_scored_pick_outcomes' THEN
      mv := obj;
    ELSE
      saved := saved || obj;
    END IF;
  END LOOP;

  FOR v IN SELECT * FROM jsonb_array_elements(saved) AS e(x) LOOP
    EXECUTE format('DROP VIEW public.%I', v.x->>'name');
  END LOOP;

  DROP MATERIALIZED VIEW public.mv_scored_pick_outcomes;

  EXECUTE $v$
      CREATE MATERIALIZED VIEW public.mv_scored_pick_outcomes AS
      -- dh_guard_2026_09_25: the first 'Final' live state per game, so a pick
      -- created after its scored game had ended is not graded on it.
      WITH dh_rows AS (
        -- M1: checks 3-4 apply to doubleheader rows only. The 25 base ids
        -- 2026 stored collapsed (Stats API gameNumber=2, read 2026-09-28),
        -- plus any base id that has its own `_G2` row.
        SELECT v.game_id FROM (VALUES
          ('MLB_2026-04-04_MIL_KC'),
          ('MLB_2026-04-05_CHC_CLE'),
          ('MLB_2026-04-26_COL_NYM'),
          ('MLB_2026-04-30_HOU_BAL'),
          ('MLB_2026-04-30_SF_PHI'),
          ('MLB_2026-05-23_STL_CIN'),
          ('MLB_2026-05-24_DET_BAL'),
          ('MLB_2026-06-24_CHC_NYM'),
          ('MLB_2026-07-07_MIL_STL'),
          ('MLB_2026-07-11_MIL_PIT'),
          ('MLB_2026-07-17_TB_BOS'),
          ('MLB_2026-07-18_PIT_CLE'),
          ('MLB_2026-07-19_LAD_NYY'),
          ('MLB_2026-07-22_BAL_BOS'),
          ('MLB_2026-07-22_PIT_NYY'),
          ('MLB_2026-07-28_CLE_CIN'),
          ('MLB_2026-07-29_ATL_NYM'),
          ('MLB_2026-08-17_STL_CIN'),
          ('MLB_2026-08-29_ARI_SF'),
          ('MLB_2026-08-29_BOS_NYY'),
          ('MLB_2026-09-04_DET_CLE'),
          ('MLB_2026-09-22_TB_NYY'),
          ('MLB_2026-09-23_TOR_BAL'),
          ('MLB_2026-09-25_BAL_NYY'),
          ('MLB_2026-09-25_CHC_BOS')
        ) AS v(game_id)
        UNION
        SELECT left(g2.game_id, length(g2.game_id) - 3)
          FROM games g2 WHERE g2.sport = 'MLB' AND g2.game_id LIKE '%\_G2'
      ),
      finals AS (
        SELECT s.game_id, MIN(s.snapshot_at::timestamptz) AS final_at
          FROM live_game_state s
         WHERE s.abstract_game_state = 'Final'
           AND s.home_score IS NOT NULL
         GROUP BY s.game_id
      ),
      base AS (
        SELECT
          p.pick_id, p.model_id, p.sport, p.game_date, p.game_time, p.game_id,
          p.pick_label, p.pick_side, p.signal_type, p.confidence_tier,
          p.model_probability, p.edge, p.dk_odds, p.scored_line,
          -- The price the pick was DECIDED at. Rows from before 2026-09-09 were
          -- decided at DraftKings and carry NULL here, so dk_* is exact for them.
          COALESCE(p.decision_book,
                   CASE WHEN p.dk_odds IS NULL THEN NULL ELSE 'draftkings' END) AS decision_book,
          COALESCE(p.decision_odds, p.dk_odds) AS decision_odds,
          COALESCE(p.decision_edge, p.edge)    AS decision_edge,
          p.public_bet_pct, p.injury_flag, p.player_id,
          CASE
            -- DOUBLEHEADER GUARD (2026-09-25). Until MLB game 2 got its own
            -- `_G2` id, both games of a doubleheader shared one games row and
            -- a game-2 pick was graded on game 1's final. Such a pick is
            -- ungraded ('U', so it leaves the view) when the row's live state
            -- began 120+ minutes before the pick's own start (a book start
            -- re-stamped an hour, MLB_2026-08-13_CIN_CWS, is not a game 2), or
            -- when the pick was created after the row's game ended. The same
            -- rule as tracking/paper_tracker._settle_hold_reason checks 3-4,
            -- and like the settler only on a doubleheader row (dh_rows).
            WHEN dh.game_id IS NOT NULL
                 AND g.first_pitch_at IS NOT NULL AND p.game_time IS NOT NULL
                 AND g.first_pitch_at::timestamptz
                     < p.game_time::timestamptz - interval '120 minutes' THEN 'U'
            WHEN dh.game_id IS NOT NULL
                 AND f.final_at IS NOT NULL AND p.created_at IS NOT NULL
                 AND p.created_at::timestamptz > f.final_at THEN 'U'
            WHEN p.model_id = 'mlb_moneyline' THEN CASE
              WHEN g.home_win IS NULL THEN 'U'
              WHEN p.pick_side='home' AND g.home_win=1 OR p.pick_side='away' AND g.home_win=0 THEN 'W' ELSE 'L' END
            WHEN p.model_id = 'mlb_over_under' THEN CASE
              WHEN g.home_score IS NULL OR p.scored_line IS NULL THEN 'U'
              WHEN (g.home_score+g.away_score) = p.scored_line THEN 'P'
              WHEN p.pick_side='over' AND (g.home_score+g.away_score) > p.scored_line
                OR p.pick_side='under' AND (g.home_score+g.away_score) < p.scored_line THEN 'W' ELSE 'L' END
            -- scored_line is the HOME spread, so an away cover is (away-home) - line.
            WHEN p.model_id = 'mlb_runline' THEN CASE
              WHEN g.home_score IS NULL OR p.scored_line IS NULL THEN 'U'
              WHEN (CASE WHEN p.pick_side='home' THEN g.home_score-g.away_score+p.scored_line
                         ELSE g.away_score-g.home_score-p.scored_line END) = 0 THEN 'P'
              WHEN (CASE WHEN p.pick_side='home' THEN g.home_score-g.away_score+p.scored_line
                         ELSE g.away_score-g.home_score-p.scored_line END) > 0 THEN 'W' ELSE 'L' END
            WHEN p.model_id = 'mlb_f5_moneyline' THEN CASE
              WHEN g.home_score_f5 IS NULL OR g.away_score_f5 IS NULL THEN 'U'
              WHEN g.home_score_f5 = g.away_score_f5 THEN 'P'
              WHEN p.pick_side='home' AND g.home_score_f5 > g.away_score_f5
                OR p.pick_side='away' AND g.away_score_f5 > g.home_score_f5 THEN 'W' ELSE 'L' END
            WHEN p.model_id = 'wnba_moneyline' THEN CASE
              WHEN g.home_win IS NULL THEN 'U'
              WHEN p.pick_side='home' AND g.home_win=1 OR p.pick_side='away' AND g.home_win=0 THEN 'W' ELSE 'L' END
            WHEN p.model_id LIKE 'mlb_prop_%' THEN CASE
              WHEN p.scored_line IS NULL OR pl.actual IS NULL THEN 'U'
              WHEN pl.actual::numeric = p.scored_line THEN 'P'
              WHEN p.pick_side='over' AND pl.actual::numeric > p.scored_line
                OR p.pick_side='under' AND pl.actual::numeric < p.scored_line THEN 'W' ELSE 'L' END
            WHEN p.model_id LIKE 'wnba_prop_%' THEN CASE
              WHEN p.scored_line IS NULL OR wl.actual IS NULL THEN 'U'
              WHEN wl.actual::numeric = p.scored_line THEN 'P'
              WHEN p.pick_side='over' AND wl.actual::numeric > p.scored_line
                OR p.pick_side='under' AND wl.actual::numeric < p.scored_line THEN 'W' ELSE 'L' END
            ELSE 'U'
          END AS res,
          EXTRACT(hour FROM (p.game_time::timestamptz AT TIME ZONE 'America/New_York')) AS et_hour
        FROM picks p
        LEFT JOIN games g ON g.game_id = p.game_id
        LEFT JOIN finals f ON f.game_id = p.game_id
        LEFT JOIN dh_rows dh ON dh.game_id = p.game_id
        LEFT JOIN LATERAL (
          SELECT max(CASE p.model_id
            WHEN 'mlb_prop_pitcher_k'     THEN l.p_strikeouts
            WHEN 'mlb_prop_pitcher_walks' THEN l.p_walks
            WHEN 'mlb_prop_pitcher_hits'  THEN l.p_hits_allowed
            WHEN 'mlb_prop_pitcher_er'    THEN l.p_earned_runs
            WHEN 'mlb_prop_pitcher_outs'  THEN (floor(l.innings_pitched)*3 + round((l.innings_pitched-floor(l.innings_pitched))*10))::integer
            WHEN 'mlb_prop_batter_hits'   THEN l.hits
            WHEN 'mlb_prop_batter_tb'     THEN l.total_bases
            WHEN 'mlb_prop_batter_rbi'    THEN l.rbi
            WHEN 'mlb_prop_batter_runs'   THEN l.runs
            WHEN 'mlb_prop_batter_sb'     THEN l.stolen_bases
            WHEN 'mlb_prop_batter_walks'  THEN l.walks
            WHEN 'mlb_prop_batter_hr'     THEN l.home_runs
            ELSE NULL END) AS actual
          FROM player_game_log l
          WHERE l.game_id = p.game_id AND l.player_id = p.player_id) pl ON true
        LEFT JOIN LATERAL (
          SELECT max(CASE p.model_id
            WHEN 'wnba_prop_player_points'   THEN l.points
            WHEN 'wnba_prop_player_rebounds' THEN l.rebounds
            WHEN 'wnba_prop_player_assists'  THEN l.assists
            WHEN 'wnba_prop_player_threes'   THEN l.fg3_made
            WHEN 'wnba_prop_player_pra'      THEN l.points + l.rebounds + l.assists
            ELSE NULL END) AS actual
          FROM wnba_player_game_log l
          WHERE l.game_id = p.game_id AND l.player_id = p.player_id) wl ON true
        WHERE p.game_date >= '2026-04-14'
          AND NOT (p.model_id = 'mlb_over_under' AND p.game_date < '2026-07-05')
          AND p.is_live IS NOT TRUE
          AND (p.model_id IN ('mlb_moneyline','mlb_over_under','mlb_runline','mlb_f5_moneyline','wnba_moneyline')
               OR p.model_id LIKE 'mlb_prop_%' OR p.model_id LIKE 'wnba_prop_%')
      )
      SELECT
        b.pick_id, b.model_id, b.sport, b.game_date, b.game_time, b.game_id,
        b.pick_label, b.pick_side, b.signal_type, b.confidence_tier,
        b.model_probability, b.edge, b.dk_odds, b.scored_line,
        b.decision_book, b.decision_odds, b.decision_edge,
        b.public_bet_pct, b.injury_flag, b.player_id,
        CASE WHEN b.model_id LIKE '%\_prop\_%' THEN 'prop' ELSE 'game' END AS bet_kind,
        CASE WHEN b.decision_odds IS NULL THEN NULL
             WHEN b.decision_odds < 0 THEN 'fav' ELSE 'dog' END AS price_side,
        CASE
          WHEN b.et_hour IS NULL THEN NULL
          WHEN b.et_hour >= 22 OR b.et_hour < 5 THEN 'late'
          WHEN b.et_hour < 16 THEN 'day'
          WHEN b.et_hour < 19 THEN 'early'
          ELSE 'prime'
        END AS time_slot,
        CASE b.res WHEN 'W' THEN 'WIN' WHEN 'L' THEN 'LOSS' ELSE 'PUSH' END AS result,
        -- Units on a 1u flat stake at the DECISION price.
        CASE
          WHEN b.decision_odds IS NULL THEN NULL
          WHEN b.res = 'W' THEN CASE WHEN b.decision_odds > 0 THEN b.decision_odds/100.0 ELSE 100.0/abs(b.decision_odds) END
          WHEN b.res = 'L' THEN -1
          ELSE 0
        END AS profit_units
      FROM base b
      WHERE b.res IN ('W','L','P')
    $v$;

  CREATE UNIQUE INDEX mv_scored_pick_outcomes_pick_id_idx
    ON public.mv_scored_pick_outcomes (pick_id);
  CREATE INDEX mv_scored_pick_outcomes_model_idx
    ON public.mv_scored_pick_outcomes (model_id, model_probability, decision_edge);

  -- M2: every recreated object starts from NO grants (Supabase's default
  -- privileges would otherwise hand anon/authenticated everything), then gets
  -- back exactly what it had, WITH GRANT OPTION kept, and its comments.
  saved := jsonb_build_array(mv) || saved;
  FOR v IN SELECT * FROM jsonb_array_elements(saved) AS e(x) LOOP
    IF v.x->>'name' <> 'mv_scored_pick_outcomes' THEN
      EXECUTE format('CREATE VIEW public.%I %s AS %s',
                     v.x->>'name',
                     CASE WHEN v.x->>'opts' = '' THEN ''
                          ELSE 'WITH (' || (v.x->>'opts') || ')' END,
                     v.x->>'def');
    END IF;
    EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC, anon, authenticated',
                   v.x->>'name');
    FOR g IN SELECT * FROM jsonb_array_elements(v.x->'grants') AS e(y) LOOP
      EXECUTE format('GRANT %s ON public.%I TO %s%s',
                     g.y->>'priv', v.x->>'name', g.y->>'grantee',
                     CASE WHEN (g.y->>'opt')::boolean THEN ' WITH GRANT OPTION' ELSE '' END);
    END LOOP;
    IF v.x->>'name' <> 'mv_scored_pick_outcomes' AND v.x->>'comment' IS NOT NULL THEN
      EXECUTE format('COMMENT ON VIEW public.%I IS %L', v.x->>'name', v.x->>'comment');
    END IF;
    FOR c IN SELECT * FROM jsonb_array_elements(v.x->'colcomments') AS e(z) LOOP
      EXECUTE format('COMMENT ON COLUMN public.%I.%I IS %L',
                     v.x->>'name', c.z->>'col', c.z->>'comment');
    END LOOP;
  END LOOP;

  -- The idempotency marker (pg_get_viewdef strips comments in the body).
  EXECUTE format('COMMENT ON MATERIALIZED VIEW public.mv_scored_pick_outcomes IS %L',
                 concat_ws(E'\n', NULLIF(mv->>'comment', ''),
                           'dh_guard_2026_09_25: doubleheader rows ungraded when their '
                           'row went live 120+ min before the pick or ended before it '
                           'was written (data/migrations/scored_outcomes_doubleheader_guard_2026_09_25.sql)'));

  RAISE NOTICE 'mv_scored_pick_outcomes rebuilt with the doubleheader guard';
END
$mig$;
