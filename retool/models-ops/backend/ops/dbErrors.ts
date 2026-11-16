// Shared helpers for the dashboard's newer backend functions.

/** True when a query failed because the table or view has not been created yet. */
export function isMissingRelation(err: unknown): boolean {
  const code = (err as { code?: unknown } | null)?.code
  if (code === '42P01') return true
  const message = err instanceof Error ? err.message : String(err)
  return message.includes('does not exist')
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

export const LAYOUT_TABS = ['models', 'volume', 'ops', 'picks'] as const
export type LayoutTab = typeof LAYOUT_TABS[number]

export function isLayoutTab(v: unknown): v is LayoutTab {
  return typeof v === 'string' && (LAYOUT_TABS as readonly string[]).includes(v)
}

/** Trimmed layout name, or null when it is empty or longer than 60 characters. */
export function cleanLayoutName(v: unknown): string | null {
  if (typeof v !== 'string') return null
  const name = v.trim()
  if (name.length < 1 || name.length > 60) return null
  return name
}
