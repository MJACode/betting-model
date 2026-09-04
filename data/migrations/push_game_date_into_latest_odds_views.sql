-- push_game_date_into_latest_odds_views
-- Applied to Supabase 2026-09-04 (session: player-stats-line-availability).
--
-- THE STATS TAB TIMED OUT on "Couldn't load today's lines — canceling statement
-- due to statement timeout (57014)". Measured before touching anything:
--
--   explain (costs off) select ... from v_latest_odds_all_books
--                       where game_date = '2026-09-04'
--   -> Subquery Scan  Filter: (game_date = ...)      <- applied LAST
--        -> Unique -> Incremental Sort
--             -> Merge Join (games ⋈ odds)
--                  -> Seq Scan on odds               <- ALL 2.7M rows, 1.3 GB
--
-- The date filter sits OUTSIDE the DISTINCT ON. Postgres will only push a
-- predicate through DISTINCT ON when it references the DISTINCT ON keys — any
-- other column could change which row survives the dedup — and game_date was
-- not a key. So every read of "today's lines" deduplicated the entire history
-- of the odds table first and threw away all but ~600 rows. pg_stat_statements:
-- 442 calls at a 635 ms mean and a 2.9 s max from the Picks screen (which
-- swallows the error, so it never showed), and an outright timeout the moment
-- the database was busy.
--
-- THE FIX IS ONE COLUMN IN THE KEY. game_id determines game_date — one game,
-- one date — so DISTINCT ON (game_date, game_id, market, bookmaker) groups the
-- rows IDENTICALLY to DISTINCT ON (game_id, market, bookmaker). The output is
-- byte-for-byte the same. What changes is that the predicate is now on a key,
-- so it pushes down, and the plan becomes:
--
--   -> Unique -> Sort
--        -> Nested Loop
--             -> Index Scan idx_games_date   Index Cond: game_date = ...
--             -> Index Scan idx_odds_game    Index Cond: game_id = g.game_id
--
-- Today's ~15 games, then their odds rows by index. Same shape for the prop
-- view, where game_date is on the table itself: idx_prop_odds_date does the
-- work and the market predicate (already a key) rides along.
--
-- Column list and order are unchanged, so CREATE OR REPLACE is legal and every
-- caller (fetchPicksForDate, fetchGameLinesForDate, fetchPropLinesForDate,
-- fetchPickById) keeps working with no client change. security_invoker stays
-- on: tests/test_anon_grant_migration.py pins that these run as the caller.

CREATE OR REPLACE VIEW public.v_latest_odds_all_books
WITH (security_invoker = on) AS
SELECT DISTINCT ON (g.game_date, o.game_id, o.market, o.bookmaker)
       o.game_id,
       g.game_date,
       o.market,
       o.bookmaker,
       o.home_price,
       o.away_price,
       o.over_price,
       o.under_price,
       o.spread_home,
       o.total_line,
       o.home_link,
       o.away_link,
       o.over_link,
       o.under_link,
       o.snapshot_at
FROM odds o
JOIN games g ON g.game_id = o.game_id
WHERE o.bookmaker <> 'sbr_consensus'
  AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
ORDER BY g.game_date, o.game_id, o.market, o.bookmaker, o.snapshot_at DESC;

CREATE OR REPLACE VIEW public.v_latest_prop_odds_all_books
WITH (security_invoker = on) AS
SELECT DISTINCT ON (p.game_date, p.market, p.game_id, p.player_name, p.bookmaker)
       p.game_id,
       p.game_date,
       p.market,
       p.player_name,
       p.team,
       p.bookmaker,
       p.line,
       p.over_price,
       p.under_price,
       p.over_link,
       p.under_link,
       p.snapshot_at
FROM player_prop_odds p
WHERE p.snapshot_type IS NULL OR p.snapshot_type <> 'in_play'
ORDER BY p.game_date, p.market, p.game_id, p.player_name, p.bookmaker, p.snapshot_at DESC;

-- Grants are unchanged by CREATE OR REPLACE; restated so the file stands alone.
GRANT SELECT ON public.v_latest_odds_all_books TO anon, authenticated;
GRANT SELECT ON public.v_latest_prop_odds_all_books TO anon, authenticated;
