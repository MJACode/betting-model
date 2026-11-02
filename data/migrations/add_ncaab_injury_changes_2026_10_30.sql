-- NCAAB pre-tip injury changes. Tags only: not a model feature, and not a
-- pick. Written by data/ingestors/ncaab_injury_feed.py.
--
-- ncaab_injury_changes is append-only and change-only. A row is written when
-- a player's status, injury, note or return text changes, and when a player
-- who was listed leaves a non-empty report (status 'cleared'). A poll that
-- returns nobody does not clear anyone. received_at is when this server
-- stored the poll; neither public page carries a status-change time.
--
-- ncaab_injury_open is the previous report, one row per listed player, so
-- the next poll diffs against a state table instead of walking the log.
-- ncaab_injury_polls is the cadence and the 403/429 backoff.
-- ncaab_injury_misses is the latest unresolved team or player name. A miss
-- is logged and never matched by guessing.
--
-- The app's chip still reads injury_status_current (sport NCAAB), which this
-- job upserts from the open absences. These four tables are worker-only:
-- RLS on, no policy, anon and authenticated revoked.
--
-- One statement. Returns on a catalog read once every table exists, RLS is
-- on, and anon cannot SELECT the change log, so a later pass takes no lock
-- and fires no DDL.
DO $$
BEGIN
  IF to_regclass('public.ncaab_injury_changes') IS NOT NULL
     AND to_regclass('public.ncaab_injury_open') IS NOT NULL
     AND to_regclass('public.ncaab_injury_polls') IS NOT NULL
     AND to_regclass('public.ncaab_injury_misses') IS NOT NULL
  THEN
    IF (SELECT c.relrowsecurity FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relname = 'ncaab_injury_changes')
       AND NOT has_table_privilege('anon', 'public.ncaab_injury_changes', 'SELECT')
       AND NOT has_table_privilege('authenticated', 'public.ncaab_injury_changes', 'SELECT')
    THEN
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.ncaab_injury_changes (
    change_id        BIGSERIAL PRIMARY KEY,
    source           TEXT NOT NULL,
    received_at      TIMESTAMPTZ NOT NULL,
    team_raw         TEXT NOT NULL,
    player_raw       TEXT NOT NULL,
    espn_team_id     INTEGER,
    team             TEXT,
    player_key       TEXT,
    player_id        TEXT,
    -- Out, Doubtful, Questionable, Day-To-Day, Probable, the vendor's own
    -- word when it is not one of those, or 'cleared' when a listed player
    -- leaves a non-empty report.
    status           TEXT NOT NULL,
    injury_type      TEXT,
    note             TEXT,
    return_date      TEXT,
    vendor_player_id TEXT,
    match_status     TEXT NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_ncaab_injury_changes_player_ts
    ON public.ncaab_injury_changes (espn_team_id, player_key, received_at DESC);

  CREATE TABLE IF NOT EXISTS public.ncaab_injury_open (
    source           TEXT NOT NULL,
    team_raw         TEXT NOT NULL,
    player_raw       TEXT NOT NULL,
    espn_team_id     INTEGER,
    team             TEXT,
    player_key       TEXT,
    player_id        TEXT,
    status           TEXT NOT NULL,
    injury_type      TEXT,
    note             TEXT,
    return_date      TEXT,
    vendor_player_id TEXT,
    match_status     TEXT NOT NULL,
    received_at      TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (source, team_raw, player_raw)
  );

  CREATE TABLE IF NOT EXISTS public.ncaab_injury_polls (
    source                TEXT PRIMARY KEY,
    last_attempt_at       TIMESTAMPTZ,
    last_success_at       TIMESTAMPTZ,
    last_status_code      INTEGER,
    last_row_count        INTEGER,
    backoff_until         TIMESTAMPTZ,
    consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    last_error            TEXT
  );

  CREATE TABLE IF NOT EXISTS public.ncaab_injury_misses (
    source      TEXT NOT NULL,
    team_raw    TEXT NOT NULL,
    player_raw  TEXT NOT NULL,
    reason      TEXT NOT NULL,
    last_seen   TIMESTAMPTZ NOT NULL,
    detail      TEXT,
    PRIMARY KEY (source, team_raw, player_raw, reason)
  );

  ALTER TABLE public.ncaab_injury_changes ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.ncaab_injury_open ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.ncaab_injury_polls ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.ncaab_injury_misses ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.ncaab_injury_changes FROM anon, authenticated;
  REVOKE ALL ON public.ncaab_injury_open FROM anon, authenticated;
  REVOKE ALL ON public.ncaab_injury_polls FROM anon, authenticated;
  REVOKE ALL ON public.ncaab_injury_misses FROM anon, authenticated;
END
$$;
