-- Kalshi NCAAF GAME markets (winner, total ladder, spread ladder), one row per
-- CONTRACT per snapshot. Recording only -- nothing scores off it.
--
-- WHY IT EXISTS (session 280, 2026-09-10). The NCAAF cross-book search found
-- one number across thirteen bookmakers: DraftKings sits a mean 0.16 points
-- from the 13-book median total, the sharp books post ~5 days after DK, and no
-- consensus, dispersion or steam-lag construction cleared -110. Kalshi is not a
-- bookmaker: no vig, resting orders, a timestamped price on every rung of a
-- total or spread ladder, and it lists NCAAF winner markets on ~118 events and
-- total ladders on ~68 per weekend (probed 2026-09-10). Whether that price
-- knows anything the books do not can only be answered from a record, and
-- every weekend not recorded is evidence that cannot be recovered afterwards
-- -- the pattern this repo has paid for twice (100,116 credits of prop
-- snapshots that lived only on a container disk; 117,048 sharp quotes that
-- survived only in a tracked parquet).
--
-- KEYED ON KALSHI'S EVENT TICKER, NOT OUR GAME ID. `KXNCAAFTOTAL-26SEP12ARKUTAH`
-- carries the date and two Kalshi team codes; our id is
-- `NCAAF_2026-09-12_arkansas_utah`. A code-to-school map would fail quietly on
-- the disagreements, so the row keeps the ticker, the parsed date and the
-- contract title verbatim; the reader joins with a map it can inspect.
--
-- ONE ROW PER CONTRACT. A ladder is derived: rebuild it from the rungs at a
-- snapshot. Raw prices, no spread gate, no interpolation -- those are choices a
-- later analysis may want to vary.
--
-- GROWTH: ~480 winner + ~2,000 total + ~2,000 spread contracts open at once;
-- hourly that is ~100k rows a day in season, an order of magnitude under what
-- `odds` takes. NOT PRUNED, deliberately (see add_kalshi_prop_ladders.sql).
--
-- NO APP SURFACE. RLS on, privileges revoked, no read policy.
DO $$
BEGIN
  IF to_regclass('public.kalshi_game_markets') IS NULL THEN
    CREATE TABLE public.kalshi_game_markets (
      row_id         BIGSERIAL PRIMARY KEY,
      snapshot_at    TIMESTAMPTZ NOT NULL,
      game_date      DATE        NOT NULL,
      -- 'winner' | 'total' | 'spread'
      kind           TEXT        NOT NULL,
      event_ticker   TEXT        NOT NULL,
      market_ticker  TEXT        NOT NULL,
      -- Kalshi's contract title, verbatim ("Over 54.5 points scored",
      -- "Miami (FL) wins by over 6.5 points", "Utah wins").
      title          TEXT,
      -- yes_sub_title: the team a winner/spread contract is about.
      side_label     TEXT,
      -- floor_strike: the number the total / margin must EXCEED. NULL for winner.
      strike         NUMERIC,
      yes_bid        NUMERIC,
      yes_ask        NUMERIC,
      last_price     NUMERIC,
      volume         NUMERIC,
      open_interest  NUMERIC,
      status         TEXT,
      close_time     TIMESTAMPTZ,
      ingested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    -- One contract, one price, per snapshot: a retry cannot double a ladder.
    CREATE UNIQUE INDEX kalshi_game_markets_contract
      ON public.kalshi_game_markets (market_ticker, snapshot_at);
    -- The read that rebuilds a ladder: one event, newest snapshot first.
    CREATE INDEX kalshi_game_markets_event
      ON public.kalshi_game_markets (event_ticker, snapshot_at DESC);
    -- The read that grades an offset: everything at one snapshot / one date.
    CREATE INDEX kalshi_game_markets_date
      ON public.kalshi_game_markets (game_date, kind, snapshot_at DESC);

    ALTER TABLE public.kalshi_game_markets ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.kalshi_game_markets FROM anon, authenticated;
    REVOKE ALL ON SEQUENCE public.kalshi_game_markets_row_id_seq
      FROM anon, authenticated;
  END IF;
END $$;
