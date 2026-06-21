-- Migration: add_parlay_track_record
-- Public parlay track record: one canonical cross-game parlay per (sport, day),
-- logged by tracking/parlay_track_record.capture_parlay_track_record and settled
-- by settle_parlay_track_record from its opening_signals legs. RLS on; anon
-- SELECT so the mobile Track Record screen can publish wins AND losses. The app
-- aggregates rows client-side (headline + equity curve) — no view required.

CREATE TABLE IF NOT EXISTS public.parlay_track_record (
  id                BIGSERIAL PRIMARY KEY,
  parlay_key        TEXT NOT NULL,
  sport             TEXT NOT NULL,
  game_date         TEXT NOT NULL,
  n_legs            INTEGER NOT NULL,
  leg_keys          TEXT NOT NULL,        -- JSON array of opening_signals lock_keys
  leg_labels        TEXT NOT NULL,        -- JSON array of pick labels (display)
  leg_odds          TEXT NOT NULL,        -- JSON array of American odds per leg
  combined_decimal  NUMERIC NOT NULL,
  combined_american NUMERIC NOT NULL,
  model_prob        NUMERIC NOT NULL,
  dk_implied_prob   NUMERIC NOT NULL,
  edge              NUMERIC NOT NULL,
  locked_at         TEXT NOT NULL,
  result            TEXT,                 -- WIN | LOSS | PUSH (null = pending)
  profit_flat       NUMERIC,              -- flat 1-unit P&L
  settled_at        TEXT,
  created_at        TIMESTAMP DEFAULT now(),
  UNIQUE (parlay_key)
);

CREATE INDEX IF NOT EXISTS idx_parlay_track_date  ON public.parlay_track_record(game_date);
CREATE INDEX IF NOT EXISTS idx_parlay_track_sport ON public.parlay_track_record(sport);

ALTER TABLE public.parlay_track_record ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon read parlay_track_record"
  ON public.parlay_track_record FOR SELECT TO anon, authenticated USING (true);
