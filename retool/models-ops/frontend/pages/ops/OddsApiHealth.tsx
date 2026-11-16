import { useMemo } from 'react'
import { AlertTriangle, Coins, Flame, CalendarClock, Eye, XCircle } from 'lucide-react'
import { PanelError, StatCard, StatsSkeleton, Footnote, fmtDateTime, type StatTone } from '../../components/PanelUtils'
import { StatusBadge, statusVariant } from '../../components/StatusBadge'

type QuotaRow = {
  quota_date: string
  used: number
  remaining: number
  total: number
  pct_left: number | null
  burn_today: number | null
  days_left: number | null
  observed_at: string
  obs_age_h: number | null
}

type CheckRow = {
  check_name: string
  status: string
  severity: string
  detail: string
  checked_at: string
}

type OddsApiData = {
  quota: QuotaRow | null
  checks: CheckRow[]
}

type Props = {
  data: unknown
  loading: boolean
  error: string | null
}

function creditsTone(pctLeft: number | null): StatTone | undefined {
  if (pctLeft == null) return undefined
  if (pctLeft < 15) return 'critical'
  if (pctLeft < 25) return 'warning'
  return undefined
}

function daysTone(days: number | null): StatTone | undefined {
  if (days == null) return undefined
  if (days < 14) return 'critical'
  if (days < 30) return 'warning'
  return undefined
}

function toneIcon(tone: StatTone | undefined, fallback: typeof Coins) {
  if (tone === 'critical') return XCircle
  if (tone === 'warning') return AlertTriangle
  return fallback
}

function toneWord(tone: StatTone | undefined): string | null {
  if (tone === 'critical') return 'Critical'
  if (tone === 'warning') return 'Running low'
  return null
}

export default function OddsApiHealth({ data, loading, error }: Props) {
  const { quota, checks } = useMemo<OddsApiData>(() => {
    const d = data as OddsApiData | undefined
    return d ?? { quota: null, checks: [] }
  }, [data])

  if (loading) return <StatsSkeleton count={4} />
  if (error) return <PanelError message={error} />

  const q = quota
  const fmt = (n: number | string | null | undefined) =>
    n != null ? Number(n).toLocaleString() : '—'

  const remainingSubtitle = q && q.pct_left != null
    ? `${q.pct_left}% of ${fmt(q.total)}`
    : q ? `of ${fmt(q.total)}` : undefined
  const cTone = creditsTone(q?.pct_left ?? null)
  const dTone = daysTone(q?.days_left ?? null)
  const isStale = q?.obs_age_h != null && q.obs_age_h > 72

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3">
        <StatCard
          label="Credits remaining"
          icon={toneIcon(cTone, Coins)}
          tone={cTone}
          value={q ? fmt(q.remaining) : '—'}
          caption={[toneWord(cTone), remainingSubtitle].filter(Boolean).join(' · ') || undefined}
        />
        <StatCard
          label="Burn / day"
          icon={Flame}
          value={q ? fmt(q.burn_today) : '—'}
          caption={q ? `as of ${q.quota_date}` : undefined}
        />
        <StatCard
          label="Days left at this rate"
          icon={toneIcon(dTone, CalendarClock)}
          tone={dTone}
          value={q?.days_left != null ? q.days_left.toFixed(1) : '—'}
          caption={toneWord(dTone) ?? undefined}
        />
        <StatCard
          label="Quota observed"
          icon={Eye}
          value={<span className="text-base">{q ? fmtDateTime(q.observed_at) : '—'}</span>}
          caption={isStale ? <StatusBadge label="Stale" variant="stale" /> : undefined}
        />
      </div>

      {checks.length > 0 && (
        <ul className="space-y-1.5">
          {checks.map(row => (
            <li key={row.check_name} className="flex flex-wrap items-start gap-2 text-xs">
              <StatusBadge label={row.status} variant={statusVariant(row.status)} />
              <span className="font-mono text-foreground">{row.check_name}</span>
              <span className="text-muted-foreground">{row.detail}</span>
            </li>
          ))}
        </ul>
      )}

      <Footnote>
        These are the odds feed&#39;s own checks. The Health Checks tile lists only checks that are not OK, so a passing credits check never appears there, which is why this tile exists. Quota numbers come from the remaining-requests header the API returns on every response, including rejected ones.
      </Footnote>
    </div>
  )
}
