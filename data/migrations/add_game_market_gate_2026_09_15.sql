-- MLB (and any later sport) game-market gate log.
--
-- WHY. The pre-game GAME models decide BET from model_prob vs vig-included
-- implied of the current quote (`scorer._decide`). They never record whether
-- that quote had already steamed through the model's number, or whether the
-- Action Network ticket share sat on our side while the line moved with it.
-- `models/game_market_gate.py` computes that verdict. This table is the
-- system of record so CLEAR vs PASS_* can be graded on CLV / ROI even
-- when live mode has already written NONE on picks.
--
-- One row per (game_id, model_id, pick_side). Re-scores overwrite; a locked
-- BET on `picks` is never deleted by this (CLAUDE.md §1c). The close is not
-- a column — as_of is the quote clock, and the loader refuses later ticks.
--
-- IDEMPOTENT: CREATE TABLE IF NOT EXISTS via to_regclass. Safe every pass.
-- RLS on, no anon policy (pipeline writes via DATABASE_URL; evaluation is
-- SQL). Does not ALTER picks or touch Discord / push.

DO $$
BEGIN
  IF to_regclass('public.game_market_gate') IS NULL THEN
    CREATE TABLE public.game_market_gate (
      game_id            TEXT NOT NULL,
      model_id           TEXT NOT NULL,
      pick_side          TEXT NOT NULL,
      game_date          TEXT,
      as_of              TEXT,
      verdict            TEXT NOT NULL,
      mode               TEXT NOT NULL,
      reason             TEXT,
      applied            BOOLEAN NOT NULL DEFAULT FALSE,
      model_prob         NUMERIC,
      market_fair_prob   NUMERIC,
      open_fair_prob     NUMERIC,
      no_vig_edge        NUMERIC,
      public_bet_pct     NUMERIC,
      public_money_pct   NUMERIC,
      steamed            BOOLEAN NOT NULL DEFAULT FALSE,
      public_steam       BOOLEAN NOT NULL DEFAULT FALSE,
      rlm                BOOLEAN NOT NULL DEFAULT FALSE,
      created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (game_id, model_id, pick_side)
    );
    CREATE INDEX game_market_gate_date
      ON public.game_market_gate (game_date, model_id);
    ALTER TABLE public.game_market_gate ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.game_market_gate FROM anon, authenticated;
  END IF;
END $$;
