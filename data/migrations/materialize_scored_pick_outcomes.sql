-- mv_scored_pick_outcomes (2026-08-08): every scored pick since paper start
-- (BET + AVOID + dead-zone NONE) with the outcome it WOULD have had, graded
-- from final scores / player_game_log — regardless of whether it was ever a
-- BET. This is the universe the mobile custom-model builder backtests against:
-- without it a custom model could only tighten the built-in cuts, because only
-- BET picks are ever settled into picks.result (~3k settled vs ~100k gradeable).
--
-- Grading CASEs mirror v_model_full_outcome_picks (keep in step — this is the
-- documented grading-logic maintenance trap; runline away side = (away-home) -
-- scored_line). picks.result is deliberately NOT written for non-BET rows:
-- paper-trading P&L and the go-live gate stay BET-only.
--
-- Materialized because the same query as a plain view ran ~6s per builder
-- keystroke; refreshed daily by run_pipeline step 0d (refresh-outcomes) right
-- after settle, CONCURRENTLY so readers never block (hence the unique index).
-- Derived filter columns (bet_kind / price_side / time_slot) are defined HERE
-- so the bucket definitions live in one place; the client mirrors them only
-- for the live board (customModelFilters.ts).
--
-- THE GRADING LATERALS AGGREGATE, THEY DO NOT `LIMIT 1` (2026-09-03, mike).
-- player_game_log holds a BATTING row and a PITCHING row for the same
-- (game_id, player_id) whenever a pitcher also bats — 20,363 such pairs, all
-- of them exactly one of each. `LIMIT 1` with no ORDER BY therefore took an
-- ARBITRARY row, and landing on the batting row for a pitcher prop left the
-- mapped column NULL, so the pick graded 'U' and was dropped by the final
-- WHERE. It never mis-graded (no row carries both sides), but WHICH picks
-- survived was nondeterministic across REFRESH — the published record was not
-- reproducible. max() over the matching rows returns the single non-NULL
-- value, is identical for the ordinary one-row case, and still yields exactly
-- one row per pick (an ungrouped aggregate always does), so the LEFT JOIN
-- semantics are unchanged.
--
-- Applied as migrations: add_scored_pick_outcomes_for_custom_models (plain
-- view, superseded) → materialize_scored_pick_outcomes →
-- fix_scored_pick_outcomes_lateral. The definition below is the live one.

CREATE MATERIALIZED VIEW public.mv_scored_pick_outcomes AS
WITH base AS (
  SELECT
    p.pick_id, p.model_id, p.sport, p.game_date, p.game_time, p.game_id,
    p.pick_label, p.pick_side, p.signal_type, p.confidence_tier,
    p.model_probability, p.edge, p.dk_odds, p.scored_line,
    p.public_bet_pct, p.injury_flag, p.player_id,
    CASE
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
    -- Honest-era gate, same as the record views (pre-07-05 O/U probs are
    -- NaN-total_line tainted).
    AND NOT (p.model_id = 'mlb_over_under' AND p.game_date < '2026-07-05')
    AND p.is_live IS NOT TRUE
    AND (p.model_id IN ('mlb_moneyline','mlb_over_under','mlb_runline','mlb_f5_moneyline','wnba_moneyline')
         OR p.model_id LIKE 'mlb_prop_%' OR p.model_id LIKE 'wnba_prop_%')
)
SELECT
  b.pick_id, b.model_id, b.sport, b.game_date, b.game_time, b.game_id,
  b.pick_label, b.pick_side, b.signal_type, b.confidence_tier,
  b.model_probability, b.edge, b.dk_odds, b.scored_line,
  b.public_bet_pct, b.injury_flag, b.player_id,
  CASE WHEN b.model_id LIKE '%\_prop\_%' THEN 'prop' ELSE 'game' END AS bet_kind,
  CASE WHEN b.dk_odds IS NULL THEN NULL
       WHEN b.dk_odds < 0 THEN 'fav' ELSE 'dog' END AS price_side,
  CASE
    WHEN b.et_hour IS NULL THEN NULL
    WHEN b.et_hour >= 22 OR b.et_hour < 5 THEN 'late'
    WHEN b.et_hour < 16 THEN 'day'
    WHEN b.et_hour < 19 THEN 'early'
    ELSE 'prime'
  END AS time_slot,
  CASE b.res WHEN 'W' THEN 'WIN' WHEN 'L' THEN 'LOSS' ELSE 'PUSH' END AS result,
  CASE
    WHEN b.dk_odds IS NULL THEN NULL
    WHEN b.res = 'W' THEN CASE WHEN b.dk_odds > 0 THEN b.dk_odds/100.0 ELSE 100.0/abs(b.dk_odds) END
    WHEN b.res = 'L' THEN -1
    ELSE 0
  END AS profit_units
FROM base b
WHERE b.res IN ('W','L','P');

-- Unique index is required for REFRESH ... CONCURRENTLY (no read downtime).
CREATE UNIQUE INDEX mv_scored_pick_outcomes_pick_id_idx
  ON public.mv_scored_pick_outcomes (pick_id);
-- Every custom-model query filters by model_id first.
CREATE INDEX mv_scored_pick_outcomes_model_idx
  ON public.mv_scored_pick_outcomes (model_id, model_probability, edge);

-- Supabase's default privileges grant anon/authenticated ALL privileges on new
-- objects in public, and matviews have no RLS to fall back on — without the
-- REVOKE, anon would hold MAINTAIN and could run REFRESH MATERIALIZED VIEW
-- with the public API key (free DB-CPU burn). Found by the post-merge security
-- review; applied as migration tighten_mv_scored_pick_outcomes_grants.
REVOKE ALL ON public.mv_scored_pick_outcomes FROM anon, authenticated;
GRANT SELECT ON public.mv_scored_pick_outcomes TO anon, authenticated;
