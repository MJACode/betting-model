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
-- 08-29 BOS_NYY). The seventh, MLB_2026-08-13_CIN_CWS (91 rows), is NOT a
-- doubleheader on the Stats API schedule and is unexplained -- look at it
-- before applying.
--
-- WHAT IT DOES. The matview body is decide_on_best_price_2026_09_09.sql's,
-- unchanged but for the `finals` CTE, one join and two WHEN lines. Its two
-- dependents (v_model_full_outcome_picks, v_model_full_outcome_record -- read
-- from pg_depend on 2026-09-25) are captured with pg_get_viewdef and their
-- grants with aclexplode, dropped, and recreated verbatim. Plain DROP, never
-- CASCADE: an unexpected further dependent makes this RAISE rather than
-- silently lose a view. Idempotent on the dh_guard_2026_09_25 marker.
--
-- It does not UPDATE, DELETE or re-settle any stored pick; picks.result is
-- untouched. CREATE MATERIALIZED VIEW populates the view, so no REFRESH.

DO $mig$
DECLARE
  d text;
  v record;
  saved jsonb := '[]'::jsonb;
  g record;
BEGIN
  SELECT pg_get_viewdef('public.mv_scored_pick_outcomes'::regclass, true) INTO d;
  IF position('dh_guard_2026_09_25' in d) > 0 OR position('final_at' in d) > 0 THEN
    RETURN;
  END IF;

  -- Capture the dependents (definition + options + grants) before dropping.
  FOR v IN
    SELECT c.oid, c.relname, pg_get_viewdef(c.oid, true) AS def, c.reloptions
      FROM pg_class c
     WHERE c.relname IN ('v_model_full_outcome_picks', 'v_model_full_outcome_record')
       AND c.relnamespace = 'public'::regnamespace
  LOOP
    saved := saved || jsonb_build_object(
      'name', v.relname, 'def', v.def,
      'opts', COALESCE(array_to_string(v.reloptions, ', '), ''),
      'grants', (SELECT COALESCE(jsonb_agg(jsonb_build_object(
                   'grantee', CASE WHEN a.grantee = 0 THEN 'PUBLIC'
                                   ELSE quote_ident(a.grantee::regrole::text) END,
                   'priv', a.privilege_type)), '[]'::jsonb)
                   FROM pg_class c2, aclexplode(c2.relacl) a
                  WHERE c2.oid = v.oid AND a.grantee <> c2.relowner));
    EXECUTE format('DROP VIEW public.%I', v.relname);
  END LOOP;

  DROP MATERIALIZED VIEW public.mv_scored_pick_outcomes;

  EXECUTE $v$
      CREATE MATERIALIZED VIEW public.mv_scored_pick_outcomes AS
      -- dh_guard_2026_09_25: the first 'Final' live state per game, so a pick
      -- created after its scored game had ended is not graded on it.
      WITH finals AS (
        SELECT s.game_id, MIN(s.snapshot_at::timestamptz) AS final_at
          FROM live_game_state s
         WHERE s.abstract_game_state = 'Final'
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
            -- began more than SUSPICIOUS_EARLY_MINUTES (60) before the pick's
            -- own start, or when the pick was created after the row's game
            -- ended. The same rule as tracking/paper_tracker._settle_hold_reason.
            WHEN g.first_pitch_at IS NOT NULL AND p.game_time IS NOT NULL
                 AND g.first_pitch_at::timestamptz
                     < p.game_time::timestamptz - interval '60 minutes' THEN 'U'
            WHEN f.final_at IS NOT NULL AND p.created_at IS NOT NULL
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
  REVOKE ALL ON public.mv_scored_pick_outcomes FROM anon, authenticated;
  GRANT SELECT ON public.mv_scored_pick_outcomes TO anon, authenticated;

  -- Recreate the dependents exactly as captured, with their grants.
  FOR v IN SELECT * FROM jsonb_array_elements(saved) AS e(x) LOOP
    EXECUTE format('CREATE VIEW public.%I %s AS %s',
                   v.x->>'name',
                   CASE WHEN v.x->>'opts' = '' THEN ''
                        ELSE 'WITH (' || (v.x->>'opts') || ')' END,
                   v.x->>'def');
    FOR g IN SELECT * FROM jsonb_array_elements(v.x->'grants') AS e(y) LOOP
      EXECUTE format('GRANT %s ON public.%I TO %s',
                     g.y->>'priv', v.x->>'name', g.y->>'grantee');
    END LOOP;
  END LOOP;

  RAISE NOTICE 'mv_scored_pick_outcomes rebuilt with the doubleheader guard';
END
$mig$;
