type Params = {
  modelId: string
  minProb: number
  minEdge: number
  minOdds: number | null
}

type ThresholdPerfResult = {
  modelId: string
  candidatePicks: number
  settled: number
  wins: number
  losses: number
  pushes: number
  priced: number
  units: number
  riskedCount: number
  roiPct: number | null
  partial: boolean
}

export default async function (req: { params: Params; user: User }): Promise<ThresholdPerfResult> {
  const { modelId, minProb, minEdge, minOdds } = req.params

  // minOdds gates on price only when explicitly set — when null, picks pass regardless of
  // whether they have a price at all (mirrors the settled-performance "partial" semantics:
  // a pick can be settled without being priced).
  const result = await supabase.query<{
    candidate_picks: string
    settled: string
    wins: string
    losses: string
    pushes: string
    priced: string
    units: string
  }>(
    `SELECT
       count(*)                                                  AS candidate_picks,
       count(*) FILTER (WHERE result IN ('WIN','LOSS','PUSH'))   AS settled,
       count(*) FILTER (WHERE result = 'WIN')                    AS wins,
       count(*) FILTER (WHERE result = 'LOSS')                   AS losses,
       count(*) FILTER (WHERE result = 'PUSH')                   AS pushes,
       count(profit_units)                                       AS priced,
       COALESCE(SUM(profit_units), 0)                            AS units
     FROM mv_scored_pick_outcomes
     WHERE model_id = $1
       AND model_probability >= $2
       AND edge >= $3
       AND ($4::numeric IS NULL OR dk_odds >= $5)
       AND result IN ('WIN','LOSS','PUSH')`,
    [modelId, minProb, minEdge, minOdds, minOdds]
  )

  const row = result.data[0]
  const settled = row ? parseInt(row.settled, 10) : 0
  const wins = row ? parseInt(row.wins, 10) : 0
  const losses = row ? parseInt(row.losses, 10) : 0
  const pushes = row ? parseInt(row.pushes, 10) : 0
  const priced = row ? parseInt(row.priced, 10) : 0
  const units = row ? parseFloat(row.units) : 0
  const riskedCount = priced - pushes

  return {
    modelId,
    candidatePicks: row ? parseInt(row.candidate_picks, 10) : 0,
    settled,
    wins,
    losses,
    pushes,
    priced,
    units: Math.round(units * 100) / 100,
    riskedCount,
    roiPct: riskedCount > 0 ? Math.round((units / riskedCount) * 100 * 100) / 100 : null,
    partial: priced < settled,
  }
}
