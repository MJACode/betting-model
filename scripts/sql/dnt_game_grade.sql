-- Dunks & Threes' free pre-game predictions graded against Pinnacle (mike, 2026-11-27:
-- "just test it with the free data"). Read-only. One season per run (:season, our label,
-- the ending year), so a run stays inside the 60-second statement limit.
--
-- edge_ats  = D&T's predicted home margin + Pinnacle's home spread: the predicted home ATS margin
-- edge_tot  = D&T's predicted total - Pinnacle's total
-- Graded at Pinnacle's CLOSE (its last pre-tip snapshot) and its OPEN (the first stored),
-- each at that snapshot's own price, sized 1 unit to win (risk capped at 3), a push 0.
-- No CASE: the read-only SQL hook refuses the keyword END.
WITH d AS (
  SELECT p.season, p.game_id, p.p_home_score - p.p_away_score AS p_margin,
         p.p_home_score + p.p_away_score AS p_total, p.win_prob,
         p.home_score - p.away_score AS margin, p.home_score + p.away_score AS total,
         g.commence_time::timestamptz AS tip
  FROM dnt_game_predictions p JOIN games g ON g.game_id = p.game_id
  WHERE p.status_id = 3 AND p.seasontype = 2 AND p.season = :season),
s AS (
  SELECT d.*, sc.spread_home AS sp_c, sc.home_price AS hp_c, sc.away_price AS ap_c,
         so.spread_home AS sp_o, so.home_price AS hp_o, so.away_price AS ap_o,
         tc.total_line AS t_c, tc.over_price AS op_c, tc.under_price AS up_c,
         t_o.total_line AS t_o, t_o.over_price AS op_o, t_o.under_price AS up_o
  FROM d
  LEFT JOIN LATERAL (SELECT spread_home, home_price, away_price FROM odds o WHERE o.game_id = d.game_id
      AND o.bookmaker = 'pinnacle' AND o.market = 'spreads' AND o.snapshot_type = 'open'
      AND o.snapshot_at::timestamptz <= d.tip ORDER BY o.snapshot_at DESC LIMIT 1) sc ON true
  LEFT JOIN LATERAL (SELECT spread_home, home_price, away_price FROM odds o WHERE o.game_id = d.game_id
      AND o.bookmaker = 'pinnacle' AND o.market = 'spreads' AND o.snapshot_type = 'open'
      AND o.snapshot_at::timestamptz <= d.tip ORDER BY o.snapshot_at ASC LIMIT 1) so ON true
  LEFT JOIN LATERAL (SELECT total_line, over_price, under_price FROM odds o WHERE o.game_id = d.game_id
      AND o.bookmaker = 'pinnacle' AND o.market = 'totals' AND o.snapshot_type = 'open'
      AND o.snapshot_at::timestamptz <= d.tip ORDER BY o.snapshot_at DESC LIMIT 1) tc ON true
  LEFT JOIN LATERAL (SELECT total_line, over_price, under_price FROM odds o WHERE o.game_id = d.game_id
      AND o.bookmaker = 'pinnacle' AND o.market = 'totals' AND o.snapshot_type = 'open'
      AND o.snapshot_at::timestamptz <= d.tip ORDER BY o.snapshot_at ASC LIMIT 1) t_o ON true),
-- one row per (game, market, line timing): the side D&T points to, its result and its price
b AS (
  SELECT 'spread' AS mkt, 'close' AS at, p_margin + sp_c AS edge, (margin + sp_c) AS res_home,
         hp_c AS p_pos, ap_c AS p_neg, (sp_o - sp_c) AS move FROM s WHERE sp_c IS NOT NULL
  UNION ALL
  SELECT 'spread', 'open', p_margin + sp_o, (margin + sp_o), hp_o, ap_o, (sp_o - sp_c) FROM s WHERE sp_o IS NOT NULL
  UNION ALL
  SELECT 'total', 'close', p_total - t_c, (total - t_c), op_c, up_c, (t_c - t_o) FROM s WHERE t_c IS NOT NULL
  UNION ALL
  SELECT 'total', 'open', p_total - t_o, (total - t_o), op_o, up_o, (t_c - t_o) FROM s WHERE t_o IS NOT NULL),
-- the bet: the positive side (home / over) when edge > 0, the other when edge < 0
x AS (
  SELECT mkt, at, edge, move, res_home * sign(edge) AS res,
         p_pos * (edge > 0)::int + p_neg * (edge < 0)::int AS price
  FROM b WHERE edge <> 0),
u AS (
  SELECT x.*, 1 + greatest(price, 0) / 100.0 + (price < 0)::int * 100.0 / abs(least(price, -100)) AS dec
  FROM x),
r AS (
  SELECT u.*, least(1 / (dec - 1), 3) AS risk,
         (res > 0)::int * least(1 / (dec - 1), 3) * (dec - 1) - (res < 0)::int * least(1 / (dec - 1), 3) AS units
  FROM u),
k AS (SELECT unnest(ARRAY[0, 1, 2, 3, 4, 5, 6, 8]) AS k)
SELECT :season AS season, mkt, at, k.k AS min_edge, count(*) AS bets,
       sum((res > 0)::int) AS wins, sum((res < 0)::int) AS losses,
       round(sum(units)::numeric, 2) AS units, round((sum(units) / sum(risk))::numeric, 4) AS roi,
       round((stddev_samp(units / risk) / sqrt(count(*)))::numeric, 4) AS roi_se
FROM r JOIN k ON abs(r.edge) >= k.k
GROUP BY mkt, at, k.k ORDER BY mkt, at, k.k;
