-- Build Your Own Model: no 0.5 line on a yardage market.
--
-- 2026-11-17 (Matt): "I don't like how it picks the 0.5 line", on a
-- "Receiving yards over" model whose list was Over 0.5 on backup tight
-- ends and return men. Chosen: drop 0.5 on yardage only. 0.5 is the
-- normal line elsewhere and stays: measured the same day on
-- byom_prop_facts, 14,548 of 18,397 NBA blocks props and 307 of 1,950
-- NFL passing-TD props are 0.5, against 41 of 10,986 NFL receiving yards.
--
-- The four yardage markets on byom_official_legs (same day):
--   player_reception_yds       206 of 109,640 candidate quotes at 0.5
--   player_rush_yds            835 of  49,286
--   player_rush_reception_yds    2 of  22,978
--   player_pass_yds              0 of  22,526
--
-- A 0.5 yardage quote is never a candidate, on either timing:
--   * official: the lock search skips it, so the bet becomes official at
--     the first later quote that fits (or is not a bet at all);
--   * close: the kept filter drops it.
-- Every other market and filter is unchanged.
--
-- byom_legs is ~600 lines and the live body is the sum of five earlier
-- files. Rather than copy it, this file reads the live definition, checks
-- that each anchor below occurs exactly once (or raises and changes
-- nothing), inserts one line after each, and re-runs it. CREATE OR
-- REPLACE keeps the grants and the SET clauses
-- (plan_cache_mode=force_custom_plan, which the trend file's skip needs).
-- Every earlier marker stays, so those files still skip.
--
-- A later file that re-creates byom_legs from its own text must carry
-- these two lines, or the 0.5 lines come back. Skips once the body
-- carries byom_no_half_yards_v1. Reads facts only. Does not write picks.

DO $mig$
DECLARE
  v_proc regprocedure := to_regprocedure('public.byom_legs(integer, jsonb, text)');
  v_def text;
  v_official text := 'AND (v_max_line IS NULL OR (q.player_key <> '''' AND q.point <= v_max_line))';
  v_close text := 'AND (v_max_line IS NULL OR r.prop_line <= v_max_line)';
  v_marker text := '-- byom_trend_filters_v1';
  v_yards text := '(''player_reception_yds'', ''player_rush_yds'', '
                  '''player_rush_reception_yds'', ''player_pass_yds'')';
  v_anchor text;
BEGIN
  IF v_proc IS NULL THEN
    RAISE NOTICE 'byom_legs is not on this database - skipping';
    RETURN;
  END IF;
  IF (SELECT position('byom_no_half_yards_v1' in p.prosrc) > 0
        FROM pg_proc p WHERE p.oid = v_proc) THEN
    RAISE NOTICE 'byom no half yards already present - skipping';
    RETURN;
  END IF;

  v_def := pg_get_functiondef(v_proc);
  FOREACH v_anchor IN ARRAY ARRAY[v_official, v_close, v_marker] LOOP
    IF (length(v_def) - length(replace(v_def, v_anchor, ''))) / length(v_anchor) <> 1 THEN
      RAISE EXCEPTION 'byom_no_half_yards: anchor not found exactly once: %', v_anchor;
    END IF;
  END LOOP;

  v_def := replace(v_def, v_marker,
    v_marker || E'\n    -- byom_no_half_yards_v1');
  v_def := replace(v_def, v_official, v_official
    || E'\n         -- byom_no_half_yards_v1: no 0.5 line on a yardage market.'
    || E'\n         AND NOT COALESCE(q.player_key <> '''' AND q.market IN '
    || v_yards || ' AND q.point = 0.5, false)');
  v_def := replace(v_def, v_close, v_close
    || E'\n         AND NOT COALESCE(r.mkt IN ' || v_yards
    || ' AND r.prop_line = 0.5, false)');

  EXECUTE v_def;
END
$mig$;
