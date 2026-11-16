// The only write in this app. The database function does all validation of
// the setting itself; this only checks the level and attaches the signed-in user.
const LEVELS = ['all', 'top_75', 'top_half', 'top_quarter', 'custom'] as const
type Level = typeof LEVELS[number]

type Params = {
  modelId: string
  level: Level
  value: number | null
  note: string | null
}

type SetModelVolumeRow = {
  model: string
  setting: string | null
  cut_on: string
  config_cut: string | null
  cut_in_force: string | null
}

type Result =
  | { ok: true; row: SetModelVolumeRow | null }
  | { ok: false; message: string }

export default async function (req: { params: Params; user: User }): Promise<Result> {
  const { modelId, level, value, note } = req.params
  const who = req.user?.email
  if (!who) return { ok: false, message: 'no signed-in user' }
  if (typeof modelId !== 'string' || modelId === '') return { ok: false, message: 'no model given' }
  if (!(LEVELS as readonly string[]).includes(level)) {
    return { ok: false, message: `unknown level: ${String(level)}` }
  }

  const num = typeof value === 'number' && Number.isFinite(value) ? value : null
  const noteText = typeof note === 'string' && note.trim() !== '' ? note.trim() : null

  try {
    const result = await supabase.query<SetModelVolumeRow>(
      'SELECT * FROM set_model_volume($1, $2, $3, $4, $5)',
      [modelId, level, who, num, noteText],
    )
    return { ok: true, row: result.data[0] ?? null }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return { ok: false, message }
  }
}
