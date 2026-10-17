-- record_excludes_paused_rows (2026-09-28; Matt via CoS; Michael-gated)
--
-- WHY. models/scorer._paused_signal now keeps a paused model's REAL verdict:
-- a paused model's BET is written as signal_type = 'BET', with its real stake,
-- instead of being turned into NONE. Being paused means the pick is NOT A
-- SIGNAL -- never posted to Discord, never pushed, never staked -- so it must
-- not reach the published record either. Every row a paused model writes
-- carries downgrade_reason = 'model paused' (config.PAUSED_NOTE), stamped when
-- the pick is written. These two views now drop those rows.
--
-- THIS IS STILL A FILTER ON WHAT THE PICK WAS (CLAUDE.md 1c). The marker is on
-- the row and never changes; nothing here joins model_action_thresholds or
-- reads the model's present state. A BET a LIVE model wrote stays in the
-- record after the model is paused (settled_record_survives_a_pause_2026_09_12
-- is untouched in spirit), and a BET written while paused stays out after an
-- unpause. Before this change no row was both 'BET' and 'model paused' (the
-- scorer wrote NONE), so on the day it applies this moves no number.
--
-- SAME POPULATION IN BOTH VIEWS: the curve must total to the hero card.
-- Everything else is verbatim from the owners:
--   * v_public_track_record       -- track_record_clv_no_vig_2026_09_14.sql
--   * v_public_track_record_daily -- settled_record_survives_a_pause_2026_09_12.sql
-- and each owner's guard skips this definition (it keeps 'clv_method',
-- '2026-09-01' and 'dk_odds IS NOT NULL', and has no 'min_prob' / 't.paused').
--
-- Guard on the clause itself, so a later owner can supersede without this file
-- putting the old definition back (the live-date revert lesson).
--
-- MUST run after track_record_clv_no_vig_2026_09_14.sql (ACTIVE_MIGRATIONS).
-- ROLLBACK: re-run track_record_clv_no_vig_2026_09_14.sql's body and
-- settled_record_survives_a_pause_2026_09_12.sql's daily branch.

DO $mig$
DECLARE
  d text;
BEGIN
  -- ── v_public_track_record ────────────────────────────────────────────────
  d := pg_get_viewdef('public.v_public_track_record'::regclass, true);
  IF position('model paused' in d) > 0 THEN
    RAISE NOTICE 'v_public_track_record already excludes paused rows - skipping';
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
                 WHERE (p.result = ANY (ARRAY['WIN','LOSS','PUSH']))
                   AND p.clv_pct IS NOT NULL
                   AND p.clv_method IN ('no_vig','zero_vig'))                         AS clv_settled,
             count(*) FILTER (
                 WHERE (p.result = ANY (ARRAY['WIN','LOSS','PUSH']))
                   AND p.clv_pct > 0::numeric
                   AND p.clv_method IN ('no_vig','zero_vig'))                         AS clv_beat,
             avg(p.clv_pct) FILTER (
                 WHERE (p.result = ANY (ARRAY['WIN','LOSS','PUSH']))
                   AND p.clv_pct IS NOT NULL
                   AND p.clv_method IN ('no_vig','zero_vig'))                         AS avg_clv_pct,
             min(p.game_date)                                                        AS first_date,
             max(p.game_date)                                                        AS last_date
        FROM picks p
       WHERE p.signal_type = 'BET'
         AND (p.is_live IS NOT TRUE OR p.model_id LIKE '%\_live\_%')
         AND p.game_date >= '2026-09-01'
         AND NOT (p.model_id = 'mlb_over_under' AND p.game_date < '2026-07-05')
         AND p.downgrade_reason IS DISTINCT FROM 'model paused'
       GROUP BY p.sport, p.model_id
    $v$;
    GRANT SELECT ON public.v_public_track_record TO anon, authenticated;
    RAISE NOTICE 'v_public_track_record now excludes paused rows';
  END IF;

  -- ── v_public_track_record_daily ──────────────────────────────────────────
  d := pg_get_viewdef('public.v_public_track_record_daily'::regclass, true);
  IF position('model paused' in d) > 0 THEN
    RAISE NOTICE 'v_public_track_record_daily already excludes paused rows - skipping';
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
         AND p.downgrade_reason IS DISTINCT FROM 'model paused'
       GROUP BY p.game_date, p.sport
      HAVING count(*) FILTER (WHERE p.result = ANY (ARRAY['WIN','LOSS','PUSH'])) > 0
    $v$;
    GRANT SELECT ON public.v_public_track_record_daily TO anon, authenticated;
    RAISE NOTICE 'v_public_track_record_daily now excludes paused rows';
  END IF;
END $mig$;
