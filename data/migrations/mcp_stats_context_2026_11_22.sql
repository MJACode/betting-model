-- AI assistant (MCP): game context views (Matt, 2026-11-22: "1 - all, 2 - yes
-- we can use these stats"). A member's assistant (Grok, screenshot 2026-11-22)
-- said Signal Base could not answer injuries, public betting percentage, rest
-- or positional matchups, searched the web instead and named a player who is
-- on neither team. These views let the connector answer from our own tables.
--
--   injuries        the current injury status per player (injury_status_current),
--                   every sport that table carries
--   public_splits   % of bets and % of money per game, market and side, every
--                   PRE-START snapshot (scoreboard_splits_history). DraftKings'
--                   own split where DK Network publishes it (NFL today), the
--                   multi-book consensus otherwise; `book` says which
--   position_games  one row per player, game and stat with the player's
--                   position group and the OPPONENT (the defense), for
--                   defense-vs-position: NBA and WNBA (G/F/C from
--                   player_positions, the player's CURRENT listed position)
--                   and NFL (QB/RB/WR/TE from the game log's own position)
--
-- Rest needs no view: get_rest reads mcp_stats.games.
--
-- Same rules as mcp_stats_views_2026_11_21.sql: owned by postgres, SELECT for
-- mcp_reader only, display-safe columns (no feed, provider or ingestion
-- fields). One DO block; it (re)creates the views only while the marker
-- 'mcp_stats context v1' is missing from the comment on mcp_stats.injuries.

DO $context$
BEGIN
  IF to_regclass('mcp_stats.injuries') IS NOT NULL
     AND coalesce(obj_description(to_regclass('mcp_stats.injuries'), 'pg_class'), '') LIKE '%mcp_stats context v1%'
  THEN
    RETURN;
  END IF;
  IF to_regnamespace('mcp_stats') IS NULL THEN
    RAISE EXCEPTION 'mcp_stats schema missing: apply mcp_foundation_2026_11_21.sql first';
  END IF;

  CREATE OR REPLACE VIEW mcp_stats.injuries AS
  SELECT i.sport, i.team, i.player_name, i.status, i.injury_type AS detail,
         i.status_ts AS status_time
    FROM public.injury_status_current i;

  -- Pre-start only: a split stamped after the start is in-game money, not the
  -- pre-game market (CLAUDE.md §6: pre-game and in-play never mix).
  CREATE OR REPLACE VIEW mcp_stats.public_splits AS
  SELECT h.sport, h.game_id, h.market, h.side,
         CASE WHEN h.source = 'dk_network' THEN 'DraftKings' ELSE 'Consensus' END AS book,
         h.bet_pct, h.money_pct, h.line_value, h.odds, h.snapshot_at
    FROM public.scoreboard_splits_history h
    JOIN public.games g ON g.sport = h.sport AND g.game_id = h.game_id
   WHERE nullif(coalesce(g.first_pitch_at, g.commence_time), '') IS NULL
      OR h.snapshot_at <= nullif(coalesce(g.first_pitch_at, g.commence_time), '')::timestamptz;

  CREATE OR REPLACE VIEW mcp_stats.position_games AS
  SELECT 'NBA'::text AS sport, l.season, l.game_id, l.game_date, l.team,
         CASE WHEN g.home_team = l.team THEN g.away_team ELSE g.home_team END AS opponent,
         pp.pos_group, s.stat, s.value::numeric AS value
    FROM public.nba_player_game_log l
    JOIN public.games g ON g.sport = 'NBA' AND g.game_id = l.game_id
    JOIN public.player_positions pp ON pp.sport = 'NBA' AND pp.player_id::text = l.player_id::text
    CROSS JOIN LATERAL (VALUES
      ('points', l.points), ('rebounds', l.rebounds), ('assists', l.assists),
      ('threes', l.fg3_made), ('steals', l.steals), ('blocks', l.blocks),
      ('turnovers', l.turnovers),
      ('pra', coalesce(l.points, 0) + coalesce(l.rebounds, 0) + coalesce(l.assists, 0))
    ) AS s(stat, value)
   WHERE pp.pos_group IN ('G', 'F', 'C')
  UNION ALL
  SELECT 'WNBA', l.season, l.game_id, l.game_date, l.team,
         CASE WHEN g.home_team = l.team THEN g.away_team ELSE g.home_team END,
         pp.pos_group, s.stat, s.value::numeric
    FROM public.wnba_player_game_log l
    JOIN public.games g ON g.sport = 'WNBA' AND g.game_id = l.game_id
    JOIN public.player_positions pp ON pp.sport = 'WNBA' AND pp.player_id::text = l.player_id::text
    CROSS JOIN LATERAL (VALUES
      ('points', l.points), ('rebounds', l.rebounds), ('assists', l.assists),
      ('threes', l.fg3_made), ('steals', l.steals), ('blocks', l.blocks),
      ('turnovers', l.turnovers),
      ('pra', coalesce(l.points, 0) + coalesce(l.rebounds, 0) + coalesce(l.assists, 0))
    ) AS s(stat, value)
   WHERE pp.pos_group IN ('G', 'F', 'C')
  UNION ALL
  SELECT 'NFL', l.season, l.game_id, l.game_date, l.team, l.opponent,
         CASE WHEN l.pos = 'FB' THEN 'RB' ELSE l.pos END, s.stat, s.value::numeric
    FROM public.nfl_player_game_log l
    CROSS JOIN LATERAL (VALUES
      ('pass_yds', l.passing_yards), ('pass_tds', l.passing_tds::numeric),
      ('pass_completions', l.completions::numeric), ('pass_attempts', l.attempts::numeric),
      ('interceptions', l.interceptions::numeric), ('rush_yds', l.rushing_yards),
      ('rush_attempts', l.carries::numeric), ('rush_tds', l.rushing_tds::numeric),
      ('receptions', l.receptions::numeric), ('targets', l.targets::numeric),
      ('reception_yds', l.receiving_yards), ('rec_tds', l.receiving_tds::numeric),
      ('rush_reception_yds', coalesce(l.rushing_yards, 0) + coalesce(l.receiving_yards, 0))
    ) AS s(stat, value)
   WHERE l.pos IN ('QB', 'RB', 'FB', 'WR', 'TE');

  GRANT USAGE ON SCHEMA mcp_stats TO mcp_reader;
  GRANT SELECT ON mcp_stats.injuries, mcp_stats.public_splits, mcp_stats.position_games TO mcp_reader;

  COMMENT ON VIEW mcp_stats.public_splits IS 'Pre-start % of bets / % of money per game, market, side; book = DraftKings or Consensus.';
  COMMENT ON VIEW mcp_stats.position_games IS 'Player stat lines with position group and opponent, for defense vs position (NBA, WNBA, NFL).';
  -- The marker goes last: a failure above leaves it missing, so the next pass retries.
  COMMENT ON VIEW mcp_stats.injuries IS 'Current injury status per player. mcp_stats context v1';
END
$context$;
