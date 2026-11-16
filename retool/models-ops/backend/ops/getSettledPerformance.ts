type PerformanceRow = {
  model_id: string
  sport: string
  settled: string
  wins: string
  losses: string
  pushes: string
  priced: string
  units: string
  risked: string
  roi_pct: string | null
  partial: boolean
  last_date: string
}

export default async function (_req: { params: Record<string, never>; user: User }) {
  const result = await supabase.query<PerformanceRow>(`
    WITH perf AS (
      SELECT model_id, sport,
             COUNT(*)                              AS settled,
             COUNT(*) FILTER (WHERE result='WIN')  AS wins,
             COUNT(*) FILTER (WHERE result='LOSS') AS losses,
             COUNT(*) FILTER (WHERE result='PUSH') AS pushes,
             COUNT(profit_units)                   AS priced,
             COALESCE(SUM(profit_units), 0)        AS units,
             MAX(game_date)                        AS last_date
      FROM mv_scored_pick_outcomes
      WHERE signal_type = 'BET' AND result IN ('WIN','LOSS','PUSH')
      GROUP BY model_id, sport)
    SELECT model_id, sport, settled, wins, losses, pushes, priced,
           ROUND(units, 2)   AS units,
           (priced - pushes) AS risked,
           CASE WHEN (priced - pushes) > 0
                THEN ROUND(units / (priced - pushes) * 100, 2) END AS roi_pct,
           (priced < settled) AS partial,
           last_date
    FROM perf ORDER BY settled DESC
  `)
  return result.data
}
