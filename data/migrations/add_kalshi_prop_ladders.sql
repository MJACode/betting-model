-- Kalshi NFL player-prop ladders, one row per RUNG per snapshot.
--
-- WHY IT EXISTS. `models/prop_ladder` can read a fair probability at any line
-- off a Kalshi strike ladder, which recovers 11.1% of the soft board that no
-- sharp reference can price today (docs/prop_market_research.md §6b). It is not
-- wired into scoring and must not be, because there is nothing to validate it
-- against: Kalshi's NFL prop markets are new and settled history reaches back
-- only to 2026 preseason.
--
-- That is the whole point of this table. Pinnacle became a reference by clearing
-- a placebo on three seasons; Kalshi cannot be graded at all until a record
-- exists, and every week without recording is a week of evidence that cannot be
-- recovered later. The pattern is the one this repo has already paid for twice:
-- 100,116 credits of prop snapshots that existed nowhere but a container disk,
-- and 117,048 sharp quotes that survived only in a tracked parquet.
--
-- ONE ROW PER RUNG, NOT PER LADDER. The ladder is a derived object -- rebuild it
-- with models.prop_ladder.Ladder from the rungs at a given snapshot. Storing the
-- interpolated output instead would freeze today's interpolation choices into
-- the history, and those choices (logit space, PAVA, the spread gate) are
-- exactly what a later analysis may want to vary.
--
-- KEYED ON (game_date, player_key, market), NOT A GAME ID. Kalshi's event code
-- is `26SEP13ATLPIT` and ours is `NFL_2026_02_ATL_PIT`; mapping between them
-- needs a team-abbreviation table that would fail quietly on the disagreements.
-- A player appears at most once per date, so this key is already unique and
-- joins to our board with no mapping at all.
--
-- GROWTH, measured rather than guessed: 1,333 open NFL prop markets on
-- 2026-09-08, hourly, is ~32k rows/day and ~4M over a season. That is an order
-- of magnitude below what `odds` and `player_prop_odds` already take daily.
--
-- NOT PRUNED, DELIBERATELY. data/prune_odds.py touches `odds` and
-- `player_prop_odds` only. This table is the evidence a reference is or is not
-- worth using, which is exactly the kind of history the pruner has twice
-- destroyed elsewhere. If retention is ever added here, it needs the same
-- carve-out reasoning as the sharp books, not a default.
--
-- NO APP SURFACE. Internal research data: RLS on, privileges revoked by name,
-- and no read policy. Nothing in the app reads it, so nothing is granted.
DO $$
BEGIN
  IF to_regclass('public.kalshi_prop_ladders') IS NULL THEN
    CREATE TABLE public.kalshi_prop_ladders (
      rung_id        BIGSERIAL PRIMARY KEY,
      snapshot_at    TIMESTAMPTZ NOT NULL,
      game_date      DATE        NOT NULL,
      -- norm_player_name(...) -- the join to our board and to nflverse.
      player_key     TEXT        NOT NULL,
      -- The spelling Kalshi printed, kept for display and for debugging a
      -- normalisation that stops matching.
      player_display TEXT,
      -- Our market name (player_pass_yds, ...), already translated from the
      -- Kalshi series so a reader never needs the series map.
      market         TEXT        NOT NULL,
      -- The number the stat must EXCEED. Kalshi lists "300+ passing yards" with
      -- floor_strike 299.5, which is already the over convention.
      strike         NUMERIC     NOT NULL,
      yes_bid        NUMERIC,
      yes_ask        NUMERIC,
      volume         NUMERIC,
      open_interest  NUMERIC,
      event_ticker   TEXT,
      market_ticker  TEXT        NOT NULL,
      ingested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    -- One contract, one price, per snapshot. Makes a re-run inside the same
    -- snapshot idempotent instead of doubling the ladder.
    CREATE UNIQUE INDEX kalshi_prop_ladders_rung
      ON public.kalshi_prop_ladders (market_ticker, snapshot_at);
    -- The read that rebuilds a ladder: everything for one proposition, newest
    -- snapshot first.
    CREATE INDEX kalshi_prop_ladders_prop
      ON public.kalshi_prop_ladders (game_date, player_key, market, snapshot_at DESC);
    -- The read that grades an offset: everything at one snapshot.
    CREATE INDEX kalshi_prop_ladders_snapshot
      ON public.kalshi_prop_ladders (snapshot_at DESC);

    ALTER TABLE public.kalshi_prop_ladders ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.kalshi_prop_ladders FROM anon, authenticated;
    REVOKE ALL ON SEQUENCE public.kalshi_prop_ladders_rung_id_seq
      FROM anon, authenticated;
  END IF;
END $$;
