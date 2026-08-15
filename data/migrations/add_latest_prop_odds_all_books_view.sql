-- add_latest_prop_odds_all_books_view
-- Applied to Supabase 2026-08-01 (session: multiple-betting-lines).
--
-- Prop analog of v_latest_odds_all_books. player_prop_odds became multi-book in
-- the same session (prop_odds_ingestor now parses every returned bookmaker, not
-- just DraftKings), so the app needs a bounded "latest line per book" read to
-- line-shop props the way it already line-shops game markets.
--
-- DISPLAY ONLY. The models score props against DraftKings exclusively —
-- models/scorer.py `_get_prop_dk_odds` reads player_prop_odds directly with
-- `bookmaker = 'draftkings'` and never touches this view.
-- tests/test_multi_book_odds.py asserts that filter still exists.
--
-- security_invoker = on: repo convention so the view respects caller RLS and
-- doesn't trip the security_definer_view advisor ERROR. player_prop_odds already
-- has an anon SELECT policy (session 18b), so anon reads resolve through it.
--
-- Unlike the game-market view this needs no join to `games` — player_prop_odds
-- carries game_date itself.

CREATE OR REPLACE VIEW public.v_latest_prop_odds_all_books
WITH (security_invoker = on) AS
SELECT DISTINCT ON (p.game_id, p.market, p.player_name, p.bookmaker)
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
ORDER BY p.game_id, p.market, p.player_name, p.bookmaker, p.snapshot_at DESC;

GRANT SELECT ON public.v_latest_prop_odds_all_books TO anon, authenticated;
