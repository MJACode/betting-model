-- Migration: fix_runline_away_grading_in_full_outcome_views (applied 2026-07-02)
--
-- BUG: away-side mlb_runline picks were graded with
--         (away_score - home_score) + scored_line
--      but picks.scored_line stores the HOME spread. The away team's spread is
--      the negation of the home spread, so the correct cover test is
--         (away_score - home_score) - scored_line > 0
--      (home picks were already correct: (home - away) + scored_line > 0).
--      The wrong sign flips the graded result of EVERY one-run game on an
--      away-side runline pick (|margin| = 1 is the only band where +line and
--      -line straddle zero for a ±1.5 spread).
--
-- VALIDATION: the corrected formula matches 30/31 stored runline settlements;
--      the single mismatch (pick_id 1165, COL -1.5 on 2026-04-26, won 3-1 =
--      covered) was a genuine settlement error, repaired separately
--      (result LOSS -> WIN, profit_flat +64.94, profit_kelly +33.81).
--
-- IMPACT: at the then-live 0.55/0.10 cut, runline flipped from a phantom
--      49-42 +15.2% to a real 35-56 -20.6%; the overall unpaused-MLB
--      full-outcome headline moved +10.21% -> +6.91%. The 2026-06-28 runline
--      re-cut to 0.55/0.10 ("48-41 +14.9% plateau") was made on the buggy
--      grading and was corrected to 0.68/0.11 alongside this migration.
--
-- SCOPE: v_model_full_outcome_record (fixed below) — v_public_track_record
--      reads from it and inherits the fix — and v_public_track_record_daily,
--      which inlines the same grading CASE and is fixed below too.
--      Both views recreated identically except the mlb_runline branch.

CREATE OR REPLACE VIEW public.v_model_full_outcome_record WITH (security_invoker = on) AS
WITH base AS (
  SELECT p.model_id,
         p.model_probability AS prob,
         p.edge,
         p.dk_odds,
         p.pick_side,
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
), graded AS (
  SELECT b.model_id, b.res, b.dk_odds, m.paused, m.prob_only,
         CASE WHEN b.dk_odds IS NULL THEN NULL::numeric
              WHEN b.res = 'W' THEN CASE WHEN b.dk_odds > 0 THEN b.dk_odds / 100.0 ELSE 100.0 / abs(b.dk_odds) END
              WHEN b.res = 'L' THEN -1::numeric
              WHEN b.res = 'P' THEN 0::numeric
              ELSE NULL::numeric END AS profit,
         (b.prob >= m.min_prob AND (m.prob_only OR b.edge >= COALESCE(m.min_edge, 0::numeric))) AS passes
  FROM base b
  JOIN model_action_thresholds m ON m.model_id = b.model_id
)
SELECT model_id,
       bool_or(paused) AS paused,
       bool_or(prob_only) AS prob_only,
       count(*) FILTER (WHERE passes AND res = ANY (ARRAY['W','L','P'])) AS bets,
       count(*) FILTER (WHERE passes AND res = 'W') AS wins,
       count(*) FILTER (WHERE passes AND res = 'L') AS losses,
       count(*) FILTER (WHERE passes AND res = 'P') AS pushes,
       count(*) FILTER (WHERE passes AND res = ANY (ARRAY['W','L','P']) AND dk_odds IS NOT NULL) AS priced_bets,
       round(COALESCE(sum(profit) FILTER (WHERE passes), 0::numeric), 2) AS units,
       round(sum(profit) FILTER (WHERE passes) / NULLIF(count(*) FILTER (WHERE passes AND res = ANY (ARRAY['W','L','P']) AND dk_odds IS NOT NULL), 0)::numeric * 100::numeric, 1) AS roi_pct
FROM graded
GROUP BY model_id;

CREATE OR REPLACE VIEW public.v_public_track_record_daily WITH (security_invoker = on) AS
WITH fo_base AS (
  SELECT p.game_date,
         p.dk_odds,
         CASE WHEN p.model_id LIKE 'wnba%' THEN 'WNBA' ELSE 'MLB' END AS sport,
         (p.model_probability >= t.min_prob AND (t.prob_only OR p.edge >= COALESCE(t.min_edge, 0::numeric))) AS passes,
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
  JOIN model_action_thresholds t ON t.model_id = p.model_id
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
    AND t.paused IS NOT TRUE
    AND (p.model_id = ANY (ARRAY['mlb_moneyline','mlb_over_under','mlb_runline','mlb_f5_moneyline','wnba_moneyline'])
         OR p.model_id LIKE 'mlb_prop_%'
         OR p.model_id LIKE 'wnba_prop_%')
), fo AS (
  SELECT fo_base.game_date,
         fo_base.sport,
         count(*) FILTER (WHERE fo_base.passes AND fo_base.res = ANY (ARRAY['W','L','P'])) AS picks,
         count(*) FILTER (WHERE fo_base.passes AND fo_base.res = 'W') AS wins,
         count(*) FILTER (WHERE fo_base.passes AND fo_base.res = 'L') AS losses,
         count(*) FILTER (WHERE fo_base.passes AND fo_base.res = 'P') AS pushes,
         COALESCE(sum(
           CASE WHEN fo_base.passes AND fo_base.dk_odds IS NOT NULL THEN
             CASE fo_base.res
               WHEN 'W' THEN CASE WHEN fo_base.dk_odds > 0 THEN fo_base.dk_odds / 100.0 ELSE 100.0 / abs(fo_base.dk_odds) END
               WHEN 'L' THEN -1::numeric
               WHEN 'P' THEN 0::numeric
               ELSE 0::numeric
             END
           ELSE NULL::numeric END), 0::numeric) * 100::numeric AS profit_flat,
         100 * count(*) FILTER (WHERE fo_base.passes AND fo_base.res = ANY (ARRAY['W','L','P']) AND fo_base.dk_odds IS NOT NULL) AS staked_flat
  FROM fo_base
  GROUP BY fo_base.game_date, fo_base.sport
), other AS (
  SELECT p.game_date,
         p.sport,
         count(*) FILTER (WHERE p.result = ANY (ARRAY['WIN','LOSS','PUSH'])) AS picks,
         count(*) FILTER (WHERE p.result = 'WIN') AS wins,
         count(*) FILTER (WHERE p.result = 'LOSS') AS losses,
         count(*) FILTER (WHERE p.result = 'PUSH') AS pushes,
         COALESCE(sum(p.profit_flat) FILTER (WHERE p.result = ANY (ARRAY['WIN','LOSS','PUSH'])), 0::numeric) AS profit_flat,
         100 * count(*) FILTER (WHERE p.result = ANY (ARRAY['WIN','LOSS','PUSH'])) AS staked_flat
  FROM picks p
  JOIN model_action_thresholds t ON t.model_id = p.model_id
  WHERE p.signal_type = 'BET'
    AND p.is_live IS NOT TRUE
    AND t.paused IS NOT TRUE
    AND p.game_date >= '2026-04-14'
    AND p.model_probability >= t.min_prob
    AND (t.prob_only OR p.edge >= t.min_edge)
    AND NOT (p.model_id = ANY (ARRAY['mlb_moneyline','mlb_over_under','mlb_runline','mlb_f5_moneyline','wnba_moneyline'])
             OR p.model_id LIKE 'mlb_prop_%'
             OR p.model_id LIKE 'wnba_prop_%')
  GROUP BY p.game_date, p.sport
)
SELECT fo.game_date, fo.sport, fo.picks, fo.wins, fo.losses, fo.pushes, fo.profit_flat, fo.staked_flat
FROM fo
WHERE fo.picks > 0
UNION ALL
SELECT other.game_date, other.sport, other.picks, other.wins, other.losses, other.pushes, other.profit_flat, other.staked_flat
FROM other;

-- One-off data repair applied with this migration (not idempotent — already run):
--   UPDATE picks SET result='WIN', profit_flat=64.94, profit_kelly=33.81
--   WHERE pick_id = 1165 AND result = 'LOSS';
