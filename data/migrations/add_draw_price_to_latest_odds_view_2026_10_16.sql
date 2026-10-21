-- Hand-applied. Matt runs this in the SQL editor. It is NOT in
-- data/view_migrations.ACTIVE_MIGRATIONS: tests/test_latest_odds_views.py
-- forbids any active file from CREATE OR REPLACE-ing
-- public.v_latest_odds_all_books (that would put the odds-log walk back).
--
-- Measured 2026-10-16 on vvprgnrmzeekokzkrkfu: latest_odds.draw_price exists,
-- v_latest_odds_all_books does not return it, security_invoker=on, and anon
-- already has SELECT. This appends l.draw_price after snapshot_at. CREATE OR
-- REPLACE refuses a column reorder, so a second run is a no-op and a drifted
-- view fails instead of dropping a column.
--
-- The Lines board selects the column and retries without it until this lands,
-- so the app does not break before the apply. After it lands, the NHL 60-min
-- sheet shows the tie price with no app release.

CREATE OR REPLACE VIEW public.v_latest_odds_all_books
WITH (security_invoker = on) AS
SELECT g.game_id,
       g.game_date,
       l.market,
       l.bookmaker,
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
       l.snapshot_at,
       l.draw_price
FROM games g
JOIN latest_odds l ON l.game_id = g.game_id
WHERE l.bookmaker <> 'sbr_consensus';

GRANT SELECT ON public.v_latest_odds_all_books TO anon, authenticated;
