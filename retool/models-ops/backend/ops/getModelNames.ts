import { isMissingRelation } from './dbErrors'

type ModelNameRow = {
  model_id: string
  name: string | null
  short_name: string | null
  sport: string | null
  in_play: boolean | null
}

export default async function (_req: { params: Record<string, never>; user: User }): Promise<ModelNameRow[]> {
  try {
    const result = await supabase.query<ModelNameRow>(
      'SELECT model_id, name, short_name, sport, in_play FROM model_display_names',
    )
    return result.data
  } catch (err) {
    // The view is added by a separate database update; until then, fall back to ids.
    if (isMissingRelation(err)) return []
    throw err
  }
}
