-- Make the public record and the equity curve agree to the cent.
--
-- v_public_track_record reports $5,053.48 while v_public_track_record_daily
-- reports $5,053.75 over the SAME 499 picks -- a 27c disagreement between two
-- surfaces that are meant to be the same number.
--
-- CAUSE, and it is precision only, NOT a grading difference: the two views
-- were verified to cover an identical pick set (499 = 499). The record view
-- derives its dollars from v_model_full_outcome_record.units, which is
-- rounded to 2dp PER MODEL and then scaled by 100 -- so each of the 13 model
-- rows can shed up to half a cent of units, i.e. up to $0.50, before the sum
-- is taken (13 x $0.50 = $6.50 of headroom; $0.27 observed). The daily view
-- sums unrounded profit and scales once, so it is the more accurate of the
-- two and is the number this migration moves the record view toward.
--
-- Confirmed against production: every MLB/WNBA row in v_public_track_record
-- is a whole dollar (468.00, 665.00, ...) -- the signature of units-rounded-
-- to-2dp x 100 -- while the UFC rows, which come from the other branch and
-- never pass through units, carry real cents (-185.92, 57.40).
--
-- FIX: round units to 6dp instead of 2dp, so units x 100 is exact to the cent.
-- Display is unaffected: the app reads Number(units) and formats it itself
-- (share copy uses toFixed(1)), so the extra precision never reaches a screen.
--
-- This is a cosmetic-precision fix, not a correction to anyone's record. No
-- pick changes grade, and no ROI percentage moves at the precision shown.
--
-- IDEMPOTENT: returns early when already at 6dp. Safe to run every pass.
-- Raises if the expression is not found, rather than silently no-oping, so a
-- future reshape of the view surfaces instead of rotting.

DO $mig$
DECLARE
  d text;
  target text := 'round(COALESCE(sum(profit) FILTER (WHERE passes), 0::numeric), 2)';
  fixed  text := 'round(COALESCE(sum(profit) FILTER (WHERE passes), 0::numeric), 6)';
BEGIN
  d := pg_get_viewdef('public.v_model_full_outcome_record'::regclass, true);

  IF position(fixed in d) > 0 THEN
    RAISE NOTICE 'units already at 6dp - skipped';
    RETURN;
  END IF;

  IF position(target in d) = 0 THEN
    RAISE EXCEPTION 'units rounding expression not found in v_model_full_outcome_record - view shape changed, re-derive this migration';
  END IF;

  d := replace(d, target, fixed);

  EXECUTE 'CREATE OR REPLACE VIEW public.v_model_full_outcome_record AS ' || d;
  -- pg_get_viewdef does not carry view options, so security_invoker must be
  -- re-asserted after every CREATE OR REPLACE (the runline sign-fix precedent).
  EXECUTE 'ALTER VIEW public.v_model_full_outcome_record SET (security_invoker = on)';
  RAISE NOTICE 'units precision raised to 6dp';
END $mig$;
