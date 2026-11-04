-- team_stats_board_main_run_line_2026_11_03
--
-- MLB and NHL "ATS%" on the Teams board grades each game against the run line
-- / puck line, the ±1.5 that DraftKings hangs as the main spread. DraftKings'
-- `spreads` rows for these two sports also carry alternates (±2.5, ±3.5), and
-- the probe takes the newest pre-game row whatever its number.
--
-- Measured 2026-11-03, the probe as it stands, 40 finished MLB 2026 games from
-- 2026-09-15: 38 graded at 1.5, 2 at 2.5. The same 40 with the probe limited
-- to abs(spread_home) = 1.5: 40 of 40 found a 1.5 row, so no game loses its
-- grade. NHL 2027, 60 finished games: 60 at 1.5 already.
--
-- The patch adds one predicate to the two DraftKings-named probes (the cfbd_%
-- probe is NCAAF only). It reads the LIVE function text, so every earlier
-- owner's marker (team_board_line_probe, team_board_commence_bound) stays in
-- the body and their migrations stay no-ops. Marker: team_board_main_run_line.
-- If the anchor text does not appear exactly twice, it changes nothing and
-- says so.

DO $mig$
DECLARE
  def    text;
  anchor text := 'AND oo.bookmaker = b.bookmaker';
  hits   int;
BEGIN
  SELECT pg_get_functiondef(p.oid) INTO def
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
  WHERE n.nspname = 'public' AND p.proname = 'team_stats_board_compute';

  IF def IS NULL THEN
    RAISE WARNING 'team_stats_board_compute not found; main run line patch skipped';
    RETURN;
  END IF;
  IF position('team_board_main_run_line' in def) > 0 THEN
    RAISE NOTICE 'team_stats_board_compute already uses team_board_main_run_line';
    RETURN;
  END IF;

  hits := (length(def) - length(replace(def, anchor, ''))) / length(anchor);
  IF hits <> 2 THEN
    RAISE WARNING 'team_board_main_run_line: anchor found % times, expected 2; skipped', hits;
    RETURN;
  END IF;

  def := replace(def, anchor,
    anchor || E'\n          AND (m.market <> ''spreads'' OR p_sport NOT IN (''MLB'', ''NHL'')'
           || E'\n               OR abs(oo.spread_home) = 1.5)  -- team_board_main_run_line');
  EXECUTE def;
END
$mig$;
