-- NHL prop overs, paper only. Recording, not a pick.
--
-- 2026-10-02 (Michael Alksninis): the all-under board was remeasured on both
-- sides. No over cell cleared (docs/nhl_market_lab.md). Live cards keep
-- publishing unders. An over that clears the same floor is written here so
-- the side can be watched without becoming a BET, a Discord post, or a push.
--
-- Not read by the app. RLS on, privileges revoked, no read policy.
DO $$
BEGIN
  IF to_regclass('public.nhl_prop_paper_overs') IS NULL THEN
    CREATE TABLE public.nhl_prop_paper_overs (
      id                 BIGSERIAL PRIMARY KEY,
      game_id            TEXT NOT NULL,
      model_id           TEXT NOT NULL,
      player_id          TEXT NOT NULL,
      game_date          TEXT NOT NULL,
      pick_label         TEXT NOT NULL,
      scored_line        NUMERIC NOT NULL,
      price              NUMERIC NOT NULL,
      book               TEXT NOT NULL,
      model_probability  NUMERIC NOT NULL,
      ev                 NUMERIC NOT NULL,
      result             TEXT,
      profit_units       NUMERIC,
      settled_at         TEXT,
      created_at         TEXT DEFAULT (NOW()::TEXT),
      UNIQUE (game_id, model_id, player_id)
    );
    CREATE INDEX nhl_prop_paper_overs_open
      ON public.nhl_prop_paper_overs (game_date)
      WHERE result IS NULL;
    ALTER TABLE public.nhl_prop_paper_overs ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_prop_paper_overs FROM anon, authenticated;
    REVOKE ALL ON SEQUENCE public.nhl_prop_paper_overs_id_seq
      FROM anon, authenticated;
  END IF;
END $$;
