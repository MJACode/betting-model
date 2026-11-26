-- Build Your Own Model: NCAAB game lines (Matt, 2026-11-26: "Do NCAAB next";
-- scope chosen the same day: game lines, no props).
--
-- Moneyline, spread and total at the official line and the closing line,
-- staked like the main models. byom_legs and byom_save_model accept sport
-- 'NCAAB'. A null season is the ending year, the NBA rule (October on is
-- next year's label): games labels the season that opened 2026-11-01 as
-- 2027 (measured 2026-11-26). The first built season is 2021
-- (byom.constants.NCAAB_DK_HISTORY_START_SEASON).
--
-- Both live bodies are the sum of several earlier files, so, as
-- byom_no_half_yards_2026_11_17.sql does, this reads each live definition,
-- checks every anchor occurs exactly once (or raises and changes nothing),
-- adds 'NCAAB' beside 'NHL' in the sport check and the ending-year rule,
-- and re-runs it. CREATE OR REPLACE keeps the grants and the SET clauses
-- (plan_cache_mode=force_custom_plan, which the trend file's skip needs).
-- Every earlier marker stays, so those files still skip. A later file that
-- re-creates either function from its own text must carry 'NCAAB', or the
-- sport is refused again.
--
-- Skips once both bodies carry byom_ncaab_v1. Does not write picks.

DO $mig$
DECLARE
  v_proc regprocedure;
  v_def text;
  v_anchor text;
  v_fn text;
  v_marker text;
  v_not_in text := 'IF v_sport NOT IN (''NFL'', ''NBA'', ''NHL'') THEN';
  v_ending text := 'IF v_sport IN (''NBA'', ''NHL'') THEN';
BEGIN
  FOREACH v_fn IN ARRAY ARRAY['public.byom_legs(integer, jsonb, text)',
                              'public.byom_save_model(text, jsonb, integer)'] LOOP
    v_proc := to_regprocedure(v_fn);
    IF v_proc IS NULL THEN
      RAISE NOTICE '% is not on this database - skipping', v_fn;
      CONTINUE;
    END IF;
    IF (SELECT position('byom_ncaab_v1' in p.prosrc) > 0
          FROM pg_proc p WHERE p.oid = v_proc) THEN
      RAISE NOTICE '% already accepts NCAAB - skipping', v_fn;
      CONTINUE;
    END IF;

    v_marker := CASE WHEN v_fn LIKE 'public.byom_legs%'
                     THEN '    -- byom_nhl_v1' ELSE '      -- byom_nhl_v1' END;
    v_def := pg_get_functiondef(v_proc);
    FOREACH v_anchor IN ARRAY ARRAY[v_marker, v_not_in, v_ending] LOOP
      IF (length(v_def) - length(replace(v_def, v_anchor, ''))) / length(v_anchor) <> 1 THEN
        RAISE EXCEPTION 'byom_ncaab (%): anchor not found exactly once: %', v_fn, v_anchor;
      END IF;
    END LOOP;

    v_def := replace(v_def, v_marker, v_marker || E'\n'
      || CASE WHEN v_fn LIKE 'public.byom_legs%' THEN '    ' ELSE '      ' END
      || '-- byom_ncaab_v1');
    v_def := replace(v_def, v_not_in,
      'IF v_sport NOT IN (''NFL'', ''NBA'', ''NHL'', ''NCAAB'') THEN');
    -- NCAAB seasons are the ending year too.
    v_def := replace(v_def, v_ending,
      'IF v_sport IN (''NBA'', ''NHL'', ''NCAAB'') THEN');
    EXECUTE v_def;
  END LOOP;
END
$mig$;
