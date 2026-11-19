export default async function (_req: { params: Record<string, never>; user: User }) {
  // Blocks of 25, 50 and 100 over each model's newest 500 bets; block_no 1 is the newest.
  const result = await supabase.query(`SELECT * FROM v_model_health_windows ORDER BY model_id, block_size, block_no`)
  return result.data
}
