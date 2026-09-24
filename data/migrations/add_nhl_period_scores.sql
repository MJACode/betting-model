-- NHL goals by PERIOD, one row per game.
--
-- WHY. The Sportsbook Reviews Online archive (data/ingestors/nhl_sbr_archive.py)
-- carries each period's goals for every game 2018-19 -> 2022-11-27, and the
-- ingestor read them to validate its parse (period sums agreed with `games`
-- on overtime 5,135 / 5,135) and then threw them away. Nothing else in the
-- database holds a period score. They are the settlement column for the
-- first-period moneyline and total, and for the regulation 3-way line on the
-- 4,000 games that predate `games.went_to_ot` -- markets the NHL market grid
-- (docs/nhl_market_lab.md) lists as "target not stored".
--
-- Regulation score = the sum of the three periods; a game is tied after 60
-- minutes when the two sums agree. The archive is the only source so far, so
-- `source` names it and a later loader (the NHL API's play-by-play) adds its
-- own marker rather than overwriting.
--
-- Internal research data: RLS on, privileges revoked, no read policy.
DO $$
BEGIN
  IF to_regclass('public.nhl_period_scores') IS NULL THEN
    CREATE TABLE public.nhl_period_scores (
      game_id    TEXT    NOT NULL,
      game_date  TEXT    NOT NULL,
      season     INTEGER NOT NULL,   -- ENDING year
      home_p1    INTEGER NOT NULL,
      home_p2    INTEGER NOT NULL,
      home_p3    INTEGER NOT NULL,
      away_p1    INTEGER NOT NULL,
      away_p2    INTEGER NOT NULL,
      away_p3    INTEGER NOT NULL,
      source     TEXT    NOT NULL,
      loaded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (game_id, source)
    );
    CREATE INDEX idx_nhl_period_scores_season ON public.nhl_period_scores (season);
    ALTER TABLE public.nhl_period_scores ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.nhl_period_scores FROM anon, authenticated;
  END IF;
END $$;
