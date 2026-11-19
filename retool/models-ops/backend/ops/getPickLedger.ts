type Params = Record<string, never>

export type Lane = 'pregame' | 'live' | 'repair'

export type PickLedgerRow = {
  pick_id: string
  sport: string
  model_id: string
  game_date: string
  game_id: string
  pick_label: string
  pick_side: string | null
  scored_line: string | null
  odds_at_pick: string | null
  odds_at_close: string | null
  closing_line: string | null
  clv_pct: string | null
  line_clv_pts: string | null
  clv_beat_close: boolean | null
  clv_captured_at: string | null
  is_live: boolean
  result: string | null
  dk_odds: string | null   // raw price — used to classify UNPRICED rows in the frontend
  edge: string | null
  model_probability: string | null
  created_at: string
  game_time: string | null
  profit_units: string | null
  lane: Lane
  clv_outcome: 'BEAT' | 'FLAT' | 'WORSE' | 'LINE_FOR' | 'LINE_AGAINST' | 'NOT_MEASURED' | 'UNRESOLVED'
}

export default async function getPickLedger(_req: { params: Params; user: User }) {
  const result = await supabase.query<PickLedgerRow>(`
    -- The published record's graded bets: v_model_health_bets reads its filter
    -- out of v_public_track_record itself, so this list cannot drift from it.
    -- Taken price = decision_odds, then dk_odds.
    SELECT p.pick_id, p.sport, p.model_id, p.game_date, p.game_id,
           p.pick_label, p.pick_side, p.scored_line,
           COALESCE(p.decision_odds, p.dk_odds) AS odds_at_pick,
           p.closing_dk_odds  AS odds_at_close,
           p.closing_line,
           p.clv_pct, p.line_clv_pts, p.clv_beat_close, p.clv_captured_at,
           p.is_live, p.result,
           COALESCE(p.decision_odds, p.dk_odds) AS dk_odds,
           p.edge, p.model_probability,
           p.created_at, p.game_time,
           published_pick_unit_profit(COALESCE(p.decision_odds, p.dk_odds), p.result, p.stake_units) AS profit_units,
           CASE
             WHEN p.is_live AND p.model_id LIKE '%\\_live\\_%' THEN 'live'
             WHEN p.is_live                                   THEN 'repair'
             ELSE 'pregame'
           END AS lane,
           CASE
             WHEN h.status = 'price' AND h.verdict = 'beat' THEN 'BEAT'
             WHEN h.status = 'price' AND h.verdict = 'push' THEN 'FLAT'
             WHEN h.status = 'price'                        THEN 'WORSE'
             WHEN h.status = 'line_for'                     THEN 'LINE_FOR'
             WHEN h.status = 'line_against'                 THEN 'LINE_AGAINST'
             WHEN h.status = 'no_close'                     THEN 'UNRESOLVED'
             ELSE 'NOT_MEASURED'
           END AS clv_outcome
    FROM v_model_health_bets h
    JOIN picks p ON p.pick_id = h.pick_id
    ORDER BY p.game_date DESC, p.pick_id DESC
  `)
  return result.data
}
