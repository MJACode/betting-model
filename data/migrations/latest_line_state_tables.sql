-- latest_line_state_tables
-- Applied to Supabase 2026-09-05 (session: stats-page-lines-issue).
--
-- "COULDN'T LOAD TODAY'S LINES" FOR THE FOURTH SESSION IN A ROW, and this time
-- the read failed ALONE. Measured as `authenticated` before anything was touched
-- (2026-09-05, a 157-game college-football Saturday, 401,873 prop rows for the day):
--
--   v_latest_prop_odds_all_books, today, batter_hits (the Stats board)  10,512 ms
--   v_latest_dk_odds, today (the Picks screen + three look-ahead cards)  17,945 ms
--   v_live_game_state_latest, today (the live score banner)               2,001 ms
--
-- against an 8 s statement timeout. 282 timeouts in the preceding 24 hours,
-- 189 of them v_latest_dk_odds. No background scan was needed: the day was
-- simply bigger than the day the previous fix was measured on.
--
-- WHY EVERY PREVIOUS FIX WAS TEMPORARY. All three views answer "the newest row
-- per key" over an append-only log that grows ~370,000 odds rows and ~400,000
-- prop rows a day. Each fix changed HOW the log was walked:
--
--   session 221  push game_date into the DISTINCT ON key       91 s  ->  3.4 s
--   session 222  recursive skip scan, one probe per key       3.7 s  ->  0.3 s (41 games)
--   today        the same skip scan on 157 games                        10.5 s
--
-- and none changed the fact that the walk is proportional to the day's keys
-- (34,124 skip-scan steps today, with 34,078 heap fetches because the newest
-- pages are never in the visibility map) or, for v_latest_dk_odds, to the
-- whole table (1,089,880 DraftKings rows read and sorted on disk to return 280).
-- A read whose cost scales with the log will cross any timeout on some day;
-- the only permanent shape is one whose cost scales with the ANSWER.
--
-- THE SHAPE. Three small current-state tables, one row per line, maintained at
-- WRITE time by triggers on the log tables, and the three views become plain
-- joins against them. The cost moves to the writer -- one primary-key upsert per
-- inserted row, ~0.1 ms -- where it is paid once, instead of to every reader,
-- where it was paid on every open of every screen.
--
--   latest_odds              (game_id, market, bookmaker)                 newest pre-game row
--   latest_prop_odds         (game_id, market, player_name, bookmaker, line)
--                              standard market: the one newest row;
--                              *_alternate market: every line at the newest snapshot
--                              (alternate_prop_lines_view has the reasoning)
--   latest_live_game_state   (game_id)                                    newest snapshot
--
-- SEMANTICS ARE THE VIEWS' OWN, restated so nobody re-derives them:
--   * "newest" is ORDER BY snapshot_at DESC on the TEXT column, ties broken by
--     the row id -- exactly what the views did (skip_scan_latest_odds_views
--     measured text order == timestamptz order on every key since 09-01).
--   * in_play snapshots never enter latest_odds / latest_prop_odds; a key whose
--     only rows are in_play has no state row, as it had no view row.
--   * A row with a NULL key column, NULL snapshot_at or (props) NULL line is
--     not a line and is skipped. pg_stats: null_frac 0 on every one of them.
--   * sbr_consensus is stored (it is a book's latest line) and excluded in
--     v_latest_odds_all_books, as before. v_latest_dk_odds keeps bookmaker =
--     'draftkings'. ONE DELIBERATE CHANGE: v_latest_dk_odds used to have no
--     snapshot_type filter, so after first pitch it returned an in-play price
--     as "the latest DK line". It now returns the newest PRE-GAME row, which
--     is what the app shows (it hides lines on started games) and what §6
--     ("pre-game and in-play prices never mix") requires.
--   * game_date comes from `games`, as the views already did.
--
-- WRITERS ARE COVERED WHOLESALE, NOT PER INGESTOR. Eleven modules INSERT into
-- odds and one into player_prop_odds (grep "INSERT INTO odds"); a trigger on the
-- table covers all of them plus any backfill, COPY or hand insert. The triggers
-- are STATEMENT-level with transition tables, so an executemany() of one row
-- costs one upsert and a bulk insert of 10,000 rows costs one DISTINCT ON over
-- the batch rather than 10,000 upserts.
--
-- UPDATES that relabel a row as in_play (odds_ingestor._mark_in_play, the
-- relabel_in_play job, repair_bogus_first_pitch_labels) can retire the row the
-- state table points at, so an UPDATE trigger recomputes the touched keys from
-- the log -- one index probe per key. DELETEs are NOT trapped: data/prune_odds.py
-- keeps the newest pre-game row of every key by construction (rn_last = 1 AND
-- is_pre), so no delete ever removes a state row's source, and a transition
-- table on a multi-million-row prune would be a tuplestore the pruner cannot
-- afford. If that invariant is ever broken, latest_lines_rebuild_* below
-- reconciles a range from the log.
--
-- BACKFILL. The tables start EMPTY; the triggers must exist BEFORE the backfill
-- so nothing written in between is missed. Then, in chunks that fit the MCP's
-- 60 s window:
--   SELECT latest_lines_rebuild_odds('2026-09-01', '2026-09-02');  -- snapshot_at range
--   SELECT latest_lines_rebuild_props('2026-09-01', '2026-09-02'); -- game_date range
--   SELECT latest_lines_rebuild_live_state();
-- Each is safe to re-run: a rebuild never replaces a state row with an older
-- source row, so trigger-written rows (always >= the backfill's) survive.
--
-- Everything below is idempotent. CREATE OR REPLACE VIEW enforces that the
-- column names, order and types are unchanged, so the app's column lists
-- (tests/test_latest_odds_views.py pins them) keep working untouched.

-- ── tables ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.latest_odds (
    game_id      TEXT    NOT NULL,
    market       TEXT    NOT NULL,
    bookmaker    TEXT    NOT NULL,
    snapshot_at  TEXT    NOT NULL,
    odds_id      BIGINT,
    sport        TEXT,
    home_price   NUMERIC,
    away_price   NUMERIC,
    draw_price   NUMERIC,
    spread_home  NUMERIC,
    total_line   NUMERIC,
    over_price   NUMERIC,
    under_price  NUMERIC,
    home_link    TEXT,
    away_link    TEXT,
    draw_link    TEXT,
    over_link    TEXT,
    under_link   TEXT,
    PRIMARY KEY (game_id, market, bookmaker)
);

CREATE TABLE IF NOT EXISTS public.latest_prop_odds (
    game_id      TEXT    NOT NULL,
    market       TEXT    NOT NULL,
    player_name  TEXT    NOT NULL,
    bookmaker    TEXT    NOT NULL,
    line         NUMERIC NOT NULL,
    snapshot_at  TEXT    NOT NULL,
    prop_id      BIGINT,
    team         TEXT,
    over_price   NUMERIC,
    under_price  NUMERIC,
    over_link    TEXT,
    under_link   TEXT,
    PRIMARY KEY (game_id, market, player_name, bookmaker, line)
);

CREATE TABLE IF NOT EXISTS public.latest_live_game_state (
    game_id             TEXT     NOT NULL PRIMARY KEY,
    state_id            BIGINT,
    snapshot_at         TEXT     NOT NULL,
    inning              SMALLINT,
    inning_half         TEXT,
    outs                SMALLINT,
    bases_state         TEXT,
    home_score          SMALLINT,
    away_score          SMALLINT,
    abstract_game_state TEXT
);

-- ── access: the app reads these through security_invoker views ──────────────
-- Same shape as odds / player_prop_odds / live_game_state: RLS on, a read-only
-- policy for the API roles, SELECT granted, every write revoked BY NAME
-- (.claude/rules/operations.md). The triggers write as their SECURITY DEFINER
-- owner, so the API roles never need INSERT.

ALTER TABLE public.latest_odds            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.latest_prop_odds       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.latest_live_game_state ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon read latest_odds"            ON public.latest_odds;
DROP POLICY IF EXISTS "anon read latest_prop_odds"       ON public.latest_prop_odds;
DROP POLICY IF EXISTS "anon read latest_live_game_state" ON public.latest_live_game_state;
CREATE POLICY "anon read latest_odds"            ON public.latest_odds            FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "anon read latest_prop_odds"       ON public.latest_prop_odds       FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "anon read latest_live_game_state" ON public.latest_live_game_state FOR SELECT TO anon, authenticated USING (true);

REVOKE ALL    ON public.latest_odds, public.latest_prop_odds, public.latest_live_game_state FROM anon, authenticated;
GRANT  SELECT ON public.latest_odds, public.latest_prop_odds, public.latest_live_game_state TO   anon, authenticated;

-- ── odds → latest_odds ───────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.latest_odds_on_insert() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    INSERT INTO latest_odds (game_id, market, bookmaker, snapshot_at, odds_id, sport,
                             home_price, away_price, draw_price, spread_home, total_line,
                             over_price, under_price,
                             home_link, away_link, draw_link, over_link, under_link)
    SELECT DISTINCT ON (n.game_id, n.market, n.bookmaker)
           n.game_id, n.market, n.bookmaker, n.snapshot_at, n.odds_id, n.sport,
           n.home_price, n.away_price, n.draw_price, n.spread_home, n.total_line,
           n.over_price, n.under_price,
           n.home_link, n.away_link, n.draw_link, n.over_link, n.under_link
      FROM new_rows n
     WHERE n.game_id IS NOT NULL AND n.market IS NOT NULL
       AND n.bookmaker IS NOT NULL AND n.snapshot_at IS NOT NULL
       AND (n.snapshot_type IS NULL OR n.snapshot_type <> 'in_play')
     ORDER BY n.game_id, n.market, n.bookmaker, n.snapshot_at DESC, n.odds_id DESC
    ON CONFLICT (game_id, market, bookmaker) DO UPDATE SET
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

-- One key's state, recomputed from the log: one backward probe of
-- idx_odds_book_snap. Two statements, not one CTE: a row deleted and
-- re-inserted under the same key inside ONE statement trips the unique index
-- (the delete is invisible to the insert).
CREATE OR REPLACE FUNCTION public.latest_odds_recompute(p_game_id TEXT, p_market TEXT, p_bookmaker TEXT) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    IF p_game_id IS NULL OR p_market IS NULL OR p_bookmaker IS NULL THEN RETURN; END IF;
    DELETE FROM latest_odds
     WHERE game_id = p_game_id AND market = p_market AND bookmaker = p_bookmaker;
    INSERT INTO latest_odds (game_id, market, bookmaker, snapshot_at, odds_id, sport,
                             home_price, away_price, draw_price, spread_home, total_line,
                             over_price, under_price,
                             home_link, away_link, draw_link, over_link, under_link)
    SELECT o.game_id, o.market, o.bookmaker, o.snapshot_at, o.odds_id, o.sport,
           o.home_price, o.away_price, o.draw_price, o.spread_home, o.total_line,
           o.over_price, o.under_price,
           o.home_link, o.away_link, o.draw_link, o.over_link, o.under_link
      FROM odds o
     WHERE o.game_id = p_game_id AND o.market = p_market AND o.bookmaker = p_bookmaker
       AND o.snapshot_at IS NOT NULL
       AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
     ORDER BY o.snapshot_at DESC, o.odds_id DESC
     LIMIT 1;
END $$;

-- Row-level, because Postgres refuses a transition table on a trigger that
-- names columns, and the WHEN clause is what keeps a bulk UPDATE of an
-- unrelated column (source, the *_sid columns) from firing anything at all.
CREATE OR REPLACE FUNCTION public.latest_odds_on_update() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    PERFORM latest_odds_recompute(OLD.game_id, OLD.market, OLD.bookmaker);
    IF (NEW.game_id, NEW.market, NEW.bookmaker) IS DISTINCT FROM (OLD.game_id, OLD.market, OLD.bookmaker) THEN
        PERFORM latest_odds_recompute(NEW.game_id, NEW.market, NEW.bookmaker);
    END IF;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_latest_odds_insert ON public.odds;
CREATE TRIGGER trg_latest_odds_insert
    AFTER INSERT ON public.odds
    REFERENCING NEW TABLE AS new_rows
    FOR EACH STATEMENT EXECUTE FUNCTION public.latest_odds_on_insert();

DROP TRIGGER IF EXISTS trg_latest_odds_update ON public.odds;
CREATE TRIGGER trg_latest_odds_update
    AFTER UPDATE ON public.odds
    FOR EACH ROW
    WHEN ((OLD.game_id, OLD.market, OLD.bookmaker, OLD.snapshot_type, OLD.snapshot_at,
           OLD.home_price, OLD.away_price, OLD.draw_price, OLD.spread_home, OLD.total_line,
           OLD.over_price, OLD.under_price,
           OLD.home_link, OLD.away_link, OLD.draw_link, OLD.over_link, OLD.under_link)
          IS DISTINCT FROM
          (NEW.game_id, NEW.market, NEW.bookmaker, NEW.snapshot_type, NEW.snapshot_at,
           NEW.home_price, NEW.away_price, NEW.draw_price, NEW.spread_home, NEW.total_line,
           NEW.over_price, NEW.under_price,
           NEW.home_link, NEW.away_link, NEW.draw_link, NEW.over_link, NEW.under_link))
    EXECUTE FUNCTION public.latest_odds_on_update();

-- ── player_prop_odds → latest_prop_odds ──────────────────────────────────────
-- A standard market keeps ONE row per (game, market, player, book): the newest.
-- An *_alternate market keeps EVERY line written at the newest snapshot, so a
-- newer snapshot replaces the whole set and an equal one adds to it.

CREATE OR REPLACE FUNCTION public.latest_prop_odds_on_insert() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    -- 1. Retire what this statement supersedes: older rows under the key, and
    --    for a standard market the key's other rows at the same snapshot too.
    DELETE FROM latest_prop_odds l
     USING (SELECT n.game_id, n.market, n.player_name, n.bookmaker, MAX(n.snapshot_at) AS snap
              FROM new_rows n
             WHERE n.game_id IS NOT NULL AND n.market IS NOT NULL AND n.player_name IS NOT NULL
               AND n.bookmaker IS NOT NULL AND n.snapshot_at IS NOT NULL AND n.line IS NOT NULL
               AND (n.snapshot_type IS NULL OR n.snapshot_type <> 'in_play')
             GROUP BY 1, 2, 3, 4) k
     WHERE l.game_id = k.game_id AND l.market = k.market
       AND l.player_name = k.player_name AND l.bookmaker = k.bookmaker
       AND (l.snapshot_at < k.snap
            OR (l.snapshot_at = k.snap AND l.market NOT LIKE '%\_alternate'));

    -- 2. Write the statement's newest rows, unless the state already holds a
    --    newer snapshot for the key (a late or backfilled insert).
    INSERT INTO latest_prop_odds (game_id, market, player_name, bookmaker, line, snapshot_at,
                                  prop_id, team, over_price, under_price, over_link, under_link)
    SELECT c.game_id, c.market, c.player_name, c.bookmaker, c.line, c.snapshot_at,
           c.prop_id, c.team, c.over_price, c.under_price, c.over_link, c.under_link
      FROM (SELECT n.*,
                   MAX(n.snapshot_at) OVER (PARTITION BY n.game_id, n.market, n.player_name, n.bookmaker) AS snap,
                   ROW_NUMBER() OVER (PARTITION BY n.game_id, n.market, n.player_name, n.bookmaker,
                                                   CASE WHEN n.market LIKE '%\_alternate' THEN n.line END
                                      ORDER BY n.snapshot_at DESC, n.prop_id DESC) AS rn
              FROM new_rows n
             WHERE n.game_id IS NOT NULL AND n.market IS NOT NULL AND n.player_name IS NOT NULL
               AND n.bookmaker IS NOT NULL AND n.snapshot_at IS NOT NULL AND n.line IS NOT NULL
               AND (n.snapshot_type IS NULL OR n.snapshot_type <> 'in_play')) c
     WHERE c.snapshot_at = c.snap AND c.rn = 1
       AND NOT EXISTS (SELECT 1 FROM latest_prop_odds l
                        WHERE l.game_id = c.game_id AND l.market = c.market
                          AND l.player_name = c.player_name AND l.bookmaker = c.bookmaker
                          AND l.snapshot_at > c.snapshot_at)
    ON CONFLICT (game_id, market, player_name, bookmaker, line) DO UPDATE SET
           snapshot_at = EXCLUDED.snapshot_at, prop_id = EXCLUDED.prop_id, team = EXCLUDED.team,
           over_price = EXCLUDED.over_price, under_price = EXCLUDED.under_price,
           over_link = EXCLUDED.over_link, under_link = EXCLUDED.under_link
     WHERE EXCLUDED.snapshot_at >= latest_prop_odds.snapshot_at;
    RETURN NULL;
END $$;

-- One key's state, recomputed from the log: the newest pre-game snapshot, one
-- row for a standard market, every line for an alternate. idx_prop_odds_line_snap
-- answers both the MAX and the fetch.
CREATE OR REPLACE FUNCTION public.latest_prop_odds_recompute(p_game_id TEXT, p_market TEXT, p_player_name TEXT, p_bookmaker TEXT) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    IF p_game_id IS NULL OR p_market IS NULL OR p_player_name IS NULL OR p_bookmaker IS NULL THEN RETURN; END IF;
    DELETE FROM latest_prop_odds
     WHERE game_id = p_game_id AND market = p_market AND player_name = p_player_name AND bookmaker = p_bookmaker;
    INSERT INTO latest_prop_odds (game_id, market, player_name, bookmaker, line, snapshot_at,
                                  prop_id, team, over_price, under_price, over_link, under_link)
    SELECT DISTINCT ON (CASE WHEN p.market LIKE '%\_alternate' THEN p.line END)
           p.game_id, p.market, p.player_name, p.bookmaker, p.line, p.snapshot_at,
           p.prop_id, p.team, p.over_price, p.under_price, p.over_link, p.under_link
      FROM player_prop_odds p
     WHERE p.game_id = p_game_id AND p.market = p_market
       AND p.player_name = p_player_name AND p.bookmaker = p_bookmaker
       AND p.snapshot_at IS NOT NULL AND p.line IS NOT NULL
       AND (p.snapshot_type IS NULL OR p.snapshot_type <> 'in_play')
       AND p.snapshot_at = (SELECT MAX(p2.snapshot_at) FROM player_prop_odds p2
                             WHERE p2.game_id = p_game_id AND p2.market = p_market
                               AND p2.player_name = p_player_name AND p2.bookmaker = p_bookmaker
                               AND p2.snapshot_at IS NOT NULL AND p2.line IS NOT NULL
                               AND (p2.snapshot_type IS NULL OR p2.snapshot_type <> 'in_play'))
     ORDER BY CASE WHEN p.market LIKE '%\_alternate' THEN p.line END, p.prop_id DESC;
END $$;

CREATE OR REPLACE FUNCTION public.latest_prop_odds_on_update() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    PERFORM latest_prop_odds_recompute(OLD.game_id, OLD.market, OLD.player_name, OLD.bookmaker);
    IF (NEW.game_id, NEW.market, NEW.player_name, NEW.bookmaker)
       IS DISTINCT FROM (OLD.game_id, OLD.market, OLD.player_name, OLD.bookmaker) THEN
        PERFORM latest_prop_odds_recompute(NEW.game_id, NEW.market, NEW.player_name, NEW.bookmaker);
    END IF;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_latest_prop_odds_insert ON public.player_prop_odds;
CREATE TRIGGER trg_latest_prop_odds_insert
    AFTER INSERT ON public.player_prop_odds
    REFERENCING NEW TABLE AS new_rows
    FOR EACH STATEMENT EXECUTE FUNCTION public.latest_prop_odds_on_insert();

DROP TRIGGER IF EXISTS trg_latest_prop_odds_update ON public.player_prop_odds;
CREATE TRIGGER trg_latest_prop_odds_update
    AFTER UPDATE ON public.player_prop_odds
    FOR EACH ROW
    WHEN ((OLD.game_id, OLD.market, OLD.player_name, OLD.bookmaker, OLD.line, OLD.snapshot_type,
           OLD.snapshot_at, OLD.team, OLD.over_price, OLD.under_price, OLD.over_link, OLD.under_link)
          IS DISTINCT FROM
          (NEW.game_id, NEW.market, NEW.player_name, NEW.bookmaker, NEW.line, NEW.snapshot_type,
           NEW.snapshot_at, NEW.team, NEW.over_price, NEW.under_price, NEW.over_link, NEW.under_link))
    EXECUTE FUNCTION public.latest_prop_odds_on_update();

-- ── live_game_state → latest_live_game_state ─────────────────────────────────

CREATE OR REPLACE FUNCTION public.latest_live_game_state_on_insert() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    INSERT INTO latest_live_game_state (game_id, state_id, snapshot_at, inning, inning_half, outs,
                                        bases_state, home_score, away_score, abstract_game_state)
    SELECT DISTINCT ON (n.game_id)
           n.game_id, n.state_id, n.snapshot_at, n.inning, n.inning_half, n.outs,
           n.bases_state, n.home_score, n.away_score, n.abstract_game_state
      FROM new_rows n
     WHERE n.game_id IS NOT NULL AND n.snapshot_at IS NOT NULL
     ORDER BY n.game_id, n.snapshot_at DESC, n.state_id DESC
    ON CONFLICT (game_id) DO UPDATE SET
           state_id = EXCLUDED.state_id, snapshot_at = EXCLUDED.snapshot_at,
           inning = EXCLUDED.inning, inning_half = EXCLUDED.inning_half, outs = EXCLUDED.outs,
           bases_state = EXCLUDED.bases_state, home_score = EXCLUDED.home_score,
           away_score = EXCLUDED.away_score, abstract_game_state = EXCLUDED.abstract_game_state
     WHERE (EXCLUDED.snapshot_at, EXCLUDED.state_id) >= (latest_live_game_state.snapshot_at, latest_live_game_state.state_id);
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_latest_live_game_state_insert ON public.live_game_state;
CREATE TRIGGER trg_latest_live_game_state_insert
    AFTER INSERT ON public.live_game_state
    REFERENCING NEW TABLE AS new_rows
    FOR EACH STATEMENT EXECUTE FUNCTION public.latest_live_game_state_on_insert();

-- ── rebuild / reconcile from the log ─────────────────────────────────────────
-- Never replaces a state row with an OLDER source row, so a rebuild can run
-- beside live ingestion and be repeated freely. Returns rows written.

-- odds, by snapshot_at range (idx_odds_date): a key's rows may straddle two
-- ranges, and each range contributes its newest, so the newest overall wins.
CREATE OR REPLACE FUNCTION public.latest_lines_rebuild_odds(p_from TEXT, p_to TEXT) RETURNS BIGINT
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE n BIGINT;
BEGIN
    INSERT INTO latest_odds (game_id, market, bookmaker, snapshot_at, odds_id, sport,
                             home_price, away_price, draw_price, spread_home, total_line,
                             over_price, under_price,
                             home_link, away_link, draw_link, over_link, under_link)
    SELECT DISTINCT ON (o.game_id, o.market, o.bookmaker)
           o.game_id, o.market, o.bookmaker, o.snapshot_at, o.odds_id, o.sport,
           o.home_price, o.away_price, o.draw_price, o.spread_home, o.total_line,
           o.over_price, o.under_price,
           o.home_link, o.away_link, o.draw_link, o.over_link, o.under_link
      FROM odds o
     WHERE o.snapshot_at >= p_from AND o.snapshot_at < p_to
       AND o.game_id IS NOT NULL AND o.market IS NOT NULL AND o.bookmaker IS NOT NULL
       AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
     ORDER BY o.game_id, o.market, o.bookmaker, o.snapshot_at DESC, o.odds_id DESC
    ON CONFLICT (game_id, market, bookmaker) DO UPDATE SET
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

-- props, by the table's own game_date (idx_prop_odds_date). A key lives on one
-- game_date, so the range holds every row of every key it touches, and a key
-- the trigger has already written (necessarily newer or equal) is left alone.
CREATE OR REPLACE FUNCTION public.latest_lines_rebuild_props(p_from TEXT, p_to TEXT) RETURNS BIGINT
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE n BIGINT;
BEGIN
    INSERT INTO latest_prop_odds (game_id, market, player_name, bookmaker, line, snapshot_at,
                                  prop_id, team, over_price, under_price, over_link, under_link)
    SELECT c.game_id, c.market, c.player_name, c.bookmaker, c.line, c.snapshot_at,
           c.prop_id, c.team, c.over_price, c.under_price, c.over_link, c.under_link
      FROM (SELECT p.*,
                   MAX(p.snapshot_at) OVER (PARTITION BY p.game_id, p.market, p.player_name, p.bookmaker) AS snap,
                   ROW_NUMBER() OVER (PARTITION BY p.game_id, p.market, p.player_name, p.bookmaker,
                                                   CASE WHEN p.market LIKE '%\_alternate' THEN p.line END
                                      ORDER BY p.snapshot_at DESC, p.prop_id DESC) AS rn
              FROM player_prop_odds p
             WHERE p.game_date >= p_from AND p.game_date < p_to
               AND p.game_id IS NOT NULL AND p.market IS NOT NULL AND p.player_name IS NOT NULL
               AND p.bookmaker IS NOT NULL AND p.snapshot_at IS NOT NULL AND p.line IS NOT NULL
               AND (p.snapshot_type IS NULL OR p.snapshot_type <> 'in_play')) c
     WHERE c.snapshot_at = c.snap AND c.rn = 1
       AND NOT EXISTS (SELECT 1 FROM latest_prop_odds l
                        WHERE l.game_id = c.game_id AND l.market = c.market
                          AND l.player_name = c.player_name AND l.bookmaker = c.bookmaker)
    ON CONFLICT (game_id, market, player_name, bookmaker, line) DO NOTHING;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END $$;

CREATE OR REPLACE FUNCTION public.latest_lines_rebuild_live_state() RETURNS BIGINT
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE n BIGINT;
BEGIN
    INSERT INTO latest_live_game_state (game_id, state_id, snapshot_at, inning, inning_half, outs,
                                        bases_state, home_score, away_score, abstract_game_state)
    SELECT DISTINCT ON (s.game_id)
           s.game_id, s.state_id, s.snapshot_at, s.inning, s.inning_half, s.outs,
           s.bases_state, s.home_score, s.away_score, s.abstract_game_state
      FROM live_game_state s
     WHERE s.game_id IS NOT NULL AND s.snapshot_at IS NOT NULL
     ORDER BY s.game_id, s.snapshot_at DESC, s.state_id DESC
    ON CONFLICT (game_id) DO UPDATE SET
           state_id = EXCLUDED.state_id, snapshot_at = EXCLUDED.snapshot_at,
           inning = EXCLUDED.inning, inning_half = EXCLUDED.inning_half, outs = EXCLUDED.outs,
           bases_state = EXCLUDED.bases_state, home_score = EXCLUDED.home_score,
           away_score = EXCLUDED.away_score, abstract_game_state = EXCLUDED.abstract_game_state
     WHERE (EXCLUDED.snapshot_at, EXCLUDED.state_id) > (latest_live_game_state.snapshot_at, latest_live_game_state.state_id);
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END $$;

-- None of these is an RPC. Default privileges already withhold EXECUTE from the
-- API roles on new functions; said by name anyway (operations.md).
REVOKE ALL ON FUNCTION public.latest_odds_on_insert(), public.latest_odds_on_update(),
                       public.latest_odds_recompute(TEXT, TEXT, TEXT),
                       public.latest_prop_odds_on_insert(), public.latest_prop_odds_on_update(),
                       public.latest_prop_odds_recompute(TEXT, TEXT, TEXT, TEXT),
                       public.latest_live_game_state_on_insert(),
                       public.latest_lines_rebuild_odds(TEXT, TEXT),
                       public.latest_lines_rebuild_props(TEXT, TEXT),
                       public.latest_lines_rebuild_live_state()
       FROM PUBLIC, anon, authenticated;

-- ── the views: plain joins now ───────────────────────────────────────────────
-- Same columns, same order, same types as before (CREATE OR REPLACE enforces
-- it). The app's date filter lands on idx_games_date and the join on each
-- state table's primary key, so a day costs one probe per game.

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
       l.snapshot_at
FROM games g
JOIN latest_odds l ON l.game_id = g.game_id
WHERE l.bookmaker <> 'sbr_consensus';

CREATE OR REPLACE VIEW public.v_latest_prop_odds_all_books
WITH (security_invoker = on) AS
SELECT g.game_id,
       g.game_date,
       l.market,
       l.player_name,
       l.team,
       l.bookmaker,
       l.line,
       l.over_price,
       l.under_price,
       l.over_link,
       l.under_link,
       l.snapshot_at
FROM games g
JOIN latest_prop_odds l ON l.game_id = g.game_id;

CREATE OR REPLACE VIEW public.v_latest_dk_odds
WITH (security_invoker = on) AS
SELECT l.game_id,
       g.game_date,
       l.market,
       l.home_price,
       l.away_price,
       l.spread_home,
       l.total_line,
       l.over_price,
       l.under_price,
       l.snapshot_at
FROM games g
JOIN latest_odds l ON l.game_id = g.game_id
WHERE l.bookmaker = 'draftkings';

CREATE OR REPLACE VIEW public.v_live_game_state_latest
WITH (security_invoker = on) AS
SELECT l.game_id,
       g.game_date,
       l.snapshot_at,
       l.inning,
       l.inning_half,
       l.outs,
       l.bases_state,
       l.home_score,
       l.away_score,
       l.abstract_game_state
FROM games g
JOIN latest_live_game_state l ON l.game_id = g.game_id;

GRANT SELECT ON public.v_latest_odds_all_books, public.v_latest_prop_odds_all_books,
                public.v_latest_dk_odds, public.v_live_game_state_latest
   TO anon, authenticated;
