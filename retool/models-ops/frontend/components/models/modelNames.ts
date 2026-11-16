import { createContext, useContext } from 'react'

export type ModelNameRow = {
  model_id: string
  name: string | null
  short_name: string | null
  sport: string | null
  in_play: boolean | null
}

export type ModelLabel = { name: string; shortName: string }

/** "mlb_spreads_v2" → "MLB Spreads V2", so a model never shows up blank. */
export function humanizeModelId(id: string): string {
  const parts = id.split('_').filter(p => p !== '')
  if (parts.length === 0) return id
  return parts
    .map((p, i) => (i === 0 ? p.toUpperCase() : p.charAt(0).toUpperCase() + p.slice(1)))
    .join(' ')
}

export type ModelNamesContextValue = {
  modelLabel: (id: string) => ModelLabel
  /** True / false once a panel has reported it; undefined when not known. */
  isPaused: (id: string) => boolean | undefined
  /** Panels that know paused state (roster, volume) share it here. */
  reportPaused: (rows: Array<{ model_id: string; paused: boolean }>) => void
  /** Search helper: matches the friendly name, short name or id. */
  matchesModel: (id: string, query: string) => boolean
}

function fallbackLabel(id: string): ModelLabel {
  const name = humanizeModelId(id)
  return { name, shortName: name }
}

export const ModelNamesContext = createContext<ModelNamesContextValue>({
  modelLabel: fallbackLabel,
  isPaused: () => undefined,
  reportPaused: () => {},
  matchesModel: (id, q) => {
    const query = q.trim().toLowerCase()
    return query === '' || id.toLowerCase().includes(query) || humanizeModelId(id).toLowerCase().includes(query)
  },
})

export function useModelNames(): ModelNamesContextValue {
  return useContext(ModelNamesContext)
}

/**
 * Labels for a set of models drawn together (a legend, an axis). When two
 * models share a name, the paused one is marked; failing that the id is added.
 */
export function distinctLabels(
  ids: string[],
  ctx: ModelNamesContextValue,
  useShort: boolean,
): Map<string, string> {
  const base = new Map<string, string>()
  for (const id of ids) {
    const l = ctx.modelLabel(id)
    base.set(id, useShort ? l.shortName : l.name)
  }
  const counts = new Map<string, number>()
  for (const v of base.values()) counts.set(v, (counts.get(v) ?? 0) + 1)
  const out = new Map<string, string>()
  for (const [id, label] of base) {
    if ((counts.get(label) ?? 0) < 2) {
      out.set(id, label)
      continue
    }
    const paused = ctx.isPaused(id)
    out.set(id, paused === true ? `${label} (paused)` : `${label} (${id})`)
  }
  return out
}
