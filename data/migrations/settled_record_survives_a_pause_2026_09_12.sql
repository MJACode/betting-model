-- settled_record_survives_a_pause (2026-09-12, mike)
--
-- mike: "Pausing a model should not erase settled record unless I explicitly
-- say so, and this needs to be a global rule. If I didn't explicitly say to
-- remove a settled record, and I have in the past for some others, then you
-- need to keep the record. I did not say this explicitly for NCAA football.
-- Do not do it unless I explicitly say so."
--
-- WHAT WENT WRONG. Both NCAAF live lanes were paused on the evening of
-- 2026-09-11. At the 6am sync `model_action_thresholds.paused` went TRUE, and
-- every published-record surface carried `AND t.paused IS NOT TRUE` — a
-- statement about what a model may bet NEXT, applied to what it had already bet
-- and settled. Measured from results_snapshots, the Discord recap published:
--
--     2026-09-11 06:02 ET (through 09-10)   NCAAF  27-25,  52 settled, -2.55u
--     2026-09-12 06:02 ET (through 09-11)   NCAAF   0-3,    3 settled, -3.4u
--
-- 55 settled bets, gone overnight, on both surfaces: this pair of views backs
-- the app's Models tab and its equity curve. The same clause is currently
-- hiding 1,461 settled bets across 13 paused models (only some are inside the
-- published window).
--
-- These views ALSO re-applied the current min_prob / min_edge / min_odds to
-- settled rows, so a threshold edit rewrote history too — the published
-- all-time count fell 104 on 09-02 and 22 on 09-09 with no picks deleted.
--
-- THE RULE NOW. A pick is in the published record because it was written as a
-- BET: it cleared its cut on the day, at the price available then. Only two
-- things take that back, and both are somebody's explicit decision:
--   * a VOID — scripts/void_picks.py sets result='NO_ACTION', which fails the
--     WIN/LOSS/PUSH filter below. This is the mechanism behind every removal
--     mike HAS asked for (the MLB phantom-game rows, the re-cut
--     nfl_opener_spread picks: "settled ones stand");
--   * an entry in config.RECORD_EXCLUSIONS, mirrored in the clause below.
--
-- WHAT IS DELIBERATELY UNCHANGED:
--   * the 2026-09-01 live-date window (matt, 2026-09-04) — a window, not a
--     removal: the picks before it are untouched and still the bet of record;
--   * mv_scored_pick_outcomes, v_model_full_outcome_record and
--     v_model_full_outcome_picks. Those are the threshold-SWEEP universe and
--     must keep re-cutting at today's numbers over every scored pick, BET /
--     AVOID / dead-zone alike (CLAUDE.md 7, THE EVALUATION RULE). Publishing
--     and sweeping are different questions and use different objects;
--   * the open-pick publishers and the app's passesActionFilter, which keep
--     their paused and threshold checks — a paused model must not be offered
--     as something to BET today.
--
-- The JOIN to model_action_thresholds is dropped rather than kept bare. It had
-- one remaining side effect: a model with no row in that table (a RETIRED one,
-- pruned on retirement) was silently dropped from the record. Verified against
-- production 2026-09-12 before removing it — ZERO settled BETs in the published
-- window belong to a model with no threshold row, so this changes no number
-- today. It stops a future retirement quietly erasing a settled record, which
-- is the same defect this migration exists to fix.
--
-- ROLLBACK: re-run data/migrations/live_record_start_views_2026_09_01.sql,
-- which restores the previous definitions including the paused clause.

DO $$
DECLARE
  d text;
BEGIN
  -- ── v_public_track_record ────────────────────────────────────────────────
  -- Guard on min_prob: the corrected view re-cuts nothing, so its definition
  -- cannot mention a threshold column. Guarding on the SHAPE rather than on a
  -- version marker is deliberate — tests/test_live_record_start_views.py
  -- records a migration that reverted itself every pass because its guard
  -- tested something other than the thing it was meant to assert.
  d := pg_get_viewdef('public.v_public_track_record'::regclass, true);
  IF position('min_prob' in d) = 0 AND position('paused' in d) = 0 THEN
    RAISE NOTICE 'v_public_track_record already reports the record as fired - skipping';
  ELSE
    EXECUTE $v$
      CREATE OR REPLACE VIEW public.v_public_track_record WITH (security_invoker = on) AS
      SELECT p.sport,
             p.model_id,
             count(*) FILTER (WHERE p.result = ANY (ARRAY['WIN','LOSS','PUSH']))     AS picks,
             count(*) FILTER (WHERE p.result = 'WIN')                                AS wins,
             count(*) FILTER (WHERE p.result = 'LOSS')                               AS losses,
             count(*) FILTER (WHERE p.result = 'PUSH')                               AS pushes,
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
       WHERE p.signal_type = 'BET'
         AND (p.is_live IS NOT TRUE OR p.model_id LIKE '%\_live\_%')
         AND p.game_date >= '2026-09-01'
         AND NOT (p.model_id = 'mlb_over_under' AND p.game_date < '2026-07-05')
       GROUP BY p.sport, p.model_id
    $v$;
    GRANT SELECT ON public.v_public_track_record TO anon, authenticated;
    RAISE NOTICE 'v_public_track_record now reports the record as fired';
  END IF;

  -- ── v_public_track_record_daily ──────────────────────────────────────────
  -- The same population grouped by day: the equity curve must total to the
  -- hero card, or the screen contradicts itself.
  d := pg_get_viewdef('public.v_public_track_record_daily'::regclass, true);
  IF position('min_prob' in d) = 0 AND position('paused' in d) = 0 THEN
    RAISE NOTICE 'v_public_track_record_daily already reports the record as fired - skipping';
  ELSE
    EXECUTE $v$
      CREATE OR REPLACE VIEW public.v_public_track_record_daily WITH (security_invoker = on) AS
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
       WHERE p.signal_type = 'BET'
         AND (p.is_live IS NOT TRUE OR p.model_id LIKE '%\_live\_%')
         AND p.game_date >= '2026-09-01'
         AND NOT (p.model_id = 'mlb_over_under' AND p.game_date < '2026-07-05')
       GROUP BY p.game_date, p.sport
      HAVING count(*) FILTER (WHERE p.result = ANY (ARRAY['WIN','LOSS','PUSH'])) > 0
    $v$;
    GRANT SELECT ON public.v_public_track_record_daily TO anon, authenticated;
    RAISE NOTICE 'v_public_track_record_daily now reports the record as fired';
  END IF;
END $$;
