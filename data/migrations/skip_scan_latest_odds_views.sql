-- skip_scan_latest_odds_views
-- Applied to Supabase 2026-09-04 (session: player-stats-line-availability).
--
-- "COULDN'T LOAD TODAY'S LINES" WAS STILL FIRING AFTER push_game_date_into_latest_odds_views.
-- The postgres log for one minute (2026-09-04 20:28 UTC) held 41 statement
-- timeouts across EVERY view the app reads -- v_latest_dk_odds,
-- v_latest_odds_all_books, v_latest_prop_odds_all_books, v_live_game_state_latest
-- -- and the same storm recurs several times a day (43 at 22:50, 41 at 23:50,
-- 38 at 14:00, 44 at 16:20). pg_stat_activity at the time: two identical
-- worker queries 27 s into a DataFileRead wait, the pre-game line poller's
-- fingerprint seed, a Parallel Seq Scan of the whole 842 MB odds table
-- (shared read=88,408 pages) every 15 minutes, from BOTH Railway services.
-- The poller is fixed on its own side (data/ingestors/pregame_line_poller.py:
-- the seed now probes only the keys the API quoted). This migration makes the
-- app's reads cheap enough that a background scan cannot push them over the
-- 8 s / 3 s statement timeouts again.
--
-- WHY DISTINCT ON IS THE WRONG SHAPE FOR "LATEST PER KEY" HERE. The refresh
-- pass writes every book's line on every pass, so one game carries ~2,400
-- pre-game odds rows by evening and one day of props is ~168,000 rows for
-- ~14,600 distinct (game, market, player, book) keys. DISTINCT ON must fetch
-- every one of those rows from the heap to keep the newest per key -- the
-- cost is the ROWS READ, not the sort:
--
--   v_latest_odds_all_books, game_date = today (41 games), as `authenticated`:
--     DISTINCT ON  3,739 ms   98,941 rows read, 24 MB external sort
--     skip-scan      439 ms    1,180 rows read, no sort
--   v_latest_prop_odds_all_books, game_date = today, every market (the Picks screen):
--     DISTINCT ON  4,541 ms  168,651 rows read
--     skip-scan      653 ms   14,580 rows read
--   v_latest_prop_odds_all_books, game_date = today AND market = 'batter_hits' (the Stats board):
--     DISTINCT ON    768 ms  (168,651 index entries, 145,145 filtered after the heap fetch)
--     skip-scan      653 ms  (the market filter applies to the view's output; see below)
--
-- THE SHAPE. Drive from `games` (so the app's game_date / game_id filters land
-- on idx_games_date / the primary key), then per game:
--   1. enumerate the distinct (market, bookmaker) -- or (market, player_name,
--      bookmaker) -- keys with a recursive "skip scan": each step is one index
--      probe for the next key greater than the last, so a game with 30 keys
--      costs 31 probes however many snapshots it has;
--   2. for each key, ONE backward index probe for the newest pre-game row.
-- Both halves run on idx_odds_book_snap (game_id, market, bookmaker,
-- snapshot_at) and, for props, idx_prop_odds_line_snap (game_id, market,
-- player_name, bookmaker, snapshot_at), created CONCURRENTLY beforehand:
--
--   CREATE INDEX CONCURRENTLY idx_prop_odds_line_snap
--     ON public.player_prop_odds (game_id, market, player_name, bookmaker, snapshot_at);
--
-- (CONCURRENTLY cannot run inside this migration's transaction; it was run on
-- its own first, 337 MB, valid.) idx_prop_odds_game (game_id, market) is a
-- prefix of it and is dropped below; idx_prop_odds_date_line, an intermediate
-- attempt that only helped the market-filtered read (211 ms), is dropped too --
-- 370 MB for 200 ms on one screen is not a trade.
--
-- SEMANTICS ARE UNCHANGED, checked rather than assumed:
--   * same columns, same order, same types (CREATE OR REPLACE VIEW enforces it);
--   * same exclusions: sbr_consensus, in_play snapshots; a key whose only rows
--     are in_play yields no row, exactly as DISTINCT ON did;
--   * "newest" is still ORDER BY snapshot_at DESC on the TEXT column, as both
--     views have always done. Measured before relying on the index order for
--     it: over every (game, market, book) key since 2026-09-01 (7,348 keys),
--     the text-latest row and max(snapshot_at::timestamptz) disagreed 0 times;
--     482,349 of 482,457 DK pre-game rows for unstarted games are the 20-char
--     'Z' shape, and the 108 offset-shaped rows are never the newest;
--   * game_date comes from `games` in both views now. For player_prop_odds
--     that is a change of SOURCE, not value: 0 rows since 2026-08-28 disagree
--     with games.game_date and 0 rows lack a games row.
--
-- The market filter on props is applied to the view's output, not pushed into
-- the recursive CTE (Postgres does not push predicates into recursive CTEs), so
-- the Stats board pays the whole-day cost. 653 ms against an 8 s timeout, with
-- the poller's scan gone, is the headroom this needed; a per-market RPC would
-- get the last 500 ms back and is not worth an app change today.
--
-- security_invoker = on and the anon/authenticated SELECT grants are preserved
-- by CREATE OR REPLACE. Read-only DDL apart from the two DROP INDEX, which take
-- a brief lock and fire the PostgREST schema reload once.

CREATE OR REPLACE VIEW public.v_latest_odds_all_books
WITH (security_invoker = on) AS
SELECT g.game_id,
       g.game_date,
       mb.market,
       mb.bookmaker,
       l.home_price,
       l.away_price,
       l.over_price,
       l.under_price,
       l.spread_home,
       l.total_line,
       l.home_link,
       l.away_link,
       l.over_link,
       l.under_link,
       l.snapshot_at
FROM games g
CROSS JOIN LATERAL (
  WITH RECURSIVE s AS (
    (SELECT o.market, o.bookmaker
       FROM odds o
      WHERE o.game_id = g.game_id
      ORDER BY o.market, o.bookmaker
      LIMIT 1)
    UNION ALL
    SELECT n.market, n.bookmaker
      FROM s
      CROSS JOIN LATERAL (
        SELECT o.market, o.bookmaker
          FROM odds o
         WHERE o.game_id = g.game_id
           AND (o.market, o.bookmaker) > (s.market, s.bookmaker)
         ORDER BY o.market, o.bookmaker
         LIMIT 1) n
  )
  SELECT s.market, s.bookmaker FROM s WHERE s.bookmaker <> 'sbr_consensus'
) mb
CROSS JOIN LATERAL (
  SELECT o.home_price, o.away_price, o.over_price, o.under_price,
         o.spread_home, o.total_line,
         o.home_link, o.away_link, o.over_link, o.under_link,
         o.snapshot_at
    FROM odds o
   WHERE o.game_id = g.game_id
     AND o.market = mb.market
     AND o.bookmaker = mb.bookmaker
     AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
   ORDER BY o.snapshot_at DESC
   LIMIT 1
) l;

CREATE OR REPLACE VIEW public.v_latest_prop_odds_all_books
WITH (security_invoker = on) AS
SELECT g.game_id,
       g.game_date,
       pb.market,
       pb.player_name,
       l.team,
       pb.bookmaker,
       l.line,
       l.over_price,
       l.under_price,
       l.over_link,
       l.under_link,
       l.snapshot_at
FROM games g
CROSS JOIN LATERAL (
  WITH RECURSIVE s AS (
    (SELECT p.market, p.player_name, p.bookmaker
       FROM player_prop_odds p
      WHERE p.game_id = g.game_id
      ORDER BY p.market, p.player_name, p.bookmaker
      LIMIT 1)
    UNION ALL
    SELECT n.market, n.player_name, n.bookmaker
      FROM s
      CROSS JOIN LATERAL (
        SELECT p.market, p.player_name, p.bookmaker
          FROM player_prop_odds p
         WHERE p.game_id = g.game_id
           AND (p.market, p.player_name, p.bookmaker) > (s.market, s.player_name, s.bookmaker)
         ORDER BY p.market, p.player_name, p.bookmaker
         LIMIT 1) n
  )
  SELECT s.market, s.player_name, s.bookmaker FROM s
) pb
CROSS JOIN LATERAL (
  SELECT p.team, p.line, p.over_price, p.under_price,
         p.over_link, p.under_link, p.snapshot_at
    FROM player_prop_odds p
   WHERE p.game_id = g.game_id
     AND p.market = pb.market
     AND p.player_name = pb.player_name
     AND p.bookmaker = pb.bookmaker
     AND (p.snapshot_type IS NULL OR p.snapshot_type <> 'in_play')
   ORDER BY p.snapshot_at DESC
   LIMIT 1
) l;

DROP INDEX IF EXISTS public.idx_prop_odds_date_line;
DROP INDEX IF EXISTS public.idx_prop_odds_game;
