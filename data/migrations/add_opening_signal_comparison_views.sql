-- Migration: add_opening_signal_comparison_views (applied 2026-06-20)
-- Powers the mobile "Opening vs Live" screen. Both views are security_invoker
-- (respect anon RLS on opening_signals + picks) and granted to anon.

CREATE OR REPLACE VIEW v_opening_vs_live
WITH (security_invoker = on) AS
SELECT 'opening'::text AS track,
       COUNT(*)                                       AS picks,
       COUNT(*) FILTER (WHERE result = 'WIN')         AS wins,
       COUNT(*) FILTER (WHERE result = 'LOSS')        AS losses,
       COUNT(*) FILTER (WHERE result = 'PUSH')        AS pushes,
       COALESCE(SUM(profit_flat), 0)                  AS profit_flat,
       100 * COUNT(*)                                 AS staked_flat,
       COUNT(*) FILTER (WHERE clv_pct IS NOT NULL)    AS clv_settled,
       COUNT(*) FILTER (WHERE clv_pct > 0)            AS clv_beat,
       AVG(clv_pct)                                   AS avg_clv_pct
FROM opening_signals
WHERE result IN ('WIN','LOSS','PUSH')
  AND game_date >= '2026-04-14'
  AND model_id NOT LIKE 'mlb_prop_%'  AND model_id NOT LIKE 'wnba_prop_%'
  AND model_id NOT LIKE 'nba_prop_%'  AND model_id NOT LIKE 'ufc_%'
  AND model_id NOT LIKE 'golf_%'      AND model_id NOT LIKE 'mlb_live_%'
UNION ALL
SELECT 'live'::text AS track,
       COUNT(*),
       COUNT(*) FILTER (WHERE result = 'WIN'),
       COUNT(*) FILTER (WHERE result = 'LOSS'),
       COUNT(*) FILTER (WHERE result = 'PUSH'),
       COALESCE(SUM(profit_flat), 0),
       100 * COUNT(*),
       COUNT(*) FILTER (WHERE clv_pct IS NOT NULL),
       COUNT(*) FILTER (WHERE clv_pct > 0),
       AVG(clv_pct)
FROM picks
WHERE signal_type = 'BET'
  AND result IN ('WIN','LOSS','PUSH')
  AND game_date >= '2026-04-14'
  AND model_id NOT LIKE 'mlb_prop_%'  AND model_id NOT LIKE 'wnba_prop_%'
  AND model_id NOT LIKE 'nba_prop_%'  AND model_id NOT LIKE 'ufc_%'
  AND model_id NOT LIKE 'golf_%'      AND model_id NOT LIKE 'mlb_live_%';

GRANT SELECT ON v_opening_vs_live TO anon, authenticated;

CREATE OR REPLACE VIEW v_opening_signal_slices
WITH (security_invoker = on) AS
WITH base AS (
  SELECT * FROM opening_signals
  WHERE result IN ('WIN','LOSS','PUSH')
    AND game_date >= '2026-04-14'
    AND model_id NOT LIKE 'mlb_prop_%'  AND model_id NOT LIKE 'wnba_prop_%'
    AND model_id NOT LIKE 'nba_prop_%'  AND model_id NOT LIKE 'ufc_%'
    AND model_id NOT LIKE 'golf_%'      AND model_id NOT LIKE 'mlb_live_%'
)
SELECT 'line_move'::text AS slice_kind,
       COALESCE(line_move_dir, 'unknown') AS slice_value,
       COUNT(*) AS picks,
       COUNT(*) FILTER (WHERE result = 'WIN')  AS wins,
       COUNT(*) FILTER (WHERE result = 'LOSS') AS losses,
       COUNT(*) FILTER (WHERE result = 'PUSH') AS pushes,
       COALESCE(SUM(profit_flat), 0) AS profit_flat,
       100 * COUNT(*) AS staked_flat,
       AVG(clv_pct) AS avg_clv_pct
FROM base
GROUP BY COALESCE(line_move_dir, 'unknown')
UNION ALL
SELECT 'public'::text AS slice_kind,
       COALESCE(public_side, 'no_split') AS slice_value,
       COUNT(*),
       COUNT(*) FILTER (WHERE result = 'WIN'),
       COUNT(*) FILTER (WHERE result = 'LOSS'),
       COUNT(*) FILTER (WHERE result = 'PUSH'),
       COALESCE(SUM(profit_flat), 0),
       100 * COUNT(*),
       AVG(clv_pct)
FROM base
GROUP BY COALESCE(public_side, 'no_split');

GRANT SELECT ON v_opening_signal_slices TO anon, authenticated;
