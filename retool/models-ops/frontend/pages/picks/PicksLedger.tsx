import { useState, useMemo, useCallback } from 'react'
import {
  useReactTable, getCoreRowModel, getSortedRowModel, getPaginationRowModel,
  flexRender, type ColumnDef, type SortingState,
} from '@tanstack/react-table'
import { Download } from 'lucide-react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../lib/shadcn/table'
import { Button } from '../../lib/shadcn/button'
import { cn } from '../../lib/shadcn/utils'
import { NullCell, fmtDate, SortIcon, EmptyState, Footnote, signedClass } from '../../components/PanelUtils'
import { ModelName } from '../../components/models/ModelName'
import { useModelNames } from '../../components/models/modelNames'
import { ClvBadge, ResultBadge } from './PicksAtoms'
import { fmtOddsMove, fmtLineMove, fmtClvPct, fmtClvPts, type PickRow } from './picksUtils'

const PAGE_SIZE = 50

function clvClass(n: number): string {
  return n > 0 ? 'text-brand' : n < 0 ? 'text-crit' : 'text-muted-foreground'
}

function exportCsv(rows: PickRow[], modelName: (id: string) => string) {
  const headers = [
    'pick_id','game_date','sport','model_id','model_name','pick_label','pick_side',
    'scored_line','closing_line','odds_at_pick','odds_at_close',
    'clv_pct','line_clv_pts','clv_outcome','result','profit_units',
    'is_live','edge','model_probability'
  ]
  const escape = (v: unknown) => {
    const s = v == null ? '' : String(v)
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"`
      : s
  }
  const lines = [
    headers.join(','),
    ...rows.map(r =>
      headers.map(h => escape(h === 'model_name' ? modelName(r.model_id) : r[h as keyof PickRow])).join(',')
    ),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `picks_ledger_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

type Props = { rows: PickRow[] }

export default function PicksLedger({ rows }: Props) {
  const names = useModelNames()
  const [sorting, setSorting] = useState<SortingState>([{ id: 'game_date', desc: true }])

  const columns = useMemo<ColumnDef<PickRow>[]>(() => [
    {
      accessorKey: 'game_date',
      header: 'Date',
      cell: ({ getValue }) => (
        <span className="whitespace-nowrap text-xs">{fmtDate(getValue() as string)}</span>
      ),
    },
    {
      accessorKey: 'sport',
      header: 'Sport',
      cell: ({ getValue }) => (
        <span className="text-xs font-medium text-secondary-fg">{String(getValue())}</span>
      ),
    },
    {
      id: 'model',
      accessorFn: r => names.modelLabel(r.model_id).name,
      header: 'Model',
      cell: ({ row }) => <ModelName id={row.original.model_id} className="min-w-[150px] max-w-[220px]" />,
    },
    {
      accessorKey: 'pick_label',
      header: 'Pick',
      cell: ({ row }) => (
        <div className="min-w-[120px] max-w-[220px]">
          <div className="text-xs font-medium truncate">{row.original.pick_label}</div>
          {row.original.pick_side && (
            <div className="text-[10px] text-muted-foreground capitalize">{row.original.pick_side}</div>
          )}
        </div>
      ),
    },
    {
      id: 'line_move',
      header: 'Line',
      accessorFn: (r) => r.scored_line,
      cell: ({ row }) => {
        const s = fmtLineMove(row.original.scored_line, row.original.closing_line)
        return <span className="whitespace-nowrap text-xs">{s || <NullCell />}</span>
      },
    },
    {
      id: 'odds_move',
      header: 'Odds',
      accessorFn: (r) => r.odds_at_pick,
      cell: ({ row }) => {
        const s = fmtOddsMove(row.original.odds_at_pick, row.original.odds_at_close)
        return <span className="whitespace-nowrap font-mono text-xs">{s}</span>
      },
    },
    {
      accessorKey: 'clv_pct',
      header: () => <span className="block text-right">CLV %</span>,
      cell: ({ getValue }) => {
        const v = getValue() as string | null
        const s = fmtClvPct(v)
        if (s === '—') return <span className="block text-right text-muted-foreground/60">—</span>
        const n = parseFloat(v!)
        return <span className={cn('block text-right text-xs', clvClass(n))}>{s}</span>
      },
    },
    {
      accessorKey: 'line_clv_pts',
      header: () => <span className="block text-right">Line CLV</span>,
      cell: ({ getValue }) => {
        const v = getValue() as string | null
        const s = fmtClvPts(v)
        if (s === '—') return <span className="block text-right text-muted-foreground/60">—</span>
        const n = parseFloat(v!)
        return <span className={cn('block text-right text-xs', clvClass(n))}>{s}</span>
      },
    },
    {
      accessorKey: 'clv_outcome',
      header: 'CLV',
      cell: ({ getValue }) => <ClvBadge outcome={getValue() as PickRow['clv_outcome']} />,
    },
    {
      accessorKey: 'result',
      header: 'Result',
      cell: ({ row }) => {
        const r = row.original
        const settled = r.result != null && r.result.toUpperCase() !== 'NO_ACTION'
        const isUnpriced = settled && r.dk_odds == null
        return <ResultBadge result={r.result} isUnpriced={isUnpriced} />
      },
    },
    {
      accessorKey: 'profit_units',
      header: () => <span className="block text-right">Units</span>,
      cell: ({ row }) => {
        const r = row.original
        const v = r.profit_units
        // Settled with no DK price: unpriced by design, not an error
        const settled = r.result != null && r.result.toUpperCase() !== 'NO_ACTION'
        if (v == null && settled && r.dk_odds == null) {
          return (
            <span
              className="block text-right text-muted-foreground/50 text-xs"
              title="No DraftKings price at pick time, so this pick has no units. Its P&L is deliberately not fabricated."
            >
              —
            </span>
          )
        }
        if (v == null) return <span className="block text-right text-muted-foreground/60">—</span>
        const n = parseFloat(v)
        return (
          <span className={cn('block text-right text-xs font-semibold', signedClass(n))}>
            {n >= 0 ? '+' : ''}{n.toFixed(2)}u
          </span>
        )
      },
    },
  ], [names])

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: PAGE_SIZE } },
  })

  const handleExport = useCallback(() => {
    // Export all sorted rows (not just current page)
    const sorted = table.getSortedRowModel().rows.map(r => r.original)
    exportCsv(sorted, id => names.modelLabel(id).name)
  }, [table, names])

  const pageRows = table.getRowModel().rows
  const { pageIndex } = table.getState().pagination
  const pageCount = table.getPageCount()

  if (rows.length === 0) {
    return (
      <EmptyState title="No picks match the current filter">
        Each bet pick, its prices, CLV and result will be listed here. Loosen the filters above to see more.
      </EmptyState>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">
          {rows.length.toLocaleString()} picks · page {pageIndex + 1} of {pageCount}
        </span>
        <Button variant="outline" size="sm" onClick={handleExport} className="h-8 gap-1.5 text-xs">
          <Download className="h-3.5 w-3.5" />
          Download CSV
        </Button>
      </div>

      <div className="table-frame fill">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map(hg => (
              <TableRow key={hg.id}>
                {hg.headers.map(h => (
                  <TableHead
                    key={h.id}
                    className="cursor-pointer select-none whitespace-nowrap px-3 hover:text-foreground"
                    onClick={h.column.getToggleSortingHandler()}
                  >
                    <div className="flex w-full items-center gap-1">
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {h.column.getCanSort() && <SortIcon sorted={h.column.getIsSorted()} />}
                    </div>
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {pageRows.map(row => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map(cell => (
                  <TableCell key={cell.id} className="px-3 py-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {pageCount > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>Previous</Button>
          <span className="text-xs text-muted-foreground">{pageIndex + 1} / {pageCount}</span>
          <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>Next</Button>
        </div>
      )}

      <Footnote>
        Only bet picks are shown. Avoid and no-signal picks carry no CLV and are not part of the record.
      </Footnote>
    </div>
  )
}
