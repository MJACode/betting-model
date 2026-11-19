-- Read-only. Run before data/migrations/site_public_record_v2_2026_11.sql
-- and again after it. Zero rows means the body below matches
-- site_public_record on sport, picks, wins, losses, pushes, units,
-- risked, first_date and last_date. refreshed_at is not compared.
--
-- Before the replace, an empty result is the number check (prod
-- 2026-11-19: 9 sports, 1,622 picks, +72.18 units). After the replace,
-- an empty result means the installed view still returns this body.

WITH v2 AS (
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
         MAX(b.game_date)::date AS last_date
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
   GROUP BY b.sport
)
SELECT COALESCE(v2.sport, cur.sport) AS sport,
       v2.picks AS v2_picks, cur.picks AS live_picks,
       v2.wins AS v2_wins, cur.wins AS live_wins,
       v2.losses AS v2_losses, cur.losses AS live_losses,
       v2.pushes AS v2_pushes, cur.pushes AS live_pushes,
       v2.units AS v2_units, cur.units AS live_units,
       v2.risked AS v2_risked, cur.risked AS live_risked,
       v2.first_date AS v2_first, cur.first_date AS live_first,
       v2.last_date AS v2_last, cur.last_date AS live_last
  FROM v2
  FULL OUTER JOIN public.site_public_record cur ON cur.sport = v2.sport
 WHERE v2.sport IS NULL
    OR cur.sport IS NULL
    OR v2.picks IS DISTINCT FROM cur.picks
    OR v2.wins IS DISTINCT FROM cur.wins
    OR v2.losses IS DISTINCT FROM cur.losses
    OR v2.pushes IS DISTINCT FROM cur.pushes
    OR v2.units IS DISTINCT FROM cur.units
    OR v2.risked IS DISTINCT FROM cur.risked
    OR v2.first_date IS DISTINCT FROM cur.first_date
    OR v2.last_date IS DISTINCT FROM cur.last_date
 ORDER BY 1;
