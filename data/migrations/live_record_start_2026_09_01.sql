-- live_record_start_2026_09_01 (2026-09-04, Matt)
--
-- Matt: "Just mirror retool for now. But only start tracking bets as of 9/1 and
-- on, that will be our official live date. We will set up retool to do the
-- same, but only start with games 9/1 and on."
--
-- TWO CHANGES, BOTH TO THE PUBLISHED RECORD ONLY.
--
-- 1. THE START MOVES 2026-04-14 -> 2026-09-01. 2026-09-01 is the official live
--    date. Nothing is deleted: every pick before it stays in `picks` and stays
--    the bet of record (CLAUDE.md 1c). What changes is the window the app and
--    Retool publish.
--
-- 2. ONE MEASURE, NOT TWO — the "mirror". Both views were a UNION of two
--    branches that answered DIFFERENT questions:
--      * `fo`    read the re-graded full-outcome view (every scored pick,
--                BET/AVOID/dead-zone alike, graded at TODAY's cut) for the
--                MLB/WNBA core models;
--      * `other` read `picks` for everything else — settled BET picks AS FIRED.
--    Retool reads the second kind. So the published record now uses the `other`
--    logic for EVERY model and the `fo` branch is gone. The number the app shows
--    is now the number Retool shows, by construction rather than by coincidence.
--
-- WHAT IS DELIBERATELY NOT TOUCHED: `v_model_full_outcome_record`,
-- `v_model_full_outcome_picks` and `mv_scored_pick_outcomes` keep their
-- 2026-04-14 gate and their re-graded semantics. That is the threshold-sweep
-- tool, and CLAUDE.md 7's EVALUATION RULE requires a sweep to see every scored
-- pick — BET, AVOID and dead-zone NONE. A cut cannot be swept on three days of
-- BET-only history. Publishing and sweeping are different questions and now use
-- different objects, which is the point.
--
-- THREE THINGS THIS SIMPLIFIES OUT, each verified dead rather than assumed:
--   * the mlb_over_under honest-era gate (`game_date < '2026-07-05'`) — 2026-09-01
--     is already past it, so the clause can never fire;
--   * `model_id <> 'mlb_prop_batter_hr'` — retired models were pruned from
--     `model_action_thresholds`, so the INNER JOIN drops them (verified
--     2026-09-04: batter_hr, batter_rbi, live_win_prob and live_runline all
--     absent from that table);
--   * the five-model / prop-prefix allow-list that split the two branches.
--
-- Reading `picks` rather than the matview also means the record no longer
-- inherits the matview's allow-list or its double exclusion of in-play picks —
-- the live lanes and UFC are in the published record on the same terms as
-- everything else. The `(is_live IS NOT TRUE OR model_id LIKE '%\_live\_%')`
-- clause is KEPT: a dedicated live lane counts, a pre-game model's in-play pick
-- does not, because pre-game and in-play prices never mix (CLAUDE.md 6).
--
-- MEASURED BEFORE/AFTER (production, 2026-09-04):
--   before   691-568-3 over 1,262 settled picks, +4.89%, +61.2u
--   after     46-30-0  over    76 settled picks, +15.40%, +11.7u
--   six models fire in the window: mlb_live_total_runs 26 (17-9, +19.0%),
--   mlb_prop_pitcher_hits 18 (13-5, +42.1%), mlb_prop_pitcher_k 18 (7-11,
--   -29.8%), mlb_prop_pitcher_outs 8 (6-2, +60.6%), ncaaf_live_total 5 (3-2,
--   +13.8%), ncaaf_live_win_prob 1 (0-1, -100%).
--   Those per-model ROIs are 8-26 bet samples and are NOT evidence of anything;
--   they are simply what the live window currently holds.
--
-- ROLLBACK: re-run `data/migrations/fix_runline_away_grading_in_full_outcome_views.sql`
-- and `require_price_for_published_units.sql` in that order, which together
-- rebuild the previous two-branch definitions; or restore from the definitions
-- captured in the 2026-09-04 session entry (docs/sessions/2026-09.md).

-- ── the per-model published record ───────────────────────────────────────────
CREATE OR REPLACE VIEW public.v_public_track_record
WITH (security_invoker = on) AS
SELECT p.sport,
       p.model_id,
       count(*) FILTER (WHERE p.result = ANY (ARRAY['WIN','LOSS','PUSH']))     AS picks,
       count(*) FILTER (WHERE p.result = 'WIN')                                AS wins,
       count(*) FILTER (WHERE p.result = 'LOSS')                               AS losses,
       count(*) FILTER (WHERE p.result = 'PUSH')                               AS pushes,
       -- An unpriced pick keeps its W-L and contributes no money and no stake:
       -- profit_flat FABRICATES -110 when dk_odds IS NULL (CLAUDE.md 6).
       COALESCE(sum(p.profit_flat) FILTER (
           WHERE (p.result = ANY (ARRAY['WIN','LOSS','PUSH'])) AND p.dk_odds IS NOT NULL), 0::numeric)
                                                                               AS profit_flat,
       100 * count(*) FILTER (
           WHERE (p.result = ANY (ARRAY['WIN','LOSS','PUSH'])) AND p.dk_odds IS NOT NULL)
                                                                               AS staked_flat,
       count(*) FILTER (
           WHERE (p.result = ANY (ARRAY['WIN','LOSS','PUSH'])) AND p.clv_pct IS NOT NULL)
                                                                               AS clv_settled,
       count(*) FILTER (
           WHERE (p.result = ANY (ARRAY['WIN','LOSS','PUSH'])) AND p.clv_pct > 0::numeric)
                                                                               AS clv_beat,
       avg(p.clv_pct) FILTER (
           WHERE (p.result = ANY (ARRAY['WIN','LOSS','PUSH'])) AND p.clv_pct IS NOT NULL)
                                                                               AS avg_clv_pct,
       min(p.game_date)                                                        AS first_date,
       max(p.game_date)                                                        AS last_date
  FROM picks p
  JOIN model_action_thresholds t ON t.model_id = p.model_id
 WHERE p.signal_type = 'BET'
   AND (p.is_live IS NOT TRUE OR p.model_id ~~ '%\_live\_%'::text)
   AND t.paused IS NOT TRUE
   AND p.game_date >= '2026-09-01'::text
   AND p.model_probability >= t.min_prob
   AND (t.prob_only OR p.edge >= t.min_edge)
   AND (t.min_odds IS NULL OR p.dk_odds IS NULL OR p.dk_odds >= t.min_odds)
 GROUP BY p.sport, p.model_id;

-- ── the daily series behind the equity curve ─────────────────────────────────
CREATE OR REPLACE VIEW public.v_public_track_record_daily
WITH (security_invoker = on) AS
SELECT p.game_date,
       p.sport,
       count(*) FILTER (WHERE p.result = ANY (ARRAY['WIN','LOSS','PUSH']))     AS picks,
       count(*) FILTER (WHERE p.result = 'WIN')                                AS wins,
       count(*) FILTER (WHERE p.result = 'LOSS')                               AS losses,
       count(*) FILTER (WHERE p.result = 'PUSH')                               AS pushes,
       COALESCE(sum(p.profit_flat) FILTER (
           WHERE (p.result = ANY (ARRAY['WIN','LOSS','PUSH'])) AND p.dk_odds IS NOT NULL), 0::numeric)
                                                                               AS profit_flat,
       100 * count(*) FILTER (
           WHERE (p.result = ANY (ARRAY['WIN','LOSS','PUSH'])) AND p.dk_odds IS NOT NULL)
                                                                               AS staked_flat
  FROM picks p
  JOIN model_action_thresholds t ON t.model_id = p.model_id
 WHERE p.signal_type = 'BET'
   AND (p.is_live IS NOT TRUE OR p.model_id ~~ '%\_live\_%'::text)
   AND t.paused IS NOT TRUE
   AND p.game_date >= '2026-09-01'::text
   AND p.model_probability >= t.min_prob
   AND (t.prob_only OR p.edge >= t.min_edge)
   AND (t.min_odds IS NULL OR p.dk_odds IS NULL OR p.dk_odds >= t.min_odds)
 GROUP BY p.game_date, p.sport
HAVING count(*) FILTER (WHERE p.result = ANY (ARRAY['WIN','LOSS','PUSH'])) > 0;

-- Both views are read by the mobile app through PostgREST as `anon`, so the
-- grant has to survive the redefinition (data/anon_readable.py lists them).
GRANT SELECT ON public.v_public_track_record        TO anon, authenticated;
GRANT SELECT ON public.v_public_track_record_daily  TO anon, authenticated;
