-- Every NHL shot attempt since 2018-19: one row per shot on goal, missed shot,
-- blocked shot and goal, from the league's play-by-play feed.
--
-- WHY. The NHL models have no shot-quality input. The per-game logs
-- (add_nhl_game_logs.sql) count shots but say nothing about where they came
-- from, so a team that takes 35 shots from the point and one that takes 25 from
-- the slot look alike. Expected goals (xG) needs every attempt with its
-- location, type, strength and game state: these are those attempts.
--
-- SOURCE. `api-web.nhle.com/v1/gamecenter/<nhl_game_id>/play-by-play`, one call
-- per game. Free, no key, no credits. Written by data/ingestors/nhl_shot_events.py
-- in the same run that fetches it, `source = 'nhl_api_pbp'`, and a re-run
-- imports nothing already stored (ON CONFLICT DO NOTHING on the key).
--
-- KEYS. (nhl_game_id, event_id): the league's game id and the feed's own event
-- id, unique within a game. `game_id` is ours (`NHL_<date>_<away>_<home>`),
-- copied from nhl_team_game_log, and joins to `games`.
--
-- READING IT.
--   * situation_code is the feed's four digits: away goalie in net, away
--     skaters, home skaters, home goalie in net ("1451" = home power play,
--     "0651" = away net empty, "1010"/"0101" = a penalty shot or shootout
--     attempt). The other strength columns decode it from the SHOOTER's side.
--   * x, y are the feed's coordinates. For a BLOCKED shot they are where it was
--     blocked, and its zone_code is the BLOCKING team's zone. x_norm, y_norm are
--     rotated so the net the shooting team attacks is at (+89, 0).
--   * period_type 'SO' rows are shootout attempts: stored, never counted as
--     shots (nhl_team_game_log.shots_for excludes them) and never modelled.
--   * xg is filled afterwards by data/nhl_xg.py, on unblocked attempts only,
--     with the version that produced it in xg_model_version.
--
-- Internal research data: RLS on, privileges revoked, no read policy.
-- Applied ONCE, by hand. Not in data/view_migrations.ACTIVE_MIGRATIONS and not
-- in any code path that runs on a write.
DO $$
BEGIN
  IF to_regclass('public.nhl_shot_events') IS NULL THEN
    CREATE TABLE public.nhl_shot_events (
      nhl_game_id            BIGINT  NOT NULL,
      event_id               INTEGER NOT NULL,
      game_id                TEXT    NOT NULL,
      season                 INTEGER NOT NULL,   -- ENDING year
      game_type              INTEGER NOT NULL,   -- 2 regular season, 3 playoffs
      game_date              TEXT    NOT NULL,
      sort_order             INTEGER,
      period                 INTEGER NOT NULL,
      period_type            TEXT    NOT NULL,   -- REG / OT / SO
      period_seconds         INTEGER,            -- elapsed in the period
      game_seconds           INTEGER,            -- (period - 1) * 1200 + period_seconds; NULL in a shootout
      event_type             TEXT    NOT NULL,   -- shot-on-goal / missed-shot / blocked-shot / goal
      shot_type              TEXT,
      reason                 TEXT,               -- a miss's or a block's reason, as given
      x                      INTEGER,
      y                      INTEGER,
      zone_code              TEXT,               -- as given (O / N / D)
      home_defending_side    TEXT,               -- the feed's homeTeamDefendingSide; NULL in 2018-19
      attacking_net_x        INTEGER,            -- +89 or -89: the net the shooting team attacks
      side_source            TEXT,               -- derived / feed / adjacent / shot
      x_norm                 INTEGER,
      y_norm                 INTEGER,
      situation_code         TEXT,
      away_goalie_in_net     INTEGER,
      away_skaters           INTEGER,
      home_skaters           INTEGER,
      home_goalie_in_net     INTEGER,
      shooting_skaters       INTEGER,
      defending_skaters      INTEGER,
      empty_net              INTEGER,            -- 1 = the defending team's net is empty
      shooting_goalie_pulled INTEGER,            -- 1 = the shooting team's own goalie is out
      strength               TEXT,               -- EV / PP / SH / PS (penalty shot) / SO
      strength_state         TEXT,               -- skaters, shooter first: 5v4, 6v5, 3v3
      shooting_team          TEXT    NOT NULL,
      is_home                INTEGER NOT NULL,   -- 1 = the shooting team is at home
      event_owner_team       TEXT,               -- the feed's eventOwnerTeamId, as an abbrev
      shooter_id             BIGINT,
      goalie_id              BIGINT,             -- goalieInNetId; NULL on an empty net and on blocks
      blocker_id             BIGINT,
      home_score_before      INTEGER,
      away_score_before      INTEGER,
      prev_event_type        TEXT,               -- the event just before, same period
      prev_team              TEXT,               -- its team (a shot's is the SHOOTER's)
      prev_zone_code         TEXT,
      prev_x                 INTEGER,
      prev_y                 INTEGER,
      prev_seconds_since     INTEGER,
      xg                     DOUBLE PRECISION,
      xg_model_version       TEXT,
      source                 TEXT        NOT NULL,
      fetched_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (nhl_game_id, event_id)
    );
    CREATE INDEX idx_nhl_shot_events_season_date
      ON public.nhl_shot_events (season, game_date);
    CREATE INDEX idx_nhl_shot_events_source ON public.nhl_shot_events (source);
    ALTER TABLE public.nhl_shot_events ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_shot_events FROM anon, authenticated;
  END IF;
END $$;
