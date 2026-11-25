-- AI assistant (MCP) connector: the Stats views it may read (schema mcp_stats).
--
-- mcp_reader has SELECT on these and nothing else (mcp_foundation_2026_11_21).
-- They run as their owner (postgres, BYPASSRLS), so they see the gated tables
-- without opening those tables to anyone. Each exposes generic, display-safe
-- columns only: no source, provider, feed, ingestion or internal-key fields,
-- no picks, no model data.
--
--   player_games     one row per player, game and stat (long format), all
--                    sports; stat names follow the prop markets
--   players          one row per player appearance (for name search)
--   games            the slate: teams, start, score
--   prop_prices      latest PRE-GAME player-prop prices at the seven bettable
--                    books (config.BEST_LINE_BOOKMAKERS), main and alternate lines
--   game_prices      latest pre-game game markets (every period, team totals,
--                    alternates; period / kind / is_alternate), same books
--                    (mcp_stats_all_markets_2026_11_25.sql)
--   prop_markets     stat -> prop market, per sport
--   books            book key -> display name (the seven bettable books)
--
-- One DO block in ACTIVE_MIGRATIONS; it (re)creates the views only while the
-- marker 'mcp_stats v1' is missing from the comment on mcp_stats.player_games.

DO $views$
BEGIN
  IF to_regclass('mcp_stats.player_games') IS NOT NULL
     AND coalesce(obj_description(to_regclass('mcp_stats.player_games'), 'pg_class'), '') LIKE '%mcp_stats v1%'
  THEN
    RETURN;
  END IF;
  IF to_regnamespace('mcp_stats') IS NULL THEN
    RAISE EXCEPTION 'mcp_stats schema missing: apply mcp_foundation_2026_11_21.sql first';
  END IF;

  -- Name search (find_player): trigram indexes so ILIKE '%name%' does not walk
  -- every game row. Measured 2026-11-21 on nba_player_game_log: 3,192 ms
  -- without, 3 ms with (filter first in a MATERIALIZED CTE, then DISTINCT ON).
  -- Built once: this block runs only while its marker is missing.
  CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions;
  CREATE INDEX IF NOT EXISTS mcp_trgm_nba_plog ON public.nba_player_game_log USING gin (player_name extensions.gin_trgm_ops);
  CREATE INDEX IF NOT EXISTS mcp_trgm_wnba_plog ON public.wnba_player_game_log USING gin (player_name extensions.gin_trgm_ops);
  CREATE INDEX IF NOT EXISTS mcp_trgm_ncaab_plog ON public.ncaab_player_game_log USING gin (player_name extensions.gin_trgm_ops);
  CREATE INDEX IF NOT EXISTS mcp_trgm_ncaabw_plog ON public.ncaabw_player_game_log USING gin (player_name extensions.gin_trgm_ops);
  CREATE INDEX IF NOT EXISTS mcp_trgm_nfl_plog ON public.nfl_player_game_log USING gin (player_name extensions.gin_trgm_ops);
  CREATE INDEX IF NOT EXISTS mcp_trgm_ncaaf_plog ON public.ncaaf_player_game_log USING gin (player_name extensions.gin_trgm_ops);
  CREATE INDEX IF NOT EXISTS mcp_trgm_nhl_skater ON public.nhl_skater_game_log USING gin (player_name extensions.gin_trgm_ops);
  CREATE INDEX IF NOT EXISTS mcp_trgm_nhl_goalie ON public.nhl_goalie_game_log USING gin (player_name extensions.gin_trgm_ops);
  CREATE INDEX IF NOT EXISTS mcp_trgm_mlb_plog ON public.player_game_log USING gin (player_name extensions.gin_trgm_ops);
  CREATE INDEX IF NOT EXISTS mcp_trgm_ufc_flog ON public.ufc_fight_log USING gin (fighter_name extensions.gin_trgm_ops);

  CREATE OR REPLACE VIEW mcp_stats.books AS
  SELECT * FROM (VALUES
    ('draftkings', 'DraftKings'), ('fanduel', 'FanDuel'), ('betmgm', 'BetMGM'),
    ('williamhill_us', 'Caesars'), ('fanatics', 'Fanatics'),
    ('betrivers', 'BetRivers'), ('hardrockbet', 'Hard Rock Bet')
  ) AS b(book_key, book);

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
    'mcp_stats v1 (mcp_stats_views_2026_11_21.sql). One row per player, game and stat.';

  CREATE OR REPLACE VIEW mcp_stats.players AS
  SELECT 'NBA'::text AS sport, player_id, player_name, team, game_date, season FROM public.nba_player_game_log
  UNION ALL SELECT 'WNBA', player_id, player_name, team, game_date, season FROM public.wnba_player_game_log
  UNION ALL SELECT 'NCAAB', player_id, player_name, team, game_date, season FROM public.ncaab_player_game_log
  UNION ALL SELECT 'NCAABW', player_id, player_name, team, game_date, season FROM public.ncaabw_player_game_log
  UNION ALL SELECT 'NFL', player_id, player_name, team, game_date, season FROM public.nfl_player_game_log
  UNION ALL SELECT 'NCAAF', player_id, player_name, team, game_date, season FROM public.ncaaf_player_game_log
  UNION ALL SELECT 'NHL', player_id::text, player_name, team, game_date, season FROM public.nhl_skater_game_log
  UNION ALL SELECT 'NHL', player_id::text, player_name, team, game_date, season FROM public.nhl_goalie_game_log
  UNION ALL SELECT 'MLB', player_id, player_name, team, game_date, season FROM public.player_game_log
  UNION ALL SELECT 'UFC', fighter_id, fighter_name, NULL, game_date, season FROM public.ufc_fight_log;

  -- One row per NCAAF game; twins collapsed (mcp_stats_games_twins_2026_11_21.sql).
  CREATE OR REPLACE VIEW mcp_stats.games AS
  SELECT g.sport, g.game_id, g.game_date, g.season,
         coalesce(g.first_pitch_at, g.commence_time) AS starts_at,
         g.home_team, g.away_team, g.home_score, g.away_score,
         (g.home_score IS NOT NULL AND g.away_score IS NOT NULL) AS final,
         ARRAY[g.game_id] AS alias_ids
    FROM public.games g
   WHERE g.sport <> 'NCAAF'
  UNION ALL
  SELECT t.sport, t.game_id, coalesce(t.et_date, t.game_date), t.season, t.starts_at,
         t.home_team, t.away_team,
         coalesce(t.home_score, t.twin_home_score),
         coalesce(t.away_score, t.twin_away_score),
         (coalesce(t.home_score, t.twin_home_score) IS NOT NULL
          AND coalesce(t.away_score, t.twin_away_score) IS NOT NULL),
         t.alias_ids
    FROM (
      SELECT g.sport, g.game_id, g.game_date, g.season,
             coalesce(g.first_pitch_at, g.commence_time) AS starts_at,
             to_char(nullif(coalesce(g.first_pitch_at, g.commence_time), '')::timestamptz
                     AT TIME ZONE 'America/New_York', 'YYYY-MM-DD') AS et_date,
             g.home_team, g.away_team, g.home_score, g.away_score,
             max(g.home_score) OVER w AS twin_home_score,
             max(g.away_score) OVER w AS twin_away_score,
             array_agg(g.game_id) OVER w AS alias_ids,
             row_number() OVER (w ORDER BY
               (g.game_date = to_char(nullif(coalesce(g.first_pitch_at, g.commence_time), '')::timestamptz
                                      AT TIME ZONE 'America/New_York', 'YYYY-MM-DD')) DESC NULLS LAST,
               (g.data_source IS DISTINCT FROM 'cfbd') DESC,
               g.game_id) AS rn
        FROM public.games g
       WHERE g.sport = 'NCAAF'
      WINDOW w AS (PARTITION BY g.home_team, g.away_team,
                   coalesce(to_char(nullif(coalesce(g.first_pitch_at, g.commence_time), '')::timestamptz
                                    AT TIME ZONE 'America/New_York', 'YYYY-MM-DD'),
                            g.game_id))
    ) t
   WHERE t.rn = 1;

  -- Pre-game only: a quote taken after the start is an in-play price.
  CREATE OR REPLACE VIEW mcp_stats.prop_prices AS
  -- Main and alternate lines (mcp_stats_alt_lines_2026_11_21.sql, Matt
  -- 2026-11-21): market is the base market, is_alternate names the feed.
  SELECT g.sport, p.game_id,
         regexp_replace(p.market, '_alternate$', '') AS market,
         p.player_name, p.team, b.book,
         p.line, p.over_price, p.under_price, p.snapshot_at,
         (p.market LIKE '%\_alternate' ESCAPE '\') AS is_alternate
    FROM public.latest_prop_odds p
    JOIN mcp_stats.books b ON b.book_key = p.bookmaker
    JOIN public.games g ON g.game_id = p.game_id
   WHERE (g.commence_time IS NULL OR p.snapshot_at <= g.commence_time);

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

  -- Readable by the connector's read role only.
  REVOKE ALL ON ALL TABLES IN SCHEMA mcp_stats FROM PUBLIC, anon, authenticated, mcp_meter_role;
  GRANT SELECT ON ALL TABLES IN SCHEMA mcp_stats TO mcp_reader;
END
$views$;
