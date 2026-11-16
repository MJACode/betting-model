import { useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, Terminal } from 'lucide-react'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../../lib/shadcn/table'
import { PanelError, TableSkeleton, EmptyState, Footnote, Chip, NullCell } from '../../components/PanelUtils'
import { cn } from '../../lib/shadcn/utils'
import { fmtCount, fmtDurationMs, fmtPct, fmtSpan, fmtUtc, hoursBetween } from './dbUtils'

type QueryRow = {
  queryid: string
  role_name: string
  toplevel: boolean
  calls: number
  total_exec_ms: number
  mean_exec_ms: number
  max_exec_ms: number | null
  rows: number | null
  shared_blks_read: number | null
  temp_blks_written: number | null
  query: string
  ref_calls: number | null
  ref_total_ms: number | null
}

type Meta = {
  latest_at: string | null
  ref_at: string | null
  stmt_exec_ms: number | null
  stmt_reset: string | null
  ref_stmt_exec_ms: number | null
  ref_stmt_reset: string | null
}

type QueriesResult =
  | { ok: true; available: boolean; meta: Meta; queries: QueryRow[] }
  | { ok: false; message: string }

type Props = {
  data: unknown
  loading: boolean
  error: string | null
}

type Sort = 'total' | 'recent' | 'mean' | 'calls'

const SORTS: ReadonlyArray<{ key: Sort; label: string }> = [
  { key: 'total', label: 'Most time' },
  { key: 'recent', label: 'Last 24 h' },
  { key: 'mean', label: 'Slowest per call' },
  { key: 'calls', label: 'Most calls' },
]

export default function DbQueries({ data, loading, error }: Props) {
  const [sort, setSort] = useState<Sort>('total')
  const [open, setOpen] = useState<string | null>(null)

  const res = data as QueriesResult | undefined
  const meta = res && res.ok ? res.meta : null
  const queries = useMemo(() => (res && res.ok ? res.queries : []), [res])
  // A last-day figure needs the same statement-stats period at both ends.
  const sameEpoch = !!meta?.ref_at && meta.ref_stmt_reset === meta.stmt_reset

  const rows = useMemo(() => {
    const list = queries.map(q => {
      const recent = sameEpoch && q.ref_total_ms != null && q.total_exec_ms >= q.ref_total_ms
        ? q.total_exec_ms - q.ref_total_ms : null
      return { ...q, recent }
    })
    const by: Record<Sort, (r: typeof list[number]) => number> = {
      total: r => r.total_exec_ms,
      recent: r => r.recent ?? -Infinity,
      mean: r => r.mean_exec_ms,
      calls: r => r.calls,
    }
    return [...list].sort((a, b) => by[sort](b) - by[sort](a))
  }, [queries, sort, sameEpoch])

  if (loading) return <TableSkeleton rows={8} />
  if (error) return <PanelError message={error} />
  if (res && !res.ok) return <PanelError message={res.message} />
  if (!meta || !meta.latest_at || queries.length === 0) {
    return (
      <EmptyState icon={Terminal} title="No statement snapshot yet">
        The heaviest statements are recorded on the first hourly snapshot of each six-hour block.
      </EmptyState>
    )
  }

  const allMs = meta.stmt_exec_ms ?? 0
  const refSpan = meta.ref_at && meta.latest_at ? hoursBetween(meta.ref_at, meta.latest_at) : null
  const maxShare = Math.max(...rows.map(r => (allMs > 0 ? r.total_exec_ms / allMs : 0)), 0.0001)

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-xs font-medium text-muted-foreground">Sort</span>
        {SORTS.map(s => (
          <Chip
            key={s.key}
            active={sort === s.key}
            onClick={() => setSort(s.key)}
            title={s.key === 'recent' && !sameEpoch ? 'Needs a statement snapshot from a day earlier' : undefined}
          >
            {s.label}
          </Chip>
        ))}
        <span className="ml-auto text-xs text-muted-foreground">
          {fmtDurationMs(allMs)} of statement time since {fmtUtc(meta.stmt_reset)}
        </span>
      </div>

      <div className="table-frame fill">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8 px-2" />
              <TableHead className="px-3">Statement</TableHead>
              <TableHead className="w-[14%] px-3">Share of all time</TableHead>
              <TableHead className="px-3 text-right">Total time</TableHead>
              <TableHead className="px-3 text-right">Last 24 h</TableHead>
              <TableHead className="px-3 text-right">Calls</TableHead>
              <TableHead className="px-3 text-right">Per call</TableHead>
              <TableHead className="px-3">Role</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(q => {
              const key = `${q.queryid}:${q.role_name}:${q.toplevel ? 't' : 'n'}`
              const isOpen = open === key
              const share = allMs > 0 ? q.total_exec_ms / allMs : null
              return (
                <TableRow
                  key={key}
                  className="cursor-pointer align-top"
                  onClick={() => setOpen(isOpen ? null : key)}
                  aria-expanded={isOpen}
                >
                  <TableCell className="px-2 py-2 text-muted-foreground">
                    {isOpen ? <ChevronDown className="h-3.5 w-3.5" aria-hidden /> : <ChevronRight className="h-3.5 w-3.5" aria-hidden />}
                  </TableCell>
                  <TableCell className="max-w-[560px] px-3 py-2">
                    <div className={cn('sb-code whitespace-pre-wrap break-words text-foreground', !isOpen && 'line-clamp-2')}>
                      {q.query}
                    </div>
                    {isOpen && (
                      <div className="mt-1.5 text-[11px] text-muted-foreground">
                        Slowest call {fmtDurationMs(q.max_exec_ms)} · {fmtCount(q.rows)} rows returned · {fmtCount(q.shared_blks_read)} blocks read from disk
                        {q.temp_blks_written ? ` · ${fmtCount(q.temp_blks_written)} temp blocks written` : ''}
                        {!q.toplevel ? ' · run inside a function' : ''}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div className="sb-meter flex-1">
                        <span style={{ width: `${share != null ? Math.max(2, (share / maxShare) * 100) : 0}%`, background: 'var(--series-1)' }} />
                      </div>
                      <span className="w-12 text-right text-xs tabular-nums text-muted-foreground">{fmtPct(share, 1)}</span>
                    </div>
                  </TableCell>
                  <TableCell className="px-3 py-2 text-right tabular-nums">{fmtDurationMs(q.total_exec_ms)}</TableCell>
                  <TableCell className="px-3 py-2 text-right tabular-nums">{q.recent != null ? fmtDurationMs(q.recent) : <NullCell />}</TableCell>
                  <TableCell className="px-3 py-2 text-right tabular-nums">{fmtCount(q.calls)}</TableCell>
                  <TableCell className="px-3 py-2 text-right tabular-nums">{fmtDurationMs(q.mean_exec_ms)}</TableCell>
                  <TableCell className="px-3 py-2 text-xs text-muted-foreground">{q.role_name}</TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
      <Footnote>
        Postgres’s statement statistics, as of {fmtUtc(meta.latest_at)}: the 100 statements with the most time and the 25 slowest per call,
        totals since {fmtUtc(meta.stmt_reset)}. Constants appear as $1, $2.
        {' '}{sameEpoch && refSpan != null
          ? `Last 24 h compares with the snapshot ${fmtSpan(refSpan)} earlier; a dash means the statement was not in that list.`
          : 'Last 24 h fills in once there is a statement snapshot from a day earlier.'}
        {' '}Click a row for its full text.
      </Footnote>
    </div>
  )
}
