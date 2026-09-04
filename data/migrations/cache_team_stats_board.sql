-- cache_team_stats_board
-- Applied to Supabase 2026-09-04 (session: player-stats-line-availability).
--
-- THE TEAMS BOARD TIMED OUT: "Connection error: canceling statement due to
-- statement timeout (57014)". Measured before touching anything:
--
--   explain (analyze, buffers) select * from team_stats_board('MLB', 2026)
--   -> Execution Time: 31,669 ms   Buffers: shared hit=368,782 read=70,757, temp 796
--
-- against an 8 s statement_timeout on `authenticated` (3 s on `anon`). The
-- cost is one CTE, `picked`: the pre-game closing line for EVERY finished game
-- of the season, recomputed on every call — 1,883 MLB games, each walking
-- ~234 odds rows, 88,040 rows sorted to disk to keep 3,766. A better index
-- condition (bookmaker = ANY(...) so idx_odds_book_snap applies) was tried and
-- measured at 17.6 s: the time is 63,000 random heap reads of a 1.3 GB table,
-- i.e. data volume, not plan shape. No rewrite of a per-call query gets a
-- season of odds under 8 s.
--
-- A finished game's closing line never changes, and a season aggregate moves
-- once a day. So the board is COMPUTED ONCE and READ MANY TIMES:
--
--   team_stats_board_compute(sport, season)   the heavy function, unchanged
--                                             body, renamed, worker-only.
--   team_stats_board_cache                    one row per (sport, season, team),
--                                             refreshed per pair by the daily
--                                             pipeline — a per-pair swap in one
--                                             transaction, so readers never see
--                                             a half-built board.
--   refresh_team_stats_board(sport, season)   the swap, callable by the worker
--                                             and by a session with the service
--                                             key. Returns rows written.
--   team_stats_board(sport, season)           the SAME signature the app calls
--                                             today, now a ~30-row index read.
--
-- A plain table rather than a materialized view, deliberately: the full
-- compute across 6 sports x 3 seasons is minutes, which is longer than the
-- 60 s a session tool can hold a statement, and REFRESH MATERIALIZED VIEW is
-- all-or-nothing. Per-pair refresh fits in any window, and RLS applies.
--
-- Grants follow the operations rule: REVOKE from anon and authenticated BY
-- NAME on every new object, then grant back exactly what the app needs.

-- 1. The heavy function keeps its body and loses its public name.
ALTER FUNCTION public.team_stats_board(text, integer)
  RENAME TO team_stats_board_compute;
REVOKE ALL ON FUNCTION public.team_stats_board_compute(text, integer)
  FROM PUBLIC, anon, authenticated;

-- 2. The cache.
CREATE TABLE public.team_stats_board_cache (
  sport text NOT NULL,
  season integer NOT NULL,
  team text,
  conference text,
  games_played bigint,
  wins bigint,
  losses bigint,
  win_pct numeric,
  points_for_pg numeric,
  points_against_pg numeric,
  point_diff_pg numeric,
  ats_w bigint,
  ats_l bigint,
  ats_p bigint,
  ats_pct numeric,
  ou_o bigint,
  ou_u bigint,
  ou_p bigint,
  over_pct numeric,
  home_w bigint,
  home_l bigint,
  away_w bigint,
  away_l bigint,
  ats_home_pct numeric,
  ats_away_pct numeric,
  fav_ats_pct numeric,
  dog_ats_pct numeric,
  rest_adv_games bigint,
  rest_adv_ats_pct numeric,
  short_rest_games bigint,
  short_rest_ats_pct numeric,
  wrc_plus numeric,
  ops numeric,
  team_era numeric,
  bullpen_era numeric,
  team_whip numeric,
  off_rating numeric,
  def_rating numeric,
  net_rating numeric,
  pace numeric,
  efg_pct numeric,
  tov_pct numeric,
  corsi_for_pct numeric,
  pp_pct numeric,
  pk_pct numeric,
  sp_overall numeric,
  epa_off numeric,
  epa_def numeric,
  success_off numeric,
  success_def numeric,
  explosiveness_off numeric,
  havoc_rate numeric,
  yards_per_play numeric,
  pass_yards_pg numeric,
  rush_yards_pg numeric,
  refreshed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (sport, season, team)
);
ALTER TABLE public.team_stats_board_cache ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.team_stats_board_cache FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.team_stats_board_cache TO anon, authenticated;
CREATE POLICY team_stats_board_cache_read
  ON public.team_stats_board_cache FOR SELECT TO anon, authenticated USING (true);

-- 3. The swap. One transaction per (sport, season): the old rows go and the
--    new ones land together, or neither does.
CREATE OR REPLACE FUNCTION public.refresh_team_stats_board(p_sport text, p_season integer)
RETURNS integer
LANGUAGE plpgsql
SET search_path TO 'public', 'pg_temp'
AS $$
DECLARE
  n integer;
BEGIN
  DELETE FROM public.team_stats_board_cache
   WHERE sport = p_sport AND season = p_season;
  INSERT INTO public.team_stats_board_cache
    (sport, season, team, conference, games_played, wins, losses, win_pct, points_for_pg, points_against_pg, point_diff_pg, ats_w, ats_l, ats_p, ats_pct, ou_o, ou_u, ou_p, over_pct, home_w, home_l, away_w, away_l, ats_home_pct, ats_away_pct, fav_ats_pct, dog_ats_pct, rest_adv_games, rest_adv_ats_pct, short_rest_games, short_rest_ats_pct, wrc_plus, ops, team_era, bullpen_era, team_whip, off_rating, def_rating, net_rating, pace, efg_pct, tov_pct, corsi_for_pct, pp_pct, pk_pct, sp_overall, epa_off, epa_def, success_off, success_def, explosiveness_off, havoc_rate, yards_per_play, pass_yards_pg, rush_yards_pg, refreshed_at)
  SELECT p_sport, p_season, team, conference, games_played, wins, losses, win_pct, points_for_pg, points_against_pg, point_diff_pg, ats_w, ats_l, ats_p, ats_pct, ou_o, ou_u, ou_p, over_pct, home_w, home_l, away_w, away_l, ats_home_pct, ats_away_pct, fav_ats_pct, dog_ats_pct, rest_adv_games, rest_adv_ats_pct, short_rest_games, short_rest_ats_pct, wrc_plus, ops, team_era, bullpen_era, team_whip, off_rating, def_rating, net_rating, pace, efg_pct, tov_pct, corsi_for_pct, pp_pct, pk_pct, sp_overall, epa_off, epa_def, success_off, success_def, explosiveness_off, havoc_rate, yards_per_play, pass_yards_pg, rush_yards_pg, now()
    FROM public.team_stats_board_compute(p_sport, p_season);
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END
$$;
REVOKE ALL ON FUNCTION public.refresh_team_stats_board(text, integer)
  FROM PUBLIC, anon, authenticated;

-- 4. What the app calls: same name, same signature, same columns, same order.
CREATE FUNCTION public.team_stats_board(p_sport text, p_season integer)
RETURNS TABLE(team text, conference text, games_played bigint, wins bigint, losses bigint, win_pct numeric, points_for_pg numeric, points_against_pg numeric, point_diff_pg numeric, ats_w bigint, ats_l bigint, ats_p bigint, ats_pct numeric, ou_o bigint, ou_u bigint, ou_p bigint, over_pct numeric, home_w bigint, home_l bigint, away_w bigint, away_l bigint, ats_home_pct numeric, ats_away_pct numeric, fav_ats_pct numeric, dog_ats_pct numeric, rest_adv_games bigint, rest_adv_ats_pct numeric, short_rest_games bigint, short_rest_ats_pct numeric, wrc_plus numeric, ops numeric, team_era numeric, bullpen_era numeric, team_whip numeric, off_rating numeric, def_rating numeric, net_rating numeric, pace numeric, efg_pct numeric, tov_pct numeric, corsi_for_pct numeric, pp_pct numeric, pk_pct numeric, sp_overall numeric, epa_off numeric, epa_def numeric, success_off numeric, success_def numeric, explosiveness_off numeric, havoc_rate numeric, yards_per_play numeric, pass_yards_pg numeric, rush_yards_pg numeric)
LANGUAGE sql
STABLE
SET search_path TO 'public', 'pg_temp'
AS $$
  SELECT team, conference, games_played, wins, losses, win_pct, points_for_pg, points_against_pg, point_diff_pg, ats_w, ats_l, ats_p, ats_pct, ou_o, ou_u, ou_p, over_pct, home_w, home_l, away_w, away_l, ats_home_pct, ats_away_pct, fav_ats_pct, dog_ats_pct, rest_adv_games, rest_adv_ats_pct, short_rest_games, short_rest_ats_pct, wrc_plus, ops, team_era, bullpen_era, team_whip, off_rating, def_rating, net_rating, pace, efg_pct, tov_pct, corsi_for_pct, pp_pct, pk_pct, sp_overall, epa_off, epa_def, success_off, success_def, explosiveness_off, havoc_rate, yards_per_play, pass_yards_pg, rush_yards_pg
    FROM public.team_stats_board_cache
   WHERE sport = p_sport AND season = p_season
   ORDER BY team
$$;
REVOKE ALL ON FUNCTION public.team_stats_board(text, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.team_stats_board(text, integer) TO anon, authenticated;
