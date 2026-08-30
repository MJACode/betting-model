-- track_record_include_live_models (applied 2026-08-30)
--
-- Fold genuine live (in-play) models into the public track record, so a settled
-- live bet shows up in the app's Record tab instead of vanishing.
--
-- Both views excluded every `is_live` pick. That flag carries TWO different
-- populations, which is why the exclusion was written and why it cannot simply
-- be dropped:
--   1. Real in-play picks from the live models (mlb_live_*, ncaaf_live_*).
--      These are bets of record and belong in the record (Matt, 2026-08-30).
--   2. The session-114 repair rows: 14,113 PRE-GAME prop picks retroactively
--      flagged is_live because they were scored against in-play prices after
--      first pitch. Those are contamination and MUST stay excluded.
--
-- `model_id LIKE '%\_live\_%'` separates them exactly: all 5 live models match,
-- none of the 17 repaired prop models do, and NO pre-game-flagged model matches
-- (verified against every distinct model_id in picks), so the OR clause is
-- purely additive on is_live rows and can never widen the pre-game set.
--
-- Live models land in each view's `other` CTE (they are outside the MLB/WNBA
-- full-outcome whitelist), so that is where this takes effect; the occurrences
-- in clv / dates_fo / fo_base are no-ops kept identical so there is one
-- predicate to reason about. v_model_full_outcome_record / _picks and
-- mv_scored_pick_outcomes are deliberately NOT touched: their model_id
-- whitelist already excludes live models, so changing them would be a no-op.
--
-- Measured effect: 513 -> 547 picks, 295-195-23 -> 314-210-23,
-- +$0.71 profit on +$3,400 staked (overall ROI 10.79% -> 10.11%).
-- NCAAF 0 -> 9 picks; MLB 425 -> 450. record and _daily still reconcile exactly.
--
-- Self-patching via pg_get_viewdef + replace so the giant grading CASEs are
-- never re-transcribed (the runline sign-fix technique). Idempotent: a re-run
-- detects the marker and skips rather than double-wrapping.
DO $mig$
DECLARE
  v        text;
  def      text;
  n        int;
  old_pred constant text := '(p.is_live IS NOT TRUE)';
  new_pred constant text := '((p.is_live IS NOT TRUE) OR (p.model_id ~~ ''%\_live\_%''::text))';
  marker   constant text := '\_live\_';
BEGIN
  FOREACH v IN ARRAY ARRAY['v_public_track_record', 'v_public_track_record_daily'] LOOP
    def := pg_get_viewdef(('public.' || v)::regclass);

    IF position(marker in def) > 0 THEN
      RAISE NOTICE 'view % already patched - skipping', v;
      CONTINUE;
    END IF;

    n := (length(def) - length(replace(def, old_pred, ''))) / length(old_pred);
    IF n = 0 THEN
      RAISE EXCEPTION 'expected predicate % not found in %', old_pred, v;
    END IF;

    def := replace(def, old_pred, new_pred);
    EXECUTE format('CREATE OR REPLACE VIEW public.%I WITH (security_invoker = on) AS %s', v, def);
    RAISE NOTICE 'patched % occurrence(s) in %', n, v;
  END LOOP;
END
$mig$;

GRANT SELECT ON public.v_public_track_record        TO anon, authenticated;
GRANT SELECT ON public.v_public_track_record_daily  TO anon, authenticated;
