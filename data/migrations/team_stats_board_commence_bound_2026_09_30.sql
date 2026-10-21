-- team_stats_board_commence_bound_2026_09_30
--
-- Daily runs 873cb1fe2e1e487d975ae3367f219a3f (2026-09-29) and
-- fd57b13575f04d63b219134d62f434dc (2026-09-30), both
-- failed_steps = refresh_team_board,health_check. The health_check half is
-- PR #852. This file is the team-board half.
--
-- team_stats_board_cache MLB 2026 last_refresh was 2026-09-28 10:04:47+00
-- (30 teams). Every other pair refreshed on 2026-09-30, MLB 2025 at
-- 10:03:50+00 and WNBA 2025 at 10:05:56+00. statement_timeout on the
-- postgres role is 2min. The pair between those two cache writes is
-- MLB 2026 (2,209 finals).
--
-- The 2026-09-28 probe (team_board_line_probe) already uses
-- idx_odds_book_snap. It still times out on MLB 2026 because snapshot_at
-- and games.commence_time are text, and the pre-game cutoff is
-- `snapshot_at::timestamptz <= commence_time::timestamptz`. That cast is a
-- heap Filter, not an index condition, so the backward scan starts at the
-- newest in-play row. DraftKings MLB 2026 spreads: 406,606 in_play rows
-- across 1,802 games (totals 408,109 / 1,808). MLB 2025 spreads in_play is
-- 706 rows, which is why that season finishes. One game,
-- MLB_2026-09-15_OAK_TB spreads: the live probe removed 866 rows (855
-- buffers, 3.880 ms hot). The same probe with a text upper bound removed
-- 11 rows (16 buffers, 0.408 ms) and kept the index condition.
--
-- EXPLAIN ANALYZE of every finished MLB 2026 game, both markets, the five
-- named books, with that bound: 11,626.902 ms, 4,418 pairs, Index Cond
-- snapshot_at < the Z upper bound, average 1 row removed by the residual
-- timestamptz filter. NCAAF 2026 on 2026-09-26 (124 game-markets) and six
-- MLB 2026 dates (134 game-markets) matched the old probe on book,
-- snapshot_at, spread_home and total_line: 0 mismatches.
--
-- The bound is one second past commence, formatted UTC `...Z`, because
-- snapshot_at is the 20-char Z shape and commence_time is either
-- `+00:00` or fractional Z. Text `< next second` includes the closing
-- second; `snapshot_at::timestamptz <= commence_time::timestamptz` drops
-- anything in that window that is actually after first pitch. A missing
-- commence_time keeps the old unbounded probe (NBA finals have no
-- commence_time and refreshed in the same daily run). snapshot_at is
-- NOT NULL, so DESC NULLS FIRST has no null to prefer.
--
-- Book order is unchanged. One statement. The marker in the function body
-- makes the second pass a no-op. The body still contains
-- team_board_line_probe so the 2026-09-28 migration stays a no-op.

DO $mig$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.proname = 'team_stats_board_compute'
      AND pg_get_functiondef(p.oid) LIKE '%team_board_commence_bound%'
  ) THEN
    RAISE NOTICE 'team_stats_board_compute already uses team_board_commence_bound';
    RETURN;
  END IF;

  EXECUTE $sql$
CREATE OR REPLACE FUNCTION public.team_stats_board_compute(p_sport text, p_season integer)
 RETURNS TABLE(team text, conference text, games_played bigint, wins bigint, losses bigint, win_pct numeric, points_for_pg numeric, points_against_pg numeric, point_diff_pg numeric, ats_w bigint, ats_l bigint, ats_p bigint, ats_pct numeric, ou_o bigint, ou_u bigint, ou_p bigint, over_pct numeric, home_w bigint, home_l bigint, away_w bigint, away_l bigint, ats_home_pct numeric, ats_away_pct numeric, fav_ats_pct numeric, dog_ats_pct numeric, rest_adv_games bigint, rest_adv_ats_pct numeric, short_rest_games bigint, short_rest_ats_pct numeric, wrc_plus numeric, ops numeric, team_era numeric, bullpen_era numeric, team_whip numeric, off_rating numeric, def_rating numeric, net_rating numeric, pace numeric, efg_pct numeric, tov_pct numeric, corsi_for_pct numeric, pp_pct numeric, pk_pct numeric, sp_overall numeric, epa_off numeric, epa_def numeric, success_off numeric, success_def numeric, explosiveness_off numeric, havoc_rate numeric, yards_per_play numeric, pass_yards_pg numeric, rush_yards_pg numeric)
 LANGUAGE sql
 STABLE
 SET search_path TO 'public', 'pg_temp'
AS $fn$
WITH cand AS (
  SELECT g.game_id, g.game_date::date AS gd, g.commence_time,
         g.home_team, g.away_team, g.home_score, g.away_score
  FROM games g
  WHERE p_sport <> 'NFL'
    AND g.sport = p_sport AND g.season = p_season
    AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
),
picked AS (
  -- team_board_line_probe: one index lookup per (game, market, book) on
  -- idx_odds_book_snap. team_board_commence_bound: the pre-game cutoff is an
  -- index condition on that same index. snapshot_at is text, so
  -- `snapshot_at::timestamptz <= commence_time::timestamptz` cannot bound the
  -- scan; the backward scan was starting at the newest in-play row and MLB
  -- 2026 cancelled at statement_timeout on 2026-09-29 and 2026-09-30.
  --
  -- PRE-GAME ONLY: the evening refresh keeps writing snapshot_type='open'
  -- after first pitch. A missing commence_time keeps every non-in-play row
  -- (the previous fail-open). snapshot_at is NOT NULL.
  SELECT c.game_id, m.market,
         CASE WHEN named.ok THEN named.spread_home ELSE other.spread_home END AS spread_home,
         CASE WHEN named.ok THEN named.total_line ELSE other.total_line END AS total_line
  FROM cand c
  CROSS JOIN (VALUES ('spreads'::text), ('totals'::text)) AS m(market)
  LEFT JOIN LATERAL (
    SELECT o.spread_home, o.total_line, true AS ok
    FROM (VALUES
            ('draftkings'::text, 0),
            ('cfbd_draftkings', 1),
            ('cfbd_bovada', 2),
            ('cfbd_consensus', 3),
            ('cfbd_teamrankings', 4)
         ) AS b(bookmaker, pri)
    JOIN LATERAL (
      (
        SELECT oo.spread_home, oo.total_line
        FROM odds oo
        WHERE c.commence_time IS NOT NULL
          AND oo.game_id = c.game_id
          AND oo.market = m.market
          AND oo.bookmaker = b.bookmaker
          AND oo.snapshot_at < to_char(
                (c.commence_time::timestamptz + interval '1 second') AT TIME ZONE 'UTC',
                'YYYY-MM-DD"T"HH24:MI:SS"Z"')
          AND oo.snapshot_type IS DISTINCT FROM 'in_play'
          AND oo.snapshot_at::timestamptz <= c.commence_time::timestamptz
        ORDER BY oo.snapshot_at DESC NULLS FIRST
        LIMIT 1
      )
      UNION ALL
      (
        SELECT oo.spread_home, oo.total_line
        FROM odds oo
        WHERE c.commence_time IS NULL
          AND oo.game_id = c.game_id
          AND oo.market = m.market
          AND oo.bookmaker = b.bookmaker
          AND oo.snapshot_type IS DISTINCT FROM 'in_play'
        ORDER BY oo.snapshot_at DESC NULLS FIRST
        LIMIT 1
      )
      LIMIT 1
    ) o ON true
    ORDER BY b.pri
    LIMIT 1
  ) named ON true
  LEFT JOIN LATERAL (
    (
      SELECT oo.spread_home, oo.total_line
      FROM odds oo
      WHERE named.ok IS NOT TRUE
        AND c.commence_time IS NOT NULL
        AND oo.game_id = c.game_id
        AND oo.market = m.market
        AND oo.snapshot_at < to_char(
              (c.commence_time::timestamptz + interval '1 second') AT TIME ZONE 'UTC',
              'YYYY-MM-DD"T"HH24:MI:SS"Z"')
        AND oo.bookmaker LIKE 'cfbd\_%'
        AND oo.bookmaker NOT IN (
              'cfbd_draftkings', 'cfbd_bovada', 'cfbd_consensus', 'cfbd_teamrankings')
        AND oo.snapshot_type IS DISTINCT FROM 'in_play'
        AND oo.snapshot_at::timestamptz <= c.commence_time::timestamptz
      ORDER BY oo.snapshot_at DESC NULLS FIRST
      LIMIT 1
    )
    UNION ALL
    (
      SELECT oo.spread_home, oo.total_line
      FROM odds oo
      WHERE named.ok IS NOT TRUE
        AND c.commence_time IS NULL
        AND oo.game_id = c.game_id
        AND oo.market = m.market
        AND oo.bookmaker LIKE 'cfbd\_%'
        AND oo.bookmaker NOT IN (
              'cfbd_draftkings', 'cfbd_bovada', 'cfbd_consensus', 'cfbd_teamrankings')
        AND oo.snapshot_type IS DISTINCT FROM 'in_play'
      ORDER BY oo.snapshot_at DESC NULLS FIRST
      LIMIT 1
    )
    LIMIT 1
  ) other ON true
),
game_lines AS (
  SELECT c.game_id, c.gd, c.home_team, c.away_team, c.home_score, c.away_score,
         max(p.spread_home) FILTER (WHERE p.market = 'spreads') AS spread_home,
         max(p.total_line)  FILTER (WHERE p.market = 'totals')  AS total_line
  FROM cand c
  LEFT JOIN picked p ON p.game_id = c.game_id
  GROUP BY c.game_id, c.gd, c.home_team, c.away_team, c.home_score, c.away_score
),
fact AS (
  SELECT gl.home_team AS team, gl.game_id, gl.gd AS game_date, TRUE AS is_home,
         (gl.home_score - gl.away_score) AS margin,
         gl.spread_home AS team_spread,
         (gl.home_score + gl.away_score) AS total_pts, gl.total_line,
         NULL::numeric AS o_pass_yards, NULL::numeric AS o_rush_yards, NULL::numeric AS o_plays
  FROM game_lines gl

  UNION ALL

  SELECT gl.away_team, gl.game_id, gl.gd, FALSE,
         (gl.away_score - gl.home_score),
         -gl.spread_home,
         (gl.home_score + gl.away_score), gl.total_line,
         NULL::numeric, NULL::numeric, NULL::numeric
  FROM game_lines gl

  UNION ALL

  -- NFL: nflverse carries the closing line on the team-game row itself, so no
  -- odds join. spread_line is positive-means-home-favored — the OPPOSITE of
  -- odds.spread_home — hence the negation on the home side to reach standard
  -- form. (Verified: reading it as standard form made "favorites" win 32%.)
  SELECT n.team, n.game_id, n.game_date::date, (n.is_home = 1),
         (n.points_for - n.points_against),
         CASE WHEN n.is_home = 1 THEN -n.spread_line ELSE n.spread_line END,
         (n.points_for + n.points_against), n.total_line,
         n.pass_yards, n.rush_yards, n.plays
  FROM nfl_team_game_stats n
  WHERE p_sport = 'NFL' AND n.season = p_season
    AND n.points_for IS NOT NULL AND n.points_against IS NOT NULL
),
rested AS (
  SELECT f.*,
         (f.game_date - lag(f.game_date) OVER (PARTITION BY f.team ORDER BY f.game_date, f.game_id))
           AS rest_days
  FROM fact f
),
paired AS (
  SELECT r.*,
         opp.rest_days AS opp_rest_days,
         CASE
           WHEN p_sport IN ('NBA', 'WNBA', 'NHL') THEN r.rest_days <= 1
           WHEN p_sport IN ('NFL', 'NCAAF')       THEN r.rest_days <= 6
           ELSE r.rest_days = 0
         END AS is_short_rest,
         (r.margin + r.team_spread) AS ats_edge
  FROM rested r
  LEFT JOIN rested opp ON opp.game_id = r.game_id AND opp.team <> r.team
),
agg AS (
  SELECT
    p.team AS t,
    count(*) AS gp,
    count(*) FILTER (WHERE p.margin > 0) AS w,
    count(*) FILTER (WHERE p.margin < 0) AS l,
    avg((p.total_pts + p.margin) / 2.0) AS pf_pg,
    avg((p.total_pts - p.margin) / 2.0) AS pa_pg,
    avg(p.margin) AS pd_pg,
    count(*) FILTER (WHERE p.ats_edge > 0) AS a_w,
    count(*) FILTER (WHERE p.ats_edge < 0) AS a_l,
    count(*) FILTER (WHERE p.ats_edge = 0) AS a_p,
    count(*) FILTER (WHERE p.total_line IS NOT NULL AND p.total_pts > p.total_line) AS o_o,
    count(*) FILTER (WHERE p.total_line IS NOT NULL AND p.total_pts < p.total_line) AS o_u,
    count(*) FILTER (WHERE p.total_line IS NOT NULL AND p.total_pts = p.total_line) AS o_p,
    count(*) FILTER (WHERE p.is_home AND p.margin > 0) AS h_w,
    count(*) FILTER (WHERE p.is_home AND p.margin < 0) AS h_l,
    count(*) FILTER (WHERE NOT p.is_home AND p.margin > 0) AS a_wins,
    count(*) FILTER (WHERE NOT p.is_home AND p.margin < 0) AS a_losses,
    count(*) FILTER (WHERE p.is_home AND p.ats_edge > 0) AS ah_w,
    count(*) FILTER (WHERE p.is_home AND p.ats_edge < 0) AS ah_l,
    count(*) FILTER (WHERE NOT p.is_home AND p.ats_edge > 0) AS aa_w,
    count(*) FILTER (WHERE NOT p.is_home AND p.ats_edge < 0) AS aa_l,
    count(*) FILTER (WHERE p.team_spread < 0 AND p.ats_edge > 0) AS fav_w,
    count(*) FILTER (WHERE p.team_spread < 0 AND p.ats_edge < 0) AS fav_l,
    count(*) FILTER (WHERE p.team_spread > 0 AND p.ats_edge > 0) AS dog_w,
    count(*) FILTER (WHERE p.team_spread > 0 AND p.ats_edge < 0) AS dog_l,
    count(*) FILTER (WHERE p.rest_days > p.opp_rest_days) AS ra_gp,
    count(*) FILTER (WHERE p.rest_days > p.opp_rest_days AND p.ats_edge > 0) AS ra_w,
    count(*) FILTER (WHERE p.rest_days > p.opp_rest_days AND p.ats_edge < 0) AS ra_l,
    count(*) FILTER (WHERE p.is_short_rest) AS sr_gp,
    count(*) FILTER (WHERE p.is_short_rest AND p.ats_edge > 0) AS sr_w,
    count(*) FILTER (WHERE p.is_short_rest AND p.ats_edge < 0) AS sr_l,
    sum(p.o_pass_yards) AS s_pass, sum(p.o_rush_yards) AS s_rush, sum(p.o_plays) AS s_plays
  FROM paired p
  GROUP BY p.team
),
eff_mlb AS (
  SELECT DISTINCT ON (m.team) m.team AS t, NULL::text AS conf,
         m.wrc_plus, m.ops, m.team_era, m.bullpen_era, m.team_whip,
         NULL::numeric AS off_rating, NULL::numeric AS def_rating, NULL::numeric AS pace,
         NULL::numeric AS efg_pct, NULL::numeric AS tov_pct,
         NULL::numeric AS corsi_for_pct, NULL::numeric AS pp_pct, NULL::numeric AS pk_pct,
         NULL::numeric AS sp_overall, NULL::numeric AS epa_off, NULL::numeric AS epa_def,
         NULL::numeric AS success_off, NULL::numeric AS success_def,
         NULL::numeric AS explosiveness_off, NULL::numeric AS havoc_rate
  FROM mlb_team_stats m WHERE p_sport = 'MLB' AND m.season = p_season
  ORDER BY m.team, m.as_of_date DESC
),
eff_nba AS (
  SELECT DISTINCT ON (b.team) b.team, NULL::text,
         NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric,
         b.off_rating, b.def_rating, b.pace, b.efg_pct, b.tov_pct,
         NULL::numeric, NULL::numeric, NULL::numeric,
         NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric,
         NULL::numeric, NULL::numeric
  FROM nba_team_stats b WHERE p_sport = 'NBA' AND b.season = p_season
  ORDER BY b.team, b.as_of_date DESC
),
eff_wnba AS (
  SELECT DISTINCT ON (b.team) b.team, NULL::text,
         NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric,
         b.off_rating, b.def_rating, b.pace, b.efg_pct, b.tov_pct,
         NULL::numeric, NULL::numeric, NULL::numeric,
         NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric,
         NULL::numeric, NULL::numeric
  FROM wnba_team_stats b WHERE p_sport = 'WNBA' AND b.season = p_season
  ORDER BY b.team, b.as_of_date DESC
),
eff_nhl AS (
  SELECT DISTINCT ON (h.team) h.team, NULL::text,
         NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric,
         NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric,
         h.corsi_for_pct, h.power_play_pct, h.penalty_kill_pct,
         NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric,
         NULL::numeric, NULL::numeric
  FROM nhl_team_stats h WHERE p_sport = 'NHL' AND h.season = p_season
  ORDER BY h.team, h.as_of_date DESC
),
eff_ncaaf AS (
  SELECT DISTINCT ON (c.team) c.team, c.conference,
         NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric,
         NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric, NULL::numeric,
         NULL::numeric, NULL::numeric, NULL::numeric,
         c.sp_overall, c.epa_per_play_off, c.epa_per_play_def,
         c.success_rate_off, c.success_rate_def, c.explosiveness_off, c.havoc_rate
  FROM ncaaf_team_stats c
  WHERE p_sport = 'NCAAF' AND c.season = p_season AND c.classification = 'fbs'
  ORDER BY c.team, c.as_of_date DESC
),
eff AS (
  SELECT * FROM eff_mlb
  UNION ALL SELECT * FROM eff_nba
  UNION ALL SELECT * FROM eff_wnba
  UNION ALL SELECT * FROM eff_nhl
  UNION ALL SELECT * FROM eff_ncaaf
)
SELECT
  a.t,
  e.conf,
  a.gp, a.w, a.l,
  round(a.w::numeric / nullif(a.w + a.l, 0), 3),
  round(a.pf_pg, 2), round(a.pa_pg, 2), round(a.pd_pg, 2),
  a.a_w, a.a_l, a.a_p,
  round(a.a_w::numeric / nullif(a.a_w + a.a_l, 0), 3),
  a.o_o, a.o_u, a.o_p,
  round(a.o_o::numeric / nullif(a.o_o + a.o_u, 0), 3),
  a.h_w, a.h_l, a.a_wins, a.a_losses,
  round(a.ah_w::numeric / nullif(a.ah_w + a.ah_l, 0), 3),
  round(a.aa_w::numeric / nullif(a.aa_w + a.aa_l, 0), 3),
  round(a.fav_w::numeric / nullif(a.fav_w + a.fav_l, 0), 3),
  round(a.dog_w::numeric / nullif(a.dog_w + a.dog_l, 0), 3),
  a.ra_gp, round(a.ra_w::numeric / nullif(a.ra_w + a.ra_l, 0), 3),
  a.sr_gp, round(a.sr_w::numeric / nullif(a.sr_w + a.sr_l, 0), 3),
  e.wrc_plus, e.ops, e.team_era, e.bullpen_era, e.team_whip,
  e.off_rating, e.def_rating,
  CASE WHEN e.off_rating IS NOT NULL AND e.def_rating IS NOT NULL
       THEN round(e.off_rating - e.def_rating, 2) END,
  e.pace, e.efg_pct, e.tov_pct,
  e.corsi_for_pct, e.pp_pct, e.pk_pct,
  e.sp_overall, e.epa_off, e.epa_def, e.success_off, e.success_def,
  e.explosiveness_off, e.havoc_rate,
  round(nullif(a.s_pass + a.s_rush, 0) / nullif(a.s_plays, 0), 2),
  round(a.s_pass / nullif(a.gp, 0), 1),
  round(a.s_rush / nullif(a.gp, 0), 1)
FROM agg a
LEFT JOIN eff e ON e.t = a.t
WHERE p_sport <> 'NCAAF' OR e.t IS NOT NULL
ORDER BY a.t
$fn$
  $sql$;

  REVOKE ALL ON FUNCTION public.team_stats_board_compute(text, integer)
    FROM PUBLIC, anon, authenticated;
END
$mig$;
