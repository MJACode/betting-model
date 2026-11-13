-- DraftKings' own in-play board, read from mike's machine every few seconds
-- (data/ingestors/dk_live_board.py), and read by the in-play loops on the
-- worker (models/ncaab_live_dk.py) so a bet is decided on DraftKings' line and
-- DraftKings' own score in the same read, and posted within seconds.
--
-- Why (mike, 2026-11-12: "This is live betting ... This needs to be as close to
-- Real time as possible"): the loops decided on the odds provider's copy of
-- DraftKings (a median 32.5 s old when served, a different number from
-- DraftKings' board 28% of the time) and then waited 150-232 s for ESPN to
-- confirm the score. DraftKings' board shows the score a median 3.7 s after a
-- basket and moves its line with it (177 of 180 baskets, same read or later).
-- It answers a residential address only (the worker is refused), so the feed
-- runs on mike's machine and this table is the hand-off.
--
-- dk_live_reads  one row per game each time its score, its main spread or its
--                main total (number or price) changes: the read time a state
--                was FIRST seen, which is what a quote's stamp means in the
--                model (the provider's last_update). The clock is the clock at
--                that read. Home and away are OUR games row's sides.
-- dk_live_feed   one row per sport, written on every read: the last read and
--                whether it answered. A reader trusts dk_live_reads only while
--                this is seconds old; a line still standing at last_read_at
--                was seen on that read too.
--
-- anon and authenticated get nothing; the local DATABASE_URL writes, the
-- worker reads. One DO block: data/view_migrations.py runs each file as one
-- statement, on every pass. The early return answers "already applied" on the
-- property this migration establishes (both tables exist, RLS on, no
-- anon/authenticated privilege), read through to_regclass so a fresh database
-- never casts a missing relation.

DO $mig$
DECLARE
  t text;
  done boolean := true;
BEGIN
  FOREACH t IN ARRAY ARRAY['public.dk_live_reads', 'public.dk_live_feed'] LOOP
    IF to_regclass(t) IS NULL
       OR NOT EXISTS (SELECT 1 FROM pg_class WHERE oid = to_regclass(t) AND relrowsecurity)
       -- the oid form: a missing table is NULL here, never a "does not exist" error
       OR has_table_privilege('anon', to_regclass(t), 'SELECT')
       OR has_table_privilege('anon', to_regclass(t), 'INSERT')
       OR has_table_privilege('anon', to_regclass(t), 'UPDATE')
       OR has_table_privilege('anon', to_regclass(t), 'DELETE')
       OR has_table_privilege('authenticated', to_regclass(t), 'SELECT')
       OR has_table_privilege('authenticated', to_regclass(t), 'INSERT')
       OR has_table_privilege('authenticated', to_regclass(t), 'UPDATE')
       OR has_table_privilege('authenticated', to_regclass(t), 'DELETE')
    THEN
      done := false;
    END IF;
  END LOOP;
  IF done THEN
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.dk_live_reads (
    id             BIGSERIAL PRIMARY KEY,
    sport          TEXT NOT NULL,
    game_id        TEXT NOT NULL,
    read_at        TIMESTAMPTZ NOT NULL,
    dk_event_id    TEXT NOT NULL,
    flipped        BOOLEAN NOT NULL DEFAULT FALSE,
    period_label   TEXT,
    period         INTEGER,
    clock_s        DOUBLE PRECISION,
    clock_running  BOOLEAN,
    home_score     INTEGER,
    away_score     INTEGER,
    spread_home    DOUBLE PRECISION,
    spread_home_price DOUBLE PRECISION,
    spread_away_price DOUBLE PRECISION,
    total_line     DOUBLE PRECISION,
    over_price     DOUBLE PRECISION,
    under_price    DOUBLE PRECISION,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  CREATE UNIQUE INDEX IF NOT EXISTS uq_dk_live_reads_game_read
    ON public.dk_live_reads (game_id, read_at);
  CREATE INDEX IF NOT EXISTS dk_live_reads_sport_read_idx
    ON public.dk_live_reads (sport, read_at);

  CREATE TABLE IF NOT EXISTS public.dk_live_feed (
    sport          TEXT PRIMARY KEY,
    last_read_at   TIMESTAMPTZ NOT NULL,
    ok             BOOLEAN NOT NULL,
    live_events    INTEGER,
    matched        INTEGER,
    detail         TEXT
  );

  ALTER TABLE public.dk_live_reads ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.dk_live_feed ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.dk_live_reads FROM anon;
  REVOKE ALL ON public.dk_live_reads FROM authenticated;
  REVOKE ALL ON public.dk_live_feed FROM anon;
  REVOKE ALL ON public.dk_live_feed FROM authenticated;
END
$mig$;
