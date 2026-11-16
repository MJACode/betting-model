import { errorMessage, isLayoutTab, cleanLayoutName } from './dbErrors'

type Params = { tab: string; name: string }

type Result =
  | { ok: true; deleted: number }
  | { ok: false; message: string }

export default async function (req: { params: Params; user: User }): Promise<Result> {
  const owner = req.user?.email
  if (!owner) return { ok: false, message: 'no signed-in user' }
  const { tab, name } = req.params ?? ({} as Params)
  if (!isLayoutTab(tab)) return { ok: false, message: `unknown tab: ${String(tab)}` }
  const cleanName = cleanLayoutName(name)
  if (!cleanName) return { ok: false, message: 'name must be 1 to 60 characters' }

  try {
    const result = await supabase.query<{ name: string }>(
      'DELETE FROM dashboard_layouts WHERE owner = $1 AND tab = $2 AND name = $3 RETURNING name',
      [owner, tab, cleanName],
    )
    return { ok: true, deleted: result.data.length }
  } catch (err) {
    return { ok: false, message: errorMessage(err) }
  }
}
