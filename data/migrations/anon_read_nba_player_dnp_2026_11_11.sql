-- anon_read_nba_player_dnp_2026_11_11
--
-- NOT APPLIED. Matt's OK is required before this runs on production.
-- Do not apply it from a client session.
--
-- The NBA player page reads did-not-play games from nba_player_dnp
-- (mobile/src/lib/queries.ts fetchPlayerGameLog). Measured 2026-11-11 on
-- production, read-only: 1,199 rows, 361 players, 236 games, game_date
-- 2026-04-01 through 2026-11-09.
--
-- The table was created by the results ingestor and locked down: RLS on,
-- no policy. A GRANT alone returns zero rows to anon (the same hole as
-- public_betting, anon_read_public_betting_2026_09_20.sql). The policy is
-- the one the player game logs already use. Display only: who sat out, and
-- why ESPN said so is not selected by the app.
--
-- WNBA and NCAAB have no did-not-play table. Their ingestors drop those
-- athletes before insert. This file does not invent one.

GRANT SELECT ON public.nba_player_dnp TO anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.nba_player_dnp FROM anon, authenticated;

ALTER TABLE public.nba_player_dnp ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon read nba_player_dnp" ON public.nba_player_dnp;
CREATE POLICY "anon read nba_player_dnp" ON public.nba_player_dnp
  FOR SELECT TO anon, authenticated
  USING (true);
