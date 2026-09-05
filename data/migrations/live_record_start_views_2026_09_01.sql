-- live_record_start_views_2026_09_01 (2026-09-04)
--
-- THE SECOND HALF OF live_record_start_2026_09_01.sql, MADE SELF-HEALING.
--
-- That migration moved the published record to the official live date. Only
-- half of it survived in production. Measured 2026-09-04:
--
--   v_public_track_record        gated at 2026-09-01  (correct)
--   v_public_track_record_daily  gated at 2026-04-14  (the pre-migration UNION)
--
-- The app reads the first for the hero card and the second for the equity
-- curve, so the Track Record screen showed "+17.2%, 43-27, 70 settled picks"
-- (the 9/1 window, +12.02u) directly above a curve ending at +64.1u — which is
-- MLB from 2026-04-17 to 2026-09-03. Two windows, one screen, no warning.
--
-- WHY IT DRIFTED — not a hand-edit that was forgotten. It was REVERTED, every
-- pipeline pass, by a migration still in data/view_migrations.py's active list:
-- track_record_reads_graded_matview.sql redefined the daily view too, guarded
-- on `position('mv_scored_pick_outcomes' in pg_get_viewdef(...)) > 0`. Once the
-- daily view stopped reading the matview, that guard read "not applied yet" and
-- the ELSE branch restored the 2026-04-14 definition on the next pass. Measured
-- immediately before this file was written: the guard evaluated to 0, so the
-- revert was pending, not hypothetical. That branch has been removed from that
-- file; this one owns the daily view now.
--
-- The lesson generalises, which is why it is written here rather than in a
-- session log: AN IDEMPOTENCY GUARD THAT ASKS "DOES THE VIEW STILL LOOK LIKE MY
-- OUTPUT?" IS A LOCK, NOT A GUARD. It cannot tell "never applied" from
-- "deliberately superseded", and it re-applies itself over the newer
-- definition every pass, silently, forever. A guard belongs on the property the
-- migration is trying to establish — here, the live-date gate.
--
-- WHAT THE DEFINITIONS ARE: verbatim from live_record_start_2026_09_01.sql,
-- which is the reviewed and merged source of truth for the published record
-- (settled BET picks as fired, one measure for every model, mirroring Retool).
-- Nothing about the numbers changes; this only makes the daily half stick.
--
-- IDEMPOTENT: each view is skipped once its own definition carries the
-- 2026-09-01 gate, so the runner can execute this on every pass with no DDL on
-- the no-op path. Every DDL statement, GRANT included, forces a PostgREST
-- schema-cache reload, so the GRANTs sit inside the guarded branches
-- (CLAUDE.md §7). Single statement, as data/view_migrations.py requires.

DO $mig$
DECLARE
  d text;
BEGIN
  -- ── v_public_track_record ────────────────────────────────────────────────
  d := pg_get_viewdef('public.v_public_track_record'::regclass, true);
  IF position('2026-09-01' in d) > 0 THEN
    RAISE NOTICE 'v_public_track_record already starts at the live date - skipping';
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
        JOIN model_action_thresholds t ON t.model_id = p.model_id
       WHERE p.signal_type = 'BET'
         AND (p.is_live IS NOT TRUE OR p.model_id LIKE '%\_live\_%')
         AND t.paused IS NOT TRUE
         AND p.game_date >= '2026-09-01'
         AND p.model_probability >= t.min_prob
         AND (t.prob_only OR p.edge >= t.min_edge)
         AND (t.min_odds IS NULL OR p.dk_odds IS NULL OR p.dk_odds >= t.min_odds)
       GROUP BY p.sport, p.model_id
    $v$;
    GRANT SELECT ON public.v_public_track_record TO anon, authenticated;
    RAISE NOTICE 'v_public_track_record re-gated at the 2026-09-01 live date';
  END IF;

  -- ── v_public_track_record_daily ──────────────────────────────────────────
  -- The same population, grouped by day instead of by model: the equity curve
  -- must total to the hero card, or the screen contradicts itself.
  d := pg_get_viewdef('public.v_public_track_record_daily'::regclass, true);
  IF position('2026-09-01' in d) > 0 THEN
    RAISE NOTICE 'v_public_track_record_daily already starts at the live date - skipping';
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
        JOIN model_action_thresholds t ON t.model_id = p.model_id
       WHERE p.signal_type = 'BET'
         AND (p.is_live IS NOT TRUE OR p.model_id LIKE '%\_live\_%')
         AND t.paused IS NOT TRUE
         AND p.game_date >= '2026-09-01'
         AND p.model_probability >= t.min_prob
         AND (t.prob_only OR p.edge >= t.min_edge)
         AND (t.min_odds IS NULL OR p.dk_odds IS NULL OR p.dk_odds >= t.min_odds)
       GROUP BY p.game_date, p.sport
      HAVING count(*) FILTER (WHERE p.result = ANY (ARRAY['WIN','LOSS','PUSH'])) > 0
    $v$;
    GRANT SELECT ON public.v_public_track_record_daily TO anon, authenticated;
    RAISE NOTICE 'v_public_track_record_daily re-gated at the 2026-09-01 live date';
  END IF;
END
$mig$;
