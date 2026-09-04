-- track_record_reads_graded_matview (applied 2026-09-02)
--
-- THE RECORD TAB WAS EMPTY. v_public_track_record took 14.3s and
-- v_public_track_record_daily 12.3s (EXPLAIN ANALYZE as `authenticated`,
-- 2026-09-02), against PostgREST's 8s statement_timeout -- so every app load of
-- the Track Record screen was cancelled ("canceling statement due to statement
-- timeout", 57014) and the screen showed 0-0 over a red error. pg_stat_statements
-- only records the calls that finished (mean 1.5s, max 2.96s under `anon`), which
-- is why the slowdown was invisible until the tail crossed the timeout.
--
-- WHERE THE TIME WENT. Both views re-graded the whole MLB/WNBA full-outcome
-- universe on EVERY read: ~126k pick rows, each looked up in player_game_log and
-- wnba_player_game_log through a LATERAL ... LIMIT 1 (71k index probes, ~8.5s),
-- under a nested loop the planner chose because it estimated 6.5k rows for the
-- correlated model_id predicates. The universe grows ~2-3k rows a day (dead-zone
-- NONE rows are the evaluation dataset and are never deleted), so this was
-- always going to cross the line; it did on 2026-09-01.
--
-- THE FIX. That grading already exists, precomputed: mv_scored_pick_outcomes is
-- the SAME grading CASEs over the SAME universe (game_date >= 2026-04-14, the
-- O/U honest-era gate, is_live IS NOT TRUE, the MLB/WNBA model whitelist),
-- refreshed by run_pipeline step 0d right after settle and now by every refresh
-- pass too. The two views now read their full-outcome branch from it and keep
-- everything else exactly as it was: thresholds are still joined LIVE from
-- model_action_thresholds (a cut change still reaches the record with no
-- refresh), the `other` branch (UFC/NHL/NBA/golf/NFL/NCAAF + the live models)
-- still reads picks.result, and v_public_track_record itself is untouched --
-- it inherits through v_model_full_outcome_record.
--
-- VERIFIED EQUIVALENT before applying, in one statement so thresholds could not
-- move underneath: v_model_full_outcome_record old vs new = 20 rows, 0 differ
-- either way; v_public_track_record_daily old vs new = 202 rows, 0 differ
-- either way (EXCEPT ALL both directions, after refreshing the matview).
--
-- WHAT CHANGES SEMANTICALLY: nothing at the numbers. The one behavioural
-- difference is freshness -- the full-outcome branch now moves when the
-- matview is refreshed (after settle in the 6am run and in every refresh pass)
-- instead of the instant a box score lands. The Record tab already says
-- "updated after each morning settlement". A model with picks in the universe
-- but not one gradeable pick yet no longer appears as a 0-0 row (the matview
-- holds only graded rows); no such model existed at apply time.
--
-- IDEMPOTENT: each view is skipped once its definition names the matview, so
-- data/view_migrations.py can run this every pass (no DDL fires on a no-op
-- run -- the GRANTs sit inside the guarded branches on purpose, because every
-- DDL statement, GRANT included, forces a PostgREST schema-cache reload; see
-- CLAUDE.md section 7). Single statement, as that runner requires.
--
-- KEEP IN STEP: units_precision_for_public_record.sql (also in the active
-- list) asserts the exact expression
--   round(COALESCE(sum(profit) FILTER (WHERE passes), 0::numeric), 6)
-- is present in v_model_full_outcome_record, and
-- require_price_for_published_units.sql asserts the priced profit_flat /
-- staked_flat expressions in the `other` branch of both public views. Both are
-- preserved verbatim below; tests/test_track_record_views.py pins them.

DO $mig$
DECLARE
  d text;
BEGIN
  -- ── v_model_full_outcome_record ──────────────────────────────────────────
  d := pg_get_viewdef('public.v_model_full_outcome_record'::regclass, true);
  IF position('mv_scored_pick_outcomes' in d) > 0 THEN
    RAISE NOTICE 'v_model_full_outcome_record already reads the matview - skipping';
  ELSE
    EXECUTE $v$
      CREATE OR REPLACE VIEW public.v_model_full_outcome_record WITH (security_invoker = on) AS
      WITH graded AS (
        SELECT o.model_id,
               CASE o.result WHEN 'WIN' THEN 'W' WHEN 'LOSS' THEN 'L' ELSE 'P' END AS res,
               o.dk_odds,
               m.paused,
               m.prob_only,
               o.profit_units AS profit,
               (o.model_probability >= m.min_prob
                AND (m.prob_only OR o.edge >= COALESCE(m.min_edge, 0::numeric))
                AND (m.min_odds IS NULL OR o.dk_odds IS NULL OR o.dk_odds >= m.min_odds)) AS passes
        FROM mv_scored_pick_outcomes o
        JOIN model_action_thresholds m ON m.model_id = o.model_id
      )
      SELECT model_id,
             bool_or(paused) AS paused,
             bool_or(prob_only) AS prob_only,
             count(*) FILTER (WHERE passes AND res = ANY (ARRAY['W','L','P'])) AS bets,
             count(*) FILTER (WHERE passes AND res = 'W') AS wins,
             count(*) FILTER (WHERE passes AND res = 'L') AS losses,
             count(*) FILTER (WHERE passes AND res = 'P') AS pushes,
             count(*) FILTER (WHERE passes AND res = ANY (ARRAY['W','L','P']) AND dk_odds IS NOT NULL) AS priced_bets,
             CASE WHEN model_id = 'mlb_prop_batter_hr' THEN 0::numeric
                  ELSE round(COALESCE(sum(profit) FILTER (WHERE passes), 0::numeric), 6) END AS units,
             CASE WHEN model_id = 'mlb_prop_batter_hr' THEN NULL::numeric
                  ELSE round(sum(profit) FILTER (WHERE passes)
                             / NULLIF(count(*) FILTER (WHERE passes AND res = ANY (ARRAY['W','L','P']) AND dk_odds IS NOT NULL), 0)::numeric
                             * 100::numeric, 1) END AS roi_pct
      FROM graded
      GROUP BY model_id
    $v$;
    GRANT SELECT ON public.v_model_full_outcome_record TO anon, authenticated;
    RAISE NOTICE 'v_model_full_outcome_record now reads mv_scored_pick_outcomes';
  END IF;

  -- ── v_public_track_record_daily: REMOVED 2026-09-04 ──────────────────────
  -- This file also redefined the daily view, guarded on "does the view still
  -- read mv_scored_pick_outcomes?". That guard is a LOCK, not an idempotency
  -- check: it cannot tell "never applied" from "deliberately superseded". When
  -- live_record_start_2026_09_01.sql moved the daily view to the 2026-09-01
  -- live date, the guard read 0 and this branch restored the 2026-04-14
  -- definition on the next pass — silently, every pass. The app then drew a
  -- +64.1u equity curve (Apr 17 → Sep 3) beside a hero card reading +12.02u
  -- over the same 70 picks.
  --
  -- The daily view is owned by live_record_start_views_2026_09_01.sql now, and
  -- its guard is on the live-date gate — the property the migration is trying
  -- to establish, not the shape of its own output. The perf fix this file
  -- exists for is unaffected: the daily view no longer re-grades from the
  -- player logs either, because it no longer reads them at all.
END
$mig$;
