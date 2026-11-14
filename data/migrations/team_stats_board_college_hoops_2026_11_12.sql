-- team_stats_board_college_hoops_2026_11_12
--
-- NCAAB and NCAABW Teams boards. The app calls team_stats_board(sport, season),
-- which already exists and reads team_stats_board_cache. This file does not
-- create a relation and does not change that signature.
--
-- It patches team_stats_board_compute so a refresh can fill efficiency from
-- the box tables that already exist (ncaab_team_game_stats,
-- ncaabw_team_game_stats). Record and ATS still come from games + the
-- pre-game line, the same walk the other sports use. The school name on
-- games.home_team matches ncaab_teams.school / ncaabw_teams.school (measured
-- 2026-11-12: 727 of 727 men's 2025-26 teams, 661 of 661 women's). The NCAA
-- box name does not ("Arizona St." vs "Arizona State"), so the join is
-- team_espn_id -> registry espn_id -> school.
--
-- eFG% is written as points (56.6), not a 0-1 rate. The catalog formats
-- efg_pct as dec1, which prints toFixed(1). A stored 0.566 would show 0.6.
-- Duke, men's season 2026, from the box: eFG 56.6, Off Rtg 122.4, Def Rtg
-- 94.8, pace 66.7, TOV% 16.0. Net Rtg is Off minus Def, computed below the
-- join the way it already is for NBA. NBA and WNBA cache rows are still a
-- 0-1 eFG (measured the same day); this patch does not touch them.
-- TOV% is already points (100 * turnovers / possessions), the same scale
-- nba_team_stats.tov_pct uses. Pace is possessions per game.
--
-- Conference is left null. The board prints it beside the school name, and
-- a conference label is what truncates a long college name.
--
-- The board row is Division I only. games carries the non-D1 opponent, and
-- the box does too (measured 2026-11-13: 2026-27 men's games are 365 D1 and
-- 164 not, and 160 of those non-D1 schools have a box row). Requiring an
-- efficiency row, the NCAAF trick, would not drop them. Win% has no
-- small-sample guard, so a 1-0 non-D1 school (Fort Valley State, Georgia
-- Gwinnett, that date) ties every unbeaten D1 team at the top of Win%.
-- The filter is on the OUTPUT row. The non-D1 game still counts in the D1
-- team's record, because the aggregate is already built.
--
-- NOT in data/view_migrations.ACTIVE_MIGRATIONS. Apply by hand once Matt
-- says so. A merge or an OTA does not query a relation this file creates:
-- team_stats_board() is already there, and an unfilled cache returns no
-- rows (the app then tries the previous ending-year label, then an empty
-- board). Until this is applied AND refresh_team_stats_board has run for
-- NCAAB and NCAABW, the default chip (Net Rtg) has nothing to show. Apply
-- this, then refresh, before relying on the board. Do not apply it while
-- opening the pull request.
--
-- Marker: team_board_college_hoops. Re-running is a no-op (NOTICE). If an
-- anchor is not in the live function exactly once, the apply raises and
-- changes nothing. A warning there would look like a successful apply.

DO $mig$
DECLARE
  def text;
  anchor text := $a$  WHERE p_sport = 'NCAAF' AND c.season = p_season AND c.classification = 'fbs'
  ORDER BY c.team, c.as_of_date DESC
),
eff AS ($a$;
  replacement text := $a$  WHERE p_sport = 'NCAAF' AND c.season = p_season AND c.classification = 'fbs'
  ORDER BY c.team, c.as_of_date DESC
),
-- team_board_college_hoops
eff_ncaabw AS (
  SELECT sch.school,
         NULL::text,
         NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric,
         round((100.0 * sum(s.pts) / nullif(sum(s.o_poss), 0))::numeric, 1),
         round((100.0 * sum(s.d_pts) / nullif(sum(s.d_poss), 0))::numeric, 1),
         round((sum(s.o_poss) / nullif(count(*), 0))::numeric, 1),
         round((100.0 * (sum(s.fgm) + 0.5 * sum(s.tpm)) / nullif(sum(s.fga), 0))::numeric, 1),
         round((100.0 * sum(s.tov) / nullif(sum(s.o_poss), 0))::numeric, 1),
         NULL::numeric, NULL::numeric, NULL::numeric,
         NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric,
         NULL::numeric, NULL::numeric
  FROM ncaabw_team_game_stats s
  JOIN ncaabw_teams sch ON sch.espn_id = s.team_espn_id
  WHERE p_sport = 'NCAABW' AND s.season = p_season
  GROUP BY sch.school
),
eff_ncaab AS (
  SELECT sch.school,
         NULL::text,
         NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric,
         round((100.0 * sum(s.pts) / nullif(sum(s.o_poss), 0))::numeric, 1),
         round((100.0 * sum(s.d_pts) / nullif(sum(s.d_poss), 0))::numeric, 1),
         round((sum(s.o_poss) / nullif(count(*), 0))::numeric, 1),
         round((100.0 * (sum(s.fgm) + 0.5 * sum(s.tpm)) / nullif(sum(s.fga), 0))::numeric, 1),
         round((100.0 * sum(s.tov) / nullif(sum(s.o_poss), 0))::numeric, 1),
         NULL::numeric, NULL::numeric, NULL::numeric,
         NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric,
         NULL::numeric, NULL::numeric
  FROM ncaab_team_game_stats s
  JOIN ncaab_teams sch ON sch.espn_id = s.team_espn_id
  WHERE p_sport = 'NCAAB' AND s.season = p_season
  GROUP BY sch.school
),
eff AS ($a$;
  union_anchor text := $a$  UNION ALL SELECT * FROM eff_ncaaf
)$a$;
  union_replacement text := $a$  UNION ALL SELECT * FROM eff_ncaaf
  UNION ALL SELECT * FROM eff_ncaabw
  UNION ALL SELECT * FROM eff_ncaab
)$a$;
  d1_anchor text := $a$WHERE p_sport <> 'NCAAF' OR e.t IS NOT NULL
ORDER BY a.t$a$;
  d1_replacement text := $a$WHERE (p_sport <> 'NCAAF' OR e.t IS NOT NULL)
  AND (
    p_sport NOT IN ('NCAABW', 'NCAAB')
    OR EXISTS (
      SELECT 1 FROM ncaabw_teams w
      WHERE p_sport = 'NCAABW' AND w.school = a.t AND w.is_d1
    )
    OR EXISTS (
      SELECT 1 FROM ncaab_teams m
      WHERE p_sport = 'NCAAB' AND m.school = a.t AND m.is_d1
    )
  )
ORDER BY a.t$a$;
  hits int;
BEGIN
  SELECT pg_get_functiondef(p.oid) INTO def
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
  WHERE n.nspname = 'public' AND p.proname = 'team_stats_board_compute';

  IF def IS NULL THEN
    RAISE WARNING 'team_stats_board_compute not found; college hoops patch skipped';
    RETURN;
  END IF;
  IF position('team_board_college_hoops' in def) > 0 THEN
    RAISE NOTICE 'team_stats_board_compute already has team_board_college_hoops';
    RETURN;
  END IF;

  hits := (length(def) - length(replace(def, anchor, ''))) / length(anchor);
  IF hits <> 1 THEN
    RAISE EXCEPTION 'team_board_college_hoops: anchor found % times, expected 1', hits;
  END IF;
  hits := (length(def) - length(replace(def, union_anchor, ''))) / length(union_anchor);
  IF hits <> 1 THEN
    RAISE EXCEPTION 'team_board_college_hoops: union anchor found % times, expected 1', hits;
  END IF;
  hits := (length(def) - length(replace(def, d1_anchor, ''))) / length(d1_anchor);
  IF hits <> 1 THEN
    RAISE EXCEPTION 'team_board_college_hoops: D1 anchor found % times, expected 1', hits;
  END IF;

  def := replace(def, anchor, replacement);
  def := replace(def, union_anchor, union_replacement);
  def := replace(def, d1_anchor, d1_replacement);
  EXECUTE def;
END
$mig$;
