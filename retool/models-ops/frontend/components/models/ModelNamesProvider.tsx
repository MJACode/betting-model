import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useGetModelNames } from '../../hooks/backend/ops'
import {
  ModelNamesContext, humanizeModelId,
  type ModelLabel, type ModelNameRow, type ModelNamesContextValue,
} from './modelNames'

/** Loads friendly model names once for the whole app. */
export function ModelNamesProvider({ children }: { children: ReactNode }) {
  const { data, trigger } = useGetModelNames({ cachePolicy: 'stale-while-revalidate' })
  const [paused, setPaused] = useState<Record<string, boolean>>({})

  useEffect(() => {
    trigger().result.catch(() => {
      // Names are a nicety: on failure every model falls back to its id in words.
    })
  }, [trigger])

  const byId = useMemo(() => {
    const map = new Map<string, ModelLabel>()
    const rows = Array.isArray(data) ? (data as ModelNameRow[]) : []
    for (const r of rows) {
      const name = r.name?.trim() || humanizeModelId(r.model_id)
      const shortName = r.short_name?.trim() || name
      map.set(r.model_id, { name, shortName })
    }
    return map
  }, [data])

  const modelLabel = useCallback((id: string): ModelLabel => {
    const found = byId.get(id)
    if (found) return found
    const name = humanizeModelId(id)
    return { name, shortName: name }
  }, [byId])

  const isPaused = useCallback((id: string) => paused[id], [paused])

  const reportPaused = useCallback((rows: Array<{ model_id: string; paused: boolean }>) => {
    setPaused(prev => {
      let changed = false
      const next = { ...prev }
      for (const r of rows) {
        if (next[r.model_id] !== r.paused) {
          next[r.model_id] = r.paused
          changed = true
        }
      }
      return changed ? next : prev
    })
  }, [])

  const matchesModel = useCallback((id: string, query: string) => {
    const q = query.trim().toLowerCase()
    if (q === '') return true
    const l = modelLabel(id)
    return id.toLowerCase().includes(q) || l.name.toLowerCase().includes(q) || l.shortName.toLowerCase().includes(q)
  }, [modelLabel])

  const value = useMemo<ModelNamesContextValue>(
    () => ({ modelLabel, isPaused, reportPaused, matchesModel }),
    [modelLabel, isPaused, reportPaused, matchesModel],
  )

  return <ModelNamesContext.Provider value={value}>{children}</ModelNamesContext.Provider>
}
