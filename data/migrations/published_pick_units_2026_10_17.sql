-- The posted stake, as three functions. No view change in this file.
--
-- data/view_migrations.py commits one file at a time. The view patch that
-- reads these functions is the next file. If that patch raises, this
-- commit stays, and settlement can still call the functions. A view
-- refinement must not take down settlement.
--
-- published_pick_unit_risked is 0 unless the result is WIN or LOSS. A
-- push, a void (NO_ACTION), and a pick that has not graded (NULL) laid
-- nothing. Re-read 2026-10-17, SELECT only, on the posted record (the
-- view's own WHERE, which does not filter result): through 2026-10-15
-- the graded stake is 918.2090 (439 wins, 378 losses, 2 pushes; units
-- 21.5501). The 917.1090 measured on 2026-10-16 is that total minus one
-- later −110 loss. The same WHERE with no date cap also holds 106
-- NO_ACTION rows (122.0643) and 30 ungraded rows (31.5742). Adding those
-- stakes would make risked 1071.8475. This function does not add them.
--
-- Idempotent. A catalog read returns when the body is already the one
-- below, so a second pass does not replace the function. Does not rewrite
-- snapshots, picks, or push_sent. Does not post.

DO $mig$
DECLARE
  replace_risked boolean;
BEGIN
  IF to_regprocedure('public.published_pick_stake(numeric)') IS NULL THEN
    CREATE FUNCTION public.published_pick_stake(price numeric, OUT risk numeric, OUT win numeric)
    LANGUAGE sql
    IMMUTABLE
    PARALLEL SAFE
    SET search_path = pg_catalog
    AS $stake$
      SELECT
        CASE
          WHEN price IS NULL OR price = 0 THEN 1.0
          WHEN (1.0 / (CASE WHEN price > 0 THEN price / 100.0
                            ELSE 100.0 / abs(price) END)) > 3.0 THEN 3.0
          ELSE 1.0 / (CASE WHEN price > 0 THEN price / 100.0
                           ELSE 100.0 / abs(price) END)
        END,
        CASE
          WHEN price IS NULL OR price = 0 THEN 1.0
          WHEN (1.0 / (CASE WHEN price > 0 THEN price / 100.0
                            ELSE 100.0 / abs(price) END)) > 3.0
            THEN 3.0 * (CASE WHEN price > 0 THEN price / 100.0
                             ELSE 100.0 / abs(price) END)
          ELSE 1.0
        END
    $stake$;
  END IF;

  IF to_regprocedure('public.published_pick_unit_profit(numeric, text)') IS NULL THEN
    CREATE FUNCTION public.published_pick_unit_profit(price numeric, result text)
    RETURNS numeric
    LANGUAGE sql
    IMMUTABLE
    PARALLEL SAFE
    SET search_path = pg_catalog
    AS $profit$
      SELECT CASE result
        WHEN 'WIN' THEN (public.published_pick_stake(price)).win
        WHEN 'LOSS' THEN - (public.published_pick_stake(price)).risk
        ELSE 0
      END
    $profit$;
  END IF;

  -- Replace a body that still counts every non-push. The first create is
  -- the WHEN 'WIN' / WHEN 'LOSS' body. A later pass sees that text and
  -- returns on the catalog read. The missing-function check is its own
  -- statement so a missing function is not cast to regprocedure.
  replace_risked := to_regprocedure('public.published_pick_unit_risked(numeric, text)') IS NULL;
  IF NOT replace_risked THEN
    replace_risked := position(
      'WHEN ''WIN'''
      IN pg_get_functiondef('public.published_pick_unit_risked(numeric, text)'::regprocedure)
    ) = 0;
  END IF;
  IF replace_risked THEN
    CREATE OR REPLACE FUNCTION public.published_pick_unit_risked(price numeric, result text)
    RETURNS numeric
    LANGUAGE sql
    IMMUTABLE
    PARALLEL SAFE
    SET search_path = pg_catalog
    AS $risked$
      SELECT CASE result
        WHEN 'WIN' THEN (public.published_pick_stake(price)).risk
        WHEN 'LOSS' THEN (public.published_pick_stake(price)).risk
        ELSE 0
      END
    $risked$;
  END IF;

  GRANT EXECUTE ON FUNCTION public.published_pick_stake(numeric) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.published_pick_unit_profit(numeric, text) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.published_pick_unit_risked(numeric, text) TO anon, authenticated;
END $mig$;
