-- AI assistant (MCP) connector: alternate prop lines become visible.
--
-- Matt, 2026-11-21: "Yes alt lines". mcp_stats.prop_prices excluded every
-- '%_alternate' market, so the connector only saw each player's main line
-- (one number near his average). A question at any other line -- "Maxey 15+
-- points" -- came back not_found, though the database held it: on 2026-11-21
-- the NBA slate carried 597 player_points rows against 6,090
-- player_points_alternate rows for the same 71 players.
--
-- The view now carries both. `market` is the BASE market (the '_alternate'
-- suffix stripped) so mcp_stats.prop_markets still maps one stat to one
-- market, and the new last column `is_alternate` says which feed a row came
-- from. The edge function reads main lines only when no line is asked for, so
-- "what is his line?" still answers with the main line, not 3.5.
--
-- Same columns as before plus one at the end (CREATE OR REPLACE VIEW can only
-- append), same pre-game bound, same seven books. Grants carry over.
--
-- Idempotent on the PROPERTY this file establishes (prop_prices has an
-- is_alternate column), not on the shape of its own text. mcp_stats_views
-- carries the same definition, so a rerun of that file agrees with this one.

DO $alt$
BEGIN
  IF to_regclass('mcp_stats.prop_prices') IS NULL THEN
    RAISE EXCEPTION 'mcp_stats.prop_prices missing: apply mcp_stats_views_2026_11_21.sql first';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_attribute
     WHERE attrelid = to_regclass('mcp_stats.prop_prices')
       AND attname = 'is_alternate' AND NOT attisdropped
  ) THEN
    RETURN;
  END IF;

  -- Pre-game only: a quote taken after the start is an in-play price.
  CREATE OR REPLACE VIEW mcp_stats.prop_prices AS
  SELECT g.sport, p.game_id,
         regexp_replace(p.market, '_alternate$', '') AS market,
         p.player_name, p.team, b.book,
         p.line, p.over_price, p.under_price, p.snapshot_at,
         (p.market LIKE '%\_alternate' ESCAPE '\') AS is_alternate
    FROM public.latest_prop_odds p
    JOIN mcp_stats.books b ON b.book_key = p.bookmaker
    JOIN public.games g ON g.game_id = p.game_id
   WHERE (g.commence_time IS NULL OR p.snapshot_at <= g.commence_time);

  GRANT SELECT ON mcp_stats.prop_prices TO mcp_reader;
END
$alt$;
