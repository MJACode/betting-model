-- Unpriced settled picks must not contribute P&L to the published record.
--
-- Settlement grades a pick with no book price at a -110 fallback. That price
-- never existed, so every such pick fabricates units. Since 2026-04-14 there
-- are 282 unpriced BETs, 205 of them settled.
--
-- config.REQUIRE_DK_PRICE stops new ones being created. This neutralises the
-- historical ones the same way mlb_prop_batter_hr already is: the W-L record is
-- KEPT, the money is zeroed.
--
-- SCOPE. Only the `other` branch (UFC / NHL / NBA / golf) needs patching.
-- v_model_full_outcome_record was already correct -- its `graded` CTE computes
--     CASE WHEN b.dk_odds IS NULL THEN NULL ... END AS profit
-- and sum() skips NULLs, so unpriced picks never reached its units. The `fo`
-- branch of both public views derives from that view and is therefore clean
-- too. The `other` branch is the one that sums the raw picks.profit_flat
-- column, which is where the -110 fallback lives.
--
-- Self-patching via pg_get_viewdef + replace so the (very large) view bodies
-- are not re-transcribed; each replacement is asserted.

DO $mig$
DECLARE d text; before text;
BEGIN
  FOREACH before IN ARRAY ARRAY['v_public_track_record', 'v_public_track_record_daily'] LOOP
    d := pg_get_viewdef(('public.' || before)::regclass, true);

    IF position('COALESCE(sum(p.profit_flat) FILTER (WHERE p.result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])), 0::numeric)' in d) = 0 THEN
      RAISE EXCEPTION '%: profit_flat anchor not found -- view shape changed, re-derive this migration', before;
    END IF;

    d := replace(d,
      'COALESCE(sum(p.profit_flat) FILTER (WHERE p.result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])), 0::numeric)',
      'COALESCE(sum(p.profit_flat) FILTER (WHERE (p.result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND p.dk_odds IS NOT NULL), 0::numeric)');

    d := replace(d,
      '100 * count(*) FILTER (WHERE p.result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AS staked_flat',
      '100 * count(*) FILTER (WHERE (p.result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND p.dk_odds IS NOT NULL) AS staked_flat');

    EXECUTE format('CREATE OR REPLACE VIEW public.%I AS %s', before, d);
    RAISE NOTICE 'patched %', before;
  END LOOP;
END $mig$;

-- security_invoker is a view property and survives CREATE OR REPLACE, but
-- re-assert it so a future reviewer does not have to check.
ALTER VIEW public.v_public_track_record        SET (security_invoker = on);
ALTER VIEW public.v_public_track_record_daily  SET (security_invoker = on);
