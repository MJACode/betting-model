import { isMissingRelation, errorMessage, isLayoutTab } from './dbErrors'

type Params = { tab: string }

type LayoutRow = {
  name: string
  layout: unknown
  updated_at: string
}

type Result =
  | { ok: true; layouts: LayoutRow[]; available: boolean }
  | { ok: false; message: string }

export default async function (req: { params: Params; user: User }): Promise<Result> {
  const owner = req.user?.email
  if (!owner) return { ok: false, message: 'no signed-in user' }
  const tab = req.params?.tab
  if (!isLayoutTab(tab)) return { ok: false, message: `unknown tab: ${String(tab)}` }

  try {
    const result = await supabase.query<LayoutRow>(
      'SELECT name, layout, updated_at FROM dashboard_layouts WHERE owner = $1 AND tab = $2 ORDER BY name',
      [owner, tab],
    )
    return { ok: true, layouts: result.data, available: true }
  } catch (err) {
    if (isMissingRelation(err)) return { ok: true, layouts: [], available: false }
    return { ok: false, message: errorMessage(err) }
  }
}
