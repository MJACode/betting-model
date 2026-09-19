-- NCAAF live game state, one row per CHANGE in what the live engine prices.
--
-- WHY IT EXISTS (2026-09-19, Coastal Carolina at Delaware). The live moneyline
-- model bet Delaware +100 on a state that said 0-0, fifteen seconds before the
-- CFBD scoreboard reported the touchdown DraftKings had already re-hung for
-- (-174 -> +100 in two and a half minutes). The post-mortem could prove that
-- for ONE pick, because the poller's log happened to hold that minute. It
-- could not be run for the other 14 live moneyline bets that followed the
-- same book move, because the state the loop priced on was never stored:
-- the loop read the scoreboard, priced it, and threw it away. The in-play
-- QUOTES have been written to `odds` since 2026-09-08; this puts the STATE
-- beside them, so "what did we think the score was when we bet" is a query.
--
-- IT IS ALSO THE MEASUREMENT THE NEW GUARD NEEDS. `BookMoveClock`
-- (data/live_quote_guard.py) declines a quote the book has moved past a cap
-- since our state last changed. The caps shipped as a first cut from the
-- single-republish distribution in `odds`; the quantity they actually bound
-- is the cumulative move BETWEEN state changes, and this table is the only
-- way to compute it. Re-measure after one slate.
--
-- ONE ROW PER CHANGE, NOT PER PASS. The loop polls every 5s across a 40-game
-- Saturday; per-pass rows would be ~30k an hour of mostly identical clock
-- ticks. A change in (score, period, possession) is what the engine's guard
-- keys on, and ~150 such changes per game is a few thousand rows a slate.
-- `raw_state` keeps the whole payload at that moment (clock, down, distance,
-- yardline) for anything the columns do not answer.
--
-- Not `live_game_state`: that table is MLB-shaped (inning, outs, bases) and
-- the app reads its latest-state view for every game on the board, so NCAAF
-- rows there would render as innings.
--
-- NO APP SURFACE. RLS on, privileges revoked, no read policy.
DO $$
BEGIN
  IF to_regclass('public.ncaaf_live_states') IS NULL THEN
    CREATE TABLE public.ncaaf_live_states (
      state_id      BIGSERIAL PRIMARY KEY,
      game_id       TEXT NOT NULL,              -- platform game_id (games.game_id)
      seen_at       TEXT NOT NULL,              -- OUR clock, ISO UTC: when the loop saw it
      period        INTEGER,
      clock_seconds INTEGER,                    -- remaining in the period
      home_score    INTEGER,
      away_score    INTEGER,
      possession    TEXT,                       -- 'home' | 'away' | NULL
      down          INTEGER,
      distance      INTEGER,
      yardline_100  INTEGER,
      source        TEXT,                       -- 'cfbd' | 'espn'
      raw_state     TEXT,                       -- JSON, the whole parsed payload
      created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE (game_id, seen_at)
    );

    -- The read: one game's changes in order.
    CREATE INDEX ncaaf_live_states_game
      ON public.ncaaf_live_states (game_id, seen_at);

    ALTER TABLE public.ncaaf_live_states ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.ncaaf_live_states FROM anon, authenticated;
  END IF;
END $$;
