-- custom_model_backtest / custom_model_picks (2026-08-08): server-side
-- evaluation of a user's custom model against mv_scored_pick_outcomes — the
-- phone sends the criteria and gets the answer, instead of downloading ~100k
-- graded rows.
--
-- p_rules:   [{"model_id":"mlb_moneyline","min_prob":0.6,"min_edge":0.05}, ...] (OR'd)
-- p_filters: the mobile CustomModelFilters object, passed verbatim (AND'd):
--            {"signals":[...],"betKinds":[...],"sides":[...],"price":[...],
--             "timeSlots":[...],"tiers":[...],"minOdds":-140,"maxOdds":200,
--             "maxPublicBetPct":40,"minPublicBetPct":10,"excludeInjuries":true}
-- Absent/empty = unconstrained; a filter whose datum is missing on a pick
-- EXCLUDES it — must stay in lockstep with pickMatchesFilters in
-- mobile/src/lib/customModelFilters.ts.
--
-- plpgsql with the filters extracted to locals, NOT a sql function: the first
-- version cross-joined a filter CTE built from the opaque jsonb parameter and
-- ran ~4.5s; as plain bound locals the same query plans to ~50ms.
--
-- Applied as migrations: add_custom_model_backtest_rpcs (sql fns, superseded)
-- → point_custom_model_rpcs_at_matview → custom_model_rpcs_plpgsql_locals.
-- The definitions below are the live ones.

CREATE OR REPLACE FUNCTION public._jsonb_text_array(j jsonb)
RETURNS text[] LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
  SELECT CASE
    WHEN j IS NULL OR jsonb_typeof(j) <> 'array' OR jsonb_array_length(j) = 0 THEN NULL
    ELSE ARRAY(SELECT jsonb_array_elements_text(j))
  END;
$$;

CREATE OR REPLACE FUNCTION public.custom_model_backtest(
  p_rules jsonb,
  p_filters jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (
  bets bigint, wins bigint, losses bigint, pushes bigint,
  priced bigint, units numeric, roi_pct numeric
)
LANGUAGE plpgsql STABLE SET search_path = public, pg_temp AS $$
DECLARE
  v_signals    text[] := _jsonb_text_array(p_filters->'signals');
  v_bet_kinds  text[] := _jsonb_text_array(p_filters->'betKinds');
  v_sides      text[] := _jsonb_text_array(p_filters->'sides');
  v_price      text[] := _jsonb_text_array(p_filters->'price');
  v_slots      text[] := _jsonb_text_array(p_filters->'timeSlots');
  v_tiers      text[] := _jsonb_text_array(p_filters->'tiers');
  v_min_odds   numeric := (p_filters->>'minOdds')::numeric;
  v_max_odds   numeric := (p_filters->>'maxOdds')::numeric;
  v_max_public numeric := (p_filters->>'maxPublicBetPct')::numeric;
  v_min_public numeric := (p_filters->>'minPublicBetPct')::numeric;
  v_excl_inj   boolean := COALESCE((p_filters->>'excludeInjuries')::boolean, false);
BEGIN
  RETURN QUERY
  WITH r AS (
    SELECT (x->>'model_id')::text AS mid,
           COALESCE((x->>'min_prob')::numeric, 0) AS mp,
           COALESCE((x->>'min_edge')::numeric, -9.99) AS me
    FROM jsonb_array_elements(COALESCE(p_rules,'[]'::jsonb)) x
  ),
  m AS (
    SELECT v.result AS res, v.profit_units AS pu
    FROM mv_scored_pick_outcomes v
    WHERE EXISTS (
        SELECT 1 FROM r
        WHERE r.mid = v.model_id AND v.model_probability >= r.mp AND v.edge >= r.me)
      AND (v_signals   IS NULL OR v.signal_type = ANY(v_signals))
      AND (v_bet_kinds IS NULL OR v.bet_kind    = ANY(v_bet_kinds))
      AND (v_sides     IS NULL OR v.pick_side   = ANY(v_sides))
      AND (v_price     IS NULL OR (v.price_side IS NOT NULL AND v.price_side = ANY(v_price)))
      AND (v_slots     IS NULL OR (v.time_slot  IS NOT NULL AND v.time_slot  = ANY(v_slots)))
      AND (v_tiers     IS NULL OR (v.confidence_tier IS NOT NULL AND v.confidence_tier = ANY(v_tiers)))
      AND (v_min_odds  IS NULL OR (v.dk_odds IS NOT NULL AND v.dk_odds >= v_min_odds))
      AND (v_max_odds  IS NULL OR (v.dk_odds IS NOT NULL AND v.dk_odds <= v_max_odds))
      AND (v_max_public IS NULL OR (v.public_bet_pct IS NOT NULL AND v.public_bet_pct <= v_max_public))
      AND (v_min_public IS NULL OR (v.public_bet_pct IS NOT NULL AND v.public_bet_pct >= v_min_public))
      AND (NOT v_excl_inj OR v.injury_flag IS NULL OR btrim(v.injury_flag) = '')
  )
  SELECT
    count(*)                                      AS bets,
    count(*) FILTER (WHERE res = 'WIN')           AS wins,
    count(*) FILTER (WHERE res = 'LOSS')          AS losses,
    count(*) FILTER (WHERE res = 'PUSH')          AS pushes,
    count(*) FILTER (WHERE pu IS NOT NULL)        AS priced,
    COALESCE(sum(pu), 0)                          AS units,
    -- ROI over priced picks only: an unpriced (prob-only) pick has a real
    -- record but no honest P&L, so counting it as stake would understate ROI.
    CASE WHEN count(*) FILTER (WHERE pu IS NOT NULL) > 0
         THEN round(100.0 * COALESCE(sum(pu),0) / count(*) FILTER (WHERE pu IS NOT NULL), 2)
         ELSE NULL END                            AS roi_pct
  FROM m;
END;
$$;

CREATE OR REPLACE FUNCTION public.custom_model_picks(
  p_rules jsonb,
  p_filters jsonb DEFAULT '{}'::jsonb,
  p_limit int DEFAULT 200
)
RETURNS TABLE (
  pick_id bigint, model_id text, game_date text, game_id text,
  pick_label text, pick_side text, signal_type text,
  model_probability numeric, edge numeric, dk_odds numeric,
  result text, profit_units numeric
)
LANGUAGE plpgsql STABLE SET search_path = public, pg_temp AS $$
DECLARE
  v_signals    text[] := _jsonb_text_array(p_filters->'signals');
  v_bet_kinds  text[] := _jsonb_text_array(p_filters->'betKinds');
  v_sides      text[] := _jsonb_text_array(p_filters->'sides');
  v_price      text[] := _jsonb_text_array(p_filters->'price');
  v_slots      text[] := _jsonb_text_array(p_filters->'timeSlots');
  v_tiers      text[] := _jsonb_text_array(p_filters->'tiers');
  v_min_odds   numeric := (p_filters->>'minOdds')::numeric;
  v_max_odds   numeric := (p_filters->>'maxOdds')::numeric;
  v_max_public numeric := (p_filters->>'maxPublicBetPct')::numeric;
  v_min_public numeric := (p_filters->>'minPublicBetPct')::numeric;
  v_excl_inj   boolean := COALESCE((p_filters->>'excludeInjuries')::boolean, false);
BEGIN
  RETURN QUERY
  WITH r AS (
    SELECT (x->>'model_id')::text AS mid,
           COALESCE((x->>'min_prob')::numeric, 0) AS mp,
           COALESCE((x->>'min_edge')::numeric, -9.99) AS me
    FROM jsonb_array_elements(COALESCE(p_rules,'[]'::jsonb)) x
  )
  SELECT v.pick_id, v.model_id, v.game_date, v.game_id, v.pick_label,
         v.pick_side, v.signal_type, v.model_probability, v.edge, v.dk_odds,
         v.result, v.profit_units
  FROM mv_scored_pick_outcomes v
  WHERE EXISTS (
      SELECT 1 FROM r
      WHERE r.mid = v.model_id AND v.model_probability >= r.mp AND v.edge >= r.me)
    AND (v_signals   IS NULL OR v.signal_type = ANY(v_signals))
    AND (v_bet_kinds IS NULL OR v.bet_kind    = ANY(v_bet_kinds))
    AND (v_sides     IS NULL OR v.pick_side   = ANY(v_sides))
    AND (v_price     IS NULL OR (v.price_side IS NOT NULL AND v.price_side = ANY(v_price)))
    AND (v_slots     IS NULL OR (v.time_slot  IS NOT NULL AND v.time_slot  = ANY(v_slots)))
    AND (v_tiers     IS NULL OR (v.confidence_tier IS NOT NULL AND v.confidence_tier = ANY(v_tiers)))
    AND (v_min_odds  IS NULL OR (v.dk_odds IS NOT NULL AND v.dk_odds >= v_min_odds))
    AND (v_max_odds  IS NULL OR (v.dk_odds IS NOT NULL AND v.dk_odds <= v_max_odds))
    AND (v_max_public IS NULL OR (v.public_bet_pct IS NOT NULL AND v.public_bet_pct <= v_max_public))
    AND (v_min_public IS NULL OR (v.public_bet_pct IS NOT NULL AND v.public_bet_pct >= v_min_public))
    AND (NOT v_excl_inj OR v.injury_flag IS NULL OR btrim(v.injury_flag) = '')
  ORDER BY v.game_date DESC, v.pick_id DESC
  LIMIT GREATEST(p_limit, 0);
END;
$$;

GRANT EXECUTE ON FUNCTION public._jsonb_text_array(jsonb) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.custom_model_backtest(jsonb, jsonb) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.custom_model_picks(jsonb, jsonb, int) TO anon, authenticated;
