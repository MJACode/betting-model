-- NBA first-quarter team stats for the Stats tab (Matt, 2026-10-28).
--
-- A member asked for each team's first-quarter record, home/away splits over
-- the last 5 and 10 games, and first-quarter offensive and defensive
-- efficiency. These are stats only. The first-quarter model was tested and
-- closed in docs/nba_models_2026.md §9.
--
-- nba_team_q1_games: one row per team per regular-season game. Points come
-- from nba_period_scores (period 1). Possessions come from nba_stints and are
-- counted from play-by-play events, not estimated. Possessions are NULL when
-- the stints' first-quarter points do not match the quarter score, so a bad
-- derivation is left out of the efficiency figures. Written by
-- data/ingestors/nba_team_q1.py. The app reads it.
--
-- v_nba_team_q1_season: per season, team and venue (all / home / away),
-- the record, points and per-100-possession ratings, ranked across the
-- league. security_invoker, so the table's SELECT policy is what allows it.
--
-- Measured 2026-10-28 on 2025-26: 1,230 games, 2,460 rows, 25.6 first-quarter
-- possessions per team per game, league rating 114.9, stint points off the
-- quarter score in 1 game. The writer's query took 136 ms.
--
-- Once the table, the policy and the view's marker comment exist, this
-- returns on a catalog read. A no-op CREATE OR REPLACE still reloads
-- PostgREST's schema cache (data/ddl_guard.py).
DO $$
BEGIN
  IF to_regclass('public.nba_team_q1_games') IS NOT NULL
     AND to_regclass('public.v_nba_team_q1_season') IS NOT NULL
     AND COALESCE(obj_description(to_regclass('public.v_nba_team_q1_season'), 'pg_class'), '')
         = 'nba_team_q1 v1'
     AND EXISTS (
       SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'nba_team_q1_games'
          AND policyname = 'anon read nba_team_q1_games')
  THEN
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.nba_team_q1_games (
    game_id       TEXT    NOT NULL,
    team          TEXT    NOT NULL,
    season        INTEGER NOT NULL,
    game_date     TEXT    NOT NULL,
    opponent      TEXT    NOT NULL,
    is_home       BOOLEAN NOT NULL,
    pts_for       INTEGER NOT NULL,
    pts_against   INTEGER NOT NULL,
    poss_for      INTEGER,
    poss_against  INTEGER,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, team)
  );
  CREATE INDEX IF NOT EXISTS nba_team_q1_games_team_date
    ON public.nba_team_q1_games (team, game_date DESC);

  ALTER TABLE public.nba_team_q1_games ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.nba_team_q1_games FROM anon, authenticated;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'nba_team_q1_games'
       AND policyname = 'anon read nba_team_q1_games'
  ) THEN
    CREATE POLICY "anon read nba_team_q1_games"
      ON public.nba_team_q1_games
      FOR SELECT
      TO anon, authenticated
      USING (true);
  END IF;
  GRANT SELECT ON public.nba_team_q1_games TO anon, authenticated;

  EXECUTE $view$
    CREATE OR REPLACE VIEW public.v_nba_team_q1_season
    WITH (security_invoker = on) AS
    WITH split AS (
      SELECT season, team, 'all'::text AS venue,
             pts_for, pts_against, poss_for, poss_against
        FROM public.nba_team_q1_games
      UNION ALL
      SELECT season, team, CASE WHEN is_home THEN 'home' ELSE 'away' END,
             pts_for, pts_against, poss_for, poss_against
        FROM public.nba_team_q1_games
    ),
    agg AS (
      SELECT season, team, venue,
             count(*)::int AS games,
             count(*) FILTER (WHERE pts_for > pts_against)::int AS wins,
             count(*) FILTER (WHERE pts_for < pts_against)::int AS losses,
             count(*) FILTER (WHERE pts_for = pts_against)::int AS ties,
             sum(pts_for)::int AS pts_for,
             sum(pts_against)::int AS pts_against,
             count(*) FILTER (WHERE poss_for IS NOT NULL AND poss_against IS NOT NULL)::int
               AS rated_games,
             round(100.0 * sum(pts_for) FILTER (WHERE poss_for IS NOT NULL AND poss_against IS NOT NULL)
                   / NULLIF(sum(poss_for) FILTER (WHERE poss_for IS NOT NULL AND poss_against IS NOT NULL), 0), 1)
               AS ortg,
             round(100.0 * sum(pts_against) FILTER (WHERE poss_for IS NOT NULL AND poss_against IS NOT NULL)
                   / NULLIF(sum(poss_against) FILTER (WHERE poss_for IS NOT NULL AND poss_against IS NOT NULL), 0), 1)
               AS drtg
        FROM split
       GROUP BY season, team, venue
    )
    SELECT agg.*,
           (agg.ortg - agg.drtg) AS net_rtg,
           rank() OVER (PARTITION BY season, venue ORDER BY ortg DESC NULLS LAST)::int AS ortg_rank,
           rank() OVER (PARTITION BY season, venue ORDER BY drtg ASC NULLS LAST)::int AS drtg_rank,
           rank() OVER (PARTITION BY season, venue ORDER BY (ortg - drtg) DESC NULLS LAST)::int AS net_rank,
           count(*) OVER (PARTITION BY season, venue)::int AS teams
      FROM agg
  $view$;
  EXECUTE $c$COMMENT ON VIEW public.v_nba_team_q1_season IS 'nba_team_q1 v1'$c$;
  REVOKE ALL ON public.v_nba_team_q1_season FROM anon, authenticated;
  GRANT SELECT ON public.v_nba_team_q1_season TO anon, authenticated;
END $$;
