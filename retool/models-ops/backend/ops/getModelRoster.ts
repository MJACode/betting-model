type ModelRosterRow = {
  model_id: string
  paused: boolean
  prob_only: boolean
  min_prob: string | null
  min_edge: string | null
  min_odds: string | null
  version: string | null
  trained_on: string | null
  holdout_accuracy: string | null
  calibration_score: string | null
  holdout_picks: number | null
  sport: string
  is_live: boolean
  scoring_method: 'artifact' | 'rule' | 'engine'
  state: 'LIVE' | 'PAUSED' | 'RULES BASED' | 'ENGINE' | 'NO ARTIFACT'
}

export default async function (_req: { params: Record<string, never>; user: User }) {
  const result = await supabase.query<ModelRosterRow>(`
    WITH pick_meta AS (
      SELECT model_id, min(sport) AS sport, bool_and(is_live IS TRUE) AS all_live
      FROM picks GROUP BY 1
    )
    SELECT t.model_id, t.paused, t.prob_only, t.min_prob, t.min_edge, t.min_odds,
           t.scoring_method, r.version, r.trained_on, r.holdout_accuracy, r.calibration_score,
           r.holdout_picks,
           COALESCE(m.sport, upper(split_part(t.model_id, '_', 1))) AS sport,
           (t.model_id LIKE '%live%') AS is_live,
           CASE WHEN t.paused                    THEN 'PAUSED'
                WHEN t.scoring_method = 'rule'   THEN 'RULES BASED'
                WHEN t.scoring_method = 'engine' THEN 'ENGINE'
                WHEN r.version IS NULL           THEN 'NO ARTIFACT'
                ELSE 'LIVE' END AS state
    FROM model_action_thresholds t
    LEFT JOIN pick_meta m ON m.model_id = t.model_id
    LEFT JOIN LATERAL (
      SELECT version, trained_on, holdout_accuracy, calibration_score, holdout_picks
      FROM model_registry mr
      WHERE mr.model_id = t.model_id AND mr.is_active = 1
      ORDER BY mr.created_at DESC LIMIT 1
    ) r ON TRUE
    ORDER BY state, t.model_id
  `)
  return result.data
}
