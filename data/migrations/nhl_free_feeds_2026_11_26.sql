-- NHL shift charts, Daily Faceoff line snapshots, officials and
-- scratches, and NHL EDGE season-to-date snapshots.
--
-- WHY. These four feeds are free and were not stored. Nothing that writes
-- a pick reads them. Personal, non-commercial use.
--
-- Shifts: api.nhle.com/stats/rest/en/shiftcharts, one row per shift.
-- shift_id is the feed's id. Shared ice (nhl_shift_linemates) is derived
-- from overlapping shifts. The chart has no strength, so it is not a
-- power-play unit.
-- Officials and scratches: api-web.nhle.com/v1/gamecenter/{id}/right-rail.
-- The scratch's team is the log's home or away, not a field on the feed.
-- Lines: Daily Faceoff, one snapshot per run. The key includes
-- snapshot_at so a later run inserts and does not update.
-- EDGE: one row per skater, goalie and team per snapshot_date. The
-- payload is the detail document. A retry of the same date updates that
-- night's row. There is no historical backfill.
--
-- Written by data/ingestors/nhl_shifts.py, nhl_right_rail.py,
-- dailyfaceoff_lines.py and nhl_edge.py.
-- Internal research data: RLS on, privileges revoked, no read policy.
-- One statement. The worker applies it from ACTIVE_MIGRATIONS.
DO $$
BEGIN
  IF to_regclass('public.nhl_shifts') IS NULL THEN
    CREATE TABLE public.nhl_shifts (
      shift_id           BIGINT PRIMARY KEY,
      nhl_game_id        BIGINT NOT NULL,
      season_end         INTEGER NOT NULL,
      game_type          INTEGER NOT NULL,
      game_date          TEXT,
      our_game_id        TEXT,
      player_id          BIGINT NOT NULL,
      player_name        TEXT,
      team_abbr          TEXT,
      period             INTEGER,
      shift_number       INTEGER,
      start_seconds      INTEGER,
      end_seconds        INTEGER,
      duration_seconds   INTEGER,
      start_time         TEXT,
      end_time           TEXT,
      duration           TEXT,
      type_code          INTEGER,
      detail_code        INTEGER,
      event_number       INTEGER,
      source             TEXT NOT NULL,
      fetched_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX idx_nhl_shifts_game ON public.nhl_shifts (nhl_game_id);
    CREATE INDEX idx_nhl_shifts_player ON public.nhl_shifts (player_id, game_date);
    CREATE INDEX idx_nhl_shifts_date ON public.nhl_shifts (game_date);
    ALTER TABLE public.nhl_shifts ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_shifts FROM anon, authenticated;
    EXECUTE 'COMMENT ON TABLE public.nhl_shifts IS ''NHL shift chart. Personal non-commercial copy of the public API. Not a pick input.''';
  END IF;

  IF to_regclass('public.nhl_shift_linemates') IS NULL THEN
    CREATE TABLE public.nhl_shift_linemates (
      nhl_game_id        BIGINT NOT NULL,
      team_abbr          TEXT NOT NULL,
      player_id_lo       BIGINT NOT NULL,
      player_id_hi       BIGINT NOT NULL,
      player_name_lo     TEXT,
      player_name_hi     TEXT,
      shared_seconds     INTEGER NOT NULL,
      season_end         INTEGER,
      game_date          TEXT,
      our_game_id        TEXT,
      source             TEXT NOT NULL,
      fetched_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (nhl_game_id, player_id_lo, player_id_hi)
    );
    CREATE INDEX idx_nhl_shift_linemates_date ON public.nhl_shift_linemates (game_date);
    ALTER TABLE public.nhl_shift_linemates ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_shift_linemates FROM anon, authenticated;
    EXECUTE 'COMMENT ON TABLE public.nhl_shift_linemates IS ''Shared ice derived from nhl_shifts. Not a power-play unit. Not a pick input.''';
  END IF;

  IF to_regclass('public.nhl_game_officials') IS NULL THEN
    CREATE TABLE public.nhl_game_officials (
      nhl_game_id        BIGINT NOT NULL,
      role               TEXT NOT NULL,
      slot               INTEGER NOT NULL,
      full_name          TEXT NOT NULL,
      sweater_number     INTEGER,
      season_end         INTEGER NOT NULL,
      game_type          INTEGER NOT NULL,
      game_date          TEXT,
      our_game_id        TEXT,
      home_abbr          TEXT,
      away_abbr          TEXT,
      source             TEXT NOT NULL,
      fetched_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (nhl_game_id, role, slot)
    );
    CREATE INDEX idx_nhl_game_officials_date ON public.nhl_game_officials (game_date);
    ALTER TABLE public.nhl_game_officials ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_game_officials FROM anon, authenticated;
    EXECUTE 'COMMENT ON TABLE public.nhl_game_officials IS ''Referees and linesmen from the NHL right rail. Not a pick input.''';
  END IF;

  IF to_regclass('public.nhl_healthy_scratches') IS NULL THEN
    CREATE TABLE public.nhl_healthy_scratches (
      nhl_game_id        BIGINT NOT NULL,
      player_id          BIGINT NOT NULL,
      team_abbr          TEXT,
      side               TEXT NOT NULL,
      player_name        TEXT,
      season_end         INTEGER NOT NULL,
      game_type          INTEGER NOT NULL,
      game_date          TEXT,
      our_game_id        TEXT,
      source             TEXT NOT NULL,
      fetched_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (nhl_game_id, player_id)
    );
    CREATE INDEX idx_nhl_healthy_scratches_date ON public.nhl_healthy_scratches (game_date);
    ALTER TABLE public.nhl_healthy_scratches ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_healthy_scratches FROM anon, authenticated;
    EXECUTE 'COMMENT ON TABLE public.nhl_healthy_scratches IS ''Healthy scratches from the NHL right rail. Not a pick input.''';
  END IF;

  IF to_regclass('public.dailyfaceoff_line_snapshots') IS NULL THEN
    CREATE TABLE public.dailyfaceoff_line_snapshots (
      snapshot_at        TEXT NOT NULL,
      game_date          TEXT NOT NULL,
      team_abbr          TEXT NOT NULL,
      team_slug          TEXT,
      source_name        TEXT,
      source_updated_at  TEXT,
      category           TEXT NOT NULL,
      group_id           TEXT NOT NULL,
      group_name         TEXT,
      player_id          BIGINT NOT NULL,
      player_name        TEXT,
      position_id        TEXT,
      position_name      TEXT,
      jersey_number      INTEGER,
      source             TEXT NOT NULL,
      fetched_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (snapshot_at, team_abbr, category, group_id, player_id)
    );
    CREATE INDEX idx_dailyfaceoff_lines_date ON public.dailyfaceoff_line_snapshots (game_date, team_abbr);
    ALTER TABLE public.dailyfaceoff_line_snapshots ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.dailyfaceoff_line_snapshots FROM anon, authenticated;
    EXECUTE 'COMMENT ON TABLE public.dailyfaceoff_line_snapshots IS ''Daily Faceoff line combinations and special-teams units, one snapshot per run. Personal non-commercial. Not a pick input.''';
  END IF;

  IF to_regclass('public.nhl_edge_skater_snapshots') IS NULL THEN
    CREATE TABLE public.nhl_edge_skater_snapshots (
      snapshot_date            TEXT NOT NULL,
      season_id                INTEGER NOT NULL,
      game_type                INTEGER NOT NULL,
      player_id                BIGINT NOT NULL,
      team_abbr                TEXT,
      player_name              TEXT,
      position                 TEXT,
      games_played             INTEGER,
      top_shot_mph             DOUBLE PRECISION,
      top_shot_percentile      DOUBLE PRECISION,
      max_skate_mph            DOUBLE PRECISION,
      max_skate_percentile     DOUBLE PRECISION,
      bursts_over_20           DOUBLE PRECISION,
      distance_miles           DOUBLE PRECISION,
      oz_pct                   DOUBLE PRECISION,
      nz_pct                   DOUBLE PRECISION,
      dz_pct                   DOUBLE PRECISION,
      high_danger_shooting_pct DOUBLE PRECISION,
      payload                  JSONB NOT NULL,
      source                   TEXT NOT NULL,
      fetched_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (snapshot_date, season_id, game_type, player_id)
    );
    CREATE INDEX idx_nhl_edge_skater_date ON public.nhl_edge_skater_snapshots (snapshot_date);
    ALTER TABLE public.nhl_edge_skater_snapshots ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_edge_skater_snapshots FROM anon, authenticated;
    EXECUTE 'COMMENT ON TABLE public.nhl_edge_skater_snapshots IS ''NHL EDGE skater season-to-date snapshot. payload is the detail document. Not a pick input.''';
  END IF;

  IF to_regclass('public.nhl_edge_goalie_snapshots') IS NULL THEN
    CREATE TABLE public.nhl_edge_goalie_snapshots (
      snapshot_date          TEXT NOT NULL,
      season_id              INTEGER NOT NULL,
      game_type              INTEGER NOT NULL,
      player_id              BIGINT NOT NULL,
      team_abbr              TEXT,
      player_name            TEXT,
      games_played           INTEGER,
      save_pct               DOUBLE PRECISION,
      high_danger_save_pct   DOUBLE PRECISION,
      high_danger_saves      DOUBLE PRECISION,
      payload                JSONB NOT NULL,
      source                 TEXT NOT NULL,
      fetched_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (snapshot_date, season_id, game_type, player_id)
    );
    CREATE INDEX idx_nhl_edge_goalie_date ON public.nhl_edge_goalie_snapshots (snapshot_date);
    ALTER TABLE public.nhl_edge_goalie_snapshots ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_edge_goalie_snapshots FROM anon, authenticated;
    EXECUTE 'COMMENT ON TABLE public.nhl_edge_goalie_snapshots IS ''NHL EDGE goalie season-to-date snapshot, including save percentage by danger band. Not a pick input.''';
  END IF;

  IF to_regclass('public.nhl_edge_team_snapshots') IS NULL THEN
    CREATE TABLE public.nhl_edge_team_snapshots (
      snapshot_date            TEXT NOT NULL,
      season_id                INTEGER NOT NULL,
      game_type                INTEGER NOT NULL,
      team_id                  INTEGER NOT NULL,
      team_abbr                TEXT,
      top_shot_mph             DOUBLE PRECISION,
      shots_over_90            DOUBLE PRECISION,
      max_skate_mph            DOUBLE PRECISION,
      bursts_over_20           DOUBLE PRECISION,
      bursts_over_22           DOUBLE PRECISION,
      distance_miles           DOUBLE PRECISION,
      oz_pct                   DOUBLE PRECISION,
      nz_pct                   DOUBLE PRECISION,
      dz_pct                   DOUBLE PRECISION,
      high_danger_shooting_pct DOUBLE PRECISION,
      payload                  JSONB NOT NULL,
      source                   TEXT NOT NULL,
      fetched_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (snapshot_date, season_id, game_type, team_id)
    );
    CREATE INDEX idx_nhl_edge_team_date ON public.nhl_edge_team_snapshots (snapshot_date);
    ALTER TABLE public.nhl_edge_team_snapshots ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_edge_team_snapshots FROM anon, authenticated;
    EXECUTE 'COMMENT ON TABLE public.nhl_edge_team_snapshots IS ''NHL EDGE team season-to-date snapshot. Not a pick input.''';
  END IF;
END $$;
