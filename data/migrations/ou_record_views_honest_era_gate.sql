-- ou_record_views_honest_era_gate (applied 2026-07-11, session 101b)
--
-- mlb_over_under: exclude picks before 2026-07-05 from all full-outcome /
-- track-record views. Live O/U scoring before the 2026-07-05 NaN-total_line
-- fix (session 95b, commit cae841e) predicted with the total line MISSING
-- from the feature vector, so every pre-fix O/U probability is garbage —
-- grading the current thresholds against them (211 of the 216 picks the
-- Models tab displayed) produced a meaningless -2.6% record. Same precedent
-- as the 2026-04-14 evaluation start (pre-v8 picks excluded for the same
-- model-vs-features mismatch reason).
--
-- Patches v_model_full_outcome_record, v_model_full_outcome_picks,
-- v_public_track_record_daily, and v_public_track_record (its own picks scan
-- feeds the CLV columns; its MLB grading inherits from the record view).
-- Self-patches via pg_get_viewdef + replace (the runline sign-fix technique)
-- so the giant grading CASEs are never re-transcribed. Raises if the target
-- WHERE fragment is missing from any view. Invoker mode re-asserted.
--
-- Verified after apply: mlb_over_under 216 (104-101-11, -5.70u) -> 5 picks
-- (2-3, -1.23u, all 2026-07-07..07-10); control models byte-identical
-- (moneyline 27/+29.5, f5_ml 131/+10.5, pitcher_k 25/+20.3, runline 20/+21.7).
DO $$
DECLARE
  v      text;
  def    text;
  target text := 'p.game_date >= ''2026-04-14''::text';
  gate   text := 'p.game_date >= ''2026-04-14''::text AND NOT (p.model_id = ''mlb_over_under''::text AND p.game_date < ''2026-07-05''::text)';
BEGIN
  FOREACH v IN ARRAY ARRAY[
    'v_model_full_outcome_record',
    'v_model_full_outcome_picks',
    'v_public_track_record_daily',
    'v_public_track_record'
  ] LOOP
    def := pg_get_viewdef(('public.' || v)::regclass, true);
    IF position(target IN def) = 0 THEN
      RAISE EXCEPTION 'target WHERE fragment not found in %', v;
    END IF;
    def := replace(def, target, gate);
    def := rtrim(def, E' \n;');
    EXECUTE 'CREATE OR REPLACE VIEW public.' || v || ' AS ' || def;
    EXECUTE 'ALTER VIEW public.' || v || ' SET (security_invoker = on)';
  END LOOP;
END $$;
