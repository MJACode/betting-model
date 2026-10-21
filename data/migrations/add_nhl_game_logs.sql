-- Per-game NHL logs: one row per TEAM, per GOALIE and per SKATER per game.
--
-- WHY. Until 2026-09-20 the NHL models read one row per goalie per SEASON,
-- dated `YYYY-10-01` and holding that season's FINAL line (Swayman's 2024-25
-- row read .8921 / 3.1145 on opening day — his number in April), a "GSAA"
-- column that was a copy of GAA, and team shot-share / power-play / penalty-
-- kill rates carried forward unchanged from the season before.
-- `nhl_skater_stats` has never held a row. An honest as-of-date feature needs
-- the games it is summed from, so these are those games.
--
-- SOURCE. The NHL's free stats API, `api.nhle.com/stats/rest/en/{team|goalie|
-- skater}/<report>?isGame=true`. No key, no credits. Team and goalie reports
-- return a whole season in one call (2,624 / 2,764 rows for 2024-25); skater
-- reports are capped at 10,000 rows a call, so they are pulled a week at a
-- time. Written by data/ingestors/nhl_game_logs.py, keyed on `source` so a
-- re-run imports nothing already stored.
--
-- KEYS. `nhl_game_id` is the league's own id (2024020001). `game_id` is ours
-- (`NHL_<date>_<away>_<home>`) and joins to `games`. Times on ice are SECONDS.
--
-- Internal research data: RLS on, privileges revoked, no read policy.
DO $$
BEGIN
  IF to_regclass('public.nhl_team_game_log') IS NULL THEN
    CREATE TABLE public.nhl_team_game_log (
      nhl_game_id           BIGINT  NOT NULL,
      team                  TEXT    NOT NULL,
      game_id               TEXT    NOT NULL,
      season                INTEGER NOT NULL,   -- ENDING year
      game_type             INTEGER NOT NULL,   -- 2 regular season, 3 playoffs
      game_date             TEXT    NOT NULL,
      opponent              TEXT    NOT NULL,
      is_home               INTEGER NOT NULL,
      goals_for             INTEGER,
      goals_against         INTEGER,
      shots_for             INTEGER,
      shots_against         INTEGER,
      shot_attempts_for     INTEGER,            -- all strengths; NULL before 2022-23
      shot_attempts_against INTEGER,            -- the opponent's, same game
      sat_for_5v5           INTEGER,            -- 5v5 shot attempts for / against:
      sat_against_5v5       INTEGER,            --   every season, so Corsi uses these
      sat_pct_5v5           NUMERIC,            -- the league's own 5v5 shot share
      pp_opportunities      INTEGER,
      pp_goals              INTEGER,
      times_shorthanded     INTEGER,
      pp_goals_against      INTEGER,
      faceoff_win_pct       NUMERIC,
      hits                  INTEGER,
      blocked_shots         INTEGER,
      giveaways             INTEGER,
      takeaways             INTEGER,
      source                TEXT        NOT NULL,
      fetched_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (nhl_game_id, team)
    );
    CREATE INDEX idx_nhl_team_game_log_team_date
      ON public.nhl_team_game_log (team, season, game_date);
    CREATE INDEX idx_nhl_team_game_log_source ON public.nhl_team_game_log (source);
    ALTER TABLE public.nhl_team_game_log ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_team_game_log FROM anon, authenticated;
  END IF;

  -- The table was first created without the 5v5 counts; `totalShotAttempts`
  -- turned out to be NULL before 2022-23. Guarded on the COLUMN, so this ALTER
  -- runs once and never again.
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema = 'public' AND table_name = 'nhl_team_game_log'
                   AND column_name = 'sat_for_5v5') THEN
    ALTER TABLE public.nhl_team_game_log
      ADD COLUMN sat_for_5v5 INTEGER, ADD COLUMN sat_against_5v5 INTEGER;
  END IF;

  IF to_regclass('public.nhl_goalie_game_log') IS NULL THEN
    CREATE TABLE public.nhl_goalie_game_log (
      nhl_game_id   BIGINT  NOT NULL,
      player_id     BIGINT  NOT NULL,
      player_name   TEXT    NOT NULL,
      game_id       TEXT    NOT NULL,
      season        INTEGER NOT NULL,
      game_type     INTEGER NOT NULL,
      game_date     TEXT    NOT NULL,
      team          TEXT    NOT NULL,
      opponent      TEXT    NOT NULL,
      is_home       INTEGER NOT NULL,
      started       INTEGER NOT NULL,           -- 1 = he started the game
      decision      TEXT,                       -- W / L / OTL / NULL
      toi_seconds   INTEGER,
      shots_against INTEGER,
      saves         INTEGER,
      goals_against INTEGER,
      source        TEXT        NOT NULL,
      fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (nhl_game_id, player_id)
    );
    CREATE INDEX idx_nhl_goalie_game_log_player_date
      ON public.nhl_goalie_game_log (player_id, game_date);
    CREATE INDEX idx_nhl_goalie_game_log_team_date
      ON public.nhl_goalie_game_log (team, season, game_date);
    CREATE INDEX idx_nhl_goalie_game_log_source ON public.nhl_goalie_game_log (source);
    ALTER TABLE public.nhl_goalie_game_log ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_goalie_game_log FROM anon, authenticated;
  END IF;

  IF to_regclass('public.nhl_skater_game_log') IS NULL THEN
    CREATE TABLE public.nhl_skater_game_log (
      nhl_game_id    BIGINT  NOT NULL,
      player_id      BIGINT  NOT NULL,
      player_name    TEXT    NOT NULL,
      position       TEXT,
      game_id        TEXT    NOT NULL,
      season         INTEGER NOT NULL,
      game_type      INTEGER NOT NULL,
      game_date      TEXT    NOT NULL,
      team           TEXT    NOT NULL,
      opponent       TEXT    NOT NULL,
      is_home        INTEGER NOT NULL,
      goals          INTEGER,
      assists        INTEGER,
      points         INTEGER,
      shots          INTEGER,                   -- shots on goal
      shot_attempts  INTEGER,
      missed_shots   INTEGER,
      pp_goals       INTEGER,
      pp_points      INTEGER,
      plus_minus     INTEGER,
      pim            INTEGER,
      hits           INTEGER,
      blocked_shots  INTEGER,
      toi_seconds    INTEGER,
      ev_toi_seconds INTEGER,
      pp_toi_seconds INTEGER,
      sh_toi_seconds INTEGER,
      shifts         INTEGER,
      source         TEXT        NOT NULL,
      fetched_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (nhl_game_id, player_id)
    );
    CREATE INDEX idx_nhl_skater_game_log_player_date
      ON public.nhl_skater_game_log (player_id, game_date);
    CREATE INDEX idx_nhl_skater_game_log_team_date
      ON public.nhl_skater_game_log (team, season, game_date);
    CREATE INDEX idx_nhl_skater_game_log_source ON public.nhl_skater_game_log (source);
    ALTER TABLE public.nhl_skater_game_log ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_skater_game_log FROM anon, authenticated;
  END IF;
END $$;
