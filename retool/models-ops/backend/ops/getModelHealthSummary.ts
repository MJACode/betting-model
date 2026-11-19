export default async function (_req: { params: Record<string, never>; user: User }) {
  // One row per model over the published record's bets (v_model_health_summary).
  const result = await supabase.query(`SELECT * FROM v_model_health_summary ORDER BY bets DESC, model_id`)
  return result.data
}
