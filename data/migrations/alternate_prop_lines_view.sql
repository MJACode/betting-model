-- alternate_prop_lines_view
-- Applied to Supabase 2026-09-05 (session: player-stats-line-availability).
--
-- ALTERNATE LINES (Matt, 2026-09-05: "Yes to alternate lines"). The prop
-- ingestor now writes The Odds API's `*_alternate` markets under their own
-- market key, one row per (player, line) -- 2+/3+ hits under
-- batter_hits_alternate beside the standard batter_hits line
-- (config.PROP_ALT_MARKETS has the reasoning and the measured cost).
--
-- v_latest_prop_odds_all_books returned ONE row per (game, market, player,
-- bookmaker): the newest snapshot. That is exactly right for a standard
-- market, where "the line" is one number that MOVES during the day (678 of
-- 2,092 batter_hits keys on 2026-09-04 changed line between passes), so a
-- per-line key would keep the morning's 0.5 beside the evening's 1.5 as if
-- both were current. It is exactly wrong for an alternate market, where one
-- pass writes 2+, 3+ and 4+ together and the newest single row is an
-- arbitrary one of them.
--
-- So: for a standard market the view is unchanged -- the one newest row, from
-- the same top-1 probe on idx_prop_odds_line_snap. For an alternate market it
-- returns EVERY row the newest pass wrote for that player and book, found by
-- equality on all five index columns (the probe's snapshot_at), which is an
-- index range of a handful of rows. Same columns, same order, same types;
-- the skip scan and the in_play exclusion are untouched. No new index.
--
-- Standard keys keep one row: the ingestor keys a standard market by (market,
-- player) per book, so a pass writes one row per key; the 1,546 keys since
-- 08-29 with two rows at one snapshot_at are doubleheaders sharing a game_id
-- (both games' props land under MLB_<date>_<away>_<home>), a pre-existing
-- collision this view does not change either way.

CREATE OR REPLACE VIEW public.v_latest_prop_odds_all_books
WITH (security_invoker = on) AS
SELECT g.game_id,
       g.game_date,
       pb.market,
       pb.player_name,
       r.team,
       pb.bookmaker,
       r.line,
       r.over_price,
       r.under_price,
       r.over_link,
       r.under_link,
       r.snapshot_at
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
) l
CROSS JOIN LATERAL (
  -- A standard market: the one newest row, exactly as before.
  SELECT l.team, l.line, l.over_price, l.under_price,
         l.over_link, l.under_link, l.snapshot_at
   WHERE pb.market NOT LIKE '%\_alternate'
  UNION ALL
  -- An alternate market: every line the newest pass wrote for this player
  -- and book. Equality on all five index columns.
  SELECT p.team, p.line, p.over_price, p.under_price,
         p.over_link, p.under_link, p.snapshot_at
    FROM player_prop_odds p
   WHERE pb.market LIKE '%\_alternate'
     AND p.game_id = g.game_id
     AND p.market = pb.market
     AND p.player_name = pb.player_name
     AND p.bookmaker = pb.bookmaker
     AND p.snapshot_at = l.snapshot_at
) r;
