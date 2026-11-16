import { useMemo } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../../lib/shadcn/table'
import { PanelError, TableSkeleton, Footnote, fmtDateTime, fmtDuration } from '../../components/PanelUtils'
import { StatusBadge } from '../../components/StatusBadge'
import { AlertTriangle } from 'lucide-react'
import { cn } from '../../lib/shadcn/utils'

type RunRow = {
  run_id: string
  started_at: string
  finished_at: string | null
  run_kind: string
  ok: boolean | null
  steps_total: number | null
  steps_failed: number | null
  failed_steps: string | null
}

type PipelineData = {
  runs: RunRow[]
  total: number
}

type Props = {
  data: unknown
  loading: boolean
  error: string | null
}

function RunStatusBadge({ row }: { row: RunRow }) {
  if (row.finished_at == null) return <StatusBadge label="Running" variant="running" />
  if (row.failed_steps === 'aborted') return <StatusBadge label="Aborted" variant="warn" />
  if (row.ok === true) return <StatusBadge label="OK" variant="ok" />
  return <StatusBadge label="Failed" variant="crit" />
}

export default function PipelineRuns({ data, loading, error }: Props) {
  const { runs, total } = useMemo<PipelineData>(() => {
    const d = data as PipelineData | undefined
    return d ?? { runs: [], total: 0 }
  }, [data])

  const columns = useMemo<ColumnDef<RunRow>[]>(() => [
    {
      accessorKey: 'started_at',
      header: 'Started',
      cell: ({ getValue }) => (
        <span className="whitespace-nowrap text-xs">{fmtDateTime(getValue() as string)}</span>
      ),
    },
    {
      id: 'duration',
      header: () => <span className="block text-right">Duration</span>,
      accessorFn: row => row.started_at,
      cell: ({ row }) => (
        <span className="block text-right tabular-nums text-xs">
          {fmtDuration(row.original.started_at, row.original.finished_at)}
        </span>
      ),
    },
    {
      accessorKey: 'run_kind',
      header: 'Kind',
      cell: ({ getValue }) => (
        <span className="text-xs text-muted-foreground capitalize">{String(getValue())}</span>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      accessorFn: row => row.ok,
      cell: ({ row }) => <RunStatusBadge row={row.original} />,
    },
    {
      id: 'steps',
      header: () => <span className="block text-right">Steps</span>,
      accessorFn: row => row.steps_total,
      cell: ({ row }) => {
        const { steps_total, steps_failed } = row.original
        if (steps_total == null) return <span className="block text-right text-muted-foreground/40 text-xs">—</span>
        return (
          <span className="block text-right tabular-nums text-xs">
            {steps_total - (steps_failed ?? 0)}/{steps_total}
          </span>
        )
      },
    },
    {
      accessorKey: 'failed_steps',
      header: 'Failed Steps',
      cell: ({ getValue }) => {
        const v = getValue() as string | null
        if (!v) return <span className="text-muted-foreground/40 text-xs">—</span>
        return <span className="font-mono text-xs text-crit">{v}</span>
      },
    },
    {
      accessorKey: 'run_id',
      header: 'Run ID',
      cell: ({ getValue }) => (
        <span className="font-mono text-[10px] text-muted-foreground truncate block max-w-[120px]">
          {String(getValue()).slice(0, 8)}…
        </span>
      ),
    },
  ], [])

  const table = useReactTable({
    data: runs,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    initialState: { sorting: [{ id: 'started_at', desc: true }] },
  })

  if (loading) return <TableSkeleton rows={6} toolbar={false} />
  if (error) return <PanelError message={error} />

  const hasFailures = runs.some(r => r.failed_steps && r.failed_steps !== 'aborted')

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">
          {runs.length} most recent of {total.toLocaleString()} total runs
        </span>
        {hasFailures && (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-crit">
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
            Some runs have failed steps
          </span>
        )}
      </div>

      <div className="table-frame fill">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map(hg => (
              <TableRow key={hg.id}>
                {hg.headers.map(h => (
                  <TableHead key={h.id} className="px-3">
                    {flexRender(h.column.columnDef.header, h.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {runs.length === 0 && (
              <TableRow>
                <TableCell colSpan={columns.length} className="py-10 text-center text-sm text-muted-foreground">
                  Pipeline runs will be listed here once the pipeline has run.
                </TableCell>
              </TableRow>
            )}
            {table.getRowModel().rows.map(row => {
              const hasFailedSteps = !!row.original.failed_steps && row.original.failed_steps !== 'aborted'
              return (
                <TableRow
                  key={row.id}
                  className={cn(hasFailedSteps && 'bg-crit-row')}
                >
                  {row.getVisibleCells().map(cell => (
                    <TableCell key={cell.id} className="px-3 py-2">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      <Footnote>
        Tinted rows have failed steps. Check failed steps before blaming model thresholds for an empty board.
      </Footnote>
    </div>
  )
}
