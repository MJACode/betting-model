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
  clv_outcome: 'BEAT' | 'FLAT' | 'WORSE' | 'NOT_MEASURED' | 'UNRESOLVED'
}

export default async function getPickLedger(_req: { params: Params; user: User }) {
  const result = await supabase.query<PickLedgerRow>(`
    -- Posted-only ledger: matches Discord recaps / v_public_track_record.
    -- Taken price = decision_odds, then dk_odds.
    SELECT p.pick_id, p.sport, p.model_id, p.game_date, p.game_id,
           p.pick_label, p.pick_side, p.scored_line,
           COALESCE(p.decision_odds, p.dk_odds) AS odds_at_pick,
           p.closing_dk_odds  AS odds_at_close,
           p.closing_line,
           p.clv_pct, p.line_clv_pts, p.clv_beat_close, p.clv_captured_at,
           p.is_live, p.result,
           -- Returned as the taken price so the frontend does not mark these UNPRICED
           COALESCE(p.decision_odds, p.dk_odds) AS dk_odds,
           p.edge, p.model_probability,
           p.created_at, p.game_time,
           -- Published stake function on the taken price (bare 1u when no price)
           published_pick_unit_profit(COALESCE(p.decision_odds, p.dk_odds), p.result, p.stake_units) AS profit_units,
           CASE
             WHEN p.is_live AND p.model_id LIKE '%\_live\_%' THEN 'live'
             WHEN p.is_live                                   THEN 'repair'
             ELSE 'pregame'
           END AS lane,
           CASE
             WHEN p.clv_captured_at IS NULL THEN 'NOT_MEASURED'
             WHEN p.clv_beat_close THEN 'BEAT'
             WHEN p.line_clv_pts IS NOT NULL AND abs(p.line_clv_pts) > 1e-9 THEN 'WORSE'
             WHEN p.clv_pct IS NULL THEN 'UNRESOLVED'
             WHEN p.clv_pct = 0 THEN 'FLAT'
             ELSE 'WORSE'
           END AS clv_outcome
    FROM picks p
    WHERE p.signal_type = 'BET'
      AND p.game_date >= '2026-09-01'
      AND p.result IN ('WIN', 'LOSS', 'PUSH')
      -- Exclude repair lane (live rows not scored by a live model)
      AND (p.is_live IS NOT TRUE OR p.model_id LIKE '%\_live\_%')
      AND p.downgrade_reason IS DISTINCT FROM 'model paused'
      AND p.condition_status IS DISTINCT FROM 'DUPLICATE'
      AND p.model_id <> 'nfl_live_prop'
      -- Posted to Discord
      AND EXISTS (
        SELECT 1 FROM v_discord_published d
        WHERE d.lock_key = CASE
          WHEN p.is_live THEN 'live:' || p.game_id || ':' || p.model_id || ':' || p.pick_side
                              || COALESCE(':' || p.player_id, '')
                              || COALESCE(':' || p.player_key, '')
                              || COALESCE(':' || p.prop_market, '')
          ELSE p.game_id || ':' || p.model_id
               || COALESCE(':' || p.player_id, '')
               || COALESCE(':' || p.player_key, '')
               || COALESCE(':' || p.prop_market, '')
        END
      )
    ORDER BY p.game_date DESC, p.pick_id DESC
  `)
  return result.data
}
