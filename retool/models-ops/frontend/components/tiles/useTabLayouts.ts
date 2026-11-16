import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useGetDashboardLayouts, useSaveDashboardLayout, useDeleteDashboardLayout } from '../../hooks/backend/ops'
import { useViewerEmail } from '../ViewerContext'
import { readStorage, writeStorage } from '../../utils/safeStorage'
import {
  DEFAULT_LAYOUT, GRID_COLS, bottomOf, defaultLayoutFor, normalizeLayout,
  type TabId, type TileLayout, type TileMeta,
} from './layoutTypes'

export type SavedLayout = { name: string; layout: TileLayout[]; updatedAt: string | null }

type ReadResult =
  | { ok: true; layouts: Array<{ name: string; layout: unknown; updated_at: string | null }>; available: boolean }
  | { ok: false; message: string }
type SaveResult = { ok: true; name: string; updated_at: string | null } | { ok: false; message: string }
type DeleteResult = { ok: true; deleted: number } | { ok: false; message: string }

type Session = { selected: string; working: TileLayout[]; arrange: boolean; dirty: boolean }

// Keeps each tab's arrangement for the browser session, so switching tabs does
// not throw away unsaved changes. Saved layouts themselves live only in the database.
const sessions = new Map<TabId, Session>()

function msg(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}

export function useTabLayouts(tab: TabId, metas: TileMeta[]) {
  const email = useViewerEmail()
  const defaults = useMemo(() => defaultLayoutFor(metas), [metas])
  const session = sessions.get(tab)

  const [selected, setSelected] = useState<string>(session?.selected ?? DEFAULT_LAYOUT)
  const [working, setWorking] = useState<TileLayout[]>(session?.working ?? defaults)
  const [arrange, setArrange] = useState<boolean>(session?.arrange ?? false)
  const [dirty, setDirty] = useState<boolean>(session?.dirty ?? false)
  const [saved, setSaved] = useState<SavedLayout[]>([])
  const [available, setAvailable] = useState<boolean | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const restoredFromSession = useRef(session != null)
  const prefApplied = useRef(false)

  useEffect(() => {
    sessions.set(tab, { selected, working, arrange, dirty })
  }, [tab, selected, working, arrange, dirty])

  const prefKey = `signalbase-ops:layout:${email ?? 'anon'}:${tab}`
  const writePref = useCallback((name: string) => writeStorage(prefKey, name), [prefKey])

  const read = useGetDashboardLayouts()
  const save = useSaveDashboardLayout()
  const del = useDeleteDashboardLayout()
  const readTrigger = read.trigger
  const saveTrigger = save.trigger
  const deleteTrigger = del.trigger

  useEffect(() => {
    let cancelled = false
    readTrigger({ tab }).result
      .then(raw => {
        if (cancelled) return
        const res = raw as ReadResult
        if (!res.ok) {
          setLoadError(res.message)
          setAvailable(false)
          return
        }
        setSaved(res.layouts.map(r => ({
          name: r.name,
          layout: normalizeLayout(r.layout, metas),
          updatedAt: r.updated_at ?? null,
        })))
        setAvailable(res.available)
        setLoadError(null)
      })
      .catch(e => {
        if (cancelled) return
        setLoadError(msg(e))
        setAvailable(false)
      })
    return () => { cancelled = true }
  }, [readTrigger, tab, metas])

  // Re-open the layout this viewer last chose, once the list and the viewer are known.
  useEffect(() => {
    if (restoredFromSession.current || prefApplied.current) return
    if (available === null || email === undefined) return
    prefApplied.current = true
    const pref = readStorage(prefKey)
    if (!pref || pref === DEFAULT_LAYOUT) return
    const found = saved.find(s => s.name === pref)
    if (found) {
      setSelected(found.name)
      setWorking(found.layout)
      setDirty(false)
    }
  }, [available, email, saved, prefKey])

  useEffect(() => {
    if (!notice) return
    const t = setTimeout(() => setNotice(null), 3000)
    return () => clearTimeout(t)
  }, [notice])

  const selectLayout = useCallback((name: string) => {
    setActionError(null)
    if (name === DEFAULT_LAYOUT) {
      setSelected(DEFAULT_LAYOUT)
      setWorking(defaults)
    } else {
      const found = saved.find(s => s.name === name)
      if (!found) return
      setSelected(found.name)
      setWorking(found.layout)
    }
    setDirty(false)
    writePref(name)
  }, [defaults, saved, writePref])

  const persist = useCallback(async (name: string): Promise<boolean> => {
    setBusy(true)
    setActionError(null)
    try {
      const res = (await saveTrigger({ tab, name, layout: working }).result) as SaveResult
      if (!res.ok) {
        setActionError(res.message)
        return false
      }
      const entry: SavedLayout = { name: res.name, layout: working, updatedAt: res.updated_at }
      setSaved(prev =>
        [...prev.filter(s => s.name !== res.name), entry].sort((a, b) => a.name.localeCompare(b.name)),
      )
      setSelected(res.name)
      setDirty(false)
      writePref(res.name)
      setNotice(`Saved "${res.name}"`)
      return true
    } catch (e) {
      setActionError(msg(e))
      return false
    } finally {
      setBusy(false)
    }
  }, [saveTrigger, tab, working, writePref])

  const saveCurrent = useCallback(async () => {
    if (selected === DEFAULT_LAYOUT || available !== true) return false
    return persist(selected)
  }, [available, persist, selected])

  const saveAs = useCallback(async (rawName: string) => {
    const name = rawName.trim()
    if (name.length < 1 || name.length > 60) {
      setActionError('Layout names are 1 to 60 characters.')
      return false
    }
    if (available !== true) return false
    return persist(name)
  }, [available, persist])

  const deleteSelected = useCallback(async () => {
    if (selected === DEFAULT_LAYOUT || available !== true) return false
    setBusy(true)
    setActionError(null)
    try {
      const res = (await deleteTrigger({ tab, name: selected }).result) as DeleteResult
      if (!res.ok) {
        setActionError(res.message)
        return false
      }
      const gone = selected
      setSaved(prev => prev.filter(s => s.name !== gone))
      setSelected(DEFAULT_LAYOUT)
      setWorking(defaults)
      setDirty(false)
      writePref(DEFAULT_LAYOUT)
      setNotice(`Deleted "${gone}"`)
      return true
    } catch (e) {
      setActionError(msg(e))
      return false
    } finally {
      setBusy(false)
    }
  }, [available, defaults, deleteTrigger, selected, tab, writePref])

  const resetToDefault = useCallback(() => {
    setWorking(defaults)
    setDirty(selected !== DEFAULT_LAYOUT)
    setActionError(null)
  }, [defaults, selected])

  /** Positions reported by the grid (after drags, resizes and compaction). */
  const syncPositions = useCallback((items: Array<{ i: string; x: number; y: number; w: number; h: number }>) => {
    setWorking(prev => {
      let changed = false
      const next = prev.map(t => {
        const it = items.find(i => i.i === t.id)
        if (!it || t.hidden) return t
        if (it.x === t.x && it.y === t.y && it.w === t.w && it.h === t.h) return t
        changed = true
        return { ...t, x: it.x, y: it.y, w: it.w, h: it.h }
      })
      return changed ? next : prev
    })
  }, [])

  const markDirty = useCallback(() => setDirty(true), [])

  /** Height measured from a content-fitted tile; not a user change, so not dirty. */
  const fitTileHeight = useCallback((id: string, h: number) => {
    setWorking(prev => {
      const t = prev.find(x => x.id === id)
      if (!t || t.h === h) return prev
      return prev.map(x => (x.id === id ? { ...x, h } : x))
    })
  }, [])

  const hideTile = useCallback((id: string) => {
    setWorking(prev => prev.map(t => (t.id === id ? { ...t, hidden: true } : t)))
    setDirty(true)
  }, [])

  const showTile = useCallback((id: string) => {
    setWorking(prev => {
      const y = bottomOf(prev)
      return prev.map(t => (t.id === id ? { ...t, hidden: false, y } : t))
    })
    setDirty(true)
  }, [])

  const setTileWidth = useCallback((id: string, w: number) => {
    setWorking(prev => prev.map(t => {
      if (t.id !== id) return t
      const width = Math.min(GRID_COLS, Math.max(1, w))
      return { ...t, w: width, x: Math.min(t.x, GRID_COLS - width) }
    }))
    setDirty(true)
  }, [])

  return {
    tab,
    metas,
    selected,
    saved,
    working,
    arrange,
    setArrange,
    dirty,
    available,
    loadError,
    busy,
    actionError,
    notice,
    selectLayout,
    saveCurrent,
    saveAs,
    deleteSelected,
    resetToDefault,
    syncPositions,
    markDirty,
    fitTileHeight,
    hideTile,
    showTile,
    setTileWidth,
  }
}

export type TabLayouts = ReturnType<typeof useTabLayouts>
