import { useMemo, useState } from 'react'
import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { History } from 'lucide-react'
import { PanelError, ChartSkeleton, EmptyState, Chip, Footnote } from '../../components/PanelUtils'
import { axisProps, gridProps, tooltipProps, legendProps } from '../../components/chartTheme'
import { fmtBytes, fmtCount, fmtPct, fmtUtc, intervals, toGB, type HealthPoint } from './dbUtils'

export type RangeDays = 7 | 30 | 90

type BaseProps = {
  points: HealthPoint[]
  firstAt: string | null
  loading: boolean
  error: string | null
}

function tickTime(iso: unknown): string {
  const d = new Date(String(iso))
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
}

function labelTime(iso: unknown): string {
  return fmtUtc(String(iso))
}

/** Shown until there are two snapshots to draw a line between. */
function HistoryStarts({ firstAt, what }: { firstAt: string | null; what: string }) {
  return (
    <EmptyState icon={History} title={`History starts ${fmtUtc(firstAt)}`} className="flex-1">
      {what} The worker adds a snapshot every hour, so the first line appears after the next one.
    </EmptyState>
  )
}

const SIZE_SERIES = [
  { key: 'table', label: 'Table data', color: 'var(--series-1)' },
  { key: 'index', label: 'Indexes', color: 'var(--series-7)' },
  { key: 'toast', label: 'Toast', color: 'var(--series-4)' },
] as const

export function DbSizeChart({ points, firstAt, loading, error, days }: BaseProps & { days: RangeDays }) {
  const rows = useMemo(() => points.map(p => ({
    at: p.taken_at,
    table: toGB(p.table_bytes),
    index: toGB(p.index_bytes),
    toast: toGB(p.toast_bytes),
    total: toGB(p.db_bytes),
  })), [points])

  if (loading) return <ChartSkeleton height={260} />
  if (error) return <PanelError message={error} />
  const last = points[points.length - 1]
  if (points.length < 2) {
    return (
      <div className="flex min-h-0 flex-1 flex-col gap-3">
        {last && <SizeSplit point={last} />}
        <HistoryStarts firstAt={firstAt} what="Each snapshot records the database’s size." />
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      {last && <SizeSplit point={last} />}
      <div className="chart-fill">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid {...gridProps} vertical={false} />
            <XAxis dataKey="at" tickFormatter={tickTime} minTickGap={28} {...axisProps} />
            <YAxis {...axisProps} width={48} tickFormatter={(v: number) => `${Math.round(v)} GB`} />
            <Tooltip
              {...tooltipProps}
              labelFormatter={labelTime}
              formatter={(value: unknown, name: unknown) => [`${Number(value).toFixed(2)} GB`, String(name)] as [string, string]}
            />
            <Legend {...legendProps} />
            {SIZE_SERIES.map(s => (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stackId="size"
                stroke={s.color}
                fill={s.color}
                fillOpacity={0.35}
                strokeWidth={1.75}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <Footnote>Last {days} days; older than 14 days, one point per six hours. 1 GB = 1,024³ bytes.</Footnote>
    </div>
  )
}

/** The newest snapshot's size split into table data, indexes and toast. */
function SizeSplit({ point }: { point: HealthPoint }) {
  const parts = SIZE_SERIES.map(s => ({
    ...s,
    bytes: s.key === 'table' ? point.table_bytes ?? 0 : s.key === 'index' ? point.index_bytes ?? 0 : point.toast_bytes ?? 0,
  }))
  const sum = parts.reduce((a, p) => a + p.bytes, 0)
  if (!(sum > 0)) return null
  return (
    <div className="space-y-2">
      <div className="sb-split" role="img" aria-label="Share of space by kind">
        {parts.map(p => <span key={p.key} style={{ width: `${(p.bytes / sum) * 100}%`, background: p.color }} />)}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {parts.map(p => (
          <span key={p.key} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} aria-hidden />
            {p.label} <span className="font-medium tabular-nums text-foreground">{fmtBytes(p.bytes)}</span>
            <span className="tabular-nums">({fmtPct(p.bytes / sum, 0)})</span>
          </span>
        ))}
      </div>
    </div>
  )
}

type Metric = 'load' | 'hit' | 'commits' | 'temp' | 'connections'

const HIT_DOMAIN: [string | number, string | number] = ['auto', 100]
const ZERO_DOMAIN: [string | number, string | number] = [0, 'auto']

const METRICS: ReadonlyArray<{ key: Metric; label: string; hint: string }> = [
  { key: 'load', label: 'Load', hint: 'Statements running at once, on average, between two snapshots (statement time per second).' },
  { key: 'hit', label: 'Cache hits', hint: 'Share of table and index reads served from memory between two snapshots.' },
  { key: 'commits', label: 'Commits/s', hint: 'Transactions committed per second between two snapshots; rollbacks shown beside them.' },
  { key: 'temp', label: 'Temp files', hint: 'Bytes per hour written to temporary files by queries too big for memory.' },
  { key: 'connections', label: 'Connections', hint: 'Client connections at the moment of each snapshot, against the limit.' },
]

export function DbActivityChart({ points, firstAt, loading, error }: BaseProps) {
  const [metric, setMetric] = useState<Metric>('load')
  const iv = useMemo(() => intervals(points), [points])

  const rows = useMemo(() => {
    if (metric === 'connections') {
      return points.map(p => ({
        at: p.taken_at,
        a: p.connections ?? null,
        b: p.connections_active ?? null,
        limit: p.max_connections ?? null,
      }))
    }
    return iv.map(r => ({
      at: r.at,
      a: metric === 'load' ? r.load : metric === 'hit' ? (r.hitRatio != null ? r.hitRatio * 100 : null)
        : metric === 'commits' ? r.commitsPerSec : r.tempBytesPerHour,
      b: metric === 'commits' && r.commitsPerSec != null && r.rollbackShare != null
        ? (r.commitsPerSec * r.rollbackShare) / (1 - r.rollbackShare) : null,
      limit: null as number | null,
    }))
  }, [metric, iv, points])

  if (loading) return <ChartSkeleton height={260} />
  if (error) return <PanelError message={error} />

  const current = METRICS.find(m => m.key === metric)!
  const enough = metric === 'connections' ? points.length >= 2 : iv.length >= 1 && rows.length >= 2
  const fmt = (v: number | null): string => {
    if (v == null || !Number.isFinite(v)) return '—'
    if (metric === 'load') return v.toFixed(2)
    if (metric === 'hit') return `${v.toFixed(2)}%`
    if (metric === 'commits') return v.toFixed(1)
    if (metric === 'temp') return `${fmtBytes(v)}/h`
    return fmtCount(v)
  }
  const aName = metric === 'connections' ? 'Connections' : metric === 'commits' ? 'Commits/s' : current.label
  const bName = metric === 'connections' ? 'Active' : metric === 'commits' ? 'Rollbacks/s' : ''

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-1.5">
        {METRICS.map(m => (
          <Chip key={m.key} active={metric === m.key} onClick={() => setMetric(m.key)} title={m.hint}>{m.label}</Chip>
        ))}
      </div>
      {!enough ? (
        <HistoryStarts firstAt={firstAt} what={current.hint} />
      ) : (
        <div className="chart-fill">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid {...gridProps} vertical={false} />
              <XAxis dataKey="at" tickFormatter={tickTime} minTickGap={28} {...axisProps} />
              <YAxis
                {...axisProps}
                width={52}
                domain={metric === 'hit' ? HIT_DOMAIN : ZERO_DOMAIN}
                tickFormatter={(v: number) => (
                  metric === 'temp' ? fmtBytes(v)
                    : metric === 'hit' ? `${v.toFixed(0)}%`
                      : metric === 'load' ? v.toFixed(1)
                        : fmtCount(v)
                )}
              />
              <Tooltip
                {...tooltipProps}
                labelFormatter={labelTime}
                formatter={(value: unknown, name: unknown) => [fmt(value == null ? null : Number(value)), String(name)] as [string, string]}
              />
              {(bName || metric === 'connections') && <Legend {...legendProps} />}
              <Line type="monotone" dataKey="a" name={aName} stroke="var(--series-1)" strokeWidth={2} dot={rows.length < 30} connectNulls={false} isAnimationActive={false} />
              {bName && (
                <Line type="monotone" dataKey="b" name={bName} stroke="var(--series-2)" strokeWidth={1.75} dot={false} connectNulls={false} isAnimationActive={false} />
              )}
              {metric === 'connections' && (
                <Line type="stepAfter" dataKey="limit" name="Limit" stroke="var(--series-other)" strokeDasharray="4 4" strokeWidth={1.5} dot={false} isAnimationActive={false} />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      <Footnote>{current.hint} A gap means a counter was reset between two snapshots.</Footnote>
    </div>
  )
}
