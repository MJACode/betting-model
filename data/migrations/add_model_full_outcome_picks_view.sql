-- Migration: add_model_full_outcome_picks_view (applied 2026-07-02)
--
-- Per-pick companion to v_model_full_outcome_record. The Models tab shows each
-- model's record from the aggregate view (every scored pick — BET + dead-zone
-- NONE + AVOID — graded from final scores / game-log actuals at the CURRENT
-- model_action_thresholds cut), but the model detail screen's pick history only
-- listed SETTLED BET picks, so the list never matched the record (only BET
-- picks ever get settled; dead-zone picks that clear today's cut were missing).
--
-- This view emits ONE ROW PER GRADED PICK using the exact same base grading +
-- passes logic as v_model_full_outcome_record (including the 2026-07-02
-- runline away-side sign fix), filtered to picks that pass the current cut and
-- have a decided outcome (W/L/P). Row counts per model_id reconcile with the
-- record view's `bets` column by construction.
--
-- Columns: pick_id (join/navigate to picks), model_id, game_date, game_id,
--   pick_label, pick_side, model_probability, edge, dk_odds, scored_line,
--   result ('WIN'|'LOSS'|'PUSH'), profit_units (1-unit flat at dk_odds; NULL
--   when the pick has no real price — e.g. prob-only HR — so no fabricated P&L).
--
-- security_invoker; anon SELECT (all underlying tables already have anon read
-- policies: picks, games, player_game_log, wnba_player_game_log,
-- model_action_thresholds).

CREATE OR REPLACE VIEW public.v_model_full_outcome_picks WITH (security_invoker = on) AS
WITH base AS (
  SELECT p.pick_id,
         p.model_id,
         p.game_date,
         p.game_id,
         p.pick_label,
         p.pick_side,
         p.model_probability AS prob,
         p.edge,
         p.dk_odds,
         p.scored_line,
         CASE
           WHEN p.model_id = 'mlb_moneyline' THEN
             CASE WHEN g.home_win IS NULL THEN 'U'
                  WHEN (p.pick_side = 'home' AND g.home_win = 1) OR (p.pick_side = 'away' AND g.home_win = 0) THEN 'W'
                  ELSE 'L' END
           WHEN p.model_id = 'mlb_over_under' THEN
             CASE WHEN g.home_score IS NULL OR p.scored_line IS NULL THEN 'U'
                  WHEN (g.home_score + g.away_score) = p.scored_line THEN 'P'
                  WHEN (p.pick_side = 'over' AND (g.home_score + g.away_score) > p.scored_line)
                    OR (p.pick_side = 'under' AND (g.home_score + g.away_score) < p.scored_line) THEN 'W'
                  ELSE 'L' END
           WHEN p.model_id = 'mlb_runline' THEN
             CASE WHEN g.home_score IS NULL OR p.scored_line IS NULL THEN 'U'
                  WHEN (CASE WHEN p.pick_side = 'home' THEN (g.home_score - g.away_score) + p.scored_line
                             ELSE (g.away_score - g.home_score) - p.scored_line END) = 0 THEN 'P'
                  WHEN (CASE WHEN p.pick_side = 'home' THEN (g.home_score - g.away_score) + p.scored_line
                             ELSE (g.away_score - g.home_score) - p.scored_line END) > 0 THEN 'W'
                  ELSE 'L' END
           WHEN p.model_id = 'mlb_f5_moneyline' THEN
             CASE WHEN g.home_score_f5 IS NULL OR g.away_score_f5 IS NULL THEN 'U'
                  WHEN g.home_score_f5 = g.away_score_f5 THEN 'P'
                  WHEN (p.pick_side = 'home' AND g.home_score_f5 > g.away_score_f5)
                    OR (p.pick_side = 'away' AND g.away_score_f5 > g.home_score_f5) THEN 'W'
                  ELSE 'L' END
           WHEN p.model_id = 'wnba_moneyline' THEN
             CASE WHEN g.home_win IS NULL THEN 'U'
                  WHEN (p.pick_side = 'home' AND g.home_win = 1) OR (p.pick_side = 'away' AND g.home_win = 0) THEN 'W'
                  ELSE 'L' END
           WHEN p.model_id LIKE 'mlb_prop_%' THEN
             CASE WHEN p.scored_line IS NULL OR pl.actual IS NULL THEN 'U'
                  WHEN pl.actual::numeric = p.scored_line THEN 'P'
                  WHEN (p.pick_side = 'over' AND pl.actual::numeric > p.scored_line)
                    OR (p.pick_side = 'under' AND pl.actual::numeric < p.scored_line) THEN 'W'
                  ELSE 'L' END
           WHEN p.model_id LIKE 'wnba_prop_%' THEN
             CASE WHEN p.scored_line IS NULL OR wl.actual IS NULL THEN 'U'
                  WHEN wl.actual::numeric = p.scored_line THEN 'P'
                  WHEN (p.pick_side = 'over' AND wl.actual::numeric > p.scored_line)
                    OR (p.pick_side = 'under' AND wl.actual::numeric < p.scored_line) THEN 'W'
                  ELSE 'L' END
           ELSE 'U'
         END AS res
  FROM picks p
  LEFT JOIN games g ON g.game_id = p.game_id
  LEFT JOIN LATERAL (
    SELECT CASE p.model_id
             WHEN 'mlb_prop_pitcher_k' THEN l.p_strikeouts
             WHEN 'mlb_prop_pitcher_walks' THEN l.p_walks
             WHEN 'mlb_prop_pitcher_hits' THEN l.p_hits_allowed
             WHEN 'mlb_prop_pitcher_er' THEN l.p_earned_runs
             WHEN 'mlb_prop_pitcher_outs' THEN (floor(l.innings_pitched) * 3::numeric + round((l.innings_pitched - floor(l.innings_pitched)) * 10::numeric))::integer
             WHEN 'mlb_prop_batter_hits' THEN l.hits
             WHEN 'mlb_prop_batter_tb' THEN l.total_bases
             WHEN 'mlb_prop_batter_rbi' THEN l.rbi
             WHEN 'mlb_prop_batter_runs' THEN l.runs
             WHEN 'mlb_prop_batter_sb' THEN l.stolen_bases
             WHEN 'mlb_prop_batter_walks' THEN l.walks
             WHEN 'mlb_prop_batter_hr' THEN l.home_runs
             ELSE NULL::integer
           END AS actual
    FROM player_game_log l
    WHERE l.game_id = p.game_id AND l.player_id = p.player_id
    LIMIT 1) pl ON true
  LEFT JOIN LATERAL (
    SELECT CASE p.model_id
             WHEN 'wnba_prop_player_points' THEN l.points
             WHEN 'wnba_prop_player_rebounds' THEN l.rebounds
             WHEN 'wnba_prop_player_assists' THEN l.assists
             WHEN 'wnba_prop_player_threes' THEN l.fg3_made
             WHEN 'wnba_prop_player_pra' THEN l.points + l.rebounds + l.assists
             ELSE NULL::integer
           END AS actual
    FROM wnba_player_game_log l
    WHERE l.game_id = p.game_id AND l.player_id = p.player_id
    LIMIT 1) wl ON true
  WHERE p.game_date >= '2026-04-14'
    AND p.is_live IS NOT TRUE
    AND (p.model_id = ANY (ARRAY['mlb_moneyline','mlb_over_under','mlb_runline','mlb_f5_moneyline','wnba_moneyline'])
         OR p.model_id LIKE 'mlb_prop_%'
         OR p.model_id LIKE 'wnba_prop_%')
)
SELECT b.pick_id,
       b.model_id,
       b.game_date,
       b.game_id,
       b.pick_label,
       b.pick_side,
       b.prob AS model_probability,
       b.edge,
       b.dk_odds,
       b.scored_line,
       CASE b.res WHEN 'W' THEN 'WIN' WHEN 'L' THEN 'LOSS' ELSE 'PUSH' END AS result,
       CASE WHEN b.dk_odds IS NULL THEN NULL::numeric
            WHEN b.res = 'W' THEN CASE WHEN b.dk_odds > 0 THEN b.dk_odds / 100.0 ELSE 100.0 / abs(b.dk_odds) END
            WHEN b.res = 'L' THEN -1::numeric
            ELSE 0::numeric END AS profit_units
FROM base b
JOIN model_action_thresholds m ON m.model_id = b.model_id
WHERE b.res IN ('W', 'L', 'P')
  AND b.prob >= m.min_prob
  AND (m.prob_only OR b.edge >= COALESCE(m.min_edge, 0::numeric));

GRANT SELECT ON public.v_model_full_outcome_picks TO anon, authenticated;
