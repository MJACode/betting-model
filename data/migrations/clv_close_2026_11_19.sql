-- The final close of every pre-game bet (mike, 2026-11-19, issue #1470: "yes
-- I want it to be accurate please correct"). tracking/clv_close.py measures
-- it; these tables are what that measurement stands on.
--
--   clv_close_quotes        bookmaker quotes bought from the odds feed's
--                           history, for bets whose own stored rows were
--                           pruned before 2026-11-14. One row per quote at one
--                           snapshot; fetched_at is the feed's snapshot time.
--                           Kept apart from odds and player_prop_odds on
--                           purpose: those carry insert triggers, feed the
--                           models' features, and a history purchase there
--                           has rewritten kickoffs before (#1339).
--   clv_close_purchases     one row per paid call, with what it billed (the
--                           feed's own x-requests-last). kind 'history' is a
--                           purchase from the feed's history
--                           (scripts/clv_close_history.py); kind 'closing' is
--                           the live pull a few minutes before the start
--                           (data/ingestors/clv_closing_pull.py). A game and
--                           book with an ok row is never bought again.
--   clv_close_measurements  one row per bet measured by the rule: the close
--                           it found (or that none exists), where from, and
--                           the bet's closing-line columns as they stood
--                           before, so nothing the earlier writers stored is
--                           lost (picks_log also keeps the update).
--   game_first_play         the instant a game actually began: its first
--                           play's wall clock (ESPN). A bet placed in the
--                           last minutes before the listed start, with no
--                           pull after it before that listed start, is closed
--                           against the last price before the first play
--                           instead (v3, 2026-11-19).
--
-- Worker-only: RLS on, anon, authenticated and PUBLIC hold nothing. Touches no
-- pick, view, cut or record. One DO block; returns on a catalog read once all
-- four tables exist with their comment (v2 added clv_close_purchases.kind,
-- v3 game_first_play).

DO $mig$
BEGIN
  IF to_regclass('public.clv_close_quotes') IS NOT NULL
     AND to_regclass('public.clv_close_purchases') IS NOT NULL
     AND to_regclass('public.clv_close_measurements') IS NOT NULL
     AND to_regclass('public.game_first_play') IS NOT NULL
     AND COALESCE(obj_description(to_regclass('public.clv_close_measurements'), 'pg_class'), '')
         = 'clv_close 2026-11-19 v3'
     AND NOT has_table_privilege('anon', 'public.clv_close_measurements', 'SELECT')
     AND NOT has_table_privilege('authenticated', 'public.clv_close_quotes', 'SELECT')
  THEN
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.clv_close_quotes (
    quote_id        BIGSERIAL PRIMARY KEY,
    game_id         TEXT NOT NULL,
    bookmaker       TEXT NOT NULL,
    market          TEXT NOT NULL,
    player_name     TEXT,
    spread_home     NUMERIC,
    total_line      NUMERIC,
    line            NUMERIC,
    home_price      NUMERIC,
    away_price      NUMERIC,
    draw_price      NUMERIC,
    over_price      NUMERIC,
    under_price     NUMERIC,
    fetched_at      TIMESTAMPTZ NOT NULL,
    book_last_update TEXT,
    event_id        TEXT,
    source          TEXT NOT NULL DEFAULT 'odds_api_history_clv_close',
    stored_at       TIMESTAMPTZ NOT NULL DEFAULT now()
  );
  CREATE UNIQUE INDEX IF NOT EXISTS clv_close_quotes_one_quote
    ON public.clv_close_quotes (game_id, bookmaker, market, COALESCE(player_name, ''),
                                COALESCE(spread_home, -9999), COALESCE(total_line, -9999),
                                COALESCE(line, -9999), fetched_at);
  CREATE INDEX IF NOT EXISTS clv_close_quotes_game_book
    ON public.clv_close_quotes (game_id, bookmaker);

  CREATE TABLE IF NOT EXISTS public.clv_close_purchases (
    purchase_id     BIGSERIAL PRIMARY KEY,
    game_id         TEXT NOT NULL,
    bookmaker       TEXT NOT NULL,
    asked_for       TIMESTAMPTZ NOT NULL,
    markets         TEXT NOT NULL,
    event_id        TEXT,
    snapshot_at     TIMESTAMPTZ,
    ok              BOOLEAN NOT NULL,
    credits         INTEGER,
    quotes          INTEGER,
    error           TEXT,
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind            TEXT NOT NULL DEFAULT 'history'
  );
  ALTER TABLE public.clv_close_purchases
    ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'history';
  CREATE INDEX IF NOT EXISTS clv_close_purchases_game_book
    ON public.clv_close_purchases (game_id, bookmaker, asked_for);

  CREATE TABLE IF NOT EXISTS public.clv_close_measurements (
    pick_id           BIGINT PRIMARY KEY,
    measured_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    rule              TEXT NOT NULL,
    source            TEXT NOT NULL CHECK (source IN ('feed', 'history', 'none')),
    bet_book          TEXT,
    bet_price         NUMERIC,
    close_market      TEXT,
    close_fetched_at  TIMESTAMPTZ,
    close_odds        NUMERIC,
    close_line        NUMERIC,
    clv_pct           NUMERIC,
    clv_pp            NUMERIC,
    line_clv_pts      NUMERIC,
    last_poll_at      TIMESTAMPTZ,
    note              TEXT,
    before            JSONB
  );

  CREATE TABLE IF NOT EXISTS public.game_first_play (
    game_id         TEXT PRIMARY KEY,
    first_play_at   TIMESTAMPTZ NOT NULL,
    listed_start    TIMESTAMPTZ,
    source          TEXT NOT NULL,
    source_id       TEXT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
  );

  ALTER TABLE public.clv_close_quotes ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.clv_close_purchases ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.clv_close_measurements ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.game_first_play ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.clv_close_quotes FROM anon, authenticated, PUBLIC;
  REVOKE ALL ON public.clv_close_purchases FROM anon, authenticated, PUBLIC;
  REVOKE ALL ON public.clv_close_measurements FROM anon, authenticated, PUBLIC;
  REVOKE ALL ON public.game_first_play FROM anon, authenticated, PUBLIC;
  REVOKE ALL ON SEQUENCE public.clv_close_quotes_quote_id_seq FROM anon, authenticated, PUBLIC;
  REVOKE ALL ON SEQUENCE public.clv_close_purchases_purchase_id_seq FROM anon, authenticated, PUBLIC;
  COMMENT ON TABLE public.clv_close_measurements IS 'clv_close 2026-11-19 v3';
END $mig$;
