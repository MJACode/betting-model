-- AI assistant (MCP) connector: every stored game market and the missing props.
--
-- Matt, 2026-11-25 ("Yes to everything ... include Euro and NBL"), after a
-- member asked the connector for tonight's NBA first-quarter totals and was
-- told it has no quarter markets. It had none because mcp_stats.game_prices
-- kept only h2h / spreads / totals, while latest_odds held, over the 7 days to
-- 2026-11-25: NBA quarters and halves (53-56 of 60 games), NCAAB first half
-- (~358 games), team totals, alternate spreads and totals, NHL 3-way and first
-- period, and EuroLeague / NBL lines.
--
-- 1. game_prices carries every market. Three columns are appended
--    (CREATE OR REPLACE VIEW can only append) so the edge function never parses
--    a market key:
--      period        'game', '1H', '2H', '1Q'..'4Q', '1P'..'3P'
--      kind          moneyline, moneyline_3way, spread, total,
--                    team_total_home, team_total_away (else the raw market)
--      is_alternate  an alternate ladder row, not a book's main number
--    Same pre-game bound and the same seven bettable books as before.
--
-- 2. prop_markets maps the props the database holds and the connector did not:
--    NBA rebounds+assists, blocks+steals, double-double, first basket, first
--    team basket; NFL anytime TD, sacks, tackles+assists; NCAAF anytime TD;
--    NHL anytime goal scorer (the 'goals' stat at 0.5).
--
-- 3. player_games gains the history behind them, so hit rates work:
--    NBA rebounds_assists, blocks_steals, double_double (1 or 0);
--    NFL anytime_td (rushing + receiving TDs), sacks, tackles_assists
--    (solo + assisted); NCAAF anytime_td. First basket has prices only: its
--    history lives in nba_first_basket_players, keyed on ESPN ids, not the
--    game log's.
--
-- Idempotent on the PROPERTY this file establishes: game_prices has a
-- `period` column AND prop_markets maps 'anytime_td'. The comment on
-- player_games keeps 'mcp_stats v1', so mcp_stats_views_2026_11_21.sql never
-- re-runs; it carries the same definitions anyway, so a rerun agrees.

DO $markets$
BEGIN
  IF to_regclass('mcp_stats.game_prices') IS NULL OR to_regclass('mcp_stats.player_games') IS NULL THEN
    RAISE EXCEPTION 'mcp_stats views missing: apply mcp_stats_views_2026_11_21.sql first';
  END IF;
  IF EXISTS (
       SELECT 1 FROM pg_attribute
        WHERE attrelid = to_regclass('mcp_stats.game_prices')
          AND attname = 'period' AND NOT attisdropped)
     AND EXISTS (SELECT 1 FROM mcp_stats.prop_markets WHERE stat = 'anytime_td')
  THEN
    RETURN;
  END IF;

  -- Pre-game only: a quote taken after the start is an in-play price.
  CREATE OR REPLACE VIEW mcp_stats.game_prices AS
  SELECT g.sport, o.game_id, o.market, b.book,
         o.home_price, o.away_price, o.draw_price, o.spread_home, o.total_line,
         o.over_price, o.under_price, o.snapshot_at,
         coalesce(
           (SELECT right(p, 1) || upper(left(p, 1))
              FROM (SELECT substring(o.market FROM '_([qhp][1-4])(?:_|$)') AS p) s
             WHERE p IS NOT NULL),
           'game') AS period,
         CASE
           WHEN o.market ~ '^h2h_3_?way' THEN 'moneyline_3way'
           WHEN o.market ~ '^h2h' THEN 'moneyline'
           WHEN o.market ~ 'spreads' THEN 'spread'
           WHEN o.market ~ 'team_totals.*_home' THEN 'team_total_home'
           WHEN o.market ~ 'team_totals.*_away' THEN 'team_total_away'
           WHEN o.market ~ 'totals' THEN 'total'
           ELSE o.market
         END AS kind,
         (o.market ~ '(^alternate_|_alternate$)') AS is_alternate
    FROM public.latest_odds o
    JOIN mcp_stats.books b ON b.book_key = o.bookmaker
    JOIN public.games g ON g.game_id = o.game_id
   WHERE (g.commence_time IS NULL OR o.snapshot_at <= g.commence_time);

  CREATE OR REPLACE VIEW mcp_stats.prop_markets AS
  SELECT * FROM (VALUES
    ('NBA','points','player_points'), ('NBA','rebounds','player_rebounds'),
    ('NBA','assists','player_assists'), ('NBA','threes','player_threes'),
    ('NBA','steals','player_steals'), ('NBA','blocks','player_blocks'),
    ('NBA','pra','player_points_rebounds_assists'),
    ('NBA','rebounds_assists','player_rebounds_assists'),
    ('NBA','blocks_steals','player_blocks_steals'),
    ('NBA','double_double','player_double_double'),
    ('NBA','first_basket','player_first_basket'),
    ('NBA','first_team_basket','player_first_team_basket'),
    ('WNBA','points','player_points'), ('WNBA','rebounds','player_rebounds'),
    ('WNBA','assists','player_assists'), ('WNBA','threes','player_threes'),
    ('WNBA','pra','player_points_rebounds_assists'),
    ('NFL','pass_yds','player_pass_yds'), ('NFL','pass_tds','player_pass_tds'),
    ('NFL','pass_completions','player_pass_completions'),
    ('NFL','pass_attempts','player_pass_attempts'),
    ('NFL','rush_yds','player_rush_yds'), ('NFL','rush_attempts','player_rush_attempts'),
    ('NFL','receptions','player_receptions'), ('NFL','reception_yds','player_reception_yds'),
    ('NFL','rush_reception_yds','player_rush_reception_yds'),
    ('NFL','anytime_td','player_anytime_td'), ('NFL','sacks','player_sacks'),
    ('NFL','tackles_assists','player_tackles_assists'),
    ('NCAAF','pass_yds','player_pass_yds'), ('NCAAF','pass_tds','player_pass_tds'),
    ('NCAAF','pass_completions','player_pass_completions'),
    ('NCAAF','pass_attempts','player_pass_attempts'),
    ('NCAAF','rush_yds','player_rush_yds'), ('NCAAF','receptions','player_receptions'),
    ('NCAAF','reception_yds','player_reception_yds'),
    ('NCAAF','anytime_td','player_anytime_td'),
    ('NHL','assists','player_assists'),
    ('NHL','points','player_points'), ('NHL','shots_on_goal','player_shots_on_goal'),
    ('NHL','blocked_shots','player_blocked_shots'), ('NHL','saves','player_total_saves'),
    ('NHL','goals','player_goal_scorer_anytime'),
    ('MLB','hits','batter_hits'), ('MLB','home_runs','batter_home_runs'),
    ('MLB','total_bases','batter_total_bases'), ('MLB','rbi','batter_rbis'),
    ('MLB','runs','batter_runs_scored'), ('MLB','walks','batter_walks'),
    ('MLB','stolen_bases','batter_stolen_bases'),
    ('MLB','pitcher_strikeouts','pitcher_strikeouts'), ('MLB','pitcher_outs','pitcher_outs'),
    ('MLB','earned_runs','pitcher_earned_runs'), ('MLB','hits_allowed','pitcher_hits_allowed'),
    ('MLB','walks_allowed','pitcher_walks')
  ) AS m(sport, stat, market);

  -- Basketball shape (NBA, WNBA, NCAAB, NCAABW).
  CREATE OR REPLACE VIEW mcp_stats.player_games AS
  SELECT 'NBA'::text AS sport, l.player_id, l.player_name, l.team, NULL::text AS opponent,
         l.game_id, l.game_date, l.season, s.stat, s.value::numeric AS value
    FROM public.nba_player_game_log l
    CROSS JOIN LATERAL (VALUES
      ('points', l.points), ('rebounds', l.rebounds), ('assists', l.assists),
      ('threes', l.fg3_made), ('steals', l.steals), ('blocks', l.blocks),
      ('turnovers', l.turnovers), ('minutes', l.minutes),
      ('pra', coalesce(l.points, 0) + coalesce(l.rebounds, 0) + coalesce(l.assists, 0)),
      ('rebounds_assists', coalesce(l.rebounds, 0) + coalesce(l.assists, 0)),
      ('blocks_steals', coalesce(l.blocks, 0) + coalesce(l.steals, 0)),
      ('double_double', CASE WHEN (coalesce(l.points, 0) >= 10)::int + (coalesce(l.rebounds, 0) >= 10)::int
                                  + (coalesce(l.assists, 0) >= 10)::int + (coalesce(l.steals, 0) >= 10)::int
                                  + (coalesce(l.blocks, 0) >= 10)::int >= 2 THEN 1 ELSE 0 END)
    ) AS s(stat, value)
  UNION ALL
  SELECT 'WNBA', l.player_id, l.player_name, l.team, NULL, l.game_id, l.game_date, l.season,
         s.stat, s.value::numeric
    FROM public.wnba_player_game_log l
    CROSS JOIN LATERAL (VALUES
      ('points', l.points), ('rebounds', l.rebounds), ('assists', l.assists),
      ('threes', l.fg3_made), ('steals', l.steals), ('blocks', l.blocks),
      ('turnovers', l.turnovers), ('minutes', l.minutes),
      ('pra', coalesce(l.points, 0) + coalesce(l.rebounds, 0) + coalesce(l.assists, 0))
    ) AS s(stat, value)
  UNION ALL
  SELECT 'NCAAB', l.player_id, l.player_name, l.team, NULL, l.game_id, l.game_date, l.season,
         s.stat, s.value::numeric
    FROM public.ncaab_player_game_log l
    CROSS JOIN LATERAL (VALUES
      ('points', l.points), ('rebounds', l.rebounds), ('assists', l.assists),
      ('threes', l.fg3_made), ('steals', l.steals), ('blocks', l.blocks),
      ('turnovers', l.turnovers), ('minutes', l.minutes),
      ('pra', coalesce(l.points, 0) + coalesce(l.rebounds, 0) + coalesce(l.assists, 0))
    ) AS s(stat, value)
  UNION ALL
  SELECT 'NCAABW', l.player_id, l.player_name, l.team, NULL, l.game_id, l.game_date, l.season,
         s.stat, s.value::numeric
    FROM public.ncaabw_player_game_log l
    CROSS JOIN LATERAL (VALUES
      ('points', l.points), ('rebounds', l.rebounds), ('assists', l.assists),
      ('threes', l.fg3_made), ('steals', l.steals), ('blocks', l.blocks),
      ('turnovers', l.turnovers), ('minutes', l.minutes),
      ('pra', coalesce(l.points, 0) + coalesce(l.rebounds, 0) + coalesce(l.assists, 0))
    ) AS s(stat, value)
  UNION ALL
  SELECT 'NFL', l.player_id, l.player_name, l.team, l.opponent, l.game_id, l.game_date, l.season,
         s.stat, s.value::numeric
    FROM public.nfl_player_game_log l
    CROSS JOIN LATERAL (VALUES
      ('pass_yds', l.passing_yards), ('pass_tds', l.passing_tds::numeric),
      ('pass_completions', l.completions::numeric), ('pass_attempts', l.attempts::numeric),
      ('interceptions', l.interceptions::numeric), ('rush_yds', l.rushing_yards),
      ('rush_attempts', l.carries::numeric), ('rush_tds', l.rushing_tds::numeric),
      ('receptions', l.receptions::numeric), ('targets', l.targets::numeric),
      ('reception_yds', l.receiving_yards), ('rec_tds', l.receiving_tds::numeric),
      ('rush_reception_yds', coalesce(l.rushing_yards, 0) + coalesce(l.receiving_yards, 0)),
      ('anytime_td', (coalesce(l.rushing_tds, 0) + coalesce(l.receiving_tds, 0))::numeric),
      ('sacks', l.def_sacks::numeric),
      ('tackles_assists', CASE WHEN l.def_tackles_solo IS NULL AND l.def_tackle_assists IS NULL THEN NULL
                               ELSE (coalesce(l.def_tackles_solo, 0) + coalesce(l.def_tackle_assists, 0))::numeric END)
    ) AS s(stat, value)
  UNION ALL
  SELECT 'NCAAF', l.player_id, l.player_name, l.team, l.opponent, l.game_id, l.game_date, l.season,
         s.stat, s.value::numeric
    FROM public.ncaaf_player_game_log l
    CROSS JOIN LATERAL (VALUES
      ('pass_yds', l.passing_yards::numeric), ('pass_tds', l.passing_tds::numeric),
      ('pass_completions', l.completions::numeric), ('pass_attempts', l.attempts::numeric),
      ('interceptions', l.interceptions::numeric), ('rush_yds', l.rushing_yards::numeric),
      ('rush_attempts', l.carries::numeric), ('rush_tds', l.rushing_tds::numeric),
      ('receptions', l.receptions::numeric), ('reception_yds', l.receiving_yards::numeric),
      ('rec_tds', l.receiving_tds::numeric),
      ('anytime_td', (coalesce(l.rushing_tds, 0) + coalesce(l.receiving_tds, 0))::numeric)
    ) AS s(stat, value)
  UNION ALL
  SELECT 'NHL', l.player_id::text, l.player_name, l.team, l.opponent, l.game_id, l.game_date, l.season,
         s.stat, s.value::numeric
    FROM public.nhl_skater_game_log l
    CROSS JOIN LATERAL (VALUES
      ('goals', l.goals), ('assists', l.assists), ('points', l.points),
      ('shots_on_goal', l.shots), ('blocked_shots', l.blocked_shots), ('hits', l.hits),
      ('pp_points', l.pp_points)
    ) AS s(stat, value)
  UNION ALL
  SELECT 'NHL', l.player_id::text, l.player_name, l.team, l.opponent, l.game_id, l.game_date, l.season,
         s.stat, s.value::numeric
    FROM public.nhl_goalie_game_log l
    CROSS JOIN LATERAL (VALUES
      ('saves', l.saves), ('goals_against', l.goals_against), ('shots_against', l.shots_against)
    ) AS s(stat, value)
  UNION ALL
  -- MLB innings are baseball notation (5.2 = five and two thirds): outs, not sums.
  SELECT 'MLB', l.player_id, l.player_name, l.team, NULL, l.game_id, l.game_date, l.season,
         s.stat, s.value::numeric
    FROM public.player_game_log l
    CROSS JOIN LATERAL (VALUES
      ('hits', CASE WHEN l.player_type = 'batter' THEN l.hits END::numeric),
      ('home_runs', CASE WHEN l.player_type = 'batter' THEN l.home_runs END::numeric),
      ('total_bases', CASE WHEN l.player_type = 'batter' THEN l.total_bases END::numeric),
      ('rbi', CASE WHEN l.player_type = 'batter' THEN l.rbi END::numeric),
      ('runs', CASE WHEN l.player_type = 'batter' THEN l.runs END::numeric),
      ('walks', CASE WHEN l.player_type = 'batter' THEN l.walks END::numeric),
      ('batter_strikeouts', CASE WHEN l.player_type = 'batter' THEN l.strikeouts END::numeric),
      ('stolen_bases', CASE WHEN l.player_type = 'batter' THEN l.stolen_bases END::numeric),
      ('pitcher_strikeouts', CASE WHEN l.player_type = 'pitcher' THEN l.p_strikeouts END::numeric),
      ('pitcher_outs', CASE WHEN l.player_type = 'pitcher' AND l.innings_pitched IS NOT NULL
                            THEN trunc(l.innings_pitched) * 3
                                 + round((l.innings_pitched - trunc(l.innings_pitched)) * 10) END),
      ('earned_runs', CASE WHEN l.player_type = 'pitcher' THEN l.p_earned_runs END::numeric),
      ('hits_allowed', CASE WHEN l.player_type = 'pitcher' THEN l.p_hits_allowed END::numeric),
      ('walks_allowed', CASE WHEN l.player_type = 'pitcher' THEN l.p_walks END::numeric)
    ) AS s(stat, value)
   WHERE s.value IS NOT NULL
  UNION ALL
  SELECT 'UFC', l.fighter_id, l.fighter_name, NULL, l.opponent_name, l.game_id, l.game_date, l.season,
         s.stat, s.value::numeric
    FROM public.ufc_fight_log l
    CROSS JOIN LATERAL (VALUES
      ('sig_strikes', l.sig_strikes_landed), ('takedowns', l.takedowns_landed),
      ('knockdowns', l.knockdowns)
    ) AS s(stat, value);

  COMMENT ON VIEW mcp_stats.player_games IS
    'mcp_stats v1 (mcp_stats_views_2026_11_21.sql), all markets v2 (mcp_stats_all_markets_2026_11_25.sql). One row per player, game and stat.';

  -- Readable by the connector's read role only (a replaced view keeps its
  -- grants; restated so the file stands alone).
  REVOKE ALL ON mcp_stats.game_prices, mcp_stats.prop_markets, mcp_stats.player_games
    FROM PUBLIC, anon, authenticated, mcp_meter_role;
  GRANT SELECT ON mcp_stats.game_prices, mcp_stats.prop_markets, mcp_stats.player_games TO mcp_reader;
END
$markets$;
