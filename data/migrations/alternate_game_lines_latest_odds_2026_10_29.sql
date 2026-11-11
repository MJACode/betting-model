-- alternate_game_lines_latest_odds_2026_10_29
--
-- HAND-APPLIED. Not in data/view_migrations.ACTIVE_MIGRATIONS. Matt runs
-- this in the SQL editor. Until it is applied, latest_odds keeps one row per
-- (game, market, book), so an alternate ladder written by the odds ingestor
-- collapses to whichever rung inserted last. The edit sheet then shows that
-- one extra number, not the ladder.
--
-- After this is applied, the next live odds pass rewrites upcoming games:
-- the insert trigger deletes the older collapsed row and keeps every rung of
-- the new snapshot. No backfill is required for the betslip. A rebuild of a
-- recent snapshot_at window is optional and safe to repeat.
--
-- What changes: latest_odds gains line_key. Main markets (h2h, spreads,
-- totals, and everything else) stay one row, line_key 0. alternate_spreads
-- and alternate_totals keep every rung of the newest pre-game snapshot,
-- line_key = the home spread or the total. Same rule as latest_prop_odds
-- for *_alternate markets. The views are not replaced: they already return
-- every latest_odds row, and their column lists stay the ones the app pins.
--
-- The table is one row per line, so the lock is short. Run the file as one
-- script.

ALTER TABLE public.latest_odds
    ADD COLUMN IF NOT EXISTS line_key NUMERIC NOT NULL DEFAULT 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM information_schema.key_column_usage
         WHERE table_schema = 'public'
           AND table_name = 'latest_odds'
           AND constraint_name = 'latest_odds_pkey'
           AND column_name = 'line_key'
    ) THEN
        ALTER TABLE public.latest_odds DROP CONSTRAINT latest_odds_pkey;
        ALTER TABLE public.latest_odds
            ADD PRIMARY KEY (game_id, market, bookmaker, line_key);
    END IF;
END $$;

-- 0 for a main market, so it stays one row. The rung for an alternate ladder.
CREATE OR REPLACE FUNCTION public.latest_odds_line_key(p_market TEXT, p_spread NUMERIC, p_total NUMERIC)
RETURNS NUMERIC
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
             WHEN p_market IN ('alternate_spreads', 'alternate_totals')
             THEN COALESCE(p_spread, p_total)
             ELSE 0::numeric
           END
$$;

REVOKE ALL ON FUNCTION public.latest_odds_line_key(TEXT, NUMERIC, NUMERIC)
    FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.latest_odds_on_insert() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    -- A newer snapshot replaces the whole key, including a collapsed
    -- line_key 0 row written before this migration. An equal snapshot on a
    -- ladder adds rungs and does not retire its siblings (executemany is one
    -- row per statement). A main market at the same snapshot keeps one row.
    DELETE FROM latest_odds l
     USING (SELECT n.game_id, n.market, n.bookmaker, MAX(n.snapshot_at) AS snap
              FROM new_rows n
             WHERE n.game_id IS NOT NULL AND n.market IS NOT NULL
               AND n.bookmaker IS NOT NULL AND n.snapshot_at IS NOT NULL
               AND (n.snapshot_type IS NULL OR n.snapshot_type <> 'in_play')
               AND (n.market NOT IN ('alternate_spreads', 'alternate_totals')
                    OR COALESCE(n.spread_home, n.total_line) IS NOT NULL)
             GROUP BY 1, 2, 3) k
     WHERE l.game_id = k.game_id AND l.market = k.market AND l.bookmaker = k.bookmaker
       AND (l.snapshot_at < k.snap
            OR (l.snapshot_at = k.snap
                AND l.market NOT IN ('alternate_spreads', 'alternate_totals')));

    INSERT INTO latest_odds (game_id, market, bookmaker, line_key, snapshot_at, odds_id, sport,
                             home_price, away_price, draw_price, spread_home, total_line,
                             over_price, under_price,
                             home_link, away_link, draw_link, over_link, under_link)
    SELECT c.game_id, c.market, c.bookmaker,
           public.latest_odds_line_key(c.market, c.spread_home, c.total_line),
           c.snapshot_at, c.odds_id, c.sport,
           c.home_price, c.away_price, c.draw_price, c.spread_home, c.total_line,
           c.over_price, c.under_price,
           c.home_link, c.away_link, c.draw_link, c.over_link, c.under_link
      FROM (SELECT n.*,
                   MAX(n.snapshot_at) OVER (PARTITION BY n.game_id, n.market, n.bookmaker) AS snap,
                   ROW_NUMBER() OVER (
                       PARTITION BY n.game_id, n.market, n.bookmaker,
                                    CASE WHEN n.market IN ('alternate_spreads', 'alternate_totals')
                                         THEN COALESCE(n.spread_home, n.total_line) END
                       ORDER BY n.snapshot_at DESC, n.odds_id DESC) AS rn
              FROM new_rows n
             WHERE n.game_id IS NOT NULL AND n.market IS NOT NULL
               AND n.bookmaker IS NOT NULL AND n.snapshot_at IS NOT NULL
               AND (n.snapshot_type IS NULL OR n.snapshot_type <> 'in_play')
               AND (n.market NOT IN ('alternate_spreads', 'alternate_totals')
                    OR COALESCE(n.spread_home, n.total_line) IS NOT NULL)) c
     WHERE c.snapshot_at = c.snap AND c.rn = 1
       AND NOT EXISTS (SELECT 1 FROM latest_odds l
                        WHERE l.game_id = c.game_id AND l.market = c.market
                          AND l.bookmaker = c.bookmaker
                          AND l.snapshot_at > c.snapshot_at)
    ON CONFLICT (game_id, market, bookmaker, line_key) DO UPDATE SET
           snapshot_at = EXCLUDED.snapshot_at, odds_id = EXCLUDED.odds_id, sport = EXCLUDED.sport,
           home_price = EXCLUDED.home_price, away_price = EXCLUDED.away_price,
           draw_price = EXCLUDED.draw_price, spread_home = EXCLUDED.spread_home,
           total_line = EXCLUDED.total_line, over_price = EXCLUDED.over_price,
           under_price = EXCLUDED.under_price,
           home_link = EXCLUDED.home_link, away_link = EXCLUDED.away_link,
           draw_link = EXCLUDED.draw_link, over_link = EXCLUDED.over_link,
           under_link = EXCLUDED.under_link
     WHERE EXCLUDED.snapshot_at >= latest_odds.snapshot_at;
    RETURN NULL;
END $$;

CREATE OR REPLACE FUNCTION public.latest_odds_recompute(p_game_id TEXT, p_market TEXT, p_bookmaker TEXT) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    IF p_game_id IS NULL OR p_market IS NULL OR p_bookmaker IS NULL THEN RETURN; END IF;
    DELETE FROM latest_odds
     WHERE game_id = p_game_id AND market = p_market AND bookmaker = p_bookmaker;
    INSERT INTO latest_odds (game_id, market, bookmaker, line_key, snapshot_at, odds_id, sport,
                             home_price, away_price, draw_price, spread_home, total_line,
                             over_price, under_price,
                             home_link, away_link, draw_link, over_link, under_link)
    SELECT DISTINCT ON (
               CASE WHEN o.market IN ('alternate_spreads', 'alternate_totals')
                    THEN COALESCE(o.spread_home, o.total_line) END)
           o.game_id, o.market, o.bookmaker,
           public.latest_odds_line_key(o.market, o.spread_home, o.total_line),
           o.snapshot_at, o.odds_id, o.sport,
           o.home_price, o.away_price, o.draw_price, o.spread_home, o.total_line,
           o.over_price, o.under_price,
           o.home_link, o.away_link, o.draw_link, o.over_link, o.under_link
      FROM odds o
     WHERE o.game_id = p_game_id AND o.market = p_market AND o.bookmaker = p_bookmaker
       AND o.snapshot_at IS NOT NULL
       AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
       AND (o.market NOT IN ('alternate_spreads', 'alternate_totals')
            OR COALESCE(o.spread_home, o.total_line) IS NOT NULL)
       AND o.snapshot_at = (
            SELECT MAX(o2.snapshot_at) FROM odds o2
             WHERE o2.game_id = p_game_id AND o2.market = p_market
               AND o2.bookmaker = p_bookmaker
               AND o2.snapshot_at IS NOT NULL
               AND (o2.snapshot_type IS NULL OR o2.snapshot_type <> 'in_play')
               AND (o2.market NOT IN ('alternate_spreads', 'alternate_totals')
                    OR COALESCE(o2.spread_home, o2.total_line) IS NOT NULL))
     ORDER BY CASE WHEN o.market IN ('alternate_spreads', 'alternate_totals')
                   THEN COALESCE(o.spread_home, o.total_line) END,
              o.odds_id DESC;
END $$;

-- A range contributes its newest snapshot per key. An older chunk cannot put
-- a rung back once a newer snapshot is already stored, and a newer chunk
-- drops rungs the older snapshot had. Repeating a chunk does not move a
-- newer row backwards.
CREATE OR REPLACE FUNCTION public.latest_lines_rebuild_odds(p_from TEXT, p_to TEXT) RETURNS BIGINT
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE n BIGINT;
BEGIN
    DELETE FROM latest_odds l
     USING (SELECT o.game_id, o.market, o.bookmaker, MAX(o.snapshot_at) AS snap
              FROM odds o
             WHERE o.snapshot_at >= p_from AND o.snapshot_at < p_to
               AND o.game_id IS NOT NULL AND o.market IS NOT NULL AND o.bookmaker IS NOT NULL
               AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
             GROUP BY 1, 2, 3) k
     WHERE l.game_id = k.game_id AND l.market = k.market AND l.bookmaker = k.bookmaker
       AND l.snapshot_at < k.snap;

    INSERT INTO latest_odds (game_id, market, bookmaker, line_key, snapshot_at, odds_id, sport,
                             home_price, away_price, draw_price, spread_home, total_line,
                             over_price, under_price,
                             home_link, away_link, draw_link, over_link, under_link)
    SELECT c.game_id, c.market, c.bookmaker,
           public.latest_odds_line_key(c.market, c.spread_home, c.total_line),
           c.snapshot_at, c.odds_id, c.sport,
           c.home_price, c.away_price, c.draw_price, c.spread_home, c.total_line,
           c.over_price, c.under_price,
           c.home_link, c.away_link, c.draw_link, c.over_link, c.under_link
      FROM (SELECT o.*,
                   MAX(o.snapshot_at) OVER (PARTITION BY o.game_id, o.market, o.bookmaker) AS snap,
                   ROW_NUMBER() OVER (
                       PARTITION BY o.game_id, o.market, o.bookmaker,
                                    CASE WHEN o.market IN ('alternate_spreads', 'alternate_totals')
                                         THEN COALESCE(o.spread_home, o.total_line) END
                       ORDER BY o.snapshot_at DESC, o.odds_id DESC) AS rn
              FROM odds o
             WHERE o.snapshot_at >= p_from AND o.snapshot_at < p_to
               AND o.game_id IS NOT NULL AND o.market IS NOT NULL AND o.bookmaker IS NOT NULL
               AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
               AND (o.market NOT IN ('alternate_spreads', 'alternate_totals')
                    OR COALESCE(o.spread_home, o.total_line) IS NOT NULL)) c
     WHERE c.snapshot_at = c.snap AND c.rn = 1
       AND NOT EXISTS (SELECT 1 FROM latest_odds l
                        WHERE l.game_id = c.game_id AND l.market = c.market
                          AND l.bookmaker = c.bookmaker
                          AND l.snapshot_at > c.snapshot_at)
    ON CONFLICT (game_id, market, bookmaker, line_key) DO UPDATE SET
           snapshot_at = EXCLUDED.snapshot_at, odds_id = EXCLUDED.odds_id, sport = EXCLUDED.sport,
           home_price = EXCLUDED.home_price, away_price = EXCLUDED.away_price,
           draw_price = EXCLUDED.draw_price, spread_home = EXCLUDED.spread_home,
           total_line = EXCLUDED.total_line, over_price = EXCLUDED.over_price,
           under_price = EXCLUDED.under_price,
           home_link = EXCLUDED.home_link, away_link = EXCLUDED.away_link,
           draw_link = EXCLUDED.draw_link, over_link = EXCLUDED.over_link,
           under_link = EXCLUDED.under_link
     WHERE EXCLUDED.snapshot_at > latest_odds.snapshot_at;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END $$;
