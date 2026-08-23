-- add_latest_inplay_odds_all_books_view (applied 2026-08-23)
--
-- In-play analog of v_latest_odds_all_books.
--
-- The live loop already fetches every book in config.LINE_SHOP_BOOKMAKERS (the
-- bulk endpoint's `bookmakers` param counts as ONE region, so extra books cost
-- no credits) and stores them with snapshot_type='in_play'. But BOTH pre-game
-- all-book views deliberately EXCLUDE in_play rows to protect the pre-game /
-- in-play isolation invariant, so the app had no way to read them -- a FanDuel
-- bettor on the Live tab saw DraftKings prices and a "Bet on DraftKings" button.
-- This view exposes the in-play rows, and only them.
--
-- Scoring is unaffected: live_scorer still hard-filters bookmaker='draftkings'.
CREATE OR REPLACE VIEW public.v_latest_inplay_odds_all_books
WITH (security_invoker = on) AS
  SELECT DISTINCT ON (o.game_id, o.market, o.bookmaker)
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
   WHERE o.snapshot_type = 'in_play'
   ORDER BY o.game_id, o.market, o.bookmaker, o.snapshot_at DESC;

GRANT SELECT ON public.v_latest_inplay_odds_all_books TO anon, authenticated;
