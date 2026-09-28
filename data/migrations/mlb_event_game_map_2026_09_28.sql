-- mlb_event_game_map_2026_09_28 -- NOT APPLIED. NOT IN
-- data/view_migrations.ACTIVE_MIGRATIONS. Needs Matt's go-ahead before either.
--
-- WHY. Review of PR #832 (H1): matching a sportsbook event to a doubleheader
-- game by nearest start time can swap or collapse the two games when a book
-- moves a start -- game 1 delayed 91+ minutes sits nearer game 2's effective
-- start; game 2 listed at MLB's placeholder (game 1 + 5 min) sits nearer game
-- 1. data/mlb_game_id.MlbEventBatch assigns a doubleheader's events together
-- (start order) or refuses an ambiguous lone event, and RECORDS each
-- assignment here so an event never re-maps, across passes and restarts.
--
-- Until this is applied the map lives in process memory only
-- (_EventMap._db degrades on the missing table, logs once per 15 min, and
-- retries). Single games are never written here -- only doubleheader
-- matchups (the Stats API lists 2+ games) or a day the schedule could not be
-- read.
--
-- One row per (source, event_id); UNIQUE (source, game_id) is the "one event
-- per game" rule: a second event resolving to a claimed game_id is refused
-- by the insert (ON CONFLICT DO NOTHING) and its rows are dropped at ERROR.
--
-- RLS on, no policy, anon/authenticated revoked by name (the worker writes as
-- the table owner via DATABASE_URL; the app never reads it).

DO $$
BEGIN
  IF to_regclass('public.mlb_event_game_map') IS NULL THEN
    CREATE TABLE public.mlb_event_game_map (
      source         TEXT NOT NULL,          -- 'odds_api' | 'action_network'
      event_id       TEXT NOT NULL,
      game_id        TEXT NOT NULL,
      game_date      TEXT NOT NULL,
      away_team      TEXT NOT NULL,
      home_team      TEXT NOT NULL,
      commence_time  TEXT,                   -- the event's start when assigned
      assigned_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (source, event_id),
      UNIQUE (source, game_id)
    );
    CREATE INDEX mlb_event_game_map_matchup
      ON public.mlb_event_game_map (source, game_date, away_team, home_team);
    ALTER TABLE public.mlb_event_game_map ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.mlb_event_game_map FROM PUBLIC, anon, authenticated;
  END IF;
END $$;
