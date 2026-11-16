type ModelVolumeBandRow = {
  model_id: string
  sport: string
  paused: boolean
  in_play: boolean
  cut_on: 'edge' | 'probability'
  band: 'all' | 'top_75' | 'top_half' | 'top_quarter'
  band_order: number
  threshold: string | null
  config_cut: string | null
  cut_in_force: string | null
  setting: 'top_75' | 'top_half' | 'top_quarter' | 'custom' | null
  setting_value: string | null
  setting_in_force: boolean | null
  setting_by: string | null
  setting_at: string | null
  recent_bets_at_config_cut: string | null
  recent_days_with_a_bet: string | null
  first_bet_date: string | null
  last_bet_date: string | null
  enough_bets: boolean
  recent_bets: string | null
  bets_per_day: string | null
  graded: string | null
  wins: string | null
  losses: string | null
  units: string | null
  roi_pct: string | null
}

export default async function (_req: { params: Record<string, never>; user: User }) {
  const result = await supabase.query<ModelVolumeBandRow>(`
    SELECT * FROM model_volume_bands ORDER BY sport, model_id, band_order
  `)
  return result.data
}
