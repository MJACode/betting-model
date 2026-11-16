import { useMemo, useState, type ChangeEvent } from 'react'
import { Search, Table2 } from 'lucide-react'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../../lib/shadcn/table'
import { Input } from '../../lib/shadcn/input'
import { PanelError, TableSkeleton, EmptyState, Footnote, Chip, SortIcon, NullCell } from '../../components/PanelUtils'
import { cn } from '../../lib/shadcn/utils'
import { fmtAgo, fmtBytes, fmtBytesSigned, fmtCount, fmtPct, fmtSpan, fmtUtc, hoursBetween } from './dbUtils'

type TableRowData = {
  schema_name: string
  table_name: string
  kind: string
  total_bytes: number
  heap_bytes: number | null
  index_bytes: number | null
  toast_bytes: number | null
  live_rows_est: number | null
  dead_rows_est: number | null
  last_vacuum: string | null
  last_analyze: string | null
  prev_bytes: number | null
  day_bytes: number | null
  week_bytes: number | null
}

type Refs = {
  latest_at: string | null
  prev_at: string | null
  day_at: string | null
  week_at: string | null
  first_at: string | null
  runs: number
}

type TablesResult =
  | { ok: true; available: boolean; refs: Refs; tables: TableRowData[] }
  | { ok: false; message: string }

type Props = {
  data: unknown
  loading: boolean
  error: string | null
}

type SortKey = 'size' | 'growth' | 'rows' | 'dead'

const SPLIT = [
  { key: 'heap', label: 'Table', color: 'var(--series-1)' },
  { key: 'index', label: 'Indexes', color: 'var(--series-7)' },
  { key: 'toast', label: 'Toast', color: 'var(--series-4)' },
] as const

export default function DbTables({ data, loading, error }: Props) {
  const [query, setQuery] = useState('')
  const [showAll, setShowAll] = useState(false)
  const [sort, setSort] = useState<SortKey>('size')

  const res = data as TablesResult | undefined
  const refs = res && res.ok ? res.refs : null
  const tables = useMemo(() => (res && res.ok ? res.tables : []), [res])

  // Growth is against the day-old snapshot when there is one, else the previous one.
  const { ref, refHours } = useMemo(() => {
    const r = refs?.day_at ? { at: refs.day_at, key: 'day_bytes' as const }
      : refs?.prev_at ? { at: refs.prev_at, key: 'prev_bytes' as const } : null
    return { ref: r, refHours: r && refs?.latest_at ? hoursBetween(r.at, refs.latest_at) : null }
  }, [refs])

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = tables
      .filter(t => !q || `${t.schema_name}.${t.table_name}`.toLowerCase().includes(q))
      .map(t => {
        const before = ref ? t[ref.key] : null
        const perDay = before != null && refHours ? ((t.total_bytes - before) / refHours) * 24 : null
        const deadShare = t.dead_rows_est != null && t.live_rows_est ? t.dead_rows_est / t.live_rows_est : null
        return { ...t, perDay, deadShare }
      })
    const by: Record<SortKey, (r: typeof list[number]) => number> = {
      size: r => r.total_bytes,
      growth: r => r.perDay ?? -Infinity,
      rows: r => r.live_rows_est ?? -Infinity,
      dead: r => r.deadShare ?? -Infinity,
    }
    return [...list].sort((a, b) => by[sort](b) - by[sort](a))
  }, [tables, query, sort, ref, refHours])

  if (loading) return <TableSkeleton rows={8} />
  if (error) return <PanelError message={error} />
  if (res && !res.ok) return <PanelError message={res.message} />
  if (!refs || !refs.latest_at || tables.length === 0) {
    return (
      <EmptyState icon={Table2} title="No table snapshot yet">
        Every table’s size is recorded on the first hourly snapshot of each six-hour block.
      </EmptyState>
    )
  }

  const total = tables.reduce((a, t) => a + t.total_bytes, 0)
  const shown = showAll || query ? rows : rows.slice(0, 25)
  const growthLabel = ref && refHours != null ? `vs ${fmtSpan(refHours)} ago` : 'after the next snapshot'

  const head = (key: SortKey, label: string, align: 'left' | 'right' = 'right') => (
    <TableHead className={cn('px-3', align === 'right' && 'text-right')}>
      <button
        type="button"
        onClick={() => setSort(key)}
        className={cn('inline-flex items-center gap-1 uppercase', align === 'right' && 'flex-row-reverse', sort === key && 'text-foreground')}
        aria-label={`Sort by ${label}`}
      >
        {label}
        <SortIcon sorted={sort === key ? 'desc' : false} />
      </button>
    </TableHead>
  )

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-56">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            value={query}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)}
            placeholder="Find a table"
            className="h-8 pl-8 text-[13px]"
            aria-label="Find a table"
          />
        </div>
        <Chip active={!showAll} onClick={() => setShowAll(false)}>Top 25</Chip>
        <Chip active={showAll} onClick={() => setShowAll(true)}>All {tables.length}</Chip>
        <div className="ml-auto flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {SPLIT.map(s => (
            <span key={s.key} className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: s.color }} aria-hidden />{s.label}
            </span>
          ))}
        </div>
      </div>

      <div className="table-frame fill">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="px-3">Table</TableHead>
              {head('size', 'Size')}
              <TableHead className="w-[22%] px-3">Where the space is</TableHead>
              {head('rows', 'Rows (est.)')}
              {head('growth', `Growth a day`)}
              {head('dead', 'Dead rows')}
              <TableHead className="px-3 text-right">Last vacuum</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.map(t => {
              const parts = [t.heap_bytes ?? 0, t.index_bytes ?? 0, t.toast_bytes ?? 0]
              const sum = parts.reduce((a, b) => a + b, 0) || 1
              return (
                <TableRow key={`${t.schema_name}.${t.table_name}`}>
                  <TableCell className="px-3 py-2">
                    <span className="font-medium text-foreground">{t.table_name}</span>
                    {t.schema_name !== 'public' && <span className="ml-1.5 text-xs text-muted-foreground">{t.schema_name}</span>}
                    {t.kind === 'matview' && <span className="ml-1.5 text-xs text-muted-foreground">view, stored</span>}
                  </TableCell>
                  <TableCell className="px-3 py-2 text-right tabular-nums">
                    {fmtBytes(t.total_bytes)}
                    <div className="text-[11px] text-muted-foreground">{fmtPct(t.total_bytes / (total || 1), 1)}</div>
                  </TableCell>
                  <TableCell className="px-3 py-2">
                    <div className="sb-split" title={`Table ${fmtBytes(t.heap_bytes)} · indexes ${fmtBytes(t.index_bytes)} · toast ${fmtBytes(t.toast_bytes)}`}>
                      {SPLIT.map((s, i) => <span key={s.key} style={{ width: `${(parts[i]! / sum) * 100}%`, background: s.color }} />)}
                    </div>
                  </TableCell>
                  <TableCell className="px-3 py-2 text-right tabular-nums">{t.live_rows_est != null ? fmtCount(t.live_rows_est) : <NullCell />}</TableCell>
                  <TableCell className={cn('px-3 py-2 text-right tabular-nums', t.perDay != null && t.perDay > 0 && 'text-foreground')}>
                    {t.perDay != null ? fmtBytesSigned(t.perDay) : <NullCell />}
                  </TableCell>
                  <TableCell className="px-3 py-2 text-right tabular-nums">
                    {t.dead_rows_est != null ? fmtCount(t.dead_rows_est) : <NullCell />}
                    {t.deadShare != null && t.deadShare >= 0.005 && (
                      <div className="text-[11px] text-muted-foreground">{fmtPct(t.deadShare, 1)}</div>
                    )}
                  </TableCell>
                  <TableCell className="px-3 py-2 text-right text-xs text-muted-foreground" title={t.last_vacuum ? fmtUtc(t.last_vacuum) : 'Never vacuumed'}>
                    {fmtAgo(t.last_vacuum)}
                  </TableCell>
                </TableRow>
              )
            })}
            {shown.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="px-3 py-8 text-center text-sm text-muted-foreground">No table matches “{query}”.</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <Footnote>
        Measured {fmtUtc(refs.latest_at)} across {tables.length} tables ({fmtBytes(total)}). Growth a day is {growthLabel}
        {refs.week_at ? '' : '; a week’s comparison appears once there is a week of snapshots'}.
        {' '}Per-table snapshots since {fmtUtc(refs.first_at)}, every six hours.
      </Footnote>
    </div>
  )
}
