import { useMemo } from 'react'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../../lib/shadcn/table'
import { CheckCircle2, AlertTriangle, XCircle, MinusCircle } from 'lucide-react'
import { PanelError, TableSkeleton, Footnote, fmtDateTime } from '../../components/PanelUtils'
import { Badge, StatusBadge, severityVariant, statusVariant, type BadgeTone } from '../../components/StatusBadge'

type HealthRow = {
  check_name: string
  status: string
  severity: string
  detail: string
  checked_at: string
  reason: string
  cadence: string
}

type HealthData = {
  runDate: string
  checks: HealthRow[]
}

type Props = {
  data: unknown
  loading: boolean
  error: string | null
}

// Badge tone keyed off meaning, not exact strings.
// The backend emits plain English like "3 days late", "Up to date", etc.
function reasonBadge(reason: string): { tone: BadgeTone; icon?: typeof CheckCircle2 } {
  const lower = reason.toLowerCase()
  if (lower.includes('late') || reason.startsWith('Never runs')) return { tone: 'warning', icon: AlertTriangle }
  if (reason === 'No data at all' || reason === 'Check crashed') return { tone: 'critical', icon: XCircle }
  if (reason === 'Up to date') return { tone: 'good', icon: CheckCircle2 }
  if (reason === 'Nothing to check') return { tone: 'outline', icon: MinusCircle }
  return { tone: 'neutral' }
}

export default function HealthChecks({ data, loading, error }: Props) {
  const { runDate, checks } = useMemo<HealthData>(() => {
    const d = data as HealthData | undefined
    return d ?? { runDate: '', checks: [] }
  }, [data])

  if (loading) return <TableSkeleton rows={5} toolbar={false} />
  if (error) return <PanelError message={error} />

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">
          Latest run: <span className="font-semibold text-foreground">{runDate || '—'}</span>
        </span>
        {checks.length > 0 && (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-warn">
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
            {checks.length} check{checks.length !== 1 ? 's' : ''} not OK
          </span>
        )}
      </div>

      {checks.length === 0 ? (
        <div className="flex items-center justify-center gap-2 rounded-[10px] border border-good bg-good-soft px-4 py-6 text-sm text-good">
          <CheckCircle2 className="h-4 w-4" aria-hidden />
          All checks OK{runDate ? ` on ${runDate}` : ''}
        </div>
      ) : (
        <div className="table-frame fill">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="px-3">Check</TableHead>
                <TableHead className="px-3">Status</TableHead>
                <TableHead className="px-3">What it means</TableHead>
                <TableHead className="px-3">Severity</TableHead>
                <TableHead className="px-3">Expected refresh</TableHead>
                <TableHead className="px-3">Detail</TableHead>
                <TableHead className="px-3">Checked at</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {checks.map(row => {
                const rb = row.reason ? reasonBadge(row.reason) : null
                return (
                <TableRow key={row.check_name} className="align-top">
                  <TableCell className="px-3 py-2">
                    <span className="font-mono text-xs">{row.check_name}</span>
                  </TableCell>
                  <TableCell className="px-3 py-2">
                    <StatusBadge label={row.status} variant={statusVariant(row.status)} />
                  </TableCell>
                  <TableCell className="px-3 py-2">
                    {row.reason && rb ? (
                      <Badge tone={rb.tone} icon={rb.icon}>{row.reason}</Badge>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="px-3 py-2">
                    <StatusBadge label={row.severity} variant={severityVariant(row.severity)} />
                  </TableCell>
                  <TableCell className="px-3 py-2">
                    {row.cadence ? (
                      <span className="whitespace-nowrap text-xs text-muted-foreground">{row.cadence}</span>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="max-w-xs px-3 py-2">
                    <p
                      className="text-xs text-muted-foreground line-clamp-2 hover:line-clamp-none cursor-default transition-all"
                      title={row.detail}
                    >
                      {row.detail}
                    </p>
                  </TableCell>
                  <TableCell className="px-3 py-2">
                    <span className="whitespace-nowrap text-xs">{fmtDateTime(row.checked_at)}</span>
                  </TableCell>
                </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}

      <Footnote>
        <strong>SKIPPED</strong> means the check could not run — not that it passed. <strong>What it means</strong> says which in plain words: <em>Nothing to check</em> (no games in the window), <em>N days late</em>, <em>No data at all</em>, <em>Check crashed</em>, or <em>Never runs</em>, which means the check has been skipping so long that the thing to suspect is the check&rsquo;s own condition, not the feed. <strong>Expected refresh</strong> is how fresh that check needs its data to be, so <em>2 days late</em> against <em>once a day</em> is two days behind, not two months.
      </Footnote>
    </div>
  )
}
