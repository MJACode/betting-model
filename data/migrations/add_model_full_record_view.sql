-- Migration: add_model_full_record_view (applied 2026-06-27)
--
-- Full-outcome record per game-level model, applying the CURRENT action
-- thresholds (model_action_thresholds) retroactively to EVERY scored pick
-- (BET + AVOID + dead-zone NONE), recomputing each outcome from the final game
-- score. This answers "what is this model's true record at its current
-- prob/edge cut?" — unlike the settled-BET-only record the Models tab used
-- before, which never sees AVOID/NONE picks (settlement only touches BET) and
-- so shows a thin, biased slice.
--
-- Outcome logic mirrors tracking/paper_tracker._compute_result exactly
-- (validated 2026-06-27: h2h 155/155 and h2h_1st_5_innings 104/104 vs stored
-- settled results; reproduces the session-68/74 full-outcome sweeps —
-- mlb_moneyline 40/27-13/+12.6%, mlb_f5_moneyline 105/59-31-15/+9.9%,
-- mlb_runline matches session 74). Props/UFC/golf are excluded — they can't be
-- recomputed from games alone (need player logs / fight logs); the mobile
-- Models tab keeps the settled-BET record for those.
--
-- security_invoker so it reads picks/games/model_action_thresholds through the
-- caller's existing anon SELECT policies. anon SELECT granted.

CREATE OR REPLACE VIEW public.v_model_full_record
WITH (security_invoker = on) AS
WITH scored AS (
  SELECT
    p.model_id, p.pick_side,
    p.model_probability AS prob, p.edge, p.scored_line,
    COALESCE(p.dk_odds, -110) AS dk_odds,
    g.home_score, g.away_score, g.home_win_reg, g.went_to_ot,
    g.home_score_f5, g.away_score_f5,
    t.min_prob, t.min_edge, t.prob_only, t.paused,
    CASE
      WHEN p.model_id LIKE '%f5_moneyline%'  THEN 'h2h_1st_5_innings'
      WHEN p.model_id LIKE '%f5_over_under%' THEN 'totals_1st_5_innings'
      WHEN p.model_id LIKE '%f5_runline%'    THEN 'spreads_1st_5_innings'
      WHEN p.model_id = 'nhl_moneyline_regulation' THEN 'h2h_3way'
      WHEN p.model_id LIKE '%over_under%'    THEN 'totals'
      WHEN p.model_id LIKE '%runline%' OR p.model_id LIKE '%puckline%'
        OR p.model_id LIKE '%spread%'        THEN 'spreads'
      ELSE 'h2h'
    END AS market
  FROM picks p
  JOIN games g ON g.game_id = p.game_id
  JOIN model_action_thresholds t ON t.model_id = p.model_id
  WHERE p.game_date >= '2026-04-14'
    AND p.is_live IS NOT TRUE
    AND g.home_score IS NOT NULL
    AND p.model_id NOT LIKE '%prop%'
    AND p.model_id NOT LIKE 'ufc_%'
    AND p.model_id NOT LIKE 'golf_%'
),
ev AS (
  SELECT *,
    CASE WHEN market LIKE '%1st_5_innings' THEN home_score_f5 ELSE home_score END AS sh,
    CASE WHEN market LIKE '%1st_5_innings' THEN away_score_f5 ELSE away_score END AS sa
  FROM scored
),
o AS (
  SELECT *,
    (NOT paused AND prob >= min_prob AND (prob_only OR edge >= min_edge)) AS qualifies,
    CASE
      WHEN sh IS NULL OR sa IS NULL THEN NULL
      WHEN market IN ('h2h','h2h_1st_5_innings') THEN
        CASE WHEN sh = sa THEN 'PUSH'
             WHEN pick_side='home' AND sh > sa THEN 'WIN'
             WHEN pick_side='away' AND sa > sh THEN 'WIN' ELSE 'LOSS' END
      WHEN market='h2h_3way' THEN
        CASE WHEN pick_side='home' THEN CASE WHEN home_win_reg=1 THEN 'WIN' ELSE 'LOSS' END
             WHEN pick_side='away' THEN CASE WHEN home_win_reg=0 AND COALESCE(went_to_ot,0)=0 THEN 'WIN' ELSE 'LOSS' END
             WHEN pick_side='draw' THEN CASE WHEN went_to_ot=1 THEN 'WIN' ELSE 'LOSS' END END
      WHEN market IN ('totals','totals_1st_5_innings') THEN
        CASE WHEN scored_line IS NULL THEN NULL
             WHEN (sh+sa) = scored_line THEN 'PUSH'
             WHEN pick_side='over'  AND (sh+sa) > scored_line THEN 'WIN'
             WHEN pick_side='under' AND (sh+sa) < scored_line THEN 'WIN' ELSE 'LOSS' END
      WHEN market IN ('spreads','spreads_1st_5_innings') THEN
        CASE WHEN scored_line IS NULL THEN NULL
             WHEN ((sh-sa)+scored_line) = 0 THEN 'PUSH'
             WHEN pick_side='home' AND ((sh-sa)+scored_line) > 0 THEN 'WIN'
             WHEN pick_side='away' AND ((sh-sa)+scored_line) < 0 THEN 'WIN' ELSE 'LOSS' END
    END AS res
  FROM ev
)
SELECT
  model_id,
  COUNT(*) FILTER (WHERE qualifies AND res IN ('WIN','LOSS','PUSH')) AS picks,
  COUNT(*) FILTER (WHERE qualifies AND res='WIN')  AS wins,
  COUNT(*) FILTER (WHERE qualifies AND res='LOSS') AS losses,
  COUNT(*) FILTER (WHERE qualifies AND res='PUSH') AS pushes,
  ROUND(SUM(CASE WHEN qualifies AND res='WIN'
                   THEN (CASE WHEN dk_odds>0 THEN dk_odds/100.0 ELSE 100.0/abs(dk_odds) END)
                 WHEN qualifies AND res='LOSS' THEN -1.0 ELSE 0 END)::numeric, 3) AS profit_units
FROM o
GROUP BY model_id;

GRANT SELECT ON public.v_model_full_record TO anon, authenticated;
