type PicksRow = {
  game_date: string
  model_id: string
  scored: string
  bets: string
}

export default async function (_req: { params: Record<string, never>; user: User }) {
  const result = await supabase.query<PicksRow>(`
    SELECT game_date, model_id,
           COUNT(*)                                    AS scored,
           COUNT(*) FILTER (WHERE signal_type = 'BET') AS bets
    FROM picks
    WHERE game_date >= to_char(NOW() - interval '14 days', 'YYYY-MM-DD')
      AND game_date <= to_char(NOW() + interval '1 day',  'YYYY-MM-DD')
      AND is_live IS NOT TRUE
    GROUP BY game_date, model_id
    ORDER BY game_date, model_id
  `)
  return result.data
}
