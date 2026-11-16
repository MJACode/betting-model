import { useState, useMemo, useEffect } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { AlertTriangle, CheckCircle2, Cpu, PauseCircle, Search, Sparkles } from 'lucide-react'
import { Input } from '../../lib/shadcn/input'
import { Button } from '../../lib/shadcn/button'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../../lib/shadcn/table'
import { Badge, InPlayBadge, ModelStateBadge, stateLabel } from '../../components/StatusBadge'
import {
  PanelError, NullCell, fmtPct, fmtDate, SortIcon, StatCard, StatsSkeleton, TableSkeleton, Chip, ChipGroup, Footnote,
} from '../../components/PanelUtils'
import { ModelName } from '../../components/models/ModelName'
import { useModelNames } from '../../components/models/modelNames'
import { cn } from '../../lib/shadcn/utils'

export type ModelRow = {
  model_id: string
  paused: boolean
  prob_only: boolean
  min_prob: string | null
  min_edge: string | null
  min_odds: string | null
  version: string | null
  trained_on: string | null
  holdout_accuracy: string | null
  calibration_score: string | null
  holdout_picks: number | null
  sport: string
  is_live: boolean
  scoring_method: 'artifact' | 'rule' | 'engine'
  state: 'LIVE' | 'PAUSED' | 'RULES BASED' | 'ENGINE' | 'NO ARTIFACT'
}

type Props = {
  data: unknown
  loading: boolean
  error: string | null
}

const STATE_FILTERS = ['LIVE', 'RULES BASED', 'ENGINE', 'PAUSED', 'NO ARTIFACT'] as const
type StateKey = typeof STATE_FILTERS[number]
type StateFilter = StateKey | null
type TimingFilter = 'All' | 'Pre-game' | 'In-play'

const STATE_CARD: Record<StateKey, { caption: string; icon: typeof CheckCircle2 }> = {
  'LIVE': { caption: 'On, scoring from a trained model', icon: CheckCircle2 },
  'RULES BASED': { caption: 'On, scoring from a fixed rule', icon: Sparkles },
  'ENGINE': { caption: 'On, model file kept elsewhere', icon: Cpu },
  'PAUSED': { caption: 'Switched off', icon: PauseCircle },
  'NO ARTIFACT': { caption: 'On, but cannot score', icon: AlertTriangle },
}

function RightNum({ children }: { children: React.ReactNode }) {
  return <span className="block text-right text-xs">{children}</span>
}

export default function ModelRoster({ data, loading, error }: Props) {
  const names = useModelNames()
  const [sorting, setSorting] = useState<SortingState>([])
  const [search, setSearch] = useState('')
  const [stateFilter, setStateFilter] = useState<StateFilter>(null)
  const [sportFilter, setSportFilter] = useState<string>('All')
  const [timingFilter, setTimingFilter] = useState<TimingFilter>('All')

  const rows = useMemo<ModelRow[]>(() => (data as ModelRow[] | undefined) ?? [], [data])

  // Share paused state so other panels can badge paused models.
  const reportPaused = names.reportPaused
  useEffect(() => {
    if (rows.length > 0) reportPaused(rows)
  }, [rows, reportPaused])

  const counts = useMemo(() => {
    const c: Record<StateKey, number> = { 'LIVE': 0, 'RULES BASED': 0, 'ENGINE': 0, 'PAUSED': 0, 'NO ARTIFACT': 0 }
    for (const r of rows) c[r.state] = (c[r.state] ?? 0) + 1
    return c
  }, [rows])

  const allSports = useMemo(() => Array.from(new Set(rows.map(r => r.sport))).sort(), [rows])

  const filtered = useMemo(() => {
    let r = rows
    if (stateFilter) r = r.filter(row => row.state === stateFilter)
    if (sportFilter !== 'All') r = r.filter(row => row.sport === sportFilter)
    if (timingFilter === 'In-play') r = r.filter(row => row.is_live)
    if (timingFilter === 'Pre-game') r = r.filter(row => !row.is_live)
    if (search.trim() !== '') r = r.filter(row => names.matchesModel(row.model_id, search))
    return r
  }, [rows, stateFilter, sportFilter, timingFilter, search, names])

  const columns = useMemo<ColumnDef<ModelRow>[]>(() => [
    {
      id: 'model',
      accessorFn: row => names.modelLabel(row.model_id).name,
      header: 'Model',
      cell: ({ row }) => <ModelName id={row.original.model_id} paused={row.original.paused} className="min-w-[180px] max-w-[280px]" />,
    },
    {
      accessorKey: 'sport',
      header: 'Sport',
      cell: ({ row }) => (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-medium">{row.original.sport}</span>
          {row.original.is_live && <InPlayBadge />}
        </div>
      ),
    },
    {
      accessorKey: 'state',
      header: 'State',
      cell: ({ getValue }) => <ModelStateBadge state={String(getValue())} />,
    },
    {
      accessorKey: 'trained_on',
      header: 'Trained on',
      cell: ({ getValue }) => {
        const v = getValue() as string | null
        return v ? <span className="whitespace-nowrap text-xs">{fmtDate(v)}</span> : <NullCell />
      },
    },
    {
      accessorKey: 'holdout_accuracy',
      header: () => <RightNum>Accuracy</RightNum>,
      cell: ({ getValue }) => {
        const v = getValue() as string | null
        return <RightNum>{v ? fmtPct(v) : <NullCell />}</RightNum>
      },
    },
    {
      accessorKey: 'calibration_score',
      header: () => <RightNum>Calibration</RightNum>,
      cell: ({ getValue }) => {
        const v = getValue() as string | null
        return <RightNum>{v ? fmtPct(v) : <NullCell />}</RightNum>
      },
    },
    {
      accessorKey: 'holdout_picks',
      header: () => <RightNum>Holdout picks</RightNum>,
      cell: ({ getValue }) => {
        const v = getValue() as number | null
        return <RightNum>{v != null ? v.toLocaleString() : <NullCell />}</RightNum>
      },
    },
    {
      accessorKey: 'min_prob',
      header: () => <RightNum>Min prob</RightNum>,
      cell: ({ getValue }) => {
        const v = getValue() as string | null
        return <RightNum>{v ? fmtPct(v) : <NullCell />}</RightNum>
      },
    },
    {
      accessorKey: 'min_edge',
      header: () => <RightNum>Min edge</RightNum>,
      cell: ({ getValue }) => {
        const v = getValue() as string | null
        return <RightNum>{v ? fmtPct(v) : <NullCell />}</RightNum>
      },
    },
    {
      accessorKey: 'min_odds',
      header: () => <RightNum>Min odds</RightNum>,
      cell: ({ getValue }) => {
        const v = getValue() as string | null
        return <RightNum>{v != null ? v : <NullCell />}</RightNum>
      },
    },
    {
      accessorKey: 'prob_only',
      header: 'Prob only',
      cell: ({ getValue }) => (getValue() as boolean)
        ? <Badge tone="outline">Yes</Badge>
        : <span className="text-xs text-muted-foreground/60">No</span>,
    },
    {
      accessorKey: 'version',
      header: 'Model file version',
      cell: ({ getValue }) => {
        const v = getValue() as string | null
        return v ? <span className="font-mono text-[11px] text-muted-foreground">{v}</span> : <NullCell />
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
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 20 } },
  })

  if (loading) {
    return (
      <div className="space-y-4">
        <StatsSkeleton count={5} />
        <TableSkeleton rows={8} />
      </div>
    )
  }
  if (error) return <PanelError message={error} />

  const noArtifactCount = counts['NO ARTIFACT']
  const anyFilter = stateFilter != null || sportFilter !== 'All' || timingFilter !== 'All' || search.trim() !== ''

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      {/* State cards double as filters */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        {STATE_FILTERS.map(s => {
          const cfg = STATE_CARD[s]
          const tone = s === 'LIVE' ? 'good' as const : s === 'NO ARTIFACT' && counts[s] > 0 ? 'critical' as const : undefined
          return (
            <StatCard
              key={s}
              label={stateLabel(s)}
              value={counts[s]}
              caption={cfg.caption}
              icon={cfg.icon}
              tone={tone}
              active={stateFilter === s}
              onClick={() => setStateFilter(stateFilter === s ? null : s)}
              title={stateFilter === s ? 'Click to clear this filter' : `Show only ${stateLabel(s).toLowerCase()} models`}
            />
          )
        })}
      </div>

      {noArtifactCount > 0 && (
        <div role="alert" className="flex items-start gap-2 rounded-lg border border-crit bg-crit-soft px-3 py-2.5">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-crit" aria-hidden />
          <p className="text-sm text-crit">
            <strong>{noArtifactCount} {noArtifactCount === 1 ? 'model is' : 'models are'}</strong> switched on and expect a trained model file but have none, so they cannot score.
          </p>
        </div>
      )}

      <div className="flex flex-col gap-2">
        <ChipGroup label="Sport">
          <Chip active={sportFilter === 'All'} onClick={() => setSportFilter('All')}>All</Chip>
          {allSports.map(s => (
            <Chip key={s} active={sportFilter === s} onClick={() => setSportFilter(s)}>{s}</Chip>
          ))}
        </ChipGroup>
        <ChipGroup label="Timing">
          {(['All', 'Pre-game', 'In-play'] as const).map(l => (
            <Chip key={l} active={timingFilter === l} onClick={() => setTimingFilter(l)}>{l}</Chip>
          ))}
          <span className="ml-1 text-xs text-muted-foreground">In-play means it bets during games, which is not the same as the Live state.</span>
        </ChipGroup>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            placeholder="Search by name or id…"
            value={search}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
            className="h-8 pl-8 text-sm"
            aria-label="Search models"
          />
        </div>
        <span className="text-xs text-muted-foreground">
          Showing {filtered.length} of {rows.length}
        </span>
        {anyFilter && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { setStateFilter(null); setSportFilter('All'); setTimingFilter('All'); setSearch('') }}
            className="h-7 px-2 text-xs"
          >
            Clear filters
          </Button>
        )}
      </div>

      <div className="table-frame fill">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map(hg => (
              <TableRow key={hg.id}>
                {hg.headers.map(header => (
                  <TableHead
                    key={header.id}
                    onClick={header.column.getToggleSortingHandler()}
                    className={cn('select-none px-3', header.column.getCanSort() && 'cursor-pointer hover:text-foreground')}
                  >
                    <span className="inline-flex w-full items-center gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getCanSort() && <SortIcon sorted={header.column.getIsSorted()} />}
                    </span>
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="py-10 text-center text-sm text-muted-foreground">
                  No models match these filters. Clear a filter to see more.
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map(row => (
                <TableRow key={row.id} className={cn(row.original.state === 'NO ARTIFACT' && 'bg-crit-row')}>
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

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Page {table.getState().pagination.pageIndex + 1} of {Math.max(1, table.getPageCount())}</span>
        <div className="flex gap-1">
          <Button size="sm" variant="outline" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()} className="h-7 text-xs">Previous</Button>
          <Button size="sm" variant="outline" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()} className="h-7 text-xs">Next</Button>
        </div>
      </div>

      <Footnote>
        Live, Rules based and Engine models are all switched on and scoring: Live ones use a trained model, Rules based ones follow a fixed rule, and Engine ones keep their trained model outside the usual store. Paused models are switched off on purpose. No artifact means a model is switched on but its trained model is missing, so it cannot score; that is the only state that needs fixing.
      </Footnote>
    </div>
  )
}
