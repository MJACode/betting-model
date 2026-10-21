-- Eggz's Discord picks. Separate from `picks`: those rows are the models'
-- record, and his posts must not enter #results or the published views.
--
-- capper_messages is the raw channel read. capper_picks is one leg of a
-- message. capper_ingest_cursor is the Discord snowflake the next poll
-- starts after, so a message is not read twice. A leg that cannot be
-- parsed or matched is status needs_review. It is not dropped.
--
-- Single DO block. data/view_migrations.py runs each file as one statement.
-- Once the tables exist and anon/authenticated hold none of the four
-- privileges, this returns before ALTER.

DO $mig$
BEGIN
  IF to_regclass('public.capper_messages') IS NOT NULL
     AND to_regclass('public.capper_picks') IS NOT NULL
     AND to_regclass('public.capper_ingest_cursor') IS NOT NULL
     AND NOT has_table_privilege('anon', 'public.capper_picks', 'SELECT')
     AND NOT has_table_privilege('authenticated', 'public.capper_picks', 'SELECT')
  THEN
    RAISE NOTICE 'capper picks already locked down - skipping';
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.capper_ingest_cursor (
    channel_id      TEXT PRIMARY KEY,
    newest_id       TEXT,
    oldest_id       TEXT,
    backfill_done   BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
  );

  CREATE TABLE IF NOT EXISTS public.capper_messages (
    message_id      TEXT PRIMARY KEY,
    channel_id      TEXT NOT NULL,
    author_id       TEXT NOT NULL,
    author_username TEXT,
    author_display  TEXT,
    body            TEXT NOT NULL,
    posted_at       TIMESTAMPTZ NOT NULL,
    edited          BOOLEAN NOT NULL DEFAULT FALSE,
    edited_at       TIMESTAMPTZ,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    parse_status    TEXT NOT NULL,
    parse_note      TEXT
  );

  CREATE TABLE IF NOT EXISTS public.capper_picks (
    id              BIGSERIAL PRIMARY KEY,
    message_id      TEXT NOT NULL REFERENCES public.capper_messages(message_id),
    line_no         INTEGER NOT NULL,
    status          TEXT NOT NULL,
    review_reason   TEXT,
    sport           TEXT,
    game_id         TEXT,
    game_date       TEXT,
    home_team       TEXT,
    away_team       TEXT,
    commence_time   TEXT,
    market          TEXT,
    side            TEXT,
    line            NUMERIC,
    price           NUMERIC,
    stake_units     NUMERIC NOT NULL DEFAULT 1,
    player_name     TEXT,
    prop_stat       TEXT,
    prop_market     TEXT,
    posted_at       TIMESTAMPTZ NOT NULL,
    result          TEXT,
    units           NUMERIC,
    risked          NUMERIC,
    clv_pct         NUMERIC,
    clv_beat_close  BOOLEAN,
    closing_price   NUMERIC,
    graded_at       TIMESTAMPTZ,
    UNIQUE (message_id, line_no)
  );

  CREATE INDEX IF NOT EXISTS idx_capper_picks_status
    ON public.capper_picks (status, game_date);

  REVOKE ALL ON public.capper_ingest_cursor FROM anon, authenticated;
  REVOKE ALL ON public.capper_messages FROM anon, authenticated;
  REVOKE ALL ON public.capper_picks FROM anon, authenticated;
  ALTER TABLE public.capper_ingest_cursor ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.capper_messages ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.capper_picks ENABLE ROW LEVEL SECURITY;
END $mig$;
