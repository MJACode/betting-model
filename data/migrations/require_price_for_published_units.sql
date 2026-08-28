-- Unpriced settled picks must not contribute P&L to the published record.
--
-- Settlement grades a pick with no book price at a -110 fallback. That price
-- never existed, so every such pick fabricates units. 205 settled picks since
-- 2026-04-14 carry it.
--
-- config.REQUIRE_DK_PRICE stops new ones being created. This neutralises the
-- historical ones the way mlb_prop_batter_hr already is: W-L record KEPT,
-- money zeroed.
--
-- SCOPE, established by reading the live view bodies rather than assuming:
-- v_model_full_outcome_record was ALREADY correct -- its `graded` CTE emits
--     CASE WHEN b.dk_odds IS NULL THEN NULL ... END AS profit
-- and sum() skips NULLs, so unpriced picks never reached its units. The `fo`
-- branch of both public views derives from it and is clean too. Only the
-- `other` branch (UFC / NHL / NBA / golf), which sums the raw
-- picks.profit_flat column, was fabricating.
--
-- IDEMPOTENT: each view is skipped when already patched, so this is safe to
-- run on every pipeline pass (see data/view_migrations.py).

DO $mig$
DECLARE d text; v text; patched text := ''; skipped text := '';
  old_profit CONSTANT text :=
    'COALESCE(sum(p.profit_flat) FILTER (WHERE p.result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])), 0::numeric)';
  new_profit CONSTANT text :=
    'COALESCE(sum(p.profit_flat) FILTER (WHERE (p.result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND p.dk_odds IS NOT NULL), 0::numeric)';
  old_stake CONSTANT text :=
    '100 * count(*) FILTER (WHERE p.result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AS staked_flat';
  new_stake CONSTANT text :=
    '100 * count(*) FILTER (WHERE (p.result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND p.dk_odds IS NOT NULL) AS staked_flat';
BEGIN
  FOREACH v IN ARRAY ARRAY['v_public_track_record', 'v_public_track_record_daily'] LOOP
    d := pg_get_viewdef(('public.' || v)::regclass, true);

    IF position(new_profit in d) > 0 THEN
      skipped := skipped || v || ' ';
      CONTINUE;                       -- already patched
    END IF;

    IF position(old_profit in d) = 0 THEN
      RAISE EXCEPTION '%: neither the old nor the patched profit_flat expression '
                      'is present — the view shape changed, re-derive this migration', v;
    END IF;

    d := replace(d, old_profit, new_profit);
    d := replace(d, old_stake,  new_stake);
    EXECUTE format('CREATE OR REPLACE VIEW public.%I AS %s', v, d);
    -- security_invoker survives CREATE OR REPLACE; re-asserted so a reviewer
    -- does not have to check.
    EXECUTE format('ALTER VIEW public.%I SET (security_invoker = on)', v);
    patched := patched || v || ' ';
  END LOOP;

  IF patched <> '' THEN RAISE NOTICE 'patched: %', patched; END IF;
  IF skipped <> '' THEN RAISE NOTICE 'already patched, skipped: %', skipped; END IF;
END $mig$;
