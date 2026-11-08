-- NBA first-basket stats for the Stats tab (Matt, 2026-11-08).
--
-- Stats only, no model and no pick: we buy no first-basket odds. The NBA
-- Stats tab gets a "1st Basket" board, one card per game tonight: each
-- team's usual jumper and tip record, how often it scores first (split by
-- won / lost tip), how often it gives up the first score, and its likely
-- first scorers.
--
-- DEFINITIONS (Matt chose them 2026-11-08):
--   first basket   the game's first score of ANY kind, free throws
--                  included (FanDuel's rule, not DraftKings').
--   tip            the opening Jumpball row of period 1. The tip winner is
--                  the team that gains possession: that row's team_side,
--                  which matched the side of the game's first possession in
--                  130 of 132 2026-27 games, and 1,308 of 1,313 in 2025-26.
--   first shot     the team's first field-goal attempt (a shooting play that
--                  is not a free throw). "Made" is whether that shot went in.
--   regular season only (season_type 2), this season and last.
--
-- nba_first_basket_games: one row per team per game.
-- nba_first_basket_players: one row per player per game he played.
-- Both written by data/ingestors/nba_first_basket.py from nba_pbp,
-- nba_pbp_box and nba_pbp_games, which the app cannot read.
--
-- v_nba_first_basket_team_season / v_nba_first_basket_player_season: the
-- season sums the board reads, security_invoker over the two tables.
--
-- Once both tables, the policies and the views' marker comments exist, this
-- returns on a catalog read.
DO $$
BEGIN
  IF to_regclass('public.nba_first_basket_games') IS NOT NULL
     AND to_regclass('public.nba_first_basket_players') IS NOT NULL
     AND COALESCE(obj_description(to_regclass('public.v_nba_first_basket_team_season'), 'pg_class'), '')
         = 'nba_first_basket v1'
     AND COALESCE(obj_description(to_regclass('public.v_nba_first_basket_player_season'), 'pg_class'), '')
         = 'nba_first_basket v1'
     AND (SELECT count(*) FROM pg_policies
           WHERE schemaname = 'public'
             AND policyname IN ('anon read nba_first_basket_games',
                                'anon read nba_first_basket_players')) = 2
  THEN
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.nba_first_basket_games (
    game_id              TEXT    NOT NULL,
    team                 TEXT    NOT NULL,
    season               INTEGER NOT NULL,
    game_date            TEXT    NOT NULL,
    opponent             TEXT    NOT NULL,
    is_home              BOOLEAN NOT NULL,
    -- NULL when the game has no opening Jumpball row.
    won_tip              BOOLEAN,
    jumper_espn_id       BIGINT,
    jumper_name          TEXT,
    -- This team made the game's first score (free throws count).
    scored_first         BOOLEAN NOT NULL,
    -- 'FT' / '2PT' / '3PT' on the team that scored first, else NULL.
    first_score_kind     TEXT,
    first_fga_espn_id    BIGINT,
    first_fga_made       BOOLEAN,
    first_score_espn_id  BIGINT,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, team)
  );
  CREATE INDEX IF NOT EXISTS nba_first_basket_games_season_team
    ON public.nba_first_basket_games (season, team);

  CREATE TABLE IF NOT EXISTS public.nba_first_basket_players (
    game_id           TEXT    NOT NULL,
    espn_id           BIGINT  NOT NULL,
    season            INTEGER NOT NULL,
    game_date         TEXT    NOT NULL,
    team              TEXT    NOT NULL,
    name              TEXT    NOT NULL,
    starter           BOOLEAN NOT NULL,
    -- He took his team's first field-goal attempt, and whether it went in.
    first_fga         BOOLEAN NOT NULL,
    first_fga_made    BOOLEAN NOT NULL,
    -- He made the game's first score / his team's first score.
    game_first_score  BOOLEAN NOT NULL,
    team_first_score  BOOLEAN NOT NULL,
    -- He jumped the opening tip, and his team gained possession.
    jumped            BOOLEAN NOT NULL,
    jump_won          BOOLEAN NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, espn_id)
  );
  CREATE INDEX IF NOT EXISTS nba_first_basket_players_season_espn
    ON public.nba_first_basket_players (season, espn_id);

  ALTER TABLE public.nba_first_basket_games ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.nba_first_basket_players ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.nba_first_basket_games FROM anon, authenticated;
  REVOKE ALL ON public.nba_first_basket_players FROM anon, authenticated;
  IF NOT EXISTS (SELECT 1 FROM pg_policies
                  WHERE schemaname = 'public' AND tablename = 'nba_first_basket_games'
                    AND policyname = 'anon read nba_first_basket_games') THEN
    CREATE POLICY "anon read nba_first_basket_games"
      ON public.nba_first_basket_games FOR SELECT TO anon, authenticated USING (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies
                  WHERE schemaname = 'public' AND tablename = 'nba_first_basket_players'
                    AND policyname = 'anon read nba_first_basket_players') THEN
    CREATE POLICY "anon read nba_first_basket_players"
      ON public.nba_first_basket_players FOR SELECT TO anon, authenticated USING (true);
  END IF;
  GRANT SELECT ON public.nba_first_basket_games TO anon, authenticated;
  GRANT SELECT ON public.nba_first_basket_players TO anon, authenticated;

  -- One row per season and team. The likely jumper is the player who jumped
  -- the team's opening tip most often (ties: the most recent).
  EXECUTE $view$
    CREATE OR REPLACE VIEW public.v_nba_first_basket_team_season
    WITH (security_invoker = on) AS
    WITH agg AS (
      SELECT season, team,
             count(*)::int AS games,
             count(*) FILTER (WHERE won_tip IS NOT NULL)::int AS tip_games,
             count(*) FILTER (WHERE won_tip)::int AS tips_won,
             count(*) FILTER (WHERE scored_first)::int AS scored_first,
             count(*) FILTER (WHERE won_tip AND scored_first)::int AS scored_first_won_tip,
             count(*) FILTER (WHERE won_tip IS FALSE)::int AS lost_tip_games,
             count(*) FILTER (WHERE won_tip IS FALSE AND scored_first)::int AS scored_first_lost_tip,
             count(*) FILTER (WHERE NOT scored_first)::int AS allowed_first
        FROM public.nba_first_basket_games
       GROUP BY season, team
    ),
    jumpers AS (
      SELECT season, team, jumper_espn_id, jumper_name,
             count(*)::int AS jumps,
             count(*) FILTER (WHERE won_tip)::int AS jumps_won,
             row_number() OVER (PARTITION BY season, team
                                ORDER BY count(*) DESC, max(game_date) DESC, jumper_espn_id) AS rn
        FROM public.nba_first_basket_games
       WHERE jumper_espn_id IS NOT NULL
       GROUP BY season, team, jumper_espn_id, jumper_name
    )
    SELECT agg.*,
           j.jumper_espn_id, j.jumper_name,
           COALESCE(j.jumps, 0) AS jumper_jumps,
           COALESCE(j.jumps_won, 0) AS jumper_jumps_won
      FROM agg
      LEFT JOIN jumpers j ON j.season = agg.season AND j.team = agg.team AND j.rn = 1
  $view$;
  EXECUTE $c$COMMENT ON VIEW public.v_nba_first_basket_team_season IS 'nba_first_basket v1'$c$;

  -- One row per season and player, under his most recent team. The first-shot
  -- and first-basket counts are over STARTS only, so the board's "per start"
  -- rates cannot pass 100% (review L2, 2026-11-08; 0 of 264 bench first shots).
  -- A traded player's games for his old team are included (the legend says so).
  EXECUTE $view$
    CREATE OR REPLACE VIEW public.v_nba_first_basket_player_season
    WITH (security_invoker = on) AS
    SELECT season, espn_id,
           (array_agg(name ORDER BY game_date DESC, game_id DESC))[1] AS name,
           (array_agg(team ORDER BY game_date DESC, game_id DESC))[1] AS team,
           count(*)::int AS games,
           count(*) FILTER (WHERE starter)::int AS starts,
           count(*) FILTER (WHERE first_fga AND starter)::int AS first_fga,
           count(*) FILTER (WHERE first_fga_made AND starter)::int AS first_fga_made,
           count(*) FILTER (WHERE game_first_score AND starter)::int AS game_first_scores,
           count(*) FILTER (WHERE team_first_score)::int AS team_first_scores,
           count(*) FILTER (WHERE jumped)::int AS jumps,
           count(*) FILTER (WHERE jump_won)::int AS jumps_won,
           max(game_date) AS last_game_date
      FROM public.nba_first_basket_players
     GROUP BY season, espn_id
  $view$;
  EXECUTE $c$COMMENT ON VIEW public.v_nba_first_basket_player_season IS 'nba_first_basket v1'$c$;

  REVOKE ALL ON public.v_nba_first_basket_team_season FROM anon, authenticated;
  REVOKE ALL ON public.v_nba_first_basket_player_season FROM anon, authenticated;
  GRANT SELECT ON public.v_nba_first_basket_team_season TO anon, authenticated;
  GRANT SELECT ON public.v_nba_first_basket_player_season TO anon, authenticated;
END $$;
