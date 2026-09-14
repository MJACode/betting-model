-- Published CLV pedigree reads only the no-vig (or already-no-vig) formula.
--
-- WHY. capture now writes multiplicative de-vig into picks.clv_pct and stamps
-- clv_method. Until _backfill_clv rewrites the pre-2026-09-14 rows, those
-- still carry raw_one_sided. Averaging both in v_public_track_record is the
-- mix the app's Sharp Score would publish as one number. Filter the CLV
-- aggregates, not the pick population: units and W-L stay the fired record.
--
-- MUST run after add_clv_method_2026_09_14.sql (the column) and after
-- settled_record_survives_a_pause_2026_09_12.sql (owns this view). Guard on
-- clv_method in the viewdef so a later owner can supersede without this file
-- putting the old definition back (the live-date revert lesson).
--
-- Daily view has no CLV columns; leave it alone.
--
-- ROLLBACK: re-run settled_record_survives_a_pause_2026_09_12.sql.

DO $$
DECLARE
  d text;
BEGIN
  d := pg_get_viewdef('public.v_public_track_record'::regclass, true);
  IF position('clv_method' in d) > 0 THEN
    RAISE NOTICE 'v_public_track_record already filters CLV pedigree on method - skipping';
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
       GROUP BY p.sport, p.model_id
    $v$;
    GRANT SELECT ON public.v_public_track_record TO anon, authenticated;
    RAISE NOTICE 'v_public_track_record CLV pedigree is no-vig only';
  END IF;
END $$;
