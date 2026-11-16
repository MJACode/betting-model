import { errorMessage, isLayoutTab, cleanLayoutName } from './dbErrors'

type TileLayout = {
  id: string
  x: number
  y: number
  w: number
  h: number
  hidden: boolean
}

type Params = { tab: string; name: string; layout: TileLayout[] }

type Result =
  | { ok: true; name: string; updated_at: string | null }
  | { ok: false; message: string }

export default async function (req: { params: Params; user: User }): Promise<Result> {
  const owner = req.user?.email
  if (!owner) return { ok: false, message: 'no signed-in user' }
  const { tab, name, layout } = req.params ?? ({} as Params)
  if (!isLayoutTab(tab)) return { ok: false, message: `unknown tab: ${String(tab)}` }
  const cleanName = cleanLayoutName(name)
  if (!cleanName) return { ok: false, message: 'name must be 1 to 60 characters' }
  if (!Array.isArray(layout)) return { ok: false, message: 'layout must be a list of tiles' }

  // Keep only the stored fields so nothing else ends up in the saved JSON.
  const tiles = layout
    .filter(t => t && typeof t.id === 'string')
    .map(t => ({
      id: t.id,
      x: Number(t.x) || 0,
      y: Number(t.y) || 0,
      w: Number(t.w) || 1,
      h: Number(t.h) || 1,
      hidden: t.hidden === true,
    }))

  try {
    const result = await supabase.query<{ name: string; updated_at: string }>(
      `INSERT INTO dashboard_layouts (owner, tab, name, layout, updated_at)
       VALUES ($1, $2, $3, $4::jsonb, now())
       ON CONFLICT (owner, tab, name) DO UPDATE SET layout = EXCLUDED.layout, updated_at = now()
       RETURNING name, updated_at`,
      [owner, tab, cleanName, JSON.stringify(tiles)],
    )
    return { ok: true, name: cleanName, updated_at: result.data[0]?.updated_at ?? null }
  } catch (err) {
    return { ok: false, message: errorMessage(err) }
  }
}
