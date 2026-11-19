export default async function (_req: { params: Record<string, never>; user: User }) {
  // One row per published bet, newest 500 per model; seq 1 is the model's newest.
  const result = await supabase.query(`
    SELECT pick_id, model_id, sport, game_date, created_at, pick_label, result,
           status, verdict, clv_pct, market_clv_pct, line_clv_pts, units, seq
      FROM v_model_health_bets
     WHERE seq <= 500
     ORDER BY model_id, seq DESC`)
  return result.data
}
