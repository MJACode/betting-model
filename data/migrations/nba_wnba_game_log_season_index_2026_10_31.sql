-- Season index for the NBA and WNBA player game logs.
--
-- WHY. The Stats board's hit-rate read, player_recent_games_nba, filters
-- `season IN (p_season, p_season - 1)`. nba_player_game_log has no index on
-- season, so the function walks every row through idx_nba_plog_player.
-- Measured on prod, 2026-10-31:
--   204,663 rows in the table, 28,474 in seasons 2026-27 (786 heap pages).
--   Function run with a cold cache: 3,619 ms (read=7,159 pages).
--   Generic plan with a warm cache: 417 ms (206,312 buffer hits).
--   The anon role's statement_timeout is 3s.
-- Edge logs: the first board page failed with 500 at 15:35:43 and
-- 15:37:10 UTC; postgres logged "canceling statement due to statement
-- timeout" at the same times. The retry that followed succeeded.
--
-- NFL and NCAAF already have a season index (idx_nfl_plog_season,
-- idx_ncaaf_plog_season). WNBA has the same function shape and no index,
-- so it gets one too (35,635 rows, 17 MB).
--
-- Column order matches the function's window: PARTITION BY player_id
-- ORDER BY game_date DESC, game_id DESC, inside one season.
--
-- Idempotent. One DO block. Returns on a catalog read once both exist.
-- Plain CREATE INDEX: it blocks writes to the log for the build only.
-- Does not touch picks, odds or the record.

DO $mig$
BEGIN
  IF to_regclass('public.idx_nba_plog_season_player') IS NULL THEN
    EXECUTE
      'CREATE INDEX IF NOT EXISTS idx_nba_plog_season_player '
      'ON public.nba_player_game_log '
      '(season, player_id, game_date DESC, game_id DESC)';
  END IF;

  IF to_regclass('public.wnba_player_game_log') IS NOT NULL
     AND to_regclass('public.idx_wnba_plog_season_player') IS NULL THEN
    EXECUTE
      'CREATE INDEX IF NOT EXISTS idx_wnba_plog_season_player '
      'ON public.wnba_player_game_log '
      '(season, player_id, game_date DESC, game_id DESC)';
  END IF;
END $mig$;
