-- anon_read_public_betting_2026_09_20
--
-- The team page (mobile TeamStatsScreen, 2026-09-20) reads the consensus
-- ticket/money splits for a team's next game straight from public_betting.
--
-- MEASURED BEFORE WRITING THIS: anon and authenticated already held SELECT on
-- the table (information_schema.role_table_grants), and RLS was enabled
-- (pg_class.relrowsecurity = true) with NO policy -- which for a non-owner
-- role is deny-all. So the app would have received zero rows and no error:
-- the silent empty screen data/anon_readable.py exists to prevent. The fix is
-- the same policy every other display table carries (see
-- add_team_stats_board.sql, part 1). Display data only: no picks, no model
-- output, no user data.
--
-- Coverage today, so nobody reads an empty card as a bug: 8,448 rows over
-- 1,408 games, all MLB, 2026-05-31 -> 2026-09-19. The ingestor covers one
-- sport; the screen says so for the others.

CREATE POLICY "anon read public_betting" ON public.public_betting
  FOR SELECT TO anon, authenticated USING (true);
