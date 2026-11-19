-- Model health: closing-line value per model, bet by bet and in blocks of the
-- last 25, 50 and 100 bets (mike, 2026-11-18: "rolling clv tracking per model
-- in 25 bet increments for last 500 bets and 50 and 100 bet increments ... so
-- we can truly assess health and durability"). The ops dashboard's Model
-- Health tab reads these three views and nothing else.
--
-- WHICH BETS. Exactly the published record's: the rows v_public_track_record
-- counts, graded WIN, LOSS or PUSH. The filter is not copied here. It is read
-- out of v_public_track_record's own definition when this file runs, and the
-- views carry its hash, so a change to the record's filter rebuilds these on
-- the next pass. A record view this file cannot read raises, every pass,
-- rather than build a second definition of "published".
--
-- WHAT EACH BET'S CLOSE IS. The columns the closing-line capture already
-- wrote (docs/clv.md); this file computes no price. status is one of:
--   price          the bet book closed on our number: clv_pct is the measure
--   line_for       the book's main line left our number in our favour
--   line_against   the book's main line left our number against us
--   in_play        an in-play bet: there is no pre-game close to compare to
--   no_close       the capture ran and found no closing quote
--   not_measured   the capture has not written a close (clv_method unset)
--   old_method     a close stamped by a retired method (excluded, as in the record)
-- verdict: beat / push / miss for a price close (push is |clv_pct| < 0.005,
-- the stored grain, as in the record); beat / miss for a line move; NULL
-- otherwise. The record's headline beat rate counts price closes only, and so
-- does price_beat_rate here; beat_rate_with_line adds the line moves.
--
--   v_model_health_bets     one row per bet; seq 1 is the model's newest
--                           (created_at, then pick_id)
--   v_model_health_windows  blocks of 25, 50 and 100 over each model's newest
--                           500 bets; block_no 1 is the newest block. A model
--                           with fewer bets has a short last block (full_block
--                           false).
--   v_model_health_summary  one row per model: every bet, and the newest 25,
--                           50 and 100
--
-- Reads only. Touches no pick, cut, grade, unit or record. anon,
-- authenticated and PUBLIC get nothing: the dashboard reads as the database
-- owner through its own resource.
--
-- One DO block (data/view_migrations.py runs each file as one statement on
-- every pass). It returns on a catalog read once all three views carry this
-- file's mark and the hash of the record's filter. tests/test_model_health.py
-- checks the mark is the hash of this file.

DO $mig$
DECLARE
  file_mark CONSTANT text := 'model_health 562ef6715677';
  rec_def   text;
  rec_where text;
  mark      text;
BEGIN
  IF to_regclass('public.v_public_track_record') IS NULL THEN
    RAISE NOTICE 'model_health: v_public_track_record does not exist yet; nothing built';
    RETURN;
  END IF;

  rec_def := pg_get_viewdef('public.v_public_track_record'::regclass, true);
  rec_where := substring(rec_def FROM 'FROM picks p\s+WHERE\s+(.*\S)\s+GROUP BY\s+sport,\s*model_id;?\s*$');
  IF rec_where IS NULL THEN
    RAISE EXCEPTION 'model_health: could not read the published record''s filter out of v_public_track_record';
  END IF;
  mark := file_mark || ' ' || left(md5(rec_where), 12);

  IF COALESCE(obj_description(to_regclass('public.v_model_health_bets'), 'pg_class'), '') = mark
     AND COALESCE(obj_description(to_regclass('public.v_model_health_windows'), 'pg_class'), '') = mark
     AND COALESCE(obj_description(to_regclass('public.v_model_health_summary'), 'pg_class'), '') = mark
     AND NOT has_table_privilege('anon', 'public.v_model_health_bets', 'SELECT')
     AND NOT has_table_privilege('authenticated', 'public.v_model_health_bets', 'SELECT')
     AND NOT has_table_privilege('anon', 'public.v_model_health_windows', 'SELECT')
     AND NOT has_table_privilege('authenticated', 'public.v_model_health_windows', 'SELECT')
     AND NOT has_table_privilege('anon', 'public.v_model_health_summary', 'SELECT')
     AND NOT has_table_privilege('authenticated', 'public.v_model_health_summary', 'SELECT')
  THEN
    RETURN;
  END IF;

  -- Dropped and rebuilt (only when the mark differs): the column lists may
  -- change between versions, which CREATE OR REPLACE refuses.
  DROP VIEW IF EXISTS public.v_model_health_summary;
  DROP VIEW IF EXISTS public.v_model_health_windows;
  DROP VIEW IF EXISTS public.v_model_health_bets;

  EXECUTE $v1$
    CREATE VIEW public.v_model_health_bets WITH (security_invoker = on) AS
    WITH rec AS (
      SELECT p.pick_id, p.sport, p.model_id, p.game_id, p.game_date,
             p.created_at::timestamptz AS created_at,
             p.pick_label, p.pick_side, p.is_live, p.result,
             COALESCE(p.decision_odds, p.dk_odds) AS taken_odds,
             p.clv_bet_book, p.closing_dk_odds, p.scored_line, p.closing_line,
             p.clv_method, p.clv_pct, p.market_clv_pct, p.line_clv_pts,
             p.stake_units
        FROM public.picks p
       WHERE $v1$ || rec_where || $v2$
    ), graded AS (
      SELECT r.*,
             CASE
               WHEN r.is_live IS TRUE THEN 'in_play'
               WHEN r.clv_method IS NULL THEN 'not_measured'
               WHEN r.clv_method <> 'standard_v2' THEN 'old_method'
               WHEN r.clv_pct IS NOT NULL THEN 'price'
               WHEN r.line_clv_pts > 0 THEN 'line_for'
               WHEN r.line_clv_pts < 0 THEN 'line_against'
               ELSE 'no_close'
             END AS status
        FROM rec r
       WHERE r.result IN ('WIN', 'LOSS', 'PUSH')
    )
    SELECT g.pick_id, g.sport, g.model_id, g.game_id, g.game_date, g.created_at,
           g.pick_label, g.pick_side, g.is_live, g.result,
           g.taken_odds,
           g.clv_bet_book AS bet_book,
           g.closing_dk_odds AS close_odds,
           g.scored_line, g.closing_line,
           g.status,
           CASE
             WHEN g.status = 'price' AND abs(g.clv_pct) < 0.005 THEN 'push'
             WHEN g.status = 'price' AND g.clv_pct > 0 THEN 'beat'
             WHEN g.status = 'price' THEN 'miss'
             WHEN g.status = 'line_for' THEN 'beat'
             WHEN g.status = 'line_against' THEN 'miss'
           END AS verdict,
           CASE WHEN g.status = 'price' THEN g.clv_pct END AS clv_pct,
           CASE WHEN g.clv_method = 'standard_v2' THEN g.market_clv_pct END AS market_clv_pct,
           CASE WHEN g.status IN ('line_for', 'line_against') THEN g.line_clv_pts END AS line_clv_pts,
           public.published_pick_unit_profit(g.taken_odds, g.result, g.stake_units) AS units,
           public.published_pick_unit_risked(g.taken_odds, g.result, g.stake_units) AS risked,
           row_number() OVER (PARTITION BY g.model_id ORDER BY g.created_at DESC, g.pick_id DESC) AS seq,
           count(*) OVER (PARTITION BY g.model_id) AS model_bets
      FROM graded g
  $v2$;

  EXECUTE $w$
    CREATE VIEW public.v_model_health_windows WITH (security_invoker = on) AS
    WITH blocks AS (
      SELECT b.*, s.block_size, ((b.seq - 1) / s.block_size + 1)::int AS block_no
        FROM public.v_model_health_bets b
       CROSS JOIN (VALUES (25), (50), (100)) AS s(block_size)
       WHERE b.seq <= 500
    ), agg AS (
      SELECT model_id, sport, block_size, block_no,
             count(*) AS bets,
             min(seq) AS newest_seq,
             max(seq) AS oldest_seq,
             min(game_date) AS first_date,
             max(game_date) AS last_date,
             count(*) FILTER (WHERE result = 'WIN') AS wins,
             count(*) FILTER (WHERE result = 'LOSS') AS losses,
             count(*) FILTER (WHERE result = 'PUSH') AS pushes,
             COALESCE(sum(units), 0) AS units,
             COALESCE(sum(risked), 0) AS risked,
             count(*) FILTER (WHERE status = 'price') AS price_n,
             avg(clv_pct) AS avg_clv_pct,
             stddev_samp(clv_pct) AS sd_clv_pct,
             count(*) FILTER (WHERE status = 'price' AND verdict = 'beat') AS price_beat,
             count(*) FILTER (WHERE status = 'price' AND verdict = 'push') AS price_push,
             count(*) FILTER (WHERE status = 'price' AND verdict = 'miss') AS price_miss,
             count(*) FILTER (WHERE status = 'line_for') AS line_for,
             count(*) FILTER (WHERE status = 'line_against') AS line_against,
             avg(line_clv_pts) AS avg_line_pts,
             count(*) FILTER (WHERE status = 'in_play') AS in_play,
             count(*) FILTER (WHERE status IN ('no_close', 'not_measured', 'old_method')) AS unmeasured,
             count(market_clv_pct) AS market_n,
             avg(market_clv_pct) AS avg_market_clv_pct
        FROM blocks
       GROUP BY model_id, sport, block_size, block_no
    )
    SELECT a.*,
           (a.bets = a.block_size) AS full_block,
           a.sd_clv_pct / NULLIF(sqrt(a.price_n), 0) AS se_clv_pct,
           a.price_beat::numeric / NULLIF(a.price_beat + a.price_miss, 0) AS price_beat_rate,
           (a.price_beat + a.line_for)::numeric
             / NULLIF(a.price_beat + a.price_miss + a.line_for + a.line_against, 0) AS beat_rate_with_line,
           a.units / NULLIF(a.risked, 0) * 100 AS roi_pct
      FROM agg a
  $w$;

  EXECUTE $s$
    CREATE VIEW public.v_model_health_summary WITH (security_invoker = on) AS
    WITH scopes AS (
      SELECT b.*, s.scope
        FROM public.v_model_health_bets b
       CROSS JOIN (VALUES (0), (25), (50), (100)) AS s(scope)
       WHERE s.scope = 0 OR b.seq <= s.scope
    ), agg AS (
      SELECT model_id, sport, scope,
             count(*) AS bets,
             min(game_date) AS first_date,
             max(game_date) AS last_date,
             count(*) FILTER (WHERE result = 'WIN') AS wins,
             count(*) FILTER (WHERE result = 'LOSS') AS losses,
             count(*) FILTER (WHERE result = 'PUSH') AS pushes,
             COALESCE(sum(units), 0) AS units,
             COALESCE(sum(risked), 0) AS risked,
             count(*) FILTER (WHERE status = 'price') AS price_n,
             avg(clv_pct) AS avg_clv_pct,
             stddev_samp(clv_pct) / NULLIF(sqrt(count(clv_pct)), 0) AS se_clv_pct,
             count(*) FILTER (WHERE status = 'price' AND verdict = 'beat') AS price_beat,
             count(*) FILTER (WHERE status = 'price' AND verdict = 'push') AS price_push,
             count(*) FILTER (WHERE status = 'price' AND verdict = 'miss') AS price_miss,
             count(*) FILTER (WHERE status = 'line_for') AS line_for,
             count(*) FILTER (WHERE status = 'line_against') AS line_against,
             count(*) FILTER (WHERE status = 'in_play') AS in_play,
             count(*) FILTER (WHERE status IN ('no_close', 'not_measured', 'old_method')) AS unmeasured,
             count(market_clv_pct) AS market_n,
             avg(market_clv_pct) AS avg_market_clv_pct
        FROM scopes
       GROUP BY model_id, sport, scope
    )
    SELECT a.model_id, a.sport,
           max(a.bets) FILTER (WHERE a.scope = 0) AS bets,
           max(a.first_date) FILTER (WHERE a.scope = 0) AS first_date,
           max(a.last_date) FILTER (WHERE a.scope = 0) AS last_date,
           max(a.wins) FILTER (WHERE a.scope = 0) AS wins,
           max(a.losses) FILTER (WHERE a.scope = 0) AS losses,
           max(a.pushes) FILTER (WHERE a.scope = 0) AS pushes,
           max(a.units) FILTER (WHERE a.scope = 0) AS units,
           max(a.risked) FILTER (WHERE a.scope = 0) AS risked,
           max(a.price_n) FILTER (WHERE a.scope = 0) AS price_n,
           max(a.price_beat) FILTER (WHERE a.scope = 0) AS price_beat,
           max(a.price_push) FILTER (WHERE a.scope = 0) AS price_push,
           max(a.price_miss) FILTER (WHERE a.scope = 0) AS price_miss,
           max(a.line_for) FILTER (WHERE a.scope = 0) AS line_for,
           max(a.line_against) FILTER (WHERE a.scope = 0) AS line_against,
           max(a.in_play) FILTER (WHERE a.scope = 0) AS in_play,
           max(a.unmeasured) FILTER (WHERE a.scope = 0) AS unmeasured,
           max(a.market_n) FILTER (WHERE a.scope = 0) AS market_n,
           max(a.avg_market_clv_pct) FILTER (WHERE a.scope = 0) AS avg_market_clv_pct,
           max(a.avg_clv_pct) FILTER (WHERE a.scope = 0) AS avg_clv_pct,
           max(a.se_clv_pct) FILTER (WHERE a.scope = 0) AS se_clv_pct,
           max(a.price_beat::numeric / NULLIF(a.price_beat + a.price_miss, 0))
             FILTER (WHERE a.scope = 0) AS price_beat_rate,
           max((a.price_beat + a.line_for)::numeric
               / NULLIF(a.price_beat + a.price_miss + a.line_for + a.line_against, 0))
             FILTER (WHERE a.scope = 0) AS beat_rate_with_line,
           max(a.price_n) FILTER (WHERE a.scope = 25) AS last25_price_n,
           max(a.avg_clv_pct) FILTER (WHERE a.scope = 25) AS last25_avg_clv_pct,
           max(a.se_clv_pct) FILTER (WHERE a.scope = 25) AS last25_se_clv_pct,
           max((a.price_beat + a.line_for)::numeric
               / NULLIF(a.price_beat + a.price_miss + a.line_for + a.line_against, 0))
             FILTER (WHERE a.scope = 25) AS last25_beat_rate_with_line,
           max(a.price_n) FILTER (WHERE a.scope = 50) AS last50_price_n,
           max(a.avg_clv_pct) FILTER (WHERE a.scope = 50) AS last50_avg_clv_pct,
           max(a.se_clv_pct) FILTER (WHERE a.scope = 50) AS last50_se_clv_pct,
           max((a.price_beat + a.line_for)::numeric
               / NULLIF(a.price_beat + a.price_miss + a.line_for + a.line_against, 0))
             FILTER (WHERE a.scope = 50) AS last50_beat_rate_with_line,
           max(a.price_n) FILTER (WHERE a.scope = 100) AS last100_price_n,
           max(a.avg_clv_pct) FILTER (WHERE a.scope = 100) AS last100_avg_clv_pct,
           max(a.se_clv_pct) FILTER (WHERE a.scope = 100) AS last100_se_clv_pct,
           max((a.price_beat + a.line_for)::numeric
               / NULLIF(a.price_beat + a.price_miss + a.line_for + a.line_against, 0))
             FILTER (WHERE a.scope = 100) AS last100_beat_rate_with_line
      FROM agg a
     GROUP BY a.model_id, a.sport
  $s$;

  EXECUTE format('COMMENT ON VIEW public.v_model_health_bets IS %L', mark);
  EXECUTE format('COMMENT ON VIEW public.v_model_health_windows IS %L', mark);
  EXECUTE format('COMMENT ON VIEW public.v_model_health_summary IS %L', mark);
  REVOKE ALL ON public.v_model_health_bets FROM anon, authenticated, PUBLIC;
  REVOKE ALL ON public.v_model_health_windows FROM anon, authenticated, PUBLIC;
  REVOKE ALL ON public.v_model_health_summary FROM anon, authenticated, PUBLIC;
END $mig$;
