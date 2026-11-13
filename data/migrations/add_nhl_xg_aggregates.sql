-- Expected goals per team-game and per goalie-game, summed from nhl_shot_events.
--
-- WHY. Shot-quality inputs for the NHL models: how much a team created and
-- allowed (xGF / xGA) game by game, and how many goals a goalie saved beyond
-- what the shots he faced were worth. Both are sums over nhl_shot_events.xg,
-- kept as tables so an as-of feature is a read, not a 1.2M-row aggregation.
--
-- SOURCE. Built by data/nhl_xg_aggregates.py from nhl_shot_events (`source` =
-- 'nhl_shot_events'), stamped with the xg_model_version the sums came from. A
-- rebuild after a new xG model overwrites its rows (upsert on the key).
--
-- DEFINITIONS (shootout attempts are never counted):
--   * xgf / xga: all situations, every unblocked attempt (shot on goal, miss,
--     goal), empty-net and penalty shots included.
--   * *_5v5: situation_code '1551' only -- five skaters and a goalie a side.
--   * ff / fa: unblocked attempts ("Fenwick") for / against.
--   * goalie rows: every unblocked attempt with HIM in net (goalieInNetId), so
--     an empty-net goal is never his. gsax = xg_faced - goals_allowed.
--   * xg_unscored*: unblocked attempts with no xG (no coordinates), counted so
--     a gap in a sum is visible rather than silent.
--
-- Internal research data: RLS on, privileges revoked, no read policy.
-- Applied ONCE, by hand; not in any code path that runs on a write.
DO $$
BEGIN
  IF to_regclass('public.nhl_team_game_xg') IS NULL THEN
    CREATE TABLE public.nhl_team_game_xg (
      nhl_game_id          BIGINT  NOT NULL,
      team                 TEXT    NOT NULL,
      game_id              TEXT    NOT NULL,
      season               INTEGER NOT NULL,   -- ENDING year
      game_type            INTEGER NOT NULL,   -- 2 regular season, 3 playoffs
      game_date            TEXT    NOT NULL,
      opponent             TEXT    NOT NULL,
      is_home              INTEGER NOT NULL,
      xgf                  DOUBLE PRECISION NOT NULL,
      xga                  DOUBLE PRECISION NOT NULL,
      xgf_5v5              DOUBLE PRECISION NOT NULL,
      xga_5v5              DOUBLE PRECISION NOT NULL,
      ff                   INTEGER NOT NULL,
      fa                   INTEGER NOT NULL,
      ff_5v5               INTEGER NOT NULL,
      fa_5v5               INTEGER NOT NULL,
      gf                   INTEGER NOT NULL,
      ga                   INTEGER NOT NULL,
      gf_5v5               INTEGER NOT NULL,
      ga_5v5               INTEGER NOT NULL,
      xg_unscored_for      INTEGER NOT NULL,
      xg_unscored_against  INTEGER NOT NULL,
      xg_model_version     TEXT    NOT NULL,
      source               TEXT    NOT NULL,
      built_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (nhl_game_id, team)
    );
    CREATE INDEX idx_nhl_team_game_xg_team_date
      ON public.nhl_team_game_xg (team, season, game_date);
    CREATE INDEX idx_nhl_team_game_xg_source ON public.nhl_team_game_xg (source);
    ALTER TABLE public.nhl_team_game_xg ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_team_game_xg FROM anon, authenticated;
  END IF;

  IF to_regclass('public.nhl_goalie_game_xg') IS NULL THEN
    CREATE TABLE public.nhl_goalie_game_xg (
      nhl_game_id          BIGINT  NOT NULL,
      goalie_id            BIGINT  NOT NULL,
      game_id              TEXT    NOT NULL,
      season               INTEGER NOT NULL,
      game_type            INTEGER NOT NULL,
      game_date            TEXT    NOT NULL,
      team                 TEXT    NOT NULL,   -- the goalie's team
      opponent             TEXT    NOT NULL,
      is_home              INTEGER NOT NULL,
      started              INTEGER,            -- nhl_goalie_game_log.started; NULL if it has no row
      unblocked_faced      INTEGER NOT NULL,
      sog_faced            INTEGER NOT NULL,   -- shots on goal + goals
      goals_allowed        INTEGER NOT NULL,
      xg_faced             DOUBLE PRECISION NOT NULL,
      gsax                 DOUBLE PRECISION NOT NULL,
      unblocked_faced_5v5  INTEGER NOT NULL,
      goals_allowed_5v5    INTEGER NOT NULL,
      xg_faced_5v5         DOUBLE PRECISION NOT NULL,
      gsax_5v5             DOUBLE PRECISION NOT NULL,
      xg_unscored          INTEGER NOT NULL,
      xg_model_version     TEXT    NOT NULL,
      source               TEXT    NOT NULL,
      built_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (nhl_game_id, goalie_id)
    );
    CREATE INDEX idx_nhl_goalie_game_xg_goalie_date
      ON public.nhl_goalie_game_xg (goalie_id, game_date);
    CREATE INDEX idx_nhl_goalie_game_xg_team_date
      ON public.nhl_goalie_game_xg (team, season, game_date);
    CREATE INDEX idx_nhl_goalie_game_xg_source ON public.nhl_goalie_game_xg (source);
    ALTER TABLE public.nhl_goalie_game_xg ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_goalie_game_xg FROM anon, authenticated;
  END IF;
END $$;
