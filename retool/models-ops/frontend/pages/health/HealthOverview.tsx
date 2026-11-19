import { useMemo, useState } from 'react'
import {
  useReactTable, getCoreRowModel, getSortedRowModel, flexRender,
  type ColumnDef, type SortingState,
} from '@tanstack/react-table'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../lib/shadcn/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../lib/shadcn/select'
import { PanelError, SortIcon, TableSkeleton, Footnote, Chip, signedClass } from '../../components/PanelUtils'
import { ModelName } from '../../components/models/ModelName'
import { useModelNames } from '../../components/models/modelNames'
import { Badge } from '../../components/StatusBadge'
import { cn } from '../../lib/shadcn/utils'
import {
  VERDICT, TREND_LABEL, Z95, MIN_MEASURED, fmtRate, fmtSignedPct, fmtSignedUnits, int, num, trendOf, verdictOf,
  type SummaryRow, type WindowRow, type Trend, type Verdict,
} from './healthUtils'

type Kind = 'all' | 'pregame' | 'inplay'

type Row = SummaryRow & {
  verdict: Verdict
  trend: Trend
  trendDelta: number | null
  inPlayOnly: boolean
  roi: number | null
}

type Props = {
  rows: SummaryRow[]
  windows: WindowRow[]
  loading: boolean
  error: string | null
  selected: string | null
  onSelect: (id: string) => void
}

function ClvCell({ avg, se, measured }: { avg: number | null; se: number | null; measured: number }) {
  if (avg == null) return <span className="block text-right text-xs text-muted-foreground">—</span>
  return (
    <div className="text-right leading-tight">
      <span className={cn('text-xs font-semibold tabular-nums', signedClass(avg))}>{fmtSignedPct(avg)}</span>
      <div className="whitespace-nowrap text-[11px] tabular-nums text-muted-foreground">
        {se != null ? `±${(Z95 * se).toFixed(2)} · ` : ''}{measured} measured
      </div>
    </div>
  )
}

function LastCell({ row, size }: { row: Row; size: 25 | 50 | 100 }) {
  const bets = int(row.bets)
  if (bets < size) {
    return <span className="block text-right text-xs text-muted-foreground" title={`Only ${bets} bets so far`}>—</span>
  }
  const avg = num(row[`last${size}_avg_clv_pct`])
  const se = num(row[`last${size}_se_clv_pct`])
  return <ClvCell avg={avg} se={se} measured={int(row[`last${size}_price_n`])} />
}

const TREND_TONE: Record<Trend, 'good' | 'critical' | 'neutral' | 'outline'> = {
  improving: 'good', fading: 'critical', steady: 'neutral', none: 'outline',
}

export default function HealthOverview({ rows, windows, loading, error, selected, onSelect }: Props) {
  const names = useModelNames()
  const [sorting, setSorting] = useState<SortingState>([{ id: 'bets', desc: true }])
  const [sport, setSport] = useState<string>('ALL')
  const [kind, setKind] = useState<Kind>('all')

  const enriched = useMemo<Row[]>(() => {
    const block50 = new Map<string, { b1?: WindowRow; b2?: WindowRow }>()
    for (const w of windows) {
      if (int(w.block_size) !== 50) continue
      const entry = block50.get(w.model_id) ?? {}
      if (int(w.block_no) === 1) entry.b1 = w
      if (int(w.block_no) === 2) entry.b2 = w
      block50.set(w.model_id, entry)
    }
    return rows.map(r => {
      const inPlayOnly = int(r.in_play) === int(r.bets) && int(r.bets) > 0
      const b = block50.get(r.model_id)
      const t = trendOf(b?.b1, b?.b2)
      const risked = num(r.risked)
      const units = num(r.units)
      return {
        ...r,
        inPlayOnly,
        verdict: verdictOf(num(r.avg_clv_pct), num(r.se_clv_pct), int(r.price_n), inPlayOnly),
        trend: t.trend,
        trendDelta: t.delta,
        roi: risked && units != null ? (units / risked) * 100 : null,
      }
    })
  }, [rows, windows])

  const sports = useMemo(() => ['ALL', ...Array.from(new Set(rows.map(r => r.sport))).sort()], [rows])

  const filtered = useMemo(
    () => enriched.filter(r =>
      (sport === 'ALL' || r.sport === sport)
      && (kind === 'all' || (kind === 'inplay' ? r.inPlayOnly : !r.inPlayOnly))),
    [enriched, sport, kind],
  )

  const columns = useMemo<ColumnDef<Row>[]>(() => [
    {
      id: 'model',
      accessorFn: r => names.modelLabel(r.model_id).name,
      header: 'Model',
      cell: ({ row }) => <ModelName id={row.original.model_id} className="min-w-[170px] max-w-[260px]" />,
    },
    {
      accessorKey: 'sport',
      header: 'Sport',
      cell: ({ getValue }) => <span className="text-xs font-medium text-secondary-fg">{String(getValue())}</span>,
    },
    {
      id: 'bets',
      accessorFn: r => int(r.bets),
      header: () => <span className="block text-right">Bets</span>,
      cell: ({ row }) => <span className="block text-right text-xs tabular-nums">{int(row.original.bets)}</span>,
    },
    {
      id: 'coverage',
      accessorFn: r => (int(r.bets) > 0 ? int(r.price_n) / int(r.bets) : 0),
      header: () => <span className="block text-right">Closing price</span>,
      cell: ({ row }) => {
        const r = row.original
        const bets = int(r.bets)
        const pct = bets > 0 ? Math.round((int(r.price_n) / bets) * 100) : 0
        return (
          <div className="text-right leading-tight" title={`${int(r.price_n)} on our number · ${int(r.line_for)} line moved our way · ${int(r.line_against)} against · ${int(r.in_play)} in-play · ${int(r.unmeasured)} not measured`}>
            <span className="text-xs tabular-nums">{int(r.price_n)} <span className="text-muted-foreground">({pct}%)</span></span>
            <div className="whitespace-nowrap text-[11px] tabular-nums text-muted-foreground">
              line moves {int(r.line_for)} our way · {int(r.line_against)} against
            </div>
          </div>
        )
      },
    },
    {
      id: 'avg',
      accessorFn: r => num(r.avg_clv_pct),
      sortUndefined: 'last',
      header: () => <span className="block text-right">Avg CLV, all</span>,
      cell: ({ row }) => <ClvCell avg={num(row.original.avg_clv_pct)} se={num(row.original.se_clv_pct)} measured={int(row.original.price_n)} />,
    },
    {
      id: 'last25',
      accessorFn: r => (int(r.bets) >= 25 ? num(r.last25_avg_clv_pct) : null),
      sortUndefined: 'last',
      header: () => <span className="block text-right">Last 25</span>,
      cell: ({ row }) => <LastCell row={row.original} size={25} />,
    },
    {
      id: 'last50',
      accessorFn: r => (int(r.bets) >= 50 ? num(r.last50_avg_clv_pct) : null),
      sortUndefined: 'last',
      header: () => <span className="block text-right">Last 50</span>,
      cell: ({ row }) => <LastCell row={row.original} size={50} />,
    },
    {
      id: 'last100',
      accessorFn: r => (int(r.bets) >= 100 ? num(r.last100_avg_clv_pct) : null),
      sortUndefined: 'last',
      header: () => <span className="block text-right">Last 100</span>,
      cell: ({ row }) => <LastCell row={row.original} size={100} />,
    },
    {
      id: 'beat',
      accessorFn: r => num(r.beat_rate_with_line),
      sortUndefined: 'last',
      header: () => <span className="block text-right">Beat rate</span>,
      cell: ({ row }) => (
        <div className="text-right leading-tight">
          <span className="text-xs font-semibold tabular-nums">{fmtRate(num(row.original.beat_rate_with_line))}</span>
          <div className="whitespace-nowrap text-[11px] tabular-nums text-muted-foreground">price only {fmtRate(num(row.original.price_beat_rate))}</div>
        </div>
      ),
    },
    {
      id: 'market',
      accessorFn: r => num(r.avg_market_clv_pct),
      sortUndefined: 'last',
      header: () => <span className="block text-right">Vs Pinnacle</span>,
      cell: ({ row }) => {
        const v = num(row.original.avg_market_clv_pct)
        if (v == null) return <span className="block text-right text-xs text-muted-foreground">—</span>
        return (
          <div className="text-right leading-tight">
            <span className={cn('text-xs tabular-nums', signedClass(v))}>{fmtSignedPct(v)}</span>
            <div className="text-[11px] tabular-nums text-muted-foreground">{int(row.original.market_n)} measured</div>
          </div>
        )
      },
    },
    {
      id: 'units',
      accessorFn: r => num(r.units),
      header: () => <span className="block text-right">Units</span>,
      cell: ({ row }) => {
        const u = num(row.original.units)
        return (
          <div className="text-right leading-tight">
            <span className={cn('text-xs font-semibold tabular-nums', signedClass(u))}>{fmtSignedUnits(u)}</span>
            <div className="text-[11px] tabular-nums text-muted-foreground">{row.original.roi == null ? '—' : fmtSignedPct(row.original.roi, 1)} ROI</div>
          </div>
        )
      },
    },
    {
      id: 'verdict',
      accessorFn: r => r.verdict,
      header: 'Against the close',
      cell: ({ row }) => {
        const v = VERDICT[row.original.verdict]
        return <Badge tone={v.tone} title={v.help}>{v.label}</Badge>
      },
    },
    {
      id: 'trend',
      accessorFn: r => r.trendDelta,
      sortUndefined: 'last',
      header: 'Last 50 vs prior 50',
      cell: ({ row }) => {
        const { trend, trendDelta } = row.original
        if (trend === 'none') {
          return (
            <span className="text-xs text-muted-foreground" title={`Needs two full blocks of 50 with at least ${MIN_MEASURED} closing prices each`}>
              {trendDelta == null ? '—' : `${fmtSignedPct(trendDelta)} (too few)`}
            </span>
          )
        }
        return (
          <Badge tone={TREND_TONE[trend]} title="The newest 50 bets’ average CLV against the 50 before; Improving or Fading only when the change is outside both blocks’ 95% margin">
            {TREND_LABEL[trend]} {trendDelta == null ? '' : fmtSignedPct(trendDelta)}
          </Badge>
        )
      },
    },
  ], [names])

  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  if (loading) return <TableSkeleton rows={8} />
  if (error) return <PanelError message={error} />

  const shown = table.getRowModel().rows.length

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">Sport</span>
          <Select value={sport} onValueChange={setSport}>
            <SelectTrigger className="h-8 w-28 text-xs" aria-label="Sport">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {sports.map(s => (
                <SelectItem key={s} value={s} className="text-xs">{s === 'ALL' ? 'All sports' : s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-1">
          <Chip active={kind === 'all'} onClick={() => setKind('all')}>All</Chip>
          <Chip active={kind === 'pregame'} onClick={() => setKind('pregame')}>Pre-game</Chip>
          <Chip active={kind === 'inplay'} onClick={() => setKind('inplay')}>In-play</Chip>
        </div>
        <span className="ml-auto text-xs text-muted-foreground">{shown} model{shown !== 1 ? 's' : ''}</span>
      </div>

      <div className="table-frame fill">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map(hg => (
              <TableRow key={hg.id}>
                {hg.headers.map(h => (
                  <TableHead
                    key={h.id}
                    onClick={h.column.getToggleSortingHandler()}
                    className={cn('select-none px-3', h.column.getCanSort() && 'cursor-pointer hover:text-foreground')}
                  >
                    <span className="inline-flex w-full items-center gap-1">
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {h.column.getCanSort() && <SortIcon sorted={h.column.getIsSorted()} />}
                    </span>
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {shown === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="py-10 text-center text-sm text-muted-foreground">
                  No model in this filter has a graded, published bet.
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map(row => (
                <TableRow
                  key={row.id}
                  onClick={() => onSelect(row.original.model_id)}
                  aria-selected={row.original.model_id === selected}
                  className={cn('cursor-pointer', row.original.model_id === selected && 'bg-muted/70')}
                >
                  {row.getVisibleCells().map(cell => (
                    <TableCell key={cell.id} className="px-3 py-2">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Footnote>
        In-play bets are not measured for closing-line value, by design. CLV is how much better the price we took was than the same book’s last pre-game price on the same number, in percent (the published standard). ± is the 95% margin of the average. “Last 25 / 50 / 100” are the model’s newest bets; a dash means it has fewer bets than that. Beat rate counts line moves (our way is a beat, against is a miss) and leaves out bets that closed at our exact price; “price only” is the published headline rate. “Vs Pinnacle” is our price against Pinnacle’s fair closing price, where Pinnacle closed on our number. Against the close: a verdict only from {MIN_MEASURED} closing prices up.
      </Footnote>
    </div>
  )
}
