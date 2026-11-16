import type { CSSProperties, ReactNode } from 'react'

/**
 * Shared chart styling. Colours are CSS variables defined in appTheme.css for
 * light and dark, so charts follow the theme without re-rendering.
 */
export const PALETTE = [
  'var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)',
  'var(--series-5)', 'var(--series-6)', 'var(--series-7)', 'var(--series-8)',
] as const

export const OTHER_SERIES_COLOR = 'var(--series-other)'
export const OTHER_KEY = 'Other'
export const GRID_COLOR = 'var(--chart-grid)'
export const AXIS_COLOR = 'var(--chart-axis)'
export const TEXT_COLOR = 'hsl(var(--foreground))'

/**
 * Colour by identity. The universe is every series the chart could show
 * (taken from unfiltered data), sorted by display name; the first eight get
 * palette slots in order and anything beyond folds into "Other". Because the
 * universe does not shrink when a filter narrows the data, survivors keep
 * their colour.
 */
export function colorsByIdentity(
  universe: string[],
  sortKey: (id: string) => string = id => id,
): { colorOf: (id: string) => string; isNamed: (id: string) => boolean; named: string[] } {
  const sorted = Array.from(new Set(universe)).sort((a, b) =>
    sortKey(a).localeCompare(sortKey(b)) || a.localeCompare(b),
  )
  const named = sorted.slice(0, PALETTE.length)
  const map = new Map<string, string>()
  named.forEach((id, i) => map.set(id, PALETTE[i] ?? OTHER_SERIES_COLOR))
  return {
    colorOf: id => map.get(id) ?? OTHER_SERIES_COLOR,
    isNamed: id => map.has(id),
    named,
  }
}

/**
 * Colour slots that stay with a series for as long as it is selected. Used where
 * the viewer picks series one by one from a list longer than the palette.
 */
export function assignStableSlots(prev: Record<string, number>, selected: string[]): Record<string, number> {
  const next: Record<string, number> = {}
  const used = new Set<number>()
  for (const id of selected) {
    const slot = prev[id]
    if (slot != null && !used.has(slot)) {
      next[id] = slot
      used.add(slot)
    }
  }
  for (const id of selected) {
    if (next[id] != null) continue
    let slot = 0
    while (used.has(slot)) slot++
    next[id] = slot
    used.add(slot)
  }
  return next
}

export function slotColor(slot: number | undefined): string {
  return slot != null && slot < PALETTE.length ? (PALETTE[slot] ?? OTHER_SERIES_COLOR) : OTHER_SERIES_COLOR
}

export const axisProps = {
  tick: { fontSize: 11, fill: AXIS_COLOR },
  tickLine: false,
  axisLine: false,
} as const

export const gridProps = {
  stroke: GRID_COLOR,
  strokeDasharray: '',
  strokeWidth: 1,
} as const

export const tooltipContentStyle: CSSProperties = {
  background: 'hsl(var(--popover))',
  border: '1px solid hsl(var(--border))',
  borderRadius: 8,
  boxShadow: 'var(--shadow-retool-md)',
  fontSize: 12,
  color: TEXT_COLOR,
  padding: '8px 10px',
}

export const tooltipProps = {
  contentStyle: tooltipContentStyle,
  itemStyle: { color: TEXT_COLOR, padding: 0 },
  labelStyle: { color: TEXT_COLOR, fontWeight: 600, marginBottom: 4 },
  cursor: { fill: 'hsl(var(--muted) / 0.6)', stroke: GRID_COLOR },
} as const

/** Legend text stays in the text colour; only the swatch carries the series colour. */
export const legendProps = {
  iconType: 'circle' as const,
  iconSize: 8,
  wrapperStyle: { fontSize: 12, paddingTop: 8 },
  formatter: (value: unknown): ReactNode => (
    <span style={{ color: 'hsl(var(--text-secondary))' }}>{String(value)}</span>
  ),
}

/** Container for custom tooltip content. */
export function ChartTooltipBox({ title, children }: { title?: ReactNode; children: ReactNode }) {
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-retool-md">
      {title != null && <div className="mb-1 font-semibold">{title}</div>}
      {children}
    </div>
  )
}

export function Swatch({ color }: { color: string }) {
  return <span className="mr-1.5 inline-block h-2 w-2 rounded-full align-middle" style={{ background: color }} />
}

export function shortDate(d: string) {
  const dt = new Date(d + 'T00:00:00Z')
  return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
}
