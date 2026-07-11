-- add_min_odds_price_floor (2026-07-11)
--
-- Per-model floor on the acceptable DK price (American odds), mirroring
-- config.MODEL_MIN_ODDS. A pick priced JUICIER than the floor (more negative,
-- e.g. -165 with a -140 floor) no longer counts as actionable:
--   * the scorer downgrades it BET -> NONE (models/scorer.py),
--   * the app's passesActionFilter drops it (thresholds.ts min_odds),
--   * and the track-record views below exclude it from the graded record,
--     so displayed records/ROI reflect the same criteria the picks use.
-- NULL min_odds = no floor (all models except the four below). NULL dk_odds
-- (prob-only fallback picks) always passes -- there is no price to judge.
--
-- Applied to (2026-07-11 full-outcome sweep -- capped slice beat the uncapped
-- record; the juice-heavy tail was where these props bled):
--   mlb_prop_pitcher_k    +8.9% -> +20.3% (25 capped bets)
--   mlb_prop_batter_rbi   +2.2% ->  +7.3% (36)
--   mlb_prop_batter_walks +2.5% -> +37.0% (18 -- thin)
--   mlb_prop_batter_runs  +3.1% -> +24.6% (40 -- model paused; staged for unpause)
-- NOT applied where heavy favorites ARE the edge (mlb_moneyline, f5_moneyline,
-- batter_hits -- a -140 cap guts them) or where capped samples were <15 (WNBA).
--
-- The view patches are self-applying: each view's current definition is read
-- via pg_get_viewdef and the min_odds condition is spliced into the exact
-- passes/threshold expression, so the (long) grading CASEs are never
-- re-transcribed. Idempotent: views already mentioning min_odds are skipped.

ALTER TABLE public.model_action_thresholds
  ADD COLUMN IF NOT EXISTS min_odds numeric;

UPDATE public.model_action_thresholds
   SET min_odds = -140, updated_at = NOW()
 WHERE model_id IN ('mlb_prop_pitcher_k', 'mlb_prop_batter_rbi',
                    'mlb_prop_batter_walks', 'mlb_prop_batter_runs');

DO $$
DECLARE
  defn text;
  newdefn text;
BEGIN
  -- v_model_full_outcome_picks: final WHERE threshold cut
  defn := pg_get_viewdef('public.v_model_full_outcome_picks'::regclass, true);
  IF position('min_odds' in defn) = 0 THEN
    newdefn := replace(defn,
      'b.prob >= m.min_prob AND (m.prob_only OR b.edge >= COALESCE(m.min_edge, 0::numeric))',
      'b.prob >= m.min_prob AND (m.prob_only OR b.edge >= COALESCE(m.min_edge, 0::numeric)) AND (m.min_odds IS NULL OR b.dk_odds IS NULL OR b.dk_odds >= m.min_odds)');
    IF newdefn = defn THEN
      RAISE EXCEPTION 'v_model_full_outcome_picks: threshold expression not found';
    END IF;
    EXECUTE 'CREATE OR REPLACE VIEW public.v_model_full_outcome_picks AS ' || newdefn;
  END IF;

  -- v_model_full_outcome_record: "passes" expression in the graded CTE
  defn := pg_get_viewdef('public.v_model_full_outcome_record'::regclass, true);
  IF position('min_odds' in defn) = 0 THEN
    newdefn := replace(defn,
      'b.prob >= m.min_prob AND (m.prob_only OR b.edge >= COALESCE(m.min_edge, 0::numeric)) AS passes',
      '(b.prob >= m.min_prob AND (m.prob_only OR b.edge >= COALESCE(m.min_edge, 0::numeric)) AND (m.min_odds IS NULL OR b.dk_odds IS NULL OR b.dk_odds >= m.min_odds)) AS passes');
    IF newdefn = defn THEN
      RAISE EXCEPTION 'v_model_full_outcome_record: passes expression not found';
    END IF;
    EXECUTE 'CREATE OR REPLACE VIEW public.v_model_full_outcome_record AS ' || newdefn;
  END IF;

  -- v_public_track_record: threshold cut in the clv CTE and the other-sports CTE
  defn := pg_get_viewdef('public.v_public_track_record'::regclass, true);
  IF position('min_odds' in defn) = 0 THEN
    newdefn := replace(defn,
      'AND p.model_probability >= t.min_prob AND (t.prob_only OR p.edge >= t.min_edge)',
      'AND p.model_probability >= t.min_prob AND (t.prob_only OR p.edge >= t.min_edge) AND (t.min_odds IS NULL OR p.dk_odds IS NULL OR p.dk_odds >= t.min_odds)');
    IF newdefn = defn THEN
      RAISE EXCEPTION 'v_public_track_record: threshold expression not found';
    END IF;
    EXECUTE 'CREATE OR REPLACE VIEW public.v_public_track_record AS ' || newdefn;
  END IF;

  -- v_public_track_record_daily: fo_base "passes" + the other-sports CTE cut
  defn := pg_get_viewdef('public.v_public_track_record_daily'::regclass, true);
  IF position('min_odds' in defn) = 0 THEN
    newdefn := replace(defn,
      'p.model_probability >= t.min_prob AND (t.prob_only OR p.edge >= COALESCE(t.min_edge, 0::numeric)) AS passes',
      '(p.model_probability >= t.min_prob AND (t.prob_only OR p.edge >= COALESCE(t.min_edge, 0::numeric)) AND (t.min_odds IS NULL OR p.dk_odds IS NULL OR p.dk_odds >= t.min_odds)) AS passes');
    IF newdefn = defn THEN
      RAISE EXCEPTION 'v_public_track_record_daily: passes expression not found';
    END IF;
    newdefn := replace(newdefn,
      'AND p.model_probability >= t.min_prob AND (t.prob_only OR p.edge >= t.min_edge)',
      'AND p.model_probability >= t.min_prob AND (t.prob_only OR p.edge >= t.min_edge) AND (t.min_odds IS NULL OR p.dk_odds IS NULL OR p.dk_odds >= t.min_odds)');
    EXECUTE 'CREATE OR REPLACE VIEW public.v_public_track_record_daily AS ' || newdefn;
  END IF;
END $$;

-- CREATE OR REPLACE VIEW keeps grants but re-assert invoker mode defensively.
ALTER VIEW public.v_model_full_outcome_picks   SET (security_invoker = on);
ALTER VIEW public.v_model_full_outcome_record  SET (security_invoker = on);
ALTER VIEW public.v_public_track_record        SET (security_invoker = on);
ALTER VIEW public.v_public_track_record_daily  SET (security_invoker = on);
