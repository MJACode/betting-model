-- Replace site_public_record so anon can read it after step A.
-- HAND APPLIED. Not in ACTIVE_MIGRATIONS.
--
-- site_public_record_2026_11.sql is already applied. This file does not
-- recreate site_retired_models and does not change the column list.
--
-- The first view is security_invoker off, but it reads
-- v_public_track_record, and that view reads v_discord_published. Both
-- of those are security_invoker on. Postgres then checks the inner read
-- as anon. Step A revoked anon on those views and on picks, and
-- SELECT failed with 42501 "permission denied for view v_discord_published"
-- (2026-11-18, 11:13 PM ET). Step A was undone at 11:15.
--
-- This view reads public.picks and public.push_sent. It does not read a
-- view. The publish lock is the same predicate as v_discord_published.
-- The stake math is the body of published_pick_unit_profit(price, result,
-- stake_units) and published_pick_unit_risked, inlined, because those
-- functions are SECURITY INVOKER and step A revokes anon EXECUTE on them.
-- A call from this view would be checked as anon.
--
-- Owner is postgres. Row security is on for picks, push_sent and
-- site_retired_models, and FORCE ROW LEVEL SECURITY is off, measured
-- 2026-11-19. The table owner skips row security unless FORCE is on.
-- The block below aborts if FORCE is on. Do not apply past that.
--
-- Run scripts/site_public_record_v2_verify.sql first. Zero rows means
-- this body matches the live view. Measured on prod before this file
-- was written: 9 sports, 1,622 picks, +72.18 units, zero differing rows.
-- Run the same script again after. Zero rows means the installed view
-- still returns this body.
--
-- Then apply step A. As anon: SELECT * FROM site_public_record returns
-- rows. The website does not need a redeploy.

BEGIN;

DO $force$
BEGIN
  IF EXISTS (
    SELECT 1
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relname IN ('picks', 'push_sent', 'site_retired_models')
       AND c.relforcerowsecurity
  ) THEN
    RAISE EXCEPTION
      'FORCE ROW LEVEL SECURITY is on for picks, push_sent, or site_retired_models. The view owner would be subject to it. Stop.';
  END IF;
END
$force$;

CREATE OR REPLACE VIEW public.site_public_record
WITH (security_invoker = false, security_barrier = true) AS
SELECT b.sport,
       COUNT(*) FILTER (WHERE b.result IN ('WIN', 'LOSS', 'PUSH'))::integer AS picks,
       COUNT(*) FILTER (WHERE b.result = 'WIN')::integer AS wins,
       COUNT(*) FILTER (WHERE b.result = 'LOSS')::integer AS losses,
       COUNT(*) FILTER (WHERE b.result = 'PUSH')::integer AS pushes,
       ROUND(COALESCE(SUM(
         CASE b.result
           WHEN 'WIN' THEN b.win_u
           WHEN 'LOSS' THEN -b.risk
           ELSE 0
         END
       ) FILTER (WHERE b.result IN ('WIN', 'LOSS', 'PUSH')), 0), 2)::numeric(12, 2) AS units,
       ROUND(COALESCE(SUM(
         CASE WHEN b.result IN ('WIN', 'LOSS') THEN b.risk ELSE 0 END
       ) FILTER (WHERE b.result IN ('WIN', 'LOSS', 'PUSH')), 0), 2)::numeric(12, 2) AS risked,
       MIN(b.game_date)::date AS first_date,
       MAX(b.game_date)::date AS last_date,
       now() AS refreshed_at
  FROM (
    SELECT s.sport,
           s.result,
           s.game_date,
           CASE WHEN d IS NULL THEN c
                WHEN c / d > 3.0 THEN 3.0
                ELSE c / d END AS risk,
           CASE WHEN d IS NULL THEN c
                WHEN c / d > 3.0 THEN 3.0 * d
                ELSE c END AS win_u
      FROM (
        SELECT p.sport,
               p.result,
               p.game_date,
               CASE WHEN p.stake_units >= 1 AND p.stake_units <= 3
                    THEN p.stake_units ELSE 1.0 END AS c,
               CASE WHEN px IS NULL OR px = 0 THEN NULL
                    WHEN px > 0 THEN px / 100.0
                    ELSE 100.0 / abs(px) END AS d
          FROM (
            SELECT p.sport,
                   p.result,
                   p.game_date,
                   p.stake_units,
                   COALESCE(p.decision_odds, p.dk_odds) AS px
              FROM public.picks p
             WHERE p.signal_type = 'BET'
               AND (p.is_live IS NOT TRUE OR p.model_id LIKE '%\_live\_%')
               AND p.game_date >= '2026-09-01'
               AND NOT (p.model_id = 'mlb_over_under' AND p.game_date < '2026-07-05')
               AND p.downgrade_reason IS DISTINCT FROM 'model paused'
               AND p.model_id <> 'nfl_live_prop'
               AND p.condition_status IS DISTINCT FROM 'DUPLICATE'
               AND p.model_id <> 'ufc_moneyline'
               AND p.model_id <> 'ufc_total_rounds'
               AND p.model_id <> 'ufc_method_of_victory'
               AND NOT EXISTS (
                     SELECT 1 FROM public.site_retired_models rm
                      WHERE rm.model_id = p.model_id)
               AND EXISTS (
                     SELECT 1
                       FROM public.push_sent s
                      WHERE s.lock_key = CASE
                              WHEN p.is_live THEN
                                'live:' || p.game_id || ':' || p.model_id || ':' || p.pick_side
                                || COALESCE(':' || p.player_id, '')
                                || COALESCE(':' || p.player_key, '')
                                || COALESCE(':' || p.prop_market, '')
                              ELSE
                                p.game_id || ':' || p.model_id
                                || COALESCE(':' || p.player_id, '')
                                || COALESCE(':' || p.player_key, '')
                                || COALESCE(':' || p.prop_market, '')
                            END
                        AND s.kind IN ('discord_signal', 'discord_live')
                        AND NOT EXISTS (
                              SELECT 1
                                FROM public.push_sent v
                               WHERE v.lock_key = s.lock_key
                                 AND v.kind = 'discord_void'
                                 AND (
                                       (v.sent_at IS NOT NULL
                                        AND (s.sent_at IS NULL OR v.sent_at > s.sent_at))
                                    OR (v.sent_at IS NULL AND s.sent_at IS NULL)
                                     )
                            )
                   )
          ) p
      ) s
  ) b
 GROUP BY b.sport;

ALTER VIEW public.site_public_record OWNER TO postgres;

REVOKE ALL ON public.site_public_record FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.site_public_record TO anon, authenticated;

COMMENT ON VIEW public.site_public_record IS
  'Website record row. Reads picks and push_sent directly, security_invoker off, owner postgres. No model id. Retired models excluded.';

NOTIFY pgrst, 'reload schema';
COMMIT;
