import { useMemo } from 'react'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../../lib/shadcn/table'
import { PanelError, TableSkeleton, EmptyState, Footnote } from '../../components/PanelUtils'
import { Badge } from '../../components/StatusBadge'

type ApiSourceRow = {
  api: string
  source: string
  calls_2d: number
  calls_per_day: number
  med_min_between_runs: number | null
  runs_2d: number
}

type Props = {
  data: unknown
  loading: boolean
  error: string | null
}

/** Convert median minutes between runs into plain English. */
function fmtFrequency(med: number | null): { text: string; muted: boolean } {
  if (med === null) return { text: 'once or less in 2 days', muted: true }
  if (med < 1) return { text: 'constantly', muted: false }

  if (med < 60) {
    const n = Math.round(med)
    return { text: n === 1 ? 'every minute' : `every ${n} min`, muted: false }
  }

  // 60–89 min: rounds to one hour
  if (med < 90) {
    return { text: 'every hour', muted: false }
  }

  // 90–179 min: one decimal hour, strip trailing ".0"
  if (med < 180) {
    const raw = Math.round(med / 6) / 10 // one decimal
    const label = raw % 1 === 0 ? `${raw | 0}` : `${raw}`
    return { text: `every ${label} hours`, muted: false }
  }

  // 180–1439 min: whole hours
  if (med < 1440) {
    const n = Math.round(med / 60)
    return { text: n === 1 ? 'every hour' : `every ${n} hours`, muted: false }
  }

  const n = Math.round(med / 1440)
  return { text: n === 1 ? 'every day' : `every ${n} days`, muted: false }
}

const ODDS_API = 'The Odds API'

export default function ApiSources({ data, loading, error }: Props) {
  const rows = useMemo<ApiSourceRow[]>(() => {
    const d = data as { rows: ApiSourceRow[] } | undefined
    return d?.rows ?? []
  }, [data])

  if (loading) return <TableSkeleton rows={6} toolbar={false} />
  if (error) return <PanelError message={error} />

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      {rows.length === 0 ? (
        <EmptyState title="No calls in the last 2 days">Each feed and how often it runs will be listed here.</EmptyState>
      ) : (
        <div className="table-frame fill">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="px-3">API</TableHead>
                <TableHead className="px-3">Source</TableHead>
                <TableHead className="px-3">How often</TableHead>
                <TableHead className="px-3 text-right">Calls/day</TableHead>
                <TableHead className="px-3 text-right">Runs (2d)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row, i) => {
                const prevApi = i > 0 ? rows[i - 1]?.api : undefined
                const showApi = row.api !== prevApi
                const isOdds = row.api === ODDS_API
                const freq = fmtFrequency(row.med_min_between_runs)

                return (
                  <TableRow key={`${row.api}::${row.source}`} className="text-sm align-middle">
                    {/* API cell — blank when same as previous row */}
                    <TableCell className="px-3 py-2">
                      {showApi ? (
                        <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-medium">
                          {row.api}
                          {isOdds && <Badge tone="outline">Paid</Badge>}
                        </span>
                      ) : null}
                    </TableCell>

                    <TableCell className="px-3 py-2">
                      <span className="font-mono text-xs text-muted-foreground">{row.source}</span>
                    </TableCell>

                    {/* How often — the headline */}
                    <TableCell className="px-3 py-2">
                      {freq.muted ? (
                        <span className="text-xs text-muted-foreground italic">{freq.text}</span>
                      ) : (
                        <span className="text-xs font-medium">{freq.text}</span>
                      )}
                    </TableCell>

                    <TableCell className="px-3 py-2 text-right text-xs">
                      {row.calls_per_day.toLocaleString()}
                    </TableCell>

                    <TableCell className="px-3 py-2 text-right text-xs text-muted-foreground">
                      {row.runs_2d.toLocaleString()}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}

      <Footnote>
        Measured from the last 2 days of calls actually made, not from configuration. <strong>How often</strong> is the median gap between{' '}
        <em>runs</em>, where a run is a burst of calls separated by more than two minutes: a poller
        that fires 300 calls in one second every 5 minutes runs <em>every 5 min</em>, not 300 times.{' '}
        <strong>The Odds API is the only paid feed</strong>; everything else costs nothing but time.
      </Footnote>
    </div>
  )
}
