import { useState, useMemo } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { AlertTriangle, Info } from 'lucide-react'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../../lib/shadcn/table'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../lib/shadcn/select'
import {
  PanelError, NullCell, fmtUnits, fmtDate, SortIcon, TableSkeleton, Footnote, signedClass,
} from '../../components/PanelUtils'
import { ModelName } from '../../components/models/ModelName'
import { useModelNames } from '../../components/models/modelNames'
import { cn } from '../../lib/shadcn/utils'

export type PerfRow = {
  model_id: string
  sport: string
  settled: string
  wins: string
  losses: string
  pushes: string
  priced: string
  units: string
  risked: string
  roi_pct: string | null
  partial: boolean
  last_date: string
}

type Props = {
  data: unknown
  loading: boolean
  error: string | null
  /** Every model id in the roster, to show which ones this view does not grade. */
  rosterIds?: string[] | undefined
}

function RoiCell({ row }: { row: PerfRow }) {
  const { roi_pct, partial, priced, settled } = row
  if (roi_pct == null) return <span className="block text-right"><NullCell /></span>
  const n = parseFloat(roi_pct)
  const text = `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`

  if (partial) {
    return (
      <div className="text-right">
        <span className="text-xs font-semibold text-warn">{text}</span>
        <div className="inline-flex items-center justify-end gap-1 text-[11px] text-warn">
          <AlertTriangle className="h-3 w-3" aria-hidden />
          {priced} of {settled} priced
        </div>
      </div>
    )
  }
  return <span className={cn('block text-right text-xs font-semibold', signedClass(n))}>{text}</span>
}

export default function SettledPerformance({ data, loading, error, rosterIds }: Props) {
  const names = useModelNames()
  const [sorting, setSorting] = useState<SortingState>([{ id: 'settled', desc: true }])
  const [sportFilter, setSportFilter] = useState<string>('ALL')
  const [showMissing, setShowMissing] = useState(false)

  const rows = useMemo<PerfRow[]>(() => (data as PerfRow[] | undefined) ?? [], [data])

  const sports = useMemo(() => ['ALL', ...Array.from(new Set(rows.map(r => r.sport))).sort()], [rows])

  // Coverage, all from the data: which sports are graded, up to when, and which roster models are absent.
  const coverage = useMemo(() => {
    const covered = new Set(rows.map(r => r.model_id))
    const latest = rows.reduce<string>((mx, r) => (r.last_date > mx ? r.last_date : mx), '')
    const missing = (rosterIds ?? [])
      .filter(id => !covered.has(id))
      .sort((a, b) => names.modelLabel(a).name.localeCompare(names.modelLabel(b).name))
    return { models: covered.size, latest, missing }
  }, [rows, rosterIds, names])

  const filtered = useMemo(
    () => (sportFilter === 'ALL' ? rows : rows.filter(r => r.sport === sportFilter)),
    [rows, sportFilter],
  )

  const columns = useMemo<ColumnDef<PerfRow>[]>(() => [
    {
      id: 'model',
      accessorFn: row => names.modelLabel(row.model_id).name,
      header: 'Model',
      cell: ({ row }) => <ModelName id={row.original.model_id} className="min-w-[180px] max-w-[280px]" />,
    },
    {
      accessorKey: 'sport',
      header: 'Sport',
      cell: ({ getValue }) => <span className="text-xs font-medium text-secondary-fg">{String(getValue())}</span>,
    },
    {
      id: 'record',
      header: 'W-L-P',
      accessorFn: row => parseInt(row.wins, 10),
      cell: ({ row }) => {
        const { wins, losses, pushes } = row.original
        return <span className="whitespace-nowrap text-xs">{wins}-{losses}-{pushes}</span>
      },
    },
    {
      id: 'settled',
      accessorFn: row => parseInt(row.settled, 10),
      header: () => <span className="block text-right">Settled</span>,
      cell: ({ row }) => <span className="block text-right text-xs">{row.original.settled}</span>,
    },
    {
      id: 'priced',
      accessorFn: row => parseInt(row.priced, 10),
      header: () => <span className="block text-right">Priced</span>,
      cell: ({ row }) => <span className="block text-right text-xs">{row.original.priced}</span>,
    },
    {
      id: 'units',
      accessorFn: row => parseFloat(row.units),
      header: () => <span className="block text-right">Units</span>,
      cell: ({ row }) => (
        <span className={cn('block text-right text-xs font-semibold', signedClass(parseFloat(row.original.units)))}>
          {fmtUnits(row.original.units)}
        </span>
      ),
    },
    {
      id: 'roi_pct',
      accessorFn: row => (row.roi_pct == null ? null : parseFloat(row.roi_pct)),
      header: () => <span className="block text-right">ROI</span>,
      sortDescFirst: true,
      sortUndefined: 'last',
      cell: ({ row }) => <RoiCell row={row.original} />,
    },
    {
      accessorKey: 'last_date',
      header: 'Last date',
      cell: ({ getValue }) => <span className="whitespace-nowrap text-xs">{fmtDate(getValue() as string)}</span>,
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
          <Select value={sportFilter} onValueChange={setSportFilter}>
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
        <span className="ml-auto text-xs text-muted-foreground">
          {shown} model{shown !== 1 ? 's' : ''}
        </span>
      </div>

      {rosterIds && coverage.missing.length > 0 && (
        <div className="rounded-lg border border-warn bg-warn-soft px-3 py-2.5 text-xs text-warn">
          <div className="flex items-start gap-2">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            <p className="flex-1 leading-relaxed">
              <strong>Partial coverage.</strong> This table covers {coverage.models} model{coverage.models !== 1 ? 's' : ''} ({sports.filter(s => s !== 'ALL').join(', ')})
              {coverage.latest ? `, graded up to ${fmtDate(coverage.latest)}` : ''}. The database view behind it only grades some markets,
              so {coverage.missing.length} roster model{coverage.missing.length !== 1 ? 's are' : ' is'} not shown here even if they have settled bets.
            </p>
            <button
              type="button"
              onClick={() => setShowMissing(s => !s)}
              className="shrink-0 font-medium underline underline-offset-2"
            >
              {showMissing ? 'Hide list' : 'Show which'}
            </button>
          </div>
          {showMissing && (
            <div className="mt-2 flex max-h-32 flex-wrap gap-1.5 overflow-y-auto">
              {coverage.missing.map(id => (
                <span key={id} className="inline-flex h-6 items-center rounded-full border bg-card px-2 text-[11px] text-foreground">
                  <ModelName id={id} compact />
                </span>
              ))}
            </div>
          )}
        </div>
      )}

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
                  Models appear here once they have at least one settled bet.
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map(row => (
                <TableRow key={row.id}>
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
        Each model's settled bets as graded by the database's own grading view, at a flat 1-unit stake on the taken price. These units are not the same figures as Picks & CLV, which counts only posted picks with their published stake. A ROI marked with a warning has incomplete price coverage: only priced picks are used to compute it.
      </Footnote>
    </div>
  )
}
