import type { ReactNode } from 'react'

export type TabId = 'models' | 'volume' | 'ops' | 'database' | 'picks' | 'health'

/**
 * Tabs whose layouts can be saved. It matches the tab list the layout
 * functions accept (backend/ops/dbErrors.ts) and the check on the
 * dashboard_layouts table. The Database and Model Health tabs arrange for the session only:
 * adding it there means changing two functions that write, which need
 * approval at publish, and the table's check.
 */
export const SAVABLE_TABS: ReadonlySet<TabId> = new Set<TabId>(['models', 'volume', 'ops', 'picks'])

/** The heading shown at the top of each tab. */
export const TAB_META: Record<TabId, { title: string; description: string }> = {
  models: { title: 'Models', description: 'Every model, its state, its settled record and its daily volume' },
  volume: { title: 'Volume', description: 'How many of each pre-game model’s bets get posted' },
  ops: { title: 'Ops', description: 'Feeds, pipeline runs, health checks and audience' },
  database: { title: 'Database', description: 'Size, growth and load of the Supabase database, measured every hour' },
  picks: { title: 'Picks & CLV', description: 'Every bet pick, its result and how it did against the closing price' },
  health: { title: 'Model Health', description: 'Closing-line value per model: every bet, blocks of 25, 50 and 100, and a rolling average' },
}

/** What a saved layout stores per tile. */
export type TileLayout = { id: string; x: number; y: number; w: number; h: number; hidden: boolean }

export type TileMeta = {
  id: string
  title: string
  description: string
  /** Position and size in the built-in Default layout (12 columns). */
  x: number
  y: number
  w: number
  h: number
  minW?: number
  minH?: number
  /** Height follows the content (stat strips); only the width can be resized. */
  autoHeight?: boolean
}

export type TileRender = {
  body: ReactNode
  /** Extra controls shown on the right of the tile header. */
  actions?: ReactNode
}

export const GRID_COLS = 12
export const ROW_HEIGHT = 30
export const GRID_GAP = 16
export const DEFAULT_LAYOUT = '__default__'

export const SIZE_PRESETS = [
  { key: 'small', label: 'Small', w: 4 },
  { key: 'medium', label: 'Medium', w: 6 },
  { key: 'large', label: 'Large', w: 8 },
  { key: 'full', label: 'Full width', w: 12 },
] as const

/** Grid rows needed to show `px` of tile height. */
export function rowsForPixels(px: number): number {
  return Math.max(1, Math.ceil((px + GRID_GAP) / (ROW_HEIGHT + GRID_GAP)))
}

export function defaultLayoutFor(metas: TileMeta[]): TileLayout[] {
  return metas.map(m => ({ id: m.id, x: m.x, y: m.y, w: m.w, h: m.h, hidden: false }))
}

function int(v: unknown, fallback: number): number {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? Math.round(n) : fallback
}

/**
 * Turn a stored layout into one that fits the current tiles: unknown ids are
 * dropped, values are clamped to the grid, and tiles the stored layout does not
 * mention are added at the bottom with their default size.
 */
export function normalizeLayout(raw: unknown, metas: TileMeta[]): TileLayout[] {
  const byId = new Map(metas.map(m => [m.id, m]))
  const out: TileLayout[] = []
  const seen = new Set<string>()
  const items = Array.isArray(raw) ? raw : []

  for (const item of items) {
    if (!item || typeof item !== 'object') continue
    const rec = item as Record<string, unknown>
    const id = rec['id']
    if (typeof id !== 'string' || seen.has(id)) continue
    const meta = byId.get(id)
    if (!meta) continue
    seen.add(id)
    const minW = meta.minW ?? 2
    const minH = meta.minH ?? 3
    const w = Math.min(GRID_COLS, Math.max(minW, int(rec['w'], meta.w)))
    const x = Math.min(GRID_COLS - w, Math.max(0, int(rec['x'], meta.x)))
    out.push({
      id,
      x,
      y: Math.max(0, int(rec['y'], meta.y)),
      w,
      h: Math.max(minH, int(rec['h'], meta.h)),
      hidden: rec['hidden'] === true,
    })
  }

  const missing = metas.filter(m => !seen.has(m.id))
  if (missing.length > 0) {
    const bottom = out.reduce((max, t) => Math.max(max, t.y + t.h), 0)
    const firstY = Math.min(...missing.map(m => m.y))
    for (const m of missing) {
      out.push({ id: m.id, x: m.x, y: bottom + (m.y - firstY), w: m.w, h: m.h, hidden: false })
    }
  }
  return out
}

/** Visible tiles in reading order, for the stacked (narrow screen) view. */
export function readingOrder(layout: TileLayout[]): TileLayout[] {
  return layout.filter(t => !t.hidden).sort((a, b) => a.y - b.y || a.x - b.x)
}

export function bottomOf(layout: TileLayout[]): number {
  return layout.filter(t => !t.hidden).reduce((max, t) => Math.max(max, t.y + t.h), 0)
}
